package architect

import (
	"fmt"
	"math"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"
)

func prepareQuality(config record, sources map[string]record, mappings map[string]string, raw map[string]string, artifacts, policy record, root string, analysis *measurementAnalysis) (record, error) {
	var kotlin record
	if parsed, err := parseJSONValue([]byte(raw["kotlin"])); err == nil {
		kotlin = object(parsed)
	}
	files, err := qualifiedKotlin(kotlin, sources)
	if err != nil {
		return nil, err
	}
	missing := map[string]bool{}
	fileEdges := edgeWeights{}
	for pair := range analysis.classEdges {
		for _, name := range []string{pair.from, pair.to} {
			if _, known := mappings[name]; !known {
				missing[name] = true
			}
		}
		from, to := mappings[pair.from], mappings[pair.to]
		if from != to {
			fileEdges[edge{from, to}] = 1
		}
	}
	if len(missing) > 0 {
		return nil, fmt.Errorf("jdeps classes have no source mapping: %s", strings.Join(keys(missing)[:min(10, len(missing))], ", "))
	}
	coverage := object(artifacts["coverage"])
	if coverage["format"] != "jacoco" || coverage["complete"] != true || coverage["test_result"] != "passed" {
		return nil, fmt.Errorf("Coverage requires complete JaCoCo XML and a passed selected test run; configure coverage first")
	}
	kotlinSources := map[string]record{}
	for file := range files {
		kotlinSources[file] = sources[file]
	}
	methods, lines, err := coverageMethods(raw["coverage"], kotlinSources, mappings)
	if err != nil {
		return nil, err
	}
	historyData, err := parseJSONValue([]byte(raw["history"]))
	if err != nil {
		return nil, err
	}
	history := object(historyData)
	if history["format"] != "git-history" || !truthy(history["first_parent"]) || !truthy(history["renames"]) {
		return nil, fmt.Errorf("Full audit requires first-parent history with rename tracking")
	}
	parameters := object(object(policy["measurements"])["quality_indicators"])
	asOf := todayUTC()
	cutoff := asOf.AddDate(0, 0, -integer(parameters["history_days"]))
	since, err := isotime(str(history["since"]))
	if err != nil {
		return nil, err
	}
	until, err := isotime(str(history["until"]))
	if err != nil {
		return nil, err
	}
	if since.After(cutoff) || until.Before(asOf) {
		return nil, fmt.Errorf("History does not cover the configured observation window; collect the required history")
	}
	modules := object(config["modules"])
	project, moduleResults, err := qualityIndicators(files, fileEdges, modules, methods, lines, analysis.commits, parameters, asOf)
	if err != nil {
		return nil, err
	}
	stats, moduleStats, exclusions, err := projectStatistics(raw["sizes"], config, sources, root, str(object(artifacts["sizes"])["source_root"]))
	if err != nil {
		return nil, err
	}
	project["statistics"] = stats
	for name, module := range moduleResults {
		object(module)["statistics"] = moduleStats[name]
	}
	incoming, outgoing := 0, 0
	for pair := range fileEdges {
		if files[pair.from] == nil && files[pair.to] != nil {
			incoming++
		}
		if files[pair.from] != nil && files[pair.to] == nil {
			outgoing++
		}
	}
	tools := record{}
	for name, value := range artifacts {
		metadata := object(value)
		entry := record{}
		for _, key := range []string{"tool", "version", "parser_version", "plugin_version", "command", "collected_at", "path"} {
			if value, found := metadata[key]; found {
				entry[key] = value
			}
		}
		tools[name] = entry
	}
	return record{"schema_version": 1, "collected_at": isoNow(), "project": project, "modules": moduleResults, "tools": tools,
		"profile": record{"name": "kotlin-jvm-jdeps-archdrh-re-1", "parameters": parameters,
			"dependencies": "jdeps class dependencies projected onto source files", "module_scope": "induced file graph; local clones; separate boundary exposure",
			"kotlin_metric_tool": kotlin["tool_version"]},
		"scope": record{"source_roots": config["source_roots"], "test_roots": pickDefault(config, "test_roots", []any{}), "modules": modules,
			"statistics_exclusions": exclusions, "exclude_paths": pickDefault(config, "exclude_paths", []any{}),
			"exclude_classes": pickDefault(config, "exclude_classes", []any{}), "class_directories": pickDefault(config, "class_directories", []any{}),
			"build": pickDefault(config, "scope", record{}), "incoming_non_kotlin_edges": incoming, "outgoing_non_kotlin_edges": outgoing,
			"kotlin_files": len(files), "other_production_files": len(sources) - len(files)},
		"limitations": []string{"jdeps reflects compiled dependencies; inline, reflection and DI can hide source/runtime relationships",
			"D uses the documented ArchDRH-Re implementation; real-project calibration is pending",
			"Module D/PC describe internal structure; cross-module edges are reported separately",
			"Module Q values are recomputed and must not be averaged into project Q",
			"Exact token clones preserve identifiers and literals; renamed clones may be missed"}}, nil
}

var detektVersion = regexp.MustCompile(`^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*))?(?:\+[0-9A-Za-z.-]+)?$`)

func compareVersion(left, right []string) int {
	for i := 1; i <= 3; i++ {
		a, _ := strconv.Atoi(left[i])
		b, _ := strconv.Atoi(right[i])
		if a != b {
			return a - b
		}
	}
	if left[4] == right[4] {
		return 0
	}
	if left[4] == "" {
		return 1
	}
	if right[4] == "" {
		return -1
	}
	a, b := strings.Split(left[4], "."), strings.Split(right[4], ".")
	for index := 0; index < min(len(a), len(b)); index++ {
		if a[index] == b[index] {
			continue
		}
		x, xErr := strconv.Atoi(a[index])
		y, yErr := strconv.Atoi(b[index])
		switch {
		case xErr == nil && yErr == nil:
			if x != y {
				return x - y
			}
		case xErr == nil:
			return -1
		case yErr == nil:
			return 1
		default:
			return strings.Compare(a[index], b[index])
		}
	}
	return len(a) - len(b)
}

func qualifiedKotlin(value record, sources map[string]record) (map[string]record, error) {
	metadata, err := assetObject("detekt-plugins.json")
	if err != nil {
		return nil, err
	}
	toolVersion, hasVersion := value["tool_version"].(string)
	if value["format"] != "kotlin-measurements" || numeric(value["version"]) != numeric(metadata["schema_version"]) ||
		value["complete"] != true || value["measurement_profile"] != metadata["measurement_profile"] || !hasVersion {
		return nil, fmt.Errorf("Kotlin measurements are missing or incomplete; check the project collection task and its Kotlin report")
	}
	version := detektVersion.FindStringSubmatch(toolVersion)
	if version == nil {
		return nil, fmt.Errorf("Unrecognized detekt version: %s", quoted(toolVersion))
	}
	major, _ := strconv.Atoi(version[1])
	adapter := object(object(metadata["adapters"])[strconv.Itoa(major)])
	if adapter == nil {
		return nil, fmt.Errorf("Unsupported detekt major %d; available measurement adapters: 1, 2", major)
	}
	minimum := str(adapter["minimum_version"])
	if compareVersion(version, detektVersion.FindStringSubmatch(minimum)) < 0 {
		return nil, fmt.Errorf("detekt %s is below the adapter minimum %s", toolVersion, minimum)
	}
	rows, err := qualityReportArray(pickDefault(value, "files", []any{}), "files")
	if err != nil {
		return nil, err
	}
	files, expected := map[string]record{}, map[string]bool{}
	for _, row := range rows {
		item, err := qualityReportObject(row, "file")
		if err != nil {
			return nil, err
		}
		files[str(item["file"])] = item
	}
	for file, source := range sources {
		if source["language"] == ".kt" {
			expected[file] = true
		}
	}
	if len(files) != len(rows) || len(files) != len(expected) || len(keyDiff(files, expected)) > 0 {
		return nil, fmt.Errorf("Kotlin measurements must cover each production Kotlin file exactly once")
	}
	for _, entry := range rows {
		row, err := qualityReportObject(entry, "file", "package")
		if err != nil {
			return nil, err
		}
		file := str(row["file"])
		if row["package"] != sources[file]["package"] {
			return nil, fmt.Errorf("Kotlin package does not match the source inventory: %s", file)
		}
		tokens, err := qualityReportField(row, "tokens")
		if err != nil {
			return nil, err
		}
		end := 0
		for _, entry := range tokens {
			token, err := qualityReportObject(entry, "start", "end")
			if err != nil {
				return nil, err
			}
			start, stop := integer(token["start"]), integer(token["end"])
			if !integerJSON(token["start"]) || !integerJSON(token["end"]) || start < end || stop <= start {
				return nil, fmt.Errorf("Invalid token positions: %s", file)
			}
			if _, exists := token["type"]; !exists {
				return nil, fmt.Errorf("'type'")
			}
			if _, exists := token["text"]; !exists && truthy(token["type"]) {
				return nil, fmt.Errorf("'text'")
			}
			if !truthy(token["type"]) || !truthy(token["text"]) {
				return nil, fmt.Errorf("Empty code token: %s", file)
			}
			end = stop
		}
		functions, err := qualityReportField(row, "functions")
		if err != nil {
			return nil, err
		}
		for _, entry := range functions {
			function, err := qualityReportObject(entry, "cognitive_complexity")
			if err != nil {
				return nil, err
			}
			complexity := function["cognitive_complexity"]
			if !integerJSON(complexity) || numeric(complexity) < 0 {
				return nil, fmt.Errorf("Missing cognitive complexity: %s", file)
			}
			valid, err := qualityReportRange(function)
			if err != nil {
				return nil, err
			}
			if _, exists := function["nested"]; valid && !exists {
				return nil, fmt.Errorf("'nested'")
			}
			_, nested := function["nested"].(bool)
			if !valid || !nested {
				return nil, fmt.Errorf("Invalid function range: %s", file)
			}
		}
		containers, err := qualityReportField(row, "containers")
		if err != nil {
			return nil, err
		}
		for _, entry := range containers {
			container, err := qualityReportObject(entry, "kind")
			if err != nil {
				return nil, err
			}
			if container["kind"] != "function" && container["kind"] != "class" {
				return nil, fmt.Errorf("Invalid size container: %s", file)
			}
			valid, err := qualityReportRange(container)
			if err != nil {
				return nil, err
			}
			if !valid {
				return nil, fmt.Errorf("Invalid size container: %s", file)
			}
		}
	}
	return files, nil
}

func reportType(value any) string {
	switch value.(type) {
	case nil:
		return "NoneType"
	case string:
		return "str"
	case bool:
		return "bool"
	case []any:
		return "list"
	case map[string]any:
		return "dict"
	default:
		if integerJSON(value) {
			return "int"
		}
		return "float"
	}
}

func qualityReportArray(value any, field string) ([]any, error) {
	if array := items(value); array != nil {
		return array, nil
	}
	switch reportType(value) {
	case "str", "dict":
		if truthy(value) {
			return nil, fmt.Errorf("string indices must be integers, not 'str'")
		}
		return nil, fmt.Errorf("Kotlin %s must be an array", field)
	default:
		return nil, fmt.Errorf("'%s' object is not iterable", reportType(value))
	}
}

func qualityReportField(row record, field string) ([]any, error) {
	value, exists := row[field]
	if !exists {
		return nil, fmt.Errorf("%s", quoted(field))
	}
	return qualityReportArray(value, field)
}

func qualityReportObject(value any, fields ...string) (record, error) {
	row := object(value)
	if row == nil {
		switch reportType(value) {
		case "str":
			return nil, fmt.Errorf("string indices must be integers, not 'str'")
		case "list":
			return nil, fmt.Errorf("list indices must be integers or slices, not str")
		default:
			return nil, fmt.Errorf("'%s' object is not subscriptable", reportType(value))
		}
	}
	for _, field := range fields {
		if _, exists := row[field]; !exists {
			return nil, fmt.Errorf("%s", quoted(field))
		}
	}
	return row, nil
}

func reportNumeric(value any) (float64, bool) {
	if boolean, valid := value.(bool); valid {
		if boolean {
			return 1, true
		}
		return 0, true
	}
	return decimal(value)
}

func qualityReportRange(row record) (bool, error) {
	start, exists := row["start"]
	if !exists {
		return false, fmt.Errorf("'start'")
	}
	a, valid := reportNumeric(start)
	if !valid {
		return false, fmt.Errorf("'<=' not supported between instances of 'int' and '%s'", reportType(start))
	}
	if a < 0 {
		return false, nil
	}
	end, exists := row["end"]
	if !exists {
		return false, fmt.Errorf("'end'")
	}
	b, valid := reportNumeric(end)
	if !valid {
		return false, fmt.Errorf("'<' not supported between instances of '%s' and '%s'", reportType(start), reportType(end))
	}
	return a < b, nil
}

func projectStatistics(text string, config record, sources map[string]record, root, sourceRoot string) (record, record, []string, error) {
	newCounts := func() record { return record{"Files": 0, "Lines": 0, "Code": 0, "Comment": 0, "Blank": 0} }
	newGroup := func() record { return record{"total": newCounts(), "by_language": record{}, "by_category": record{}} }
	project, modules := newGroup(), record{}
	for module := range object(config["modules"]) {
		modules[module] = newGroup()
	}
	exclusions := append([]string{}, stringsOf(config["exclude_paths"])...)
	exclusions = append(exclusions, stringsOf(config["statistics_exclude_paths"])...)
	exclusions = append(exclusions, "memory/tech-debt/**")
	parsed, err := parseJSONValue([]byte(text))
	if err != nil {
		return nil, nil, nil, err
	}
	seen, included := map[string]bool{}, map[string]bool{}
	for _, entry := range items(parsed) {
		language := object(entry)
		for _, entry := range items(language["Files"]) {
			row := object(entry)
			file, err := relativeSourcePath(str(row["Location"]), filepath.Join(root, filepath.FromSlash(sourceRoot)))
			if err != nil {
				return nil, nil, nil, err
			}
			if seen[file] {
				return nil, nil, nil, fmt.Errorf("Duplicate scc file: %s", file)
			}
			seen[file] = true
			if matchesAny(file, exclusions) {
				continue
			}
			counts := record{"Files": 1}
			for _, field := range sizeFields {
				value := row[field]
				if !integerJSON(value) || integer(value) < 0 {
					return nil, nil, nil, fmt.Errorf("Invalid scc counters: %s", file)
				}
				counts[field] = value
			}
			category, source := "other", sources[file]
			if source != nil {
				category = "production"
			} else {
				for _, name := range stringsOf(config["test_roots"]) {
					if strings.HasPrefix(file, strings.TrimRight(name, "/")+"/") {
						category = "tests"
						break
					}
				}
				if extension := filepath.Ext(file); category == "tests" && (extension == ".kt" || extension == ".java") {
					text, err := readUTF8(filepath.Join(root, filepath.FromSlash(file)))
					if err != nil {
						return nil, nil, nil, err
					}
					source = sourceDescription(text, extension)
				}
			}
			targets := []record{project}
			if source != nil {
				owner, mapped, err := moduleFor(str(source["package"]), object(config["modules"]))
				if err != nil {
					return nil, nil, nil, err
				}
				if mapped && owner != "" {
					targets = append(targets, object(modules[owner]))
				}
			}
			for _, target := range targets {
				byCategory, byLanguage := object(target["by_category"]), object(target["by_language"])
				languageName := str(language["Name"])
				if byCategory[category] == nil {
					byCategory[category] = newCounts()
				}
				if byLanguage[languageName] == nil {
					byLanguage[languageName] = newCounts()
				}
				for _, destination := range []record{object(target["total"]), object(byCategory[category]), object(byLanguage[languageName])} {
					for field, value := range counts {
						destination[field] = integer(destination[field]) + integer(value)
					}
				}
			}
			included[file] = true
		}
	}
	if missing := keyDiff(sources, included); len(missing) > 0 {
		return nil, nil, nil, fmt.Errorf("scc omits production files: %s", strings.Join(missing[:min(len(missing), 10)], ", "))
	}
	return project, modules, exclusions, nil
}

func qualityFraction(numerator, denominator int) record {
	status := "not_applicable"
	if denominator != 0 {
		status = "known"
	}
	return record{"value": ratioValue(numerator, denominator), "numerator": numerator, "denominator": denominator, "status": status}
}

func qualityScore(excess float64) float64 { return 100 / (1 + excess) }

func qualityIndicators(files map[string]record, edges edgeWeights, modules record, methods []record, lines map[sourceLine]bool, commits []record, parameters record, asOf time.Time) (record, record, error) {
	owners, err := sourceOwners(files, modules, nil)
	if err != nil {
		return nil, nil, err
	}
	if unassigned := keyDiff(files, owners); len(unassigned) > 0 {
		return nil, nil, fmt.Errorf("Assign production packages to architectural modules before auditing: %s", strings.Join(unassigned[:min(10, len(unassigned))], ", "))
	}
	if len(modules) == 0 {
		return nil, nil, fmt.Errorf("Declare architectural modules before auditing")
	}
	projectDuplicates, boundaryDuplicates := duplication(files, integer(parameters["clone_tokens"]), owners)
	calculate := func(selected map[string]record, duplicates map[string]record) (record, error) {
		paths := keys(selected)
		local := maintainability(selected, parameters)
		structure, err := structuralMetrics(paths, edges, integer(parameters["small_group_files"]))
		if err != nil {
			return nil, err
		}
		tokens, repeated := integer(local["tokens"]), 0
		for _, row := range duplicates {
			repeated += integer(row["tokens"])
		}
		var duplicationScore, qualityScoreValue any
		if tokens > 0 {
			duplicationScore = qualityScore(float64(repeated) / float64(tokens) / numeric(parameters["duplication_reference"]))
		}
		decoupling := object(structure["decoupling_level"])["value"]
		status := "not_applicable"
		if decoupling != nil && local["value"] != nil && duplicationScore != nil {
			qualityScoreValue = math.Pow(numeric(decoupling)*numeric(local["value"])*numeric(duplicationScore), 1.0/3.0)
			status = "known"
		}
		return record{"files": len(paths), "tokens": tokens, "Q": qualityScoreValue, "D": decoupling, "L": local["value"], "U": duplicationScore,
			"status": status, "structure": structure, "local_maintainability": local,
			"duplication": record{"fraction": qualityFraction(repeated, tokens), "tokens": repeated, "files": duplicates},
			"coverage":    coverageSummary(pathSet(paths), methods, lines, tokens), "history": historySummary(selected, files, commits, parameters, asOf)}, nil
	}
	project, err := calculate(files, projectDuplicates)
	if err != nil {
		return nil, nil, err
	}
	projectCyclic := map[string]bool{}
	for _, group := range object(project["structure"])["cyclic_components"].([][]string) {
		for _, path := range group {
			projectCyclic[path] = true
		}
	}
	crossCoupled := map[string]bool{}
	for _, pair := range object(project["history"])["pairs"].([]record) {
		left, right := str(pair["left"]), str(pair["right"])
		if owners[left] != owners[right] {
			crossCoupled[left], crossCoupled[right] = true, true
		}
	}
	moduleResults := record{}
	for _, module := range keys(modules) {
		selected := map[string]record{}
		for path, owner := range owners {
			if owner == module {
				selected[path] = files[path]
			}
		}
		duplicates, _ := duplication(selected, integer(parameters["clone_tokens"]), owners)
		value, err := calculate(selected, duplicates)
		if err != nil {
			return nil, nil, err
		}
		incoming, outgoing, cyclic, coupled, repeated, projectRepeated := 0, 0, 0, 0, 0, 0
		for pair := range edges {
			if selected[pair.from] == nil && selected[pair.to] != nil {
				incoming++
			}
			if selected[pair.from] != nil && selected[pair.to] == nil {
				outgoing++
			}
		}
		for path := range selected {
			if projectCyclic[path] {
				cyclic++
			}
			if crossCoupled[path] {
				coupled += len(items(files[path]["tokens"]))
			}
			repeated += integer(boundaryDuplicates[path]["tokens"])
			projectRepeated += integer(projectDuplicates[path]["tokens"])
		}
		value["boundary"] = record{"incoming_edges": incoming, "outgoing_edges": outgoing, "project_cyclic_files": cyclic,
			"cross_module_coupled_tokens": coupled, "cross_module_duplicate_tokens": repeated, "project_duplicate_tokens": projectRepeated}
		moduleResults[module] = value
	}
	return project, moduleResults, nil
}

func historySummary(selected, files map[string]record, commits []record, parameters record, asOf time.Time) record {
	cutoff := asOf.AddDate(0, 0, -integer(parameters["history_days"]))
	revisions, support := map[string]int{}, edgeWeights{}
	excluded, observations := 0, 0
	for _, commit := range commits {
		date, _ := isotime(str(commit["date"]))
		if date.Before(cutoff) || date.After(asOf) {
			continue
		}
		production, selectedPaths := 0, []string{}
		for _, path := range keys(object(commit["changes"])) {
			if files[path] != nil {
				production++
				if selected[path] != nil {
					selectedPaths = append(selectedPaths, path)
				}
			}
		}
		if integer(pickDefault(commit, "production_files", production)) > integer(parameters["history_maximum_files"]) {
			excluded++
			continue
		}
		if len(selectedPaths) > 0 {
			observations++
		}
		for index, left := range selectedPaths {
			revisions[left]++
			for _, right := range selectedPaths[index+1:] {
				support[edge{left, right}]++
			}
		}
	}
	pairs, involved := []record{}, map[string]bool{}
	for pair, shared := range support {
		average := float64(revisions[pair.from]+revisions[pair.to]) / 2
		degree := float64(shared) / average
		if shared >= integer(parameters["history_minimum_shared"]) && average >= numeric(parameters["history_minimum_average"]) && degree >= numeric(parameters["history_minimum_coupling"]) {
			pairs = append(pairs, record{"left": pair.from, "right": pair.to, "shared": shared, "coupling": degree})
			involved[pair.from], involved[pair.to] = true, true
		}
	}
	sort.Slice(pairs, func(i, j int) bool {
		a, b := pairs[i], pairs[j]
		if a["coupling"] != b["coupling"] {
			return numeric(a["coupling"]) > numeric(b["coupling"])
		}
		if a["left"] != b["left"] {
			return str(a["left"]) < str(b["left"])
		}
		return str(a["right"]) < str(b["right"])
	})
	tokens, exposed := 0, 0
	for path, row := range selected {
		count := len(items(row["tokens"]))
		tokens += count
		if involved[path] {
			exposed += count
		}
	}
	status := "limited"
	if observations >= integer(parameters["history_minimum_shared"]) {
		status = "known"
	}
	return record{"since": cutoff.Format("2006-01-02"), "until": asOf.Format("2006-01-02"), "observations": observations, "status": status,
		"excluded_large_commits": excluded, "coupled_files": len(involved), "coupled_tokens": exposed, "coupled_token_fraction": qualityFraction(exposed, tokens), "pairs": pairs}
}
