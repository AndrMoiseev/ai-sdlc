package architect

import (
	"encoding/json"
	"fmt"
	"io"
	"math"
	"net/url"
	"path/filepath"
	"regexp"
	"strings"
)

var projectPathFields = []string{"source_roots", "test_roots", "exclude_paths", "statistics_exclude_paths", "class_directories"}
var configurationFields = append(append([]string{}, projectPathFields...), "package_prefixes", "exclude_classes", "modules", "scope", "class_files", "artifacts")
var artifactFields = []string{"path", "format", "tool", "version", "parser_version", "command", "source_root", "complete_mcc", "complete", "test_result", "limitations", "since", "until"}

var fullFormats = map[string][]string{
	"dependencies": {"class-csv", "jdeps"},
	"history":      {"git-history"},
	"sizes":        {"scc"},
	"kotlin":       {"kotlin-measurements"},
	"complexity":   {"detekt-sarif"},
	"coverage":     {"jacoco"},
}

var windowsDrive = regexp.MustCompile(`^[A-Za-z]:`)
var provenanceTerms = regexp.MustCompile(`[\s=;,"'()\[\]]+`)

func unquote(value string) string {
	decoded, err := url.PathUnescape(value)
	if err != nil {
		return value
	}
	return decoded
}

func projectPath(value any, field string) (string, error) {
	path := str(value)
	if strings.TrimSpace(path) == "" {
		return "", fmt.Errorf("%s: expected a nonempty project-relative path", field)
	}
	if unquote(path) != path || strings.ContainsAny(path, `\:`) || strings.HasPrefix(path, "/") ||
		strings.HasPrefix(path, "~") || contains(strings.Split(path, "/"), "..") {
		return "", fmt.Errorf("%s: use a project-relative path with / and no parent traversal", field)
	}
	return path, nil
}

func resolveProjectPath(value any, root, field string) (string, error) {
	path, err := projectPath(value, field)
	if err != nil {
		return "", err
	}
	resolved, err := resolve(filepath.Join(root, filepath.FromSlash(path)))
	if err != nil {
		return "", err
	}
	if !within(resolved, root) {
		return "", fmt.Errorf("%s: path leaves the project through a symlink", field)
	}
	return resolved, nil
}

func unknownFields(value record, allowed []string) []string {
	unknown := []string{}
	for _, field := range keys(value) {
		if !contains(allowed, field) {
			unknown = append(unknown, field)
		}
	}
	return unknown
}

func validateConfiguration(value any) error {
	config := object(value)
	if config == nil {
		return fmt.Errorf("Audit configuration must be an object")
	}
	if unknown := unknownFields(config, configurationFields); len(unknown) > 0 {
		return fmt.Errorf("Unknown audit configuration fields: %s; pass the repository as a runtime argument", pythonList(unknown))
	}
	for _, field := range projectPathFields {
		paths, exists := config[field]
		if exists && items(paths) == nil {
			return fmt.Errorf("%s: expected an array", field)
		}
		for _, path := range items(paths) {
			if _, err := projectPath(path, field); err != nil {
				return err
			}
		}
	}
	if value, exists := config["class_files"]; exists && object(value) == nil {
		return fmt.Errorf("class_files: expected an object")
	}
	for _, path := range object(config["class_files"]) {
		if _, err := projectPath(path, "class_files"); err != nil {
			return err
		}
	}
	if value, exists := config["artifacts"]; exists && object(value) == nil {
		return fmt.Errorf("artifacts: expected an object")
	}
	artifacts := object(config["artifacts"])
	for _, name := range keys(artifacts) {
		artifact := object(artifacts[name])
		if artifact == nil || len(unknownFields(artifact, artifactFields)) > 0 {
			return fmt.Errorf("artifacts.%s: unsupported artifact fields", name)
		}
		for _, field := range []string{"path", "source_root"} {
			if value, ok := artifact[field]; ok {
				if _, err := projectPath(value, "artifacts."+name+"."+field); err != nil {
					return err
				}
			}
		}
		if command, exists := artifact["command"]; exists {
			if items(command) == nil || !stringItems(items(command)) {
				return fmt.Errorf("artifacts.%s.command: expected an argument array", name)
			}
		}
	}
	return inspectConfiguration(config, "configuration")
}

func stringItems(values []any) bool {
	for _, entry := range values {
		if _, ok := entry.(string); !ok {
			return false
		}
	}
	return true
}

func inspectConfiguration(value any, field string) error {
	switch value := value.(type) {
	case map[string]any:
		for _, key := range keys(value) {
			if err := inspectConfiguration(key, field); err != nil {
				return err
			}
			if err := inspectConfiguration(value[key], field+"."+key); err != nil {
				return err
			}
		}
	case []any:
		for _, item := range value {
			if err := inspectConfiguration(item, field); err != nil {
				return err
			}
		}
	case string:
		for _, token := range provenanceTerms.Split(unquote(value), -1) {
			token = strings.TrimLeft(token, "@")
			if windowsDrive.MatchString(token) || strings.HasPrefix(strings.ToLower(token), "file:") ||
				strings.HasPrefix(token, "/") || strings.HasPrefix(token, `\`) || strings.HasPrefix(token, "~") ||
				contains(strings.Split(strings.ReplaceAll(token, `\`, "/"), "/"), "..") {
				return fmt.Errorf("%s: absolute paths and parent traversal are not audit configuration", field)
			}
		}
	}
	return nil
}

func collectionSettings(value record, root string) (record, error) {
	if !sameKeys(value, []string{"command", "artifacts"}) {
		return nil, fmt.Errorf("architect.collection requires command and artifacts")
	}
	command := items(value["command"])
	if len(command) == 0 {
		return nil, fmt.Errorf("command must be a nonempty argument array")
	}
	for _, argument := range command {
		if strings.TrimSpace(str(argument)) == "" || strings.IndexFunc(str(argument), func(r rune) bool { return r < 32 }) >= 0 {
			return nil, fmt.Errorf("command must be a nonempty argument array")
		}
	}
	if err := validateConfiguration(record{"artifacts": value["artifacts"]}); err != nil {
		return nil, err
	}
	artifacts := object(value["artifacts"])
	missing, extra := keyDiff(fullFormats, artifacts), keyDiff(artifacts, fullFormats)
	if len(missing)+len(extra) > 0 {
		return nil, fmt.Errorf("Missing configured sources: %s; unexpected sources: %s", pythonList(missing), pythonList(extra))
	}
	for _, name := range keys(artifacts) {
		artifact := object(artifacts[name])
		if !contains(fullFormats[name], str(artifact["format"])) {
			return nil, fmt.Errorf("artifacts.%s: expected %s", name, pythonList(fullFormats[name]))
		}
		for _, field := range []string{"path", "source_root"} {
			entry, found := artifact[field]
			if !found && field == "source_root" {
				entry = "."
			}
			if _, err := resolveProjectPath(entry, root, "artifacts."+name+"."+field); err != nil {
				return nil, err
			}
		}
	}
	coverage := object(artifacts["coverage"])
	if coverage["complete"] != true || coverage["test_result"] != "passed" {
		return nil, fmt.Errorf("coverage must come from complete JaCoCo reporting after successful tests")
	}
	return value, nil
}

func projectCollection(root string) (record, error) {
	result, err := readProjectCollection(root)
	if err != nil {
		return nil, fmt.Errorf("Configure architect.collection in .sdd/settings.json with sdd-setup: %s", err)
	}
	return result, nil
}

func readProjectCollection(root string) (record, error) {
	path, err := resolveProjectPath(".sdd/settings.json", root, "settings")
	if err != nil {
		return nil, err
	}
	state, err := readDocument(path, "")
	if err != nil {
		return nil, err
	}
	settings := object(state.value)
	if settings["schema_version"] != json.Number("1") {
		return nil, fmt.Errorf("expected settings schema_version 1")
	}
	architect, found := settings["architect"]
	if !found {
		return nil, fmt.Errorf("'architect'")
	}
	collection, found := object(architect)["collection"]
	if !found {
		return nil, fmt.Errorf("'collection'")
	}
	return collectionSettings(object(collection), root)
}

func configure(args options, stdin io.Reader, stdout io.Writer) error {
	repository := filepath.Clean(args.get("repository"))
	if !isDir(repository) {
		return fmt.Errorf("Repository not found: %s", repository)
	}
	doc, err := inputDocument(args, stdin, "")
	if err != nil {
		return err
	}
	if err := validateConfiguration(doc.value); err != nil {
		return err
	}
	path := filepath.Clean(args.get("output"))
	output, err := reportOutput(path, repository, false)
	if err != nil {
		return err
	}
	root, err := resolve(repository)
	if err != nil {
		return err
	}
	if filepath.Base(output) != "collection-input.json" || filepath.Dir(filepath.Dir(output)) != filepath.Join(root, "memory", "tech-debt", "audits") {
		return fmt.Errorf("Save audit configuration as collection-input.json inside its audit")
	}
	if collectionStarted(filepath.Dir(output)) {
		return fmt.Errorf("Collection has started; retain its configuration and use a new audit for recollection")
	}
	if err := writeText(output, doc.text, false, true); err != nil {
		return err
	}
	return printJSON(stdout, record{"configuration": path}, false)
}

func collectionStarted(path string) bool {
	for _, name := range []string{"collection.json", "metrics", "selections"} {
		if exists(filepath.Join(path, name)) {
			return true
		}
	}
	return false
}

func decimal(value any) (float64, bool) {
	switch x := value.(type) {
	case json.Number:
		value, err := x.Float64()
		return value, err == nil && !math.IsInf(value, 0) && !math.IsNaN(value)
	case float64:
		return x, !math.IsInf(x, 0) && !math.IsNaN(x)
	case int:
		return float64(x), true
	default:
		return 0, false
	}
}

func numeric(value any) float64 {
	number, _ := decimal(value)
	return number
}

func integer(value any) int { return int(numeric(value)) }

func validatePolicy(value any, complete bool) (record, error) {
	schema, err := assetObject("analysis-policy.schema.json")
	if err != nil {
		return nil, err
	}
	policy, err := validatePolicyContent(value, schema, "analysis_policy", complete)
	if err != nil {
		return nil, err
	}
	result := object(policy)
	if complete {
		points := object(object(result["recommendations"])["effect_points"])
		if !(numeric(points["not_shown"]) < numeric(points["local"]) && numeric(points["local"]) < numeric(points["substantial"])) {
			return nil, fmt.Errorf("analysis_policy.recommendations.effect_points: require not_shown < local < substantial")
		}
		points = object(object(result["investigation"])["family_points"])
		if numeric(points["limited"]) > numeric(points["usable"]) {
			return nil, fmt.Errorf("analysis_policy.investigation.family_points: limited must not exceed usable")
		}
	}
	return result, nil
}

func validatePolicyContent(value any, rule record, path string, complete bool) (any, error) {
	kind := str(rule["type"])
	if kind == "object" {
		current, properties := object(value), object(rule["properties"])
		if current == nil {
			return nil, fmt.Errorf("%s: expected object", path)
		}
		if unknown := keyDiff(current, properties); len(unknown) > 0 {
			return nil, fmt.Errorf("%s: unknown keys %s", path, pythonList(unknown))
		}
		if missing := keyDiff(properties, current); complete && len(missing) > 0 {
			return nil, fmt.Errorf("%s: missing keys %s", path, pythonList(missing))
		}
		for _, name := range keys(current) {
			validated, err := validatePolicyContent(current[name], object(properties[name]), path+"."+name, complete)
			if err != nil {
				return nil, err
			}
			current[name] = validated
		}
		return current, nil
	}
	number, valid := decimal(value)
	if !valid || (kind == "integer" && math.Trunc(number) != number) {
		return nil, fmt.Errorf("%s: expected finite %s", path, kind)
	}
	for _, keyword := range []string{"minimum", "maximum", "exclusiveMinimum", "const"} {
		if bound, exists := rule[keyword]; exists {
			limit := numeric(bound)
			if (keyword == "minimum" && number < limit) || (keyword == "maximum" && number > limit) ||
				(keyword == "exclusiveMinimum" && number <= limit) || (keyword == "const" && number != limit) {
				return nil, fmt.Errorf("%s: must satisfy %s %s", path, keyword, display(bound))
			}
		}
	}
	if kind == "integer" {
		value = int(number)
	}
	return value, nil
}

func loadPolicy(repository string) (record, error) {
	defaults, err := assetObject("analysis-policy.json")
	if err != nil {
		return nil, err
	}
	if repository != "" {
		root, err := resolve(repository)
		if err != nil {
			return nil, err
		}
		path := filepath.Join(root, ".sdd", "architect", "analysis-policy.json")
		if exists(path) {
			doc, err := readDocument(path, "Duplicate policy key")
			if err != nil {
				return nil, fmt.Errorf("%s: %s", path, err)
			}
			overrides, err := validatePolicy(doc.value, false)
			if err != nil {
				return nil, err
			}
			mergePolicy(defaults, overrides)
		}
	}
	return validatePolicy(defaults, true)
}

func mergePolicy(base, overrides record) {
	for key, value := range overrides {
		if child := object(value); child != nil {
			mergePolicy(object(base[key]), child)
		} else {
			base[key] = value
		}
	}
}

func policyCommand(args options, stdout io.Writer) error {
	repository := args.get("repository")
	if !args.has("repository") && !args.has("defaults") && !args.has("collection") {
		return fmt.Errorf("Select --repository, --defaults or --collection for the policy")
	}
	if args.has("repository") {
		repository = filepath.Clean(repository)
		if !isDir(repository) {
			return fmt.Errorf("Repository not found: %s", repository)
		}
	}
	var policy record
	var err error
	if args.has("collection") {
		var collection record
		collection, err = readObject(filepath.Clean(args.get("collection")))
		if err == nil {
			if _, found := collection["analysis_policy"]; !found {
				return fmt.Errorf("'analysis_policy'")
			}
			policy, err = validatePolicy(collection["analysis_policy"], true)
		}
	} else if args.has("defaults") {
		policy, err = loadPolicy("")
	} else {
		policy, err = loadPolicy(repository)
	}
	if err != nil {
		return err
	}
	var value any = policy
	if key := args.get("get"); key != "" {
		for _, part := range strings.Split(key, ".") {
			var found bool
			value, found = object(value)[part]
			if !found {
				return fmt.Errorf("Unknown policy key: %s", key)
			}
		}
	}
	if args.has("output") {
		if repository == "" {
			return fmt.Errorf("Supply --repository with --output to locate the audit directory")
		}
		output := filepath.Clean(args.get("output"))
		if err := saveMetricJSON(output, repository, value); err != nil {
			return err
		}
		return printJSON(stdout, record{"output": output}, false)
	}
	if object(value) != nil {
		return fmt.Errorf("Use --get with a numeric key or save the policy with --repository and --output")
	}
	return printJSON(stdout, value, false)
}
