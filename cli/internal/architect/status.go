package architect

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"path/filepath"
	"regexp"
	"strings"
)

func statusCommand(args options, stdout io.Writer) error {
	collectionPath := filepath.Clean(args.get("collection"))
	collection, err := readObject(collectionPath)
	if err != nil {
		return err
	}
	root, err := resolve(args.get("repository"))
	if err != nil {
		return err
	}
	resolved, err := resolve(collectionPath)
	if err != nil {
		return err
	}
	audit := filepath.Dir(resolved)
	if _, err := reportOutput(audit, root, true); err != nil {
		return err
	}
	if collection["route"] != "full" || collection["status"] != "complete" {
		return fmt.Errorf("Publish status only after a complete full audit")
	}
	if _, found := collection["artifacts"]; !found {
		return fmt.Errorf("'artifacts'")
	}
	for _, artifact := range object(collection["artifacts"]) {
		if object(artifact)["status"] != "complete" {
			return fmt.Errorf("A required measurement source failed; resolve it before publishing status")
		}
	}
	destination := filepath.Join(root, "memory", "tech-debt")
	for _, required := range []string{filepath.Join(audit, "report.md"), filepath.Join(destination, "plan", "plan.md")} {
		if !isFile(required) {
			return fmt.Errorf("Finish the report and tech debt plan before status publication: %s", required)
		}
	}
	artifact := object(collection["quality_indicators"])
	if artifact["status"] != "complete" {
		return fmt.Errorf("Aggregate calculations are incomplete")
	}
	artifactPath, ok := artifact["path"]
	if !ok {
		return fmt.Errorf("'path'")
	}
	path, err := resolve(joinPath(audit, filepath.FromSlash(str(artifactPath))))
	if err != nil {
		return err
	}
	if !within(path, audit) {
		return fmt.Errorf("Aggregate input must be inside the selected audit")
	}
	doc, err := readDocument(path, "")
	if err != nil {
		return err
	}
	value := object(doc.value)
	if value == nil {
		return fmt.Errorf("expected a JSON object")
	}
	relative, _ := filepath.Rel(destination, audit)
	value["audit"] = filepath.ToSlash(relative)
	moduleOrder := jsonObjectOrder(doc.text, "modules")
	markdown, err := renderStatus(value, moduleOrder)
	if err != nil {
		return err
	}
	encoded, err := encodeJSON(value, true)
	if err != nil {
		return err
	}
	guide, err := assets.ReadFile("assets/status-indicators.md")
	if err != nil {
		return err
	}
	resolvedDestination, err := resolve(destination)
	if err != nil {
		return err
	}
	output := record{}
	for _, item := range []struct{ key, name string }{{"json", "status.json"}, {"markdown", "status.md"}, {"guide", "status-indicators.md"}} {
		path := filepath.Join(destination, item.name)
		resolved, err := resolve(path)
		if err != nil {
			return err
		}
		if !within(resolved, resolvedDestination) {
			return fmt.Errorf("Status output leaves memory/tech-debt")
		}
		output[item.key] = path
	}
	if err := writeText(str(output["guide"]), guide, false, false); err != nil {
		return err
	}
	if err := writeText(str(output["json"]), encoded, false, true); err != nil {
		return err
	}
	if err := writeText(str(output["markdown"]), []byte(markdown), false, true); err != nil {
		return err
	}
	return printJSON(stdout, output, false)
}

func jsonObjectOrder(data []byte, names ...string) []string {
	for _, name := range names {
		var object map[string]json.RawMessage
		if json.Unmarshal(data, &object) != nil {
			return nil
		}
		data = object[name]
	}
	decoder := json.NewDecoder(bytes.NewReader(data))
	start, err := decoder.Token()
	if err != nil || start != json.Delim('{') {
		return nil
	}
	var result []string
	for decoder.More() {
		key, err := decoder.Token()
		if err != nil {
			return nil
		}
		var value json.RawMessage
		if decoder.Decode(&value) != nil {
			return nil
		}
		result = append(result, str(key))
	}
	return result
}

var templateVariable = regexp.MustCompile(`\$([A-Za-z_][A-Za-z0-9_]*)`)

func statusTemplate(name string, substitutions record) (string, error) {
	data, err := assets.ReadFile("assets/" + name)
	if err != nil {
		return "", err
	}
	text := strings.ReplaceAll(string(data), "\r\n", "\n")
	var missing string
	text = templateVariable.ReplaceAllStringFunc(text, func(variable string) string {
		key := variable[1:]
		value, found := substitutions[key]
		if !found && missing == "" {
			missing = key
		}
		return display(value)
	})
	if missing != "" {
		return "", fmt.Errorf("%s", quoted(missing))
	}
	return text, nil
}

func statusNumber(value any) string {
	if value == nil {
		return "Неприменимо"
	}
	return fmt.Sprintf("%.1f", numeric(value))
}

func statusPercent(value any) string {
	if value == nil {
		return "Неприменимо"
	}
	return fmt.Sprintf("%.1f%%", 100*numeric(value))
}

func statusLabel(value string) string {
	return strings.NewReplacer("|", `\|`, "\n", " ").Replace(value)
}

func tableRow(cells ...any) string {
	parts := make([]string, 0, len(cells))
	for _, cell := range cells {
		parts = append(parts, display(cell))
	}
	return "| " + strings.Join(parts, " | ") + " |"
}

func renderStatus(value record, moduleOrder []string) (string, error) {
	substitutions := record{"collected_at": value["collected_at"], "audit": value["audit"], "profile": object(value["profile"])["name"]}
	for key, scope := range object(value["scope"]) {
		substitutions[key] = scope
	}
	var scores, sizes, diagnostics, boundaries []string
	type summary struct {
		name string
		row  record
	}
	summaries := []summary{{"Проект", object(value["project"])}}
	modules := object(value["modules"])
	if len(moduleOrder) == 0 {
		moduleOrder = keys(modules)
	}
	for _, name := range moduleOrder {
		summaries = append(summaries, summary{name, object(modules[name])})
	}
	for _, summary := range summaries {
		name, row := summary.name, summary.row
		for _, key := range []string{"files", "tokens", "D", "L", "U", "Q", "statistics", "structure", "local_maintainability", "coverage", "history", "duplication"} {
			if _, exists := row[key]; !exists {
				return "", fmt.Errorf("%s", quoted(key))
			}
		}
		scores = append(scores, tableRow(statusLabel(name), row["files"], row["tokens"], statusNumber(row["D"]), statusNumber(row["L"]), statusNumber(row["U"]), statusNumber(row["Q"])))
		stats := object(row["statistics"])
		addStats := func(suffix string, counts record) {
			sizes = append(sizes, tableRow(statusLabel(name+" / "+suffix), counts["Files"], counts["Lines"], counts["Code"], counts["Comment"], counts["Blank"]))
		}
		addStats("всего", object(stats["total"]))
		for _, population := range []string{"by_category", "by_language"} {
			rows := object(stats[population])
			for _, suffix := range keys(rows) {
				addStats(suffix, object(rows[suffix]))
			}
		}
		diagnostic, err := statusDiagnostics(name, row)
		if err != nil {
			return "", err
		}
		diagnostics = append(diagnostics, diagnostic)
		if boundary := object(row["boundary"]); boundary != nil {
			boundaries = append(boundaries, tableRow(statusLabel(name), boundary["incoming_edges"], boundary["outgoing_edges"], boundary["project_cyclic_files"], boundary["cross_module_coupled_tokens"], boundary["cross_module_duplicate_tokens"]))
		}
	}
	limitations := stringsOf(value["limitations"])
	for index := range limitations {
		limitations[index] = "- " + limitations[index]
	}
	substitutions["scores"], substitutions["statistics"] = strings.Join(scores, "\n"), strings.Join(sizes, "\n")
	substitutions["diagnostics"], substitutions["boundaries"] = strings.Join(diagnostics, "\n\n"), strings.Join(boundaries, "\n")
	substitutions["limitations"] = strings.Join(limitations, "\n")
	return statusTemplate("status.template.md", substitutions)
}

func statusDiagnostics(name string, row record) (string, error) {
	structure, local := object(row["structure"]), object(row["local_maintainability"])
	coverage, history, duplication := object(row["coverage"]), object(row["history"]), object(row["duplication"])
	line := object(coverage["line"])
	lineValue := statusPercent(line["value"])
	if line["status"] == "unknown" {
		lineValue = "Нет данных"
	} else if line["status"] == "measured_subset" {
		lineValue += " (по части файлов)"
	}
	omittedFiles := ""
	if omitted := stringsOf(line["omitted_files"]); len(omitted) > 0 {
		for index := range omitted {
			omitted[index] = "- " + statusLabel(omitted[index])
		}
		omittedFiles = "\nФайлы без построчных данных JaCoCo\n\n" + strings.Join(omitted, "\n")
	}
	parameters := record{"name": statusLabel(name), "pc": statusPercent(structure["propagation_cost"]),
		"cyclic_file_fraction":   statusPercent(structure["cyclic_file_fraction"]),
		"complex_token_fraction": statusPercent(object(local["complex_token_fraction"])["value"]),
		"duplicate_tokens":       duplication["tokens"], "duplicate_token_fraction": statusPercent(object(duplication["fraction"])["value"]),
		"history_status": history["status"], "coupled_token_fraction": statusPercent(object(history["coupled_token_fraction"])["value"]),
		"branch": statusPercent(object(coverage["branch"])["value"]), "instruction": statusPercent(object(coverage["instruction"])["value"]),
		"line": lineValue, "omitted_files": omittedFiles}
	for _, source := range []struct {
		object record
		fields string
		format func(any) any
	}{
		{structure, "cyclic_files largest_scc_size edge_count", nil},
		{local, "function_count function_tokens outside_function_tokens complex_tokens", nil},
		{local, "cognitive_score size_score maximum_cognitive_complexity weighted_p95_cognitive_complexity", func(value any) any { return statusNumber(value) }},
		{coverage, "method_count", nil},
		{coverage, "total_crap total_excess excess_density E_CRAP p95_crap_exec", func(value any) any { return statusNumber(value) }},
		{history, "observations excluded_large_commits coupled_files coupled_tokens", nil},
	} {
		for _, field := range strings.Fields(source.fields) {
			value := source.object[field]
			if source.format != nil {
				value = source.format(value)
			}
			parameters[field] = value
		}
	}
	text, err := statusTemplate("status-diagnostics.template.md", parameters)
	return strings.TrimRight(text, " \t\n\r"), err
}
