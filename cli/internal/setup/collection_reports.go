package setup

import (
	"bytes"
	"encoding/csv"
	"encoding/xml"
	"errors"
	"fmt"
	"io"
	"net/url"
	"path"
	"path/filepath"
	"regexp"
	"slices"
	"strconv"
	"strings"
	"time"
)

func validateReports(project string, scope, policy, artifacts object, raw map[string][]byte) error {
	sources, err := collectionSources(project, scope)
	if err != nil {
		return err
	}
	mappings, err := classMappings(project, scope, sources)
	if err != nil {
		return err
	}
	root := func(name string) string {
		value := valueOr(asObject(artifacts[name]), "source_root", ".")
		return filepath.Join(project, filepath.FromSlash(asString(value)))
	}
	if err := validateSarif(raw["complexity"], root("complexity")); err != nil {
		return err
	}
	kotlin, err := validateKotlin(raw["kotlin"], sources)
	if err != nil {
		return err
	}
	if err := validateDependencies(raw["dependencies"], asString(asObject(artifacts["dependencies"])["format"]), scope, mappings); err != nil {
		return err
	}
	if err := validateCoverage(raw["coverage"], kotlin, mappings); err != nil {
		return err
	}
	parameters := asObject(asObject(policy["measurements"])["quality_indicators"])
	if err := validateHistory(raw["history"], int(decimal(parameters["history_days"]))); err != nil {
		return err
	}
	unassigned := []string{}
	modules := asObject(scope["modules"])
	for _, file := range keys(kotlin) {
		module, err := moduleFor(kotlin[file].packageName, modules)
		if err != nil {
			return err
		}
		if module == "" {
			unassigned = append(unassigned, file)
		}
	}
	if len(unassigned) > 0 {
		return fmt.Errorf("Assign production packages to architectural modules before auditing: %s", joinComma(unassigned[:min(10, len(unassigned))]))
	}
	return validateSizes(raw["sizes"], root("sizes"), scope, sources)
}

func reportRelative(value, root string) (string, error) {
	value = unescapePath(value)
	if strings.HasPrefix(value, "file:") {
		if parsed, err := url.Parse(value); err == nil {
			value = parsed.Path
			if parsed.Host != "" {
				value = "//" + parsed.Host + value
			}
			if len(value) > 1 && value[0] == '/' && windowsDrive.MatchString(value[1:]) {
				value = value[1:]
			}
		}
	}
	value = strings.ReplaceAll(value, "\\", "/")
	root = strings.TrimRight(filepath.ToSlash(root), "/")
	if value == root {
		return "", errors.New("Expected a source file, got the repository root")
	}
	value = strings.TrimPrefix(value, root+"/")
	if strings.HasPrefix(value, "/") || windowsDrive.MatchString(value) || slices.Contains(strings.Split(value, "/"), "..") {
		return "", fmt.Errorf("Unmapped source path %s; supply project-relative report paths or the current checkout's paths", pythonString(value))
	}
	return path.Clean(value), nil
}

func validateSarif(raw []byte, root string) error {
	value, err := decodeJSON(raw, nil)
	if err != nil {
		return err
	}
	runs := array(asObject(value)["runs"])
	if runs == nil {
		return errors.New("detekt SARIF requires a runs array")
	}
	known := []string{"CyclomaticComplexMethod", "CognitiveComplexMethod", "LongMethod", "TooManyFunctions", "LongParameterList"}
	for _, rawRun := range runs {
		run := asObject(rawRun)
		if run == nil {
			return errors.New("Expected an object in detekt SARIF runs")
		}
		findings, err := reportRows(run, "results", false)
		if err != nil {
			return err
		}
		for _, rawFinding := range findings {
			finding := asObject(rawFinding)
			if finding == nil {
				return errors.New("Expected an object in detekt SARIF results")
			}
			rule := asString(finding["ruleId"])
			rule = rule[strings.LastIndex(rule, ".")+1:]
			if !slices.Contains(known, rule) {
				continue
			}
			var artifact object
			if locations := array(finding["locations"]); len(locations) > 0 {
				location := asObject(asObject(locations[0])["physicalLocation"])
				artifact = asObject(location["artifactLocation"])
			}
			uri := asString(artifact["uri"])
			if uri == "" {
				items := array(run["artifacts"])
				if index, ok := jsonInteger(artifact["index"]); ok && index >= 0 && index < len(items) {
					uri = asString(asObject(asObject(items[index])["location"])["uri"])
				}
			}
			if uri == "" {
				return errors.New("SARIF finding has no resolvable artifact URI")
			}
			if _, err := reportRelative(uri, root); err != nil {
				return err
			}
		}
	}
	return nil
}

var detektVersion = regexp.MustCompile(`^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*))?(?:\+[0-9A-Za-z.-]+)?$`)

func validateKotlin(raw []byte, sources map[string]sourceFile) (map[string]sourceFile, error) {
	value, err := decodeJSON(raw, nil)
	if err != nil {
		return nil, err
	}
	report := asObject(value)
	version, hasVersion := report["tool_version"].(string)
	schema, _ := jsonInteger(report["version"])
	if report["format"] != "kotlin-measurements" || schema != 2 || report["complete"] != true ||
		report["measurement_profile"] != "kotlin-tokens-functions-1" || !hasVersion {
		return nil, errors.New("Kotlin measurements are missing or incomplete; check the project collection task and its Kotlin report")
	}
	if err := checkAdapterVersion(version); err != nil {
		return nil, err
	}
	expected := map[string]sourceFile{}
	for file, source := range sources {
		if source.language == ".kt" {
			expected[file] = source
		}
	}
	rows := map[string]object{}
	files, err := reportRows(report, "files", false)
	if err != nil {
		return nil, err
	}
	for _, value := range files {
		row := asObject(value)
		if _, exists := row["file"]; !exists {
			return nil, errors.New("'file'")
		}
		file := asString(row["file"])
		if _, ok := expected[file]; !ok || rows[file] != nil {
			return nil, errors.New("Kotlin measurements must cover each production Kotlin file exactly once")
		}
		rows[file] = row
	}
	if len(rows) != len(expected) {
		return nil, errors.New("Kotlin measurements must cover each production Kotlin file exactly once")
	}
	for _, file := range keys(rows) {
		row := rows[file]
		if _, exists := row["package"]; !exists {
			return nil, errors.New("'package'")
		}
		if row["package"] != expected[file].packageName {
			return nil, fmt.Errorf("Kotlin package does not match the source inventory: %s", file)
		}
		tokens, err := reportRows(row, "tokens", true)
		if err != nil {
			return nil, err
		}
		end := 0
		for _, value := range tokens {
			token := asObject(value)
			start, finish, valid := jsonRange(token)
			if !valid || start < end {
				return nil, fmt.Errorf("Invalid token positions: %s", file)
			}
			if asString(token["text"]) == "" || asString(token["type"]) == "" {
				return nil, fmt.Errorf("Empty code token: %s", file)
			}
			end = finish
		}
		functions, err := reportRows(row, "functions", true)
		if err != nil {
			return nil, err
		}
		for _, value := range functions {
			function := asObject(value)
			complexity, valid := jsonInteger(function["cognitive_complexity"])
			if !valid || complexity < 0 {
				return nil, fmt.Errorf("Missing cognitive complexity: %s", file)
			}
			_, _, valid = jsonRange(function)
			if _, boolean := function["nested"].(bool); !valid || !boolean {
				return nil, fmt.Errorf("Invalid function range: %s", file)
			}
		}
		containers, err := reportRows(row, "containers", true)
		if err != nil {
			return nil, err
		}
		for _, value := range containers {
			container := asObject(value)
			_, _, valid := jsonRange(container)
			if !valid || !slices.Contains([]string{"function", "class"}, asString(container["kind"])) {
				return nil, fmt.Errorf("Invalid size container: %s", file)
			}
		}
	}
	return expected, nil
}

func reportRows(value object, field string, required bool) ([]any, error) {
	rows, exists := value[field]
	if !exists {
		if required {
			return nil, errors.New(pythonString(field))
		}
		return nil, nil
	}
	if items, ok := rows.([]any); ok {
		return items, nil
	}
	if rows == nil {
		return nil, errors.New("'NoneType' object is not iterable")
	}
	return nil, fmt.Errorf("Expected an array at %s", field)
}

func jsonRange(value object) (int, int, bool) {
	start, ok := jsonInteger(value["start"])
	end, hasEnd := jsonInteger(value["end"])
	return start, end, ok && hasEnd && start >= 0 && end > start
}

func checkAdapterVersion(version string) error {
	match := detektVersion.FindStringSubmatch(version)
	if match == nil {
		return fmt.Errorf("Unrecognized detekt version: %s", pythonString(version))
	}
	major, _ := strconv.Atoi(match[1])
	minimum := map[int]string{1: "1.23.8", 2: "2.0.0-alpha.6"}[major]
	if minimum == "" {
		return fmt.Errorf("Unsupported detekt major %d; available measurement adapters: 1, 2", major)
	}
	floor := detektVersion.FindStringSubmatch(minimum)
	cmp := compareVersions(strings.Join(match[1:4], "."), strings.Join(floor[1:4], "."))
	if cmp == 0 {
		cmp = comparePrerelease(match[4], floor[4])
	}
	if cmp < 0 {
		return fmt.Errorf("detekt %s is below the adapter minimum %s", version, minimum)
	}
	return nil
}

func comparePrerelease(left, right string) int {
	if left == "" || right == "" {
		return strings.Compare(right, left)
	}
	return slices.CompareFunc(strings.Split(left, "."), strings.Split(right, "."), func(a, b string) int {
		n, errA := strconv.Atoi(a)
		m, errB := strconv.Atoi(b)
		switch {
		case errA == nil && errB == nil:
			switch {
			case n < m:
				return -1
			case n > m:
				return 1
			default:
				return 0
			}
		case errA == nil:
			return -1
		case errB == nil:
			return 1
		default:
			return strings.Compare(a, b)
		}
	})
}

var jdepsEdge = regexp.MustCompile(`(?m)^\s+(\S+)\s+->\s+(\S+)`)

func validateDependencies(raw []byte, format string, scope object, mappings map[string]string) error {
	var pairs [][]string
	if format == "class-csv" {
		reader := csv.NewReader(bytes.NewReader(raw))
		header, _ := reader.Read()
		from, to := slices.Index(header, "from"), slices.Index(header, "to")
		if from < 0 || to < 0 {
			return errors.New("Dependencies CSV requires from,to headers")
		}
		for {
			row, err := reader.Read()
			if errors.Is(err, io.EOF) {
				break
			}
			if err != nil {
				return err
			}
			pairs = append(pairs, []string{row[from], row[to]})
		}
	} else {
		for _, match := range jdepsEdge.FindAllStringSubmatch(string(raw), -1) {
			pairs = append(pairs, match[1:3])
		}
	}
	missing := map[string]bool{}
	prefixes, excluded := stringsIn(scope["package_prefixes"]), stringsIn(scope["exclude_classes"])
	for _, pair := range pairs {
		if pair[0] != pair[1] && admittedClass(pair[0], prefixes, excluded) && admittedClass(pair[1], prefixes, excluded) {
			for _, class := range pair {
				if mappings[class] == "" {
					missing[class] = true
				}
			}
		}
	}
	if len(missing) != 0 {
		names := keys(missing)
		return fmt.Errorf("jdeps classes have no source mapping: %s", joinComma(names[:min(10, len(names))]))
	}
	return nil
}

func moduleFor(pkg string, modules object) (string, error) {
	size := -1
	owners := []string{}
	for _, module := range keys(modules) {
		for _, prefix := range stringsIn(modules[module]) {
			if pkg != prefix && !strings.HasPrefix(pkg, prefix+".") {
				continue
			}
			switch {
			case len(prefix) > size:
				size, owners = len(prefix), []string{module}
			case len(prefix) == size && !slices.Contains(owners, module):
				owners = append(owners, module)
			}
		}
	}
	if len(owners) > 1 {
		return "", fmt.Errorf("Ambiguous module ownership for %s: %s", pkg, pythonList(owners))
	}
	if len(owners) == 0 {
		return "", nil
	}
	return owners[0], nil
}

func validateSizes(raw []byte, root string, scope object, sources map[string]sourceFile) error {
	value, err := decodeJSON(raw, nil)
	if err != nil {
		return err
	}
	excluded := append(stringsIn(scope["exclude_paths"]), stringsIn(scope["statistics_exclude_paths"])...)
	excluded = append(excluded, "memory/tech-debt/**")
	seen, measured := map[string]bool{}, map[string]bool{}
	for _, language := range array(value) {
		files, err := reportRows(asObject(language), "Files", false)
		if err != nil {
			return err
		}
		for _, value := range files {
			row := asObject(value)
			if _, exists := row["Location"]; !exists {
				return errors.New("'Location'")
			}
			file, err := reportRelative(asString(row["Location"]), root)
			if err != nil {
				return err
			}
			if seen[file] {
				return fmt.Errorf("Duplicate scc file: %s", file)
			}
			seen[file] = true
			if matchesPatterns(file, excluded) {
				continue
			}
			if _, exists := asObject(language)["Name"]; !exists {
				return errors.New("'Name'")
			}
			for _, key := range []string{"Lines", "Code", "Comment", "Blank"} {
				if value, ok := jsonInteger(row[key]); !ok || value < 0 {
					return fmt.Errorf("Invalid scc counters: %s", file)
				}
			}
			if _, err := moduleFor(sources[file].packageName, asObject(scope["modules"])); err != nil {
				return err
			}
			measured[file] = true
		}
	}
	missing := []string{}
	for _, file := range keys(sources) {
		if !measured[file] {
			missing = append(missing, file)
		}
	}
	if len(missing) > 0 {
		return fmt.Errorf("scc omits production files: %s", joinComma(missing[:min(10, len(missing))]))
	}
	return nil
}

func validateHistory(raw []byte, days int) error {
	value, err := decodeJSON(raw, nil)
	if err != nil {
		return err
	}
	history := asObject(value)
	if history["format"] != "git-history" || history["first_parent"] != true || history["renames"] != true {
		return errors.New("Full audit requires first-parent history with rename tracking")
	}
	asOf, _ := time.Parse("2006-01-02", time.Now().UTC().Format("2006-01-02"))
	date := func(value any) (time.Time, error) {
		text := asString(value)
		result, err := time.Parse("2006-01-02", text)
		if err != nil {
			return time.Time{}, fmt.Errorf("Invalid isoformat string: %s", pythonString(text))
		}
		return result, nil
	}
	for _, field := range []string{"since", "until"} {
		if _, exists := history[field]; !exists {
			return errors.New(pythonString(field))
		}
	}
	since, err := date(history["since"])
	if err != nil {
		return err
	}
	until, err := date(history["until"])
	if err != nil {
		return err
	}
	if since.After(asOf.AddDate(0, 0, -days)) || until.Before(asOf) {
		return errors.New("History does not cover the configured observation window; collect the required history")
	}
	revisions := map[string]bool{}
	commits, err := reportRows(history, "commits", true)
	if err != nil {
		return err
	}
	for _, value := range commits {
		commit := asObject(value)
		for _, field := range []string{"revision", "date", "production_files", "changes"} {
			if _, exists := commit[field]; !exists {
				return errors.New(pythonString(field))
			}
		}
		id := asString(commit["revision"])
		if revisions[id] {
			return errors.New("History contains duplicate revisions")
		}
		revisions[id] = true
		if _, err := date(commit["date"]); err != nil {
			return err
		}
		changes := asObject(commit["changes"])
		if changes == nil {
			return errors.New("Expected a history changes object")
		}
		if n, valid := jsonInteger(commit["production_files"]); !valid || n < 0 || n > len(changes) {
			return errors.New("Invalid production changeset size")
		}
		for name, value := range changes {
			if strings.Contains(name, "\\") || strings.HasPrefix(name, "/") || windowsDrive.MatchString(name) ||
				slices.Contains(strings.Split(name, "/"), "..") {
				return errors.New("History path must be repository-relative")
			}
			change := asObject(value)
			for _, field := range []string{"binary", "added", "deleted"} {
				if _, exists := change[field]; !exists {
					return errors.New(pythonString(field))
				}
			}
			binary, ok := change["binary"].(bool)
			if !ok {
				return errors.New("Invalid history numstat")
			}
			for _, field := range []string{"added", "deleted"} {
				number, valid := jsonInteger(change[field])
				if (binary && change[field] != nil) || (!binary && (!valid || number < 0)) {
					return errors.New("Invalid history numstat")
				}
			}
		}
	}
	return nil
}

type jacocoCounter struct {
	Type    string `xml:"type,attr"`
	Covered int    `xml:"covered,attr"`
	Missed  int    `xml:"missed,attr"`
}

type jacocoPackage struct {
	Name    string `xml:"name,attr"`
	Sources []struct {
		Name  string `xml:"name,attr"`
		Lines []struct {
			Number  int `xml:"nr,attr"`
			Covered int `xml:"ci,attr"`
			Missed  int `xml:"mi,attr"`
		} `xml:"line"`
		Counters []jacocoCounter `xml:"counter"`
	} `xml:"sourcefile"`
	Classes []struct {
		Name    string `xml:"name,attr"`
		Methods []struct {
			Name     string          `xml:"name,attr"`
			Desc     string          `xml:"desc,attr"`
			Counters []jacocoCounter `xml:"counter"`
		} `xml:"method"`
	} `xml:"class"`
}

func validateCoverage(raw []byte, sources map[string]sourceFile, mappings map[string]string) error {
	decoder := xml.NewDecoder(bytes.NewReader(raw))
	lookup := map[[2]string][]string{}
	for file, source := range sources {
		key := [2]string{strings.ReplaceAll(source.packageName, ".", "/"), path.Base(file)}
		lookup[key] = append(lookup[key], file)
	}
	depth, root := 0, false
	lines, classes, methods := map[string]map[int]bool{}, map[string]bool{}, map[[3]string]bool{}
	for {
		token, err := decoder.Token()
		if errors.Is(err, io.EOF) {
			if root && depth == 0 {
				return nil
			}
			return errors.New("JaCoCo report is missing its document element")
		}
		if err != nil {
			return err
		}
		start, ok := token.(xml.StartElement)
		if !ok {
			switch token := token.(type) {
			case xml.EndElement:
				depth--
			case xml.CharData:
				if depth == 0 && strings.TrimSpace(string(token)) != "" {
					return errors.New("Unexpected text outside the JaCoCo report")
				}
			}
			continue
		}
		if depth == 0 && root {
			return errors.New("Unexpected element after the JaCoCo report")
		}
		if !root {
			if start.Name.Local != "report" || start.Name.Space != "" {
				return errors.New("Coverage input must be a complete JaCoCo XML report")
			}
			root = true
		}
		if start.Name.Local != "package" {
			depth++
			continue
		}
		var pkg jacocoPackage
		if err := decoder.DecodeElement(&pkg, &start); err != nil {
			return err
		}
		for _, source := range pkg.Sources {
			paths := lookup[[2]string{pkg.Name, source.Name}]
			if len(paths) > 1 {
				return errors.New("Ambiguous JaCoCo source file; provide a single selected source-set report")
			}
			if len(paths) == 0 {
				continue
			}
			file := paths[0]
			if lines[file] == nil {
				lines[file] = map[int]bool{}
			}
			covered := 0
			for _, line := range source.Lines {
				if lines[file][line.Number] {
					return errors.New("Duplicate JaCoCo source line; merge execution data before XML export")
				}
				lines[file][line.Number] = true
				if line.Number < 1 || line.Covered < 0 || line.Missed < 0 || line.Covered+line.Missed == 0 {
					return errors.New("Invalid JaCoCo executable source line")
				}
				if line.Covered > 0 {
					covered++
				}
			}
			count := 0
			var lineCounter jacocoCounter
			for _, counter := range source.Counters {
				if counter.Type == "LINE" {
					lineCounter, count = counter, count+1
				}
			}
			if count > 1 {
				return fmt.Errorf("Duplicate JaCoCo sourcefile LINE counter for %s", file)
			}
			missed := len(source.Lines) - covered
			if count == 1 && (lineCounter.Covered != covered || lineCounter.Missed != missed) {
				return fmt.Errorf("JaCoCo LINE counter mismatch for %s: declared covered/missed (%d, %d), line records give (%d, %d)",
					file, lineCounter.Covered, lineCounter.Missed, covered, missed)
			}
		}
		for _, class := range pkg.Classes {
			name := strings.ReplaceAll(class.Name, "/", ".")
			if _, ok := sources[mappings[name]]; !ok {
				continue
			}
			if classes[name] {
				return errors.New("Duplicate JaCoCo class; merge execution data before XML export")
			}
			classes[name] = true
			for _, method := range class.Methods {
				counters := map[string]int{}
				for _, counter := range method.Counters {
					if _, ok := counters[counter.Type]; ok {
						return errors.New("Duplicate JaCoCo method counter")
					}
					if counter.Covered < 0 || counter.Missed < 0 {
						return errors.New("Negative JaCoCo method counter")
					}
					counters[counter.Type] = counter.Covered + counter.Missed
				}
				instructions, hasInstructions := counters["INSTRUCTION"]
				complexity, hasComplexity := counters["COMPLEXITY"]
				if !hasInstructions || !hasComplexity {
					return fmt.Errorf("Incomplete JaCoCo method counters: %s.%s", name, method.Name)
				}
				if instructions == 0 || complexity == 0 {
					return errors.New("JaCoCo executable method has zero instructions or complexity")
				}
				key := [3]string{name, method.Name, method.Desc}
				if methods[key] {
					return errors.New("Duplicate JaCoCo method identity")
				}
				methods[key] = true
			}
		}
	}
}
