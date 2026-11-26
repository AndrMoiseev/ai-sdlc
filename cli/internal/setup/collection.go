package setup

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"slices"
	"strings"
	"time"
	"unicode/utf8"
)

var reportFormats = map[string][]string{
	"dependencies": {"class-csv", "jdeps"}, "history": {"git-history"}, "sizes": {"scc"},
	"kotlin": {"kotlin-measurements"}, "complexity": {"detekt-sarif"}, "coverage": {"jacoco"},
}

func collection(args arguments) (object, error) {
	requestRaw, err := os.ReadFile(args.value("request"))
	if err != nil {
		return nil, fileError(err)
	}
	requestOrder := fieldOrder{}
	value, err := decodeJSON(requestRaw, requestOrder)
	if err != nil {
		return nil, err
	}
	request := asObject(value)
	project, err := projectDirectory(args.value("project-root"), "project_root must be a directory")
	if err != nil {
		return nil, err
	}
	settings, artifacts, command, err := collectionSettings(project, request["collection"])
	if err != nil {
		return nil, err
	}
	if len(command) < 3 || command[0] != "mise" || command[1] != "run" || strings.HasPrefix(command[2], "-") {
		return nil, errors.New(`Select one project task as ["mise", "run", "<task>"]`)
	}
	scope, err := collectionScope(project, request["scope"])
	if err != nil {
		return nil, err
	}
	policy, err := collectionPolicy(project)
	if err != nil {
		return nil, err
	}
	runtime := asObject(policy["runtime"])
	timeout, limit := int(decimal(runtime["command_timeout_seconds"])), int(decimal(runtime["stderr_tail_characters"]))
	execute := func(argv []string) (string, error) {
		process, err := runProcess(project, time.Duration(timeout)*time.Second, nil, argv)
		if err != nil {
			if strings.Contains(err.Error(), "timed out after") {
				return "", fmt.Errorf("Command timed out after %ds: %s", timeout, argv[0])
			}
			return "", err
		}
		if process.code != 0 {
			detail := tail(process.stderr, limit)
			if process.stdout != "" {
				runes := []rune(process.stdout)
				detail = string(runes[:min(limit, len(runes))]) + "\n" + detail
			}
			return "", fmt.Errorf("Command failed (%d): %s\n%s", process.code, pythonList(argv), detail)
		}
		return process.stdout, nil
	}
	path, before, current, order, err := settingsFile(project)
	if err != nil {
		return nil, err
	}
	if current["schema_version"] != json.Number("1") {
		return nil, errors.New("Expected settings schema_version 1")
	}
	architect := object{}
	if value, exists := current["architect"]; exists {
		architect = asObject(value)
		if architect == nil {
			return nil, errors.New("settings.architect must be an object")
		}
	}
	current["architect"] = architect
	// Requests are ordered JSON. Retain the same order for tool checks and the
	// project's persisted command and report declarations.
	if err := checkTools(asObject(request["tools"]), requestOrder["/tools"], project, execute); err != nil {
		return nil, err
	}
	if _, err := execute(command); err != nil {
		return nil, err
	}
	raw := map[string][]byte{}
	reportOrder := requestOrder["/collection/artifacts"]
	for _, name := range reportOrder {
		file, err := reportPath(project, asObject(artifacts[name])["path"], name)
		if err != nil {
			return nil, err
		}
		data, err := os.ReadFile(file)
		if err != nil {
			return nil, fileError(err)
		}
		data = unbom(data)
		if !utf8.Valid(data) {
			return nil, fmt.Errorf("Invalid UTF-8 in collection report %s", name)
		}
		raw[name] = data
	}
	if err := validateReports(project, scope, policy, artifacts, raw); err != nil {
		return nil, err
	}
	changed := false
	err = withLock(project, "collection", func() error {
		now, err := optionalBytes(path)
		if err != nil {
			return err
		}
		if !bytes.Equal(now, before) || (now == nil) != (before == nil) {
			return errors.New("Project settings changed during verification; repeat setup")
		}
		changed = !equal(architect["collection"], settings)
		if !changed {
			return nil
		}
		architect["collection"] = settings
		for key, names := range requestOrder {
			if key == "/collection" || strings.HasPrefix(key, "/collection/") {
				order["/architect"+key] = names
			}
		}
		return replaceFile(path, []byte(jsonText(current, true, order)+"\n"))
	})
	if err != nil {
		return nil, err
	}
	return object{"changed": changed, "command": command, "reports": keys(artifacts)}, nil
}

func tail(value string, limit int) string {
	runes := []rune(value)
	return string(runes[max(0, len(runes)-limit):])
}

func collectionSettings(project string, value any) (object, object, []string, error) {
	if !objectFields(value, "command", "artifacts") {
		return nil, nil, nil, errors.New("architect.collection requires command and artifacts")
	}
	settings := asObject(value)
	command := stringsIn(settings["command"])
	if len(command) == 0 || slices.ContainsFunc(command, func(arg string) bool {
		return strings.TrimSpace(arg) == "" || strings.ContainsFunc(arg, func(c rune) bool { return c < 32 })
	}) {
		return nil, nil, nil, errors.New("command must be a nonempty argument array")
	}
	artifacts, err := validateArtifacts(settings["artifacts"])
	if err != nil {
		return nil, nil, nil, err
	}
	missing, unexpected := []string{}, []string{}
	for _, name := range keys(reportFormats) {
		if artifacts[name] == nil {
			missing = append(missing, name)
		}
	}
	for _, name := range keys(artifacts) {
		if reportFormats[name] == nil {
			unexpected = append(unexpected, name)
		}
	}
	if len(missing)+len(unexpected) != 0 {
		return nil, nil, nil, fmt.Errorf("Missing configured sources: %s; unexpected sources: %s", pythonList(missing), pythonList(unexpected))
	}
	for name, raw := range artifacts {
		spec := asObject(raw)
		if !slices.Contains(reportFormats[name], asString(spec["format"])) {
			return nil, nil, nil, fmt.Errorf("artifacts.%s: expected %s", name, pythonList(reportFormats[name]))
		}
		if _, err := reportPath(project, spec["path"], "artifacts."+name+".path"); err != nil {
			return nil, nil, nil, err
		}
		if _, err := reportPath(project, valueOr(spec, "source_root", "."), "artifacts."+name+".source_root"); err != nil {
			return nil, nil, nil, err
		}
	}
	coverage := asObject(artifacts["coverage"])
	if coverage["complete"] != true || coverage["test_result"] != "passed" {
		return nil, nil, nil, errors.New("coverage must come from complete JaCoCo reporting after successful tests")
	}
	return settings, artifacts, command, nil
}

func validateArtifacts(value any) (object, error) {
	artifacts := asObject(value)
	if artifacts == nil {
		return nil, errors.New("artifacts: expected an object")
	}
	allowed := []string{"path", "format", "tool", "version", "parser_version", "command", "source_root",
		"complete_mcc", "complete", "test_result", "limitations", "since", "until"}
	for name, raw := range artifacts {
		spec := asObject(raw)
		if spec == nil || len(unknownKeys(spec, allowed)) != 0 {
			return nil, fmt.Errorf("artifacts.%s: unsupported artifact fields", name)
		}
		for _, field := range []string{"path", "source_root"} {
			if path, present := spec[field]; present {
				if _, err := portablePath(path, "artifacts."+name+"."+field); err != nil {
					return nil, err
				}
			}
		}
		if value, exists := spec["command"]; exists {
			args, ok := value.([]any)
			if !ok || slices.ContainsFunc(args, func(value any) bool { _, ok := value.(string); return !ok }) {
				return nil, fmt.Errorf("artifacts.%s.command: expected an argument array", name)
			}
		}
	}
	return artifacts, inspectAuditValue(object{"artifacts": artifacts}, "configuration")
}

func collectionScope(project string, value any) (object, error) {
	scope := asObject(value)
	if scope == nil {
		return nil, errors.New("Audit configuration must be an object")
	}
	allowed := []string{"source_roots", "test_roots", "exclude_paths", "statistics_exclude_paths",
		"package_prefixes", "exclude_classes", "modules", "scope", "class_directories", "class_files", "artifacts"}
	if unknown := unknownKeys(scope, allowed); len(unknown) != 0 {
		return nil, fmt.Errorf("Unknown audit configuration fields: %s; pass the repository as a runtime argument", pythonList(unknown))
	}
	for _, field := range []string{"source_roots", "test_roots", "exclude_paths", "statistics_exclude_paths", "class_directories"} {
		if value, present := scope[field]; present {
			paths, ok := value.([]any)
			if !ok {
				return nil, fmt.Errorf("%s: expected an array", field)
			}
			for _, path := range paths {
				if _, err := portablePath(path, field); err != nil {
					return nil, err
				}
			}
		}
	}
	classFiles := asObject(valueOr(scope, "class_files", object{}))
	if classFiles == nil {
		return nil, errors.New("class_files: expected an object")
	}
	for _, path := range classFiles {
		if _, err := portablePath(path, "class_files"); err != nil {
			return nil, err
		}
	}
	if value, present := scope["artifacts"]; present {
		artifacts, err := validateArtifacts(value)
		if err != nil {
			return nil, err
		}
		if len(artifacts) > 0 {
			return nil, errors.New("Declare reports in collection.artifacts")
		}
	}
	if err := inspectAuditValue(scope, "configuration"); err != nil {
		return nil, err
	}
	if len(array(scope["source_roots"])) == 0 || len(asObject(scope["modules"])) == 0 ||
		len(array(scope["package_prefixes"])) == 0 || (len(classFiles) == 0 && len(array(scope["class_directories"])) == 0) {
		return nil, errors.New("Provide the production audit scope")
	}
	for _, field := range []string{"source_roots", "test_roots", "class_directories"} {
		for _, path := range array(scope[field]) {
			if _, err := reportPath(project, path, field); err != nil {
				return nil, err
			}
		}
	}
	return scope, nil
}

func valueOr(value object, key string, fallback any) any {
	if value, exists := value[key]; exists {
		return value
	}
	return fallback
}

func unknownKeys(values object, allowed []string) []string {
	missing := []string{}
	for _, key := range keys(values) {
		if !slices.Contains(allowed, key) {
			missing = append(missing, key)
		}
	}
	return missing
}

var auditTokenSeparator = regexp.MustCompile(`[\s=;,"'()\[\]]+`)
var windowsDrive = regexp.MustCompile(`^[A-Za-z]:`)

func inspectAuditValue(value any, field string) error {
	switch value := value.(type) {
	case object:
		for _, key := range keys(value) {
			if err := inspectAuditValue(key, field); err != nil {
				return err
			}
			if err := inspectAuditValue(value[key], field+"."+key); err != nil {
				return err
			}
		}
	case []any:
		for _, child := range value {
			if err := inspectAuditValue(child, field); err != nil {
				return err
			}
		}
	case string:
		value = unescapePath(value)
		for _, raw := range auditTokenSeparator.Split(value, -1) {
			token := strings.TrimLeft(raw, "@")
			if windowsDrive.MatchString(token) || strings.HasPrefix(strings.ToLower(token), "file:") ||
				strings.HasPrefix(token, "/") || strings.HasPrefix(token, "\\") || strings.HasPrefix(token, "~") ||
				slices.Contains(strings.Split(strings.ReplaceAll(token, "\\", "/"), "/"), "..") {
				return fmt.Errorf("%s: absolute paths and parent traversal are not audit configuration", field)
			}
		}
	}
	return nil
}

func portablePath(value any, field string) (string, error) {
	path := asString(value)
	if strings.TrimSpace(path) == "" {
		return "", fmt.Errorf("%s: expected a nonempty project-relative path", field)
	}
	if unescapePath(path) != path || strings.ContainsAny(path, ":\\") || strings.HasPrefix(path, "/") ||
		strings.HasPrefix(path, "~") || slices.Contains(strings.Split(path, "/"), "..") {
		return "", fmt.Errorf("%s: use a project-relative path with / and no parent traversal", field)
	}
	return path, nil
}

func unescapePath(path string) string {
	if decoded, err := url.PathUnescape(path); err == nil {
		return decoded
	}
	return path
}

func reportPath(project string, value any, field string) (string, error) {
	path, err := portablePath(value, field)
	if err != nil {
		return "", err
	}
	path = resolve(filepath.Join(project, filepath.FromSlash(path)))
	if !inside(project, path) {
		return "", fmt.Errorf("%s: path leaves the project through a symlink", field)
	}
	return path, nil
}

func jsonInteger(value any) (int, bool) {
	if value, ok := value.(json.Number); ok {
		if n, err := value.Int64(); err == nil {
			return int(n), true
		}
	}
	return 0, false
}
