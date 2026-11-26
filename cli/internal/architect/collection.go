package architect

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"io"
	"io/fs"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"github.com/AndrMoiseev/ai-sdlc/cli/internal/childprocess"
)

var selectionNames = []string{"rankings", "signals", "candidate-groups", "investigation-queue"}

var artifactExtensions = map[string]string{
	"jdeps": ".txt", "class-csv": ".csv", "git-log": ".log", "scc": ".json", "detekt-sarif": ".sarif",
	"jacoco": ".xml", "coverage-csv": ".csv", "kotlin-measurements": ".json", "git-history": ".json",
}

func pickDefault(value record, key string, fallback any) any {
	if item, found := value[key]; found {
		return item
	}
	return fallback
}

func isoNow() string { return time.Now().UTC().Format("2006-01-02T15:04:05.000000+00:00") }

func saveJSONTo(path string, value any) error {
	data, err := encodeJSON(value, true)
	if err != nil {
		return err
	}
	return writeText(path, data, false, true)
}

func collectCommand(args options, stdout io.Writer) error {
	selected, err := resolve(args.get("output"))
	if err != nil {
		return err
	}
	configPath, err := resolve(args.get("config"))
	if err != nil {
		return err
	}
	if configPath != filepath.Join(selected, "collection-input.json") {
		return fmt.Errorf("Use collection-input.json from the selected audit directory")
	}
	doc, err := readDocument(filepath.Clean(args.get("config")), "")
	if err != nil {
		return err
	}
	if err := validateConfiguration(doc.value); err != nil {
		return err
	}
	root, err := resolve(args.get("repository"))
	if err != nil {
		return err
	}
	if !isDir(root) {
		return fmt.Errorf("Repository not found: %s", root)
	}
	config := object(doc.value)
	if err := validateConfigPaths(config, root); err != nil {
		return err
	}
	policy, err := loadPolicy(root)
	if err != nil {
		return err
	}
	output, err := reportOutput(selected, root, true)
	if err != nil {
		return err
	}
	if collectionStarted(output) {
		return fmt.Errorf("Collection output already exists; choose a new report directory")
	}
	full, fresh := !args.has("focused"), args.has("fresh")
	description, err := collect(config, policy, output, root, full, fresh)
	if err != nil {
		return err
	}
	complete, unavailable := 0, 0
	for _, item := range object(description["outputs"]) {
		if object(item)["status"] == "complete" {
			complete++
		} else {
			unavailable++
		}
	}
	return printJSON(stdout, record{"collection": filepath.Join(filepath.Clean(args.get("output")), "collection.json"),
		"complete_outputs": complete, "unavailable_outputs": unavailable,
		"candidate_groups": object(object(description["selections"])["candidate-groups"])["records"], "gaps": len(description["gaps"].([]record))}, false)
}

func validateConfigPaths(config record, root string) error {
	for _, field := range []string{"source_roots", "test_roots", "class_directories"} {
		for _, path := range items(config[field]) {
			if _, err := resolveProjectPath(path, root, field); err != nil {
				return err
			}
		}
	}
	for _, path := range object(config["class_files"]) {
		if _, err := resolveProjectPath(path, root, "class_files"); err != nil {
			return err
		}
	}
	artifacts := object(config["artifacts"])
	for _, name := range keys(artifacts) {
		artifact := object(artifacts[name])
		for _, field := range []string{"path", "source_root"} {
			if value, found := artifact[field]; found {
				if _, err := resolveProjectPath(value, root, "artifacts."+name+"."+field); err != nil {
					return err
				}
			}
		}
	}
	return nil
}

func collect(config, policy record, output, root string, full, fresh bool) (record, error) {
	route := "focused"
	if full {
		route = "full"
	}
	parameters := record{}
	for _, name := range []string{"source_roots", "exclude_paths", "package_prefixes", "exclude_classes", "class_directories"} {
		parameters[name] = pickDefault(config, name, []any{})
	}
	for _, name := range []string{"modules", "scope"} {
		parameters[name] = pickDefault(config, name, record{})
	}
	artifacts, outputs, selections := record{}, record{}, record{}
	for name, spec := range catalog {
		outputs[name] = record{"path": spec.path, "status": "incomplete", "records": nil, "reason": "Collection has not completed this calculation"}
	}
	for _, name := range selectionNames {
		selections[name] = record{"path": "selections/" + name + ".jsonl", "status": "incomplete", "records": nil}
	}
	description := record{"status": "incomplete", "route": route, "analysis_policy": policy, "parameters": parameters,
		"artifacts": artifacts, "gaps": []record{}, "outputs": outputs, "selections": selections}
	collectionPath := filepath.Join(output, "collection.json")
	if err := saveJSONTo(collectionPath, description); err != nil {
		return nil, err
	}
	block := func(reason string) (record, error) {
		description["status"] = "blocked"
		description["gaps"] = append(description["gaps"].([]record), record{"reason": reason})
		if err := saveJSONTo(collectionPath, description); err != nil {
			return nil, err
		}
		return nil, fmt.Errorf("%s; stop the audit and resolve this prerequisite before continuing", reason)
	}
	if full || fresh {
		settings, err := projectCollection(root)
		if err != nil {
			return block(err.Error())
		}
		description["command"] = settings["command"]
		if truthy(config["artifacts"]) {
			return block("Use audit-local artifacts only for focused import of existing reports")
		}
		if err := runCollectionCommand(stringsOf(settings["command"]), root, policy); err != nil {
			return block(err.Error())
		}
		config["artifacts"] = settings["artifacts"]
		settingsArtifacts := object(settings["artifacts"])
		for _, name := range keys(settingsArtifacts) {
			item := object(settingsArtifacts[name])
			path, err := resolveProjectPath(item["path"], root, name)
			if err != nil {
				return block(err.Error())
			}
			if !isFile(path) {
				return block(fmt.Sprintf("Project command did not produce %s: %s", name, item["path"]))
			}
		}
	}
	sources, sourceError := inventory(config, root)
	mappings, mappingGaps := mapClasses(config, root, sources)
	configArtifacts := object(config["artifacts"])
	if unknown := keyDiff(configArtifacts, fullFormats); len(unknown) > 0 {
		return nil, fmt.Errorf("Unknown artifacts: %s", pythonList(unknown))
	}
	if full {
		if missing := keyDiff(fullFormats, configArtifacts); len(missing) > 0 {
			return block("Missing configured sources: " + strings.Join(missing, ", "))
		}
		if sourceError != nil {
			return block(sourceError.Error())
		}
		if len(mappingGaps) > 0 {
			var gaps []any
			for _, gap := range mappingGaps[:min(3, len(mappingGaps))] {
				gaps = append(gaps, gap)
			}
			return block("Incomplete JVM source mapping: " + pythonValue(gaps))
		}
		if !truthy(config["source_roots"]) || !truthy(config["modules"]) {
			return block("Configure production source roots and architectural module ownership")
		}
		if !truthy(config["class_directories"]) && !truthy(config["class_files"]) {
			return block("Compile production code and configure its JVM class directories")
		}
	}
	raw, retained := map[string]string{}, map[string]string{}
	for _, name := range keys(fullFormats) {
		spec := object(configArtifacts[name])
		if spec == nil {
			artifacts[name] = record{"status": "unavailable", "reason": "No source configured"}
			continue
		}
		metadata, text, err := retainArtifact(name, spec, root, output, retained)
		artifacts[name] = metadata
		if err != nil {
			metadata["status"], metadata["reason"] = "error", err.Error()
			if full || fresh {
				return block(name + ": " + err.Error())
			}
		} else {
			raw[name] = text
		}
	}
	analysis, err := prepareMeasurements(config, sources, mappings, mappingGaps, raw, artifacts, policy, sourceError, root)
	if err != nil {
		return nil, err
	}
	description["gaps"] = analysis.gaps
	if full {
		var failed []string
		for _, name := range keys(artifacts) {
			if object(artifacts[name])["status"] != "complete" {
				failed = append(failed, name)
			}
		}
		if len(failed) > 0 {
			return block("Invalid measurement sources: " + strings.Join(failed, ", "))
		}
		quality, err := prepareQuality(config, sources, mappings, raw, artifacts, policy, root, analysis)
		if err != nil {
			return block(err.Error())
		}
		path := "metrics/quality-indicators.json"
		if err := saveJSONTo(filepath.Join(output, filepath.FromSlash(path)), quality); err != nil {
			return nil, err
		}
		description["quality_indicators"] = record{"path": path, "status": "complete"}
	}
	for _, name := range keys(catalog) {
		rows := analysis.rows[name]
		spec := catalog[name]
		if err := writeJSONL(filepath.Join(output, filepath.FromSlash(spec.path)), rows); err != nil {
			return nil, err
		}
		outcome := analysis.outcomes[name]
		outcome["path"], outcome["records"] = spec.path, len(rows)
		outputs[name] = outcome
	}
	for _, name := range selectionNames {
		path := "selections/" + name + ".jsonl"
		rows := analysis.selections[name]
		if err := writeJSONL(filepath.Join(output, filepath.FromSlash(path)), rows); err != nil {
			return nil, err
		}
		selections[name] = record{"path": path, "records": len(rows), "status": "complete"}
	}
	description["status"] = "complete"
	return description, saveJSONTo(collectionPath, description)
}

func writeJSONL(path string, rows []record) error {
	var result strings.Builder
	for _, row := range rows {
		result.WriteString(keyText(row))
		result.WriteByte('\n')
	}
	return writeText(path, []byte(result.String()), false, false)
}

func retainArtifact(name string, spec record, root, output string, retained map[string]string) (record, string, error) {
	metadata := record{}
	for _, field := range artifactFields[1:] {
		if value, found := spec[field]; found {
			metadata[field] = value
		}
	}
	format := str(spec["format"])
	if !contains(fullFormats[name], format) && !(name == "history" && format == "git-log") && !(name == "coverage" && format == "coverage-csv") {
		return metadata, "", fmt.Errorf("Unsupported %s format: %s", name, display(spec["format"]))
	}
	if _, found := spec["path"]; !found {
		return metadata, "", fmt.Errorf("'path'")
	}
	path, err := resolveProjectPath(spec["path"], root, "artifacts."+name+".path")
	if err != nil {
		return metadata, "", err
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return metadata, "", fileError(err)
	}
	raw, err := resolve(filepath.Join(output, "raw"))
	if err != nil {
		return metadata, "", err
	}
	if !within(raw, output) {
		return metadata, "", fmt.Errorf("Raw report directory leaves the selected report")
	}
	target := retained[path]
	if within(path, raw) {
		target = path
	} else if target == "" {
		target, err = resolve(filepath.Join(raw, name+artifactExtensions[format]))
		if err != nil {
			return metadata, "", err
		}
		if !within(target, output) {
			return metadata, "", fmt.Errorf("Raw report path leaves the selected report")
		}
		if exists(target) {
			return metadata, "", fmt.Errorf("Raw report output already exists: %s", target)
		}
		if err := writeText(target, data, true, false); err != nil {
			return metadata, "", err
		}
	}
	retained[path] = target
	relative, _ := filepath.Rel(output, target)
	metadata["path"], metadata["status"], metadata["collected_at"] = filepath.ToSlash(relative), "complete", isoNow()
	metadata["source_root"] = pickDefault(metadata, "source_root", ".")
	if err := validUTF8(data); err != nil {
		return metadata, "", err
	}
	text := strings.TrimPrefix(string(data), "\ufeff")
	if name == "kotlin" {
		parsed, err := parseJSONValue([]byte(text))
		if err != nil {
			return metadata, "", err
		}
		report := object(parsed)
		if report == nil {
			return metadata, "", fmt.Errorf("Expected a Kotlin measurement report object")
		}
		for _, field := range []struct{ source, target string }{{"tool", "tool"}, {"tool_version", "version"}, {"parser_version", "parser_version"}, {"plugin_version", "plugin_version"}} {
			if value, found := report[field.source]; found {
				metadata[field.target] = value
			}
		}
	}
	return metadata, text, nil
}

func runCollectionCommand(argv []string, root string, policy record) error {
	runtimePolicy := object(policy["runtime"])
	timeout := integer(runtimePolicy["command_timeout_seconds"])
	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(timeout)*time.Second)
	defer cancel()
	command := exec.CommandContext(ctx, argv[0], argv[1:]...)
	command.Dir = root
	command.WaitDelay = 5 * time.Second
	childprocess.Configure(command)
	var stdout, stderr bytes.Buffer
	command.Stdout, command.Stderr = &stdout, &stderr
	err := command.Run()
	if ctx.Err() == context.DeadlineExceeded {
		return fmt.Errorf("Command timed out after %ds: %s", timeout, argv[0])
	}
	if err == nil {
		return nil
	}
	var exit *exec.ExitError
	if !errors.As(err, &exit) {
		return fileError(err)
	}
	limit := integer(runtimePolicy["stderr_tail_characters"])
	detail := []rune(strings.ToValidUTF8(stderr.String(), "�"))
	report := string(detail[max(0, len(detail)-limit):])
	if stdout.Len() > 0 {
		output := []rune(strings.ToValidUTF8(stdout.String(), "�"))
		report = string(output[:min(limit, len(output))]) + "\n" + report
	}
	return fmt.Errorf("Command failed (%d): %s\n%s", exit.ExitCode(), pythonList(argv), report)
}

func permittedClass(name string, prefixes, excluded []string) bool {
	if matchesAny(name, excluded) {
		return false
	}
	if len(prefixes) == 0 {
		return true
	}
	for _, prefix := range prefixes {
		if name == prefix || strings.HasPrefix(name, prefix+".") {
			return true
		}
	}
	return false
}

func mapClasses(config record, root string, sources map[string]record) (map[string]string, []record) {
	lookup := map[[2]string][]string{}
	for _, path := range keys(sources) {
		source := sources[path]
		key := [2]string{str(source["package"]), filepath.Base(path)}
		lookup[key] = append(lookup[key], path)
	}
	mappings, unresolved := map[string]string{}, []record{}
	prefixes, excluded := stringsOf(config["package_prefixes"]), stringsOf(config["exclude_classes"])
	for _, name := range stringsOf(config["class_directories"]) {
		directory, err := resolve(filepath.Join(root, filepath.FromSlash(name)))
		if err != nil {
			return nil, []record{{"reason": err.Error()}}
		}
		if !isDir(directory) {
			unresolved = append(unresolved, record{"reason": "Missing compiled class directory: " + directory})
			continue
		}
		err = filepath.WalkDir(directory, func(path string, entry fs.DirEntry, err error) error {
			if err != nil {
				return fileError(err)
			}
			if filepath.Ext(path) != ".class" {
				return nil
			}
			data, err := os.ReadFile(path)
			var name, sourceFile string
			if err == nil {
				name, sourceFile, err = classSourceFile(data)
			}
			if err != nil {
				unresolved = append(unresolved, record{"reason": fileError(err).Error(), "class_file": path})
				return nil
			}
			if !permittedClass(name, prefixes, excluded) {
				return nil
			}
			candidates := lookup[[2]string{packageOf(name), sourceFile}]
			if len(candidates) == 1 {
				if prior, exists := mappings[name]; exists && prior != candidates[0] {
					return fmt.Errorf("Conflicting JVM class %s", name)
				}
				mappings[name] = candidates[0]
			} else {
				var source any = sourceFile
				if sourceFile == "" {
					source = nil
				}
				unresolved = append(unresolved, record{"class": name, "source_file": source, "candidates": append([]string{}, candidates...)})
			}
			return nil
		})
		if err != nil {
			return nil, []record{{"reason": err.Error()}}
		}
	}
	explicit := object(config["class_files"])
	for _, name := range keys(explicit) {
		path, err := relativeSourcePath(str(explicit[name]), root)
		if err != nil {
			return nil, []record{{"reason": err.Error()}}
		}
		if sources[path] == nil {
			return nil, []record{{"reason": fmt.Sprintf("Explicit mapping is outside source inventory: %s -> %s", name, path)}}
		}
		mappings[name] = path
	}
	remaining := []record{}
	for _, gap := range unresolved {
		if _, found := mappings[str(gap["class"])]; !found {
			remaining = append(remaining, gap)
		}
	}
	return mappings, remaining
}
