package architect

import (
	"bufio"
	"bytes"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

type measurement struct {
	path   string
	key    []string
	inputs []string
}

var catalog = measurementCatalog()

func measurementCatalog() map[string]measurement {
	result := map[string]measurement{}
	define := func(names, levels, key, inputs string) {
		for _, name := range strings.Fields(names) {
			for _, level := range strings.Fields(levels) {
				identifier := name + "/" + level
				fields := key
				if fields == "" {
					fields = level
				}
				result[identifier] = measurement{measurementPath(identifier), strings.Fields(fields), strings.Fields(inputs)}
			}
		}
	}
	define("source-files type-count abstract-type-count", "file", "", "sources")
	define("class-files", "class", "", "mapping")
	define("dependencies cyclic-edges", "class package module", "from to", "dependencies")
	define("node-count edge-count propagation-cost", "class package module", "graph", "dependencies")
	define("fan-in fan-out incoming-weight outgoing-weight reachable-in reachable-out visibility-in visibility-out", "class package module", "node", "dependencies")
	define("cyclic-components dependency-layers", "class package module", "members", "dependencies")
	define("cohesion", "module", "", "dependencies")
	define("external-affinity", "package", "", "dependencies")
	define("ca ce instability abstractness distance", "package", "", "sources dependencies")
	define("changes", "commit", "", "history")
	define("change-frequency added-lines deleted-lines churn", "file", "", "history")
	define("change-frequency added-lines deleted-lines churn", "package module", "", "history sources")
	define("activity recent-activity", "package module", "", "sources history")
	define("coupling", "file-pair", "left right", "history")
	define("implicit-coupling", "file-pair", "left right", "history dependencies sources")
	define("code-lines total-lines", "file", "", "sizes")
	define("cyclomatic-complexity cognitive-complexity method-length", "function", "file region declaration", "complexity")
	define("function-count parameter-list", "declaration", "file region declaration", "complexity")
	define("cyclomatic-complexity", "file", "", "complexity")
	define("line-coverage branch-coverage", "file", "", "coverage")
	define("line-coverage branch-coverage", "package module", "", "coverage sources")
	define("crap-file", "file", "", "complexity coverage")
	define("crap-sum crap-mean crap-above-threshold", "package module", "", "complexity coverage sources")
	define("hotspot-in-frequency hotspot-out-frequency hotspot-in-churn", "file", "", "dependencies history mapping")
	define("changes-per-code", "file", "", "history sizes")
	return result
}

func measurementPath(identifier string) string { return "metrics/" + identifier + ".jsonl" }

func pick(row record, fields []string) record {
	result := record{}
	for _, field := range fields {
		result[field] = row[field]
	}
	return result
}

func reference(identifier string, row record) record {
	spec := catalog[identifier]
	return record{"path": spec.path, "key": pick(row, spec.key)}
}

func selectionReference(name, field, identity string) record {
	return record{"path": "selections/" + name + ".jsonl", "key": record{field: identity}}
}

func readJSONL(directory, path string) ([]record, error) {
	directory, err := resolve(directory)
	if err != nil {
		return nil, err
	}
	filename, err := resolve(joinPath(directory, filepath.FromSlash(path)))
	if err != nil {
		return nil, err
	}
	if !within(filename, directory) {
		return nil, fmt.Errorf("Evidence leaves report directory")
	}
	file, err := os.Open(filename)
	if err != nil {
		return nil, fileError(err)
	}
	defer file.Close()
	var result []record
	reader := bufio.NewReader(file)
	for {
		line, err := reader.ReadBytes('\n')
		if len(bytes.TrimSpace(line)) > 0 {
			value, err := parseJSONValue(line)
			if err != nil {
				return nil, err
			}
			row := object(value)
			if row == nil {
				return nil, fmt.Errorf("Expected a JSONL object: %s", path)
			}
			result = append(result, row)
		}
		if err != nil {
			if !errors.Is(err, io.EOF) {
				return nil, fileError(err)
			}
			return result, nil
		}
	}
}

// keyText follows the catalog's sorted JSON key format, including separators.
func keyText(value any) string {
	encoded, _ := encodeJSON(value, false)
	var result strings.Builder
	quotedValue, escaped := false, false
	for _, token := range string(bytes.TrimSpace(encoded)) {
		result.WriteRune(token)
		if quotedValue {
			if !escaped && token == '"' {
				quotedValue = false
			}
			escaped = !escaped && token == '\\'
		} else if token == '"' {
			quotedValue = true
		} else if token == ':' || token == ',' {
			result.WriteByte(' ')
		}
	}
	return result.String()
}

func readKeyedRows(directory, path string, fields []string, wanted []any) ([]record, error) {
	identities := map[string]bool{}
	for _, key := range wanted {
		if !sameKeys(object(key), fields) {
			return nil, fmt.Errorf("Evidence needs a complete record key: %s %s", path, pythonValue(key))
		}
		identities[keyText(key)] = true
	}
	rows, err := readJSONL(directory, path)
	if err != nil {
		return nil, err
	}
	var selected []record
	found := map[string]bool{}
	for _, row := range rows {
		key := keyText(pick(row, fields))
		if !identities[key] {
			continue
		}
		if found[key] {
			return nil, fmt.Errorf("Duplicate evidence key: %s %s", path, key)
		}
		found[key] = true
		selected = append(selected, row)
	}
	if missing := keyDiff(identities, found); len(missing) > 0 {
		return nil, fmt.Errorf("Missing evidence key: %s %s", path, missing[0])
	}
	return selected, nil
}

func pythonValue(value any) string {
	switch value := value.(type) {
	case string:
		return quoted(value)
	case map[string]any:
		parts := []string{}
		for _, field := range keys(value) {
			parts = append(parts, quoted(field)+": "+pythonValue(value[field]))
		}
		return "{" + strings.Join(parts, ", ") + "}"
	case []any:
		parts := []string{}
		for _, item := range value {
			parts = append(parts, pythonValue(item))
		}
		return "[" + strings.Join(parts, ", ") + "]"
	default:
		return display(value)
	}
}

func resolveMeasurements(references []record, collection record, directory string) ([]record, error) {
	byPath := map[string][]any{}
	for _, ref := range references {
		path, found := ref["path"]
		if !found {
			return nil, fmt.Errorf("'path'")
		}
		key, found := ref["key"]
		if !found {
			return nil, fmt.Errorf("'key'")
		}
		byPath[str(path)] = append(byPath[str(path)], key)
	}
	results := []record{}
	for _, path := range keys(byPath) {
		identifier := strings.TrimSuffix(strings.TrimPrefix(path, "metrics/"), ".jsonl")
		spec, found := catalog[identifier]
		if !found || spec.path != path {
			return nil, fmt.Errorf("Metric evidence needs a catalog path: %s", path)
		}
		outcome, err := metricOutcome(collection, identifier)
		if err != nil {
			return nil, err
		}
		if outcome["status"] != "complete" {
			return nil, fmt.Errorf("Metric evidence is unavailable: %s", identifier)
		}
		rows, err := readKeyedRows(directory, path, spec.key, byPath[path])
		if err != nil {
			return nil, err
		}
		for _, row := range rows {
			results = append(results, record{"reference": reference(identifier, row), "row": row})
		}
	}
	return results, nil
}

func metricOutcome(collection record, name string) (record, error) {
	outputs := object(collection["outputs"])
	if outputs == nil {
		return nil, fmt.Errorf("'outputs'")
	}
	if outcome := object(outputs[name]); outcome != nil {
		return outcome, nil
	}
	return nil, fmt.Errorf("%s", quoted(name))
}

func metricRows(collection record, directory, name string) ([]record, record, error) {
	outcome, err := metricOutcome(collection, name)
	if err != nil || outcome["status"] != "complete" {
		return nil, outcome, err
	}
	rows, err := readJSONL(directory, catalog[name].path)
	return rows, outcome, err
}

func sortedMeasurementRows(identifier string, rows []record) error {
	fields := catalog[identifier].key
	seen := map[string]bool{}
	for _, row := range rows {
		key := keyText(pick(row, fields))
		if seen[key] {
			return fmt.Errorf("Duplicate measurement key: %s", identifier)
		}
		seen[key] = true
	}
	sort.Slice(rows, func(i, j int) bool { return keyText(pick(rows[i], fields)) < keyText(pick(rows[j], fields)) })
	return nil
}
