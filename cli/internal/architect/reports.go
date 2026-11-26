package architect

import (
	"encoding/csv"
	"encoding/json"
	"encoding/xml"
	"fmt"
	"net/url"
	"path"
	"regexp"
	"strconv"
	"strings"
	"time"
)

func relativeSourcePath(value, root string) (string, error) {
	value = unquote(value)
	if strings.HasPrefix(value, "file:") {
		parsed, err := url.Parse(value)
		if err != nil {
			return "", err
		}
		value = parsed.Path
		if parsed.Host != "" {
			value = "//" + parsed.Host + value
		} else if len(value) > 3 && value[0] == '/' && windowsDrive.MatchString(value[1:]) && value[3] == '/' {
			value = value[1:]
		}
	}
	value = strings.ReplaceAll(value, `\`, "/")
	root = strings.TrimRight(strings.ReplaceAll(root, `\`, "/"), "/")
	if value == root {
		return "", fmt.Errorf("Expected a source file, got the repository root")
	}
	value = strings.TrimPrefix(value, root+"/")
	if strings.HasPrefix(value, "/") || windowsDrive.MatchString(value) || contains(strings.Split(value, "/"), "..") {
		return "", fmt.Errorf("Unmapped source path %s; supply project-relative report paths or the current checkout's paths", quoted(value))
	}
	return path.Clean(value), nil
}

type edge struct{ from, to string }
type edgeWeights map[edge]int

var jdepsEdge = regexp.MustCompile(`(?m)^\s+(\S+)\s+->\s+(\S+)`)

func csvRows(text string) ([]string, []map[string]string, error) {
	reader := csv.NewReader(strings.NewReader(text))
	reader.FieldsPerRecord = -1
	reader.LazyQuotes = true
	rows, err := reader.ReadAll()
	if err != nil || len(rows) == 0 {
		return nil, nil, err
	}
	headers := rows[0]
	var result []map[string]string
	for _, row := range rows[1:] {
		entry := map[string]string{}
		for i := 0; i < min(len(row), len(headers)); i++ {
			entry[headers[i]] = row[i]
		}
		result = append(result, entry)
	}
	return headers, result, nil
}

func parseDependencies(text, format string, prefixes, excludes []string) (edgeWeights, error) {
	if len(prefixes) == 0 {
		return nil, fmt.Errorf("package_prefixes is required for dependency scope")
	}
	result := edgeWeights{}
	add := func(from, to string) {
		if from != to && permittedClass(from, prefixes, excludes) && permittedClass(to, prefixes, excludes) {
			result[edge{from, to}] = 1
		}
	}
	if format == "jdeps" {
		for _, row := range jdepsEdge.FindAllStringSubmatch(text, -1) {
			add(row[1], row[2])
		}
	} else {
		headers, rows, err := csvRows(text)
		if err != nil {
			return nil, err
		}
		if !contains(headers, "from") || !contains(headers, "to") {
			return nil, fmt.Errorf("Dependencies CSV requires from,to headers")
		}
		for _, row := range rows {
			add(row["from"], row["to"])
		}
	}
	return result, nil
}

var complexityRules = map[string]*regexp.Regexp{
	"CyclomaticComplexMethod": regexp.MustCompile(`Cyclomatic Complexity \(complexity: (\d+)\)`),
	"CognitiveComplexMethod":  regexp.MustCompile(`Cognitive Complexity \(complexity: (\d+)\)`),
	"LongMethod":              regexp.MustCompile(`too long \((\d+)\)`),
	"TooManyFunctions":        regexp.MustCompile(`with '(\d+)' functions`),
	"LongParameterList":       nil,
}

func firstObject(value any) record {
	if all := items(value); len(all) > 0 {
		return object(all[0])
	}
	return nil
}

func parseDetekt(text, sourceRoot string) ([]record, error) {
	parsed, err := parseJSONValue([]byte(text))
	if err != nil {
		return nil, err
	}
	runs := items(object(parsed)["runs"])
	if runs == nil {
		return nil, fmt.Errorf("detekt SARIF requires a runs array")
	}
	result, seen := []record{}, map[string]bool{}
	for runIndex, data := range runs {
		run := object(data)
		for index, finding := range items(run["results"]) {
			row := object(finding)
			rule := str(row["ruleId"])
			_, suffix, found := strings.Cut(rule, ".")
			if found {
				rule = suffix[strings.LastIndexByte(suffix, '.')+1:]
			}
			pattern, known := complexityRules[rule]
			if !known {
				continue
			}
			location := object(firstObject(row["locations"])["physicalLocation"])
			artifact := object(location["artifactLocation"])
			uri := artifact["uri"]
			if uri == nil && artifact["index"] != nil {
				listed := items(run["artifacts"])
				artifactIndex := integer(artifact["index"])
				if artifactIndex < 0 {
					artifactIndex += len(listed)
				}
				if artifactIndex >= 0 && artifactIndex < len(listed) {
					uri = object(object(listed[artifactIndex])["location"])["uri"]
				}
			}
			if uri == nil {
				return nil, fmt.Errorf("SARIF finding has no resolvable artifact URI")
			}
			path, err := relativeSourcePath(str(uri), sourceRoot)
			if err != nil {
				return nil, err
			}
			region := pickDefault(location, "region", record{})
			message := str(object(row["message"])["text"])
			identity := keyText([]any{rule, path, region, message})
			if seen[identity] {
				continue
			}
			seen[identity] = true
			var value any
			if pattern == nil {
				value = parameterCount(message)
			} else if matched := pattern.FindStringSubmatch(message); matched != nil {
				value, _ = strconv.Atoi(matched[1])
			}
			result = append(result, record{"rule": rule, "file": path, "region": region, "declaration": message,
				"value": value, "suppressed": truthy(row["suppressions"]), "record": fmt.Sprintf("complexity:runs/%d/results/%d", runIndex, index)})
		}
	}
	return result, nil
}

var signatureOpening = regexp.MustCompile("(?:`[^`]+`|[^(`])*\\(")

func parameterCount(message string) any {
	ending := strings.LastIndex(message, ") has too many parameters.")
	if ending < 0 || (!strings.HasPrefix(message, "The function ") && !strings.HasPrefix(message, "The constructor(")) {
		return nil
	}
	signature := message[:ending]
	opening := signatureOpening.FindStringIndex(signature)
	if opening == nil {
		return nil
	}
	text := signature[opening[1]:]
	var stack []byte
	count, start := 0, 0
	typed, defaultValue := false, false
	for index := 0; index < len(text); {
		char := text[index]
		suffix := text[index:]
		switch {
		case strings.HasPrefix(suffix, "//"):
			end := strings.IndexByte(suffix, '\n')
			if end < 0 {
				index = len(text)
			} else {
				index += end
			}
			continue
		case strings.HasPrefix(suffix, "/*"):
			depth := 1
			index += 2
			for index < len(text) && depth > 0 {
				if strings.HasPrefix(text[index:], "/*") {
					depth++
					index += 2
				} else if strings.HasPrefix(text[index:], "*/") {
					depth--
					index += 2
				} else {
					index++
				}
			}
			if depth > 0 {
				return nil
			}
			continue
		case char == '"' || char == '\'' || char == '`':
			quote := string(char)
			if strings.HasPrefix(suffix, `"""`) {
				quote = `"""`
			}
			index += len(quote)
			for index < len(text) && !strings.HasPrefix(text[index:], quote) {
				if char == '"' && strings.HasPrefix(text[index:], "${") {
					return nil
				}
				if text[index] == '\\' && char != '`' {
					index++
				}
				index++
			}
			if index >= len(text) {
				return nil
			}
			index += len(quote)
			continue
		}
		switch {
		case char == '(' || char == '[' || char == '{':
			stack = append(stack, map[byte]byte{'(': ')', '[': ']', '{': '}'}[char])
		case char == ')' || char == ']' || char == '}' || (char == '>' && !defaultValue && (index == 0 || text[index-1] != '-')):
			if len(stack) == 0 || stack[len(stack)-1] != char {
				return nil
			}
			stack = stack[:len(stack)-1]
		case char == '<':
			if !defaultValue {
				stack = append(stack, '>')
			} else if len(stack) == 0 {
				return nil
			}
		case len(stack) == 0:
			switch char {
			case ':':
				typed = true
			case '=':
				defaultValue = true
			case ',':
				if !typed || strings.TrimSpace(text[start:index]) == "" {
					return nil
				}
				count++
				start, typed, defaultValue = index+1, false, false
			}
		}
		index++
	}
	if len(stack) > 0 {
		return nil
	}
	if strings.TrimSpace(text[start:]) != "" {
		if !typed {
			return nil
		}
		return count + 1
	}
	return count
}

var sizeFields = []string{"Lines", "Code", "Comment", "Blank"}

func parseSizes(text, sourceRoot string) (map[string]record, error) {
	parsed, err := parseJSONValue([]byte(text))
	if err != nil {
		return nil, err
	}
	languages := items(parsed)
	if languages == nil {
		return nil, fmt.Errorf("scc report must be an array")
	}
	result := map[string]record{}
	for _, language := range languages {
		for _, value := range items(object(language)["Files"]) {
			row := object(value)
			if _, found := row["Location"]; !found {
				return nil, fmt.Errorf("'Location'")
			}
			path, err := relativeSourcePath(str(row["Location"]), sourceRoot)
			if err != nil {
				return nil, err
			}
			if result[path] != nil {
				return nil, fmt.Errorf("Duplicate scc file: %s", path)
			}
			counts := record{}
			for _, field := range sizeFields {
				value, found := row[field]
				if !found {
					return nil, fmt.Errorf("%s", quoted(field))
				}
				count, err := reportInt(value)
				if err != nil {
					return nil, err
				}
				if count < 0 {
					return nil, fmt.Errorf("Negative scc count for %s", path)
				}
				counts[field] = count
			}
			result[path] = counts
		}
	}
	return result, nil
}

func reportInt(value any) (int, error) {
	if number, ok := decimal(value); ok {
		return int(number), nil
	}
	if text, ok := value.(string); ok {
		if parsed, err := strconv.Atoi(strings.TrimSpace(text)); err == nil {
			return parsed, nil
		}
		return 0, fmt.Errorf("invalid literal for int() with base 10: %s", quoted(text))
	}
	return 0, fmt.Errorf("expected numeric report counter")
}

func integerJSON(value any) bool {
	number, ok := value.(json.Number)
	return ok && !strings.ContainsAny(string(number), ".eE")
}

func coverageRatio(covered, total int) (record, error) {
	if covered < 0 || covered > total {
		return nil, fmt.Errorf("Invalid coverage counters: %d/%d", covered, total)
	}
	value := record{"covered": covered, "total": total, "value": nil, "status": "not_applicable"}
	if total > 0 {
		value["value"], value["status"] = float64(covered)/float64(total), "measured"
	}
	return value, nil
}

type jacocoCounter struct {
	Type    string `xml:"type,attr"`
	Covered string `xml:"covered,attr"`
	Missed  string `xml:"missed,attr"`
}
type jacocoLine struct {
	Number  string `xml:"nr,attr"`
	Missed  string `xml:"mi,attr"`
	Covered string `xml:"ci,attr"`
}
type jacocoSource struct {
	Name     string          `xml:"name,attr"`
	Lines    []jacocoLine    `xml:"line"`
	Counters []jacocoCounter `xml:"counter"`
}
type jacocoMethod struct {
	Name     string          `xml:"name,attr"`
	Desc     string          `xml:"desc,attr"`
	Line     string          `xml:"line,attr"`
	Counters []jacocoCounter `xml:"counter"`
}
type jacocoClass struct {
	Name    string         `xml:"name,attr"`
	Source  string         `xml:"sourcefilename,attr"`
	Methods []jacocoMethod `xml:"method"`
}
type jacocoPackage struct {
	Name    string         `xml:"name,attr"`
	Sources []jacocoSource `xml:"sourcefile"`
	Classes []jacocoClass  `xml:"class"`
}
type jacocoReport struct {
	Packages []jacocoPackage `xml:"package"`
	Groups   []jacocoReport  `xml:"group"`
}

func (report jacocoReport) allPackages() []jacocoPackage {
	packages := report.Packages
	for _, group := range report.Groups {
		packages = append(packages, group.allPackages()...)
	}
	return packages
}

func coverageCounter(counters []jacocoCounter, kind string) (record, error) {
	var matched *jacocoCounter
	for index := range counters {
		if counters[index].Type == kind {
			matched = &counters[index]
		}
	}
	if matched == nil {
		return record{"covered": nil, "total": nil, "value": nil, "status": "unknown"}, nil
	}
	covered, err := reportInt(matched.Covered)
	if err != nil {
		return nil, err
	}
	missed, err := reportInt(matched.Missed)
	if err != nil {
		return nil, err
	}
	return coverageRatio(covered, covered+missed)
}

func parseCoverage(text, format, sourceRoot string, sources map[string]record) (map[string]record, []record, error) {
	rows, unmapped := map[string]record{}, []record{}
	kinds := []string{"line", "branch"}
	if format == "coverage-csv" {
		_, values, err := csvRows(text)
		if err != nil {
			return nil, nil, err
		}
		for _, row := range values {
			if _, found := row["file"]; !found {
				return nil, nil, fmt.Errorf("'file'")
			}
			path, err := relativeSourcePath(row["file"], sourceRoot)
			if err != nil {
				return nil, nil, err
			}
			if rows[path] != nil {
				return nil, nil, fmt.Errorf("Duplicate coverage for %s; supply one merged report", path)
			}
			counters := record{}
			for _, kind := range kinds {
				covered, err := reportInt(row[kind+"_covered"])
				if err != nil {
					return nil, nil, err
				}
				total, err := reportInt(row[kind+"_total"])
				if err != nil {
					return nil, nil, err
				}
				counters[kind], err = coverageRatio(covered, total)
				if err != nil {
					return nil, nil, err
				}
			}
			rows[path] = counters
		}
		return rows, unmapped, nil
	}
	var report jacocoReport
	if err := xml.Unmarshal([]byte(text), &report); err != nil {
		return nil, nil, err
	}
	lookup := map[[2]string][]string{}
	for _, file := range keys(sources) {
		key := [2]string{strings.ReplaceAll(str(sources[file]["package"]), ".", "/"), path.Base(file)}
		lookup[key] = append(lookup[key], file)
	}
	for _, pkg := range report.allPackages() {
		for _, source := range pkg.Sources {
			matches := lookup[[2]string{pkg.Name, source.Name}]
			if len(matches) != 1 {
				unmapped = append(unmapped, record{"package": pkg.Name, "sourcefile": source.Name, "matches": append([]string{}, matches...)})
				continue
			}
			file := matches[0]
			if rows[file] != nil {
				return nil, nil, fmt.Errorf("Duplicate coverage for %s; merge execution data before XML export", file)
			}
			counters := record{}
			for _, kind := range kinds {
				counter, err := coverageCounter(source.Counters, strings.ToUpper(kind))
				if err != nil {
					return nil, nil, err
				}
				counters[kind] = counter
			}
			rows[file] = counters
		}
	}
	return rows, unmapped, nil
}

var historyHeader = regexp.MustCompile(`^--([0-9a-f]+)--(\d{4}-\d{2}-\d{2})--(.*)$`)

func isotime(date string) (time.Time, error) {
	for _, layout := range []string{"2006-01-02", "20060102"} {
		if result, err := time.Parse(layout, date); err == nil && result.Year() > 0 {
			return result, nil
		}
	}
	return time.Time{}, fmt.Errorf("Invalid isoformat string: %s", quoted(date))
}

func parseHistory(text string) ([]record, error) {
	result := []record{}
	seen := map[string]bool{}
	if strings.HasPrefix(strings.TrimSpace(text), "{") {
		parsed, err := parseJSONValue([]byte(text))
		if err != nil {
			return nil, err
		}
		history := object(parsed)
		if history["format"] != "git-history" || history["first_parent"] != true || history["renames"] != true {
			return nil, fmt.Errorf("History requires first-parent collection with rename tracking")
		}
		start, err := isotime(str(history["since"]))
		if err != nil {
			return nil, err
		}
		end, err := isotime(str(history["until"]))
		if err != nil {
			return nil, err
		}
		if start.After(end) {
			return nil, fmt.Errorf("Invalid history window")
		}
		for _, item := range items(history["commits"]) {
			commit := object(item)
			revision := str(commit["revision"])
			if seen[revision] {
				return nil, fmt.Errorf("History contains duplicate revisions")
			}
			seen[revision] = true
			if _, err := isotime(str(commit["date"])); err != nil {
				return nil, err
			}
			changes := object(commit["changes"])
			size := integer(commit["production_files"])
			if !integerJSON(commit["production_files"]) || size < 0 || size > len(changes) {
				return nil, fmt.Errorf("Invalid production changeset size")
			}
			for file, item := range changes {
				if strings.HasPrefix(file, "/") || strings.Contains(file, `\`) || windowsDrive.MatchString(file) || contains(strings.Split(file, "/"), "..") {
					return nil, fmt.Errorf("History path must be repository-relative")
				}
				change := object(item)
				binary, valid := change["binary"].(bool)
				for _, field := range []string{"added", "deleted"} {
					count := change[field]
					valid = valid && ((binary && count == nil) || (!binary && integerJSON(count) && integer(count) >= 0))
				}
				if !valid {
					return nil, fmt.Errorf("Invalid history numstat")
				}
			}
			result = append(result, commit)
		}
		return result, nil
	}
	var current record
	for index, line := range strings.Split(strings.ReplaceAll(text, "\r\n", "\n"), "\n") {
		if resultHeader := historyHeader.FindStringSubmatch(line); len(resultHeader) > 0 {
			revision := resultHeader[1]
			if _, err := isotime(str(resultHeader[2])); err != nil {
				return nil, err
			}
			if seen[revision] {
				return nil, fmt.Errorf("git.log contains duplicate revisions")
			}
			seen[revision] = true
			current = record{"revision": revision, "date": resultHeader[2], "author": resultHeader[3], "changes": record{}}
			result = append(result, current)
		} else if strings.TrimSpace(line) != "" {
			parts := strings.Split(line, "\t")
			if current == nil || len(parts) != 3 {
				return nil, fmt.Errorf("git.log line %d: expected numstat or --revision--date--author", index+1)
			}
			file := parts[2]
			if strings.HasPrefix(file, `"`) || strings.Contains(file, " => ") {
				return nil, fmt.Errorf("git.log line %d: export with -c core.quotePath=false --no-renames", index+1)
			}
			file = strings.ReplaceAll(file, `\`, "/")
			if strings.HasPrefix(file, "/") || windowsDrive.MatchString(file) || path.Clean(file) == "." || contains(strings.Split(file, "/"), "..") {
				return nil, fmt.Errorf("git.log line %d: expected a repository-relative file path", index+1)
			}
			file = path.Clean(file)
			changes := object(current["changes"])
			if _, exists := changes[file]; exists {
				return nil, fmt.Errorf("git.log line %d: duplicate path in commit", index+1)
			}
			binary := parts[0] == "-" || parts[1] == "-"
			change := record{"added": nil, "deleted": nil, "binary": binary}
			if !binary {
				added, err := reportInt(parts[0])
				if err != nil {
					return nil, err
				}
				deleted, err := reportInt(parts[1])
				if err != nil {
					return nil, err
				}
				if added < 0 || deleted < 0 {
					return nil, fmt.Errorf("git.log line %d: negative numstat", index+1)
				}
				change["added"], change["deleted"] = added, deleted
			}
			changes[file] = change
		}
	}
	return result, nil
}
