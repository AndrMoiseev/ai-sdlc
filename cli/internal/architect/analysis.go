package architect

import (
	"fmt"
	"math"
	"path/filepath"
	"strings"
	"time"
)

type measurementAnalysis struct {
	rows       map[string][]record
	outcomes   map[string]record
	selections map[string][]record
	gaps       []record
	classEdges edgeWeights
	commits    []record
}

func measurementNumber(value any, reason string) record {
	if value != nil {
		return record{"status": "measured", "value": value}
	}
	if reason == "" {
		reason = "Input is unavailable"
	}
	return record{"status": "unknown", "value": nil, "reason": reason}
}

func mergeRecords(values ...record) record {
	result := record{}
	for _, value := range values {
		for key, item := range value {
			result[key] = item
		}
	}
	return result
}

func (analysis *measurementAnalysis) add(identifier string, row record) {
	analysis.rows[identifier] = append(analysis.rows[identifier], row)
}

func (analysis *measurementAnalysis) addGap(artifact, reason string, details record) {
	gap := record{"reason": reason}
	if artifact != "" {
		gap["artifact"] = artifact
	}
	analysis.gaps = append(analysis.gaps, mergeRecords(gap, details))
}

func (analysis *measurementAnalysis) prepareOutcomes(inputs record) {
	for name, measurement := range catalog {
		status := "complete"
		var reasons []string
		for _, input := range measurement.inputs {
			outcome := object(inputs[input])
			if outcome["status"] != "complete" {
				if outcome["status"] == "error" || status == "error" {
					status = "error"
				} else {
					status = "unavailable"
				}
				reasons = append(reasons, input+": "+str(pickDefault(outcome, "reason", "No source configured")))
			}
		}
		outcome := record{"status": status}
		if len(reasons) > 0 {
			outcome["reason"] = strings.Join(reasons, "; ")
		}
		analysis.outcomes[name] = outcome
	}
}

func prepareMeasurements(config record, sources map[string]record, mappings map[string]string, mappingGaps []record, raw map[string]string, artifacts, policy record, sourceError error, root string) (*measurementAnalysis, error) {
	analysis := &measurementAnalysis{rows: map[string][]record{}, outcomes: map[string]record{}, gaps: []record{}}
	for _, gap := range mappingGaps {
		analysis.gaps = append(analysis.gaps, mergeRecords(record{"artifact": "mapping"}, gap))
	}
	meta := func(name string) record { return object(artifacts[name]) }
	sourceRoot := func(name string) string { return filepath.Join(root, str(meta(name)["source_root"])) }
	parsed := func(name string, err error) {
		if err != nil {
			metadata := meta(name)
			metadata["status"], metadata["reason"] = "error", err.Error()
		}
	}
	var err error
	var findings, coverageGaps []record
	var sizeRows, coverageRows map[string]record
	if text, found := raw["dependencies"]; found {
		analysis.classEdges, err = parseDependencies(text, str(meta("dependencies")["format"]), stringsOf(config["package_prefixes"]), stringsOf(config["exclude_classes"]))
		parsed("dependencies", err)
	}
	if text, found := raw["complexity"]; found {
		findings, err = parseDetekt(text, sourceRoot("complexity"))
		parsed("complexity", err)
	}
	if text, found := raw["sizes"]; found {
		sizeRows, err = parseSizes(text, sourceRoot("sizes"))
		parsed("sizes", err)
	}
	if text, found := raw["coverage"]; found {
		coverageRows, coverageGaps, err = parseCoverage(text, str(meta("coverage")["format"]), sourceRoot("coverage"), sources)
		parsed("coverage", err)
	}
	var history *historyMeasurements
	if text, found := raw["history"]; found {
		analysis.commits, err = parseHistory(text)
		parsed("history", err)
		if err == nil {
			history = measureHistory(analysis.commits, policy)
			meta("history")["window"] = history.window
		}
	}
	for _, gap := range coverageGaps {
		analysis.addGap("coverage", "Ambiguous or missing source mapping", gap)
	}
	for _, name := range keys(artifacts) {
		if spec := meta(name); spec["status"] != "complete" {
			analysis.addGap(name, str(pickDefault(spec, "reason", "Source is unavailable")), nil)
		}
	}
	sourceOutcomes := record{"status": "complete"}
	if len(sources) == 0 && !truthy(config["source_roots"]) {
		sourceOutcomes = record{"status": "unavailable", "reason": "No source population supplied"}
	}
	if sourceError != nil {
		sourceOutcomes = record{"status": "error", "reason": sourceError.Error()}
		analysis.addGap("sources", sourceError.Error(), nil)
	}
	mappingOutcomes := record{"status": "complete"}
	if len(mappings) == 0 && !truthy(config["class_directories"]) && !truthy(config["class_files"]) {
		mappingOutcomes = record{"status": "unavailable", "reason": "No JVM-to-source mapping supplied"}
	}
	if len(mappingGaps) > 0 && len(mappings) == 0 {
		mappingOutcomes = record{"status": "error", "reason": "JVM-to-source mapping could not be resolved"}
	}
	analysis.prepareOutcomes(mergeRecords(artifacts, record{"sources": sourceOutcomes, "mapping": mappingOutcomes}))
	for file, source := range sources {
		analysis.add("source-files/file", mergeRecords(record{"file": file}, pick(source, []string{"package", "language"})))
		for _, metric := range []struct{ name, field string }{{"type-count", "types"}, {"abstract-type-count", "abstract"}} {
			analysis.add(metric.name+"/file", mergeRecords(record{"file": file}, measurementNumber(source[metric.field], "Declaration extraction is unavailable for this language")))
		}
	}
	for name, path := range mappings {
		origin := "JVM SourceFile"
		if _, found := object(config["class_files"])[name]; found {
			origin = "explicit"
		}
		analysis.add("class-files/class", record{"class": name, "file": path, "source": origin})
	}
	if sourceOutcomes["status"] == "complete" {
		extra := map[string]bool{}
		for file := range sizeRows {
			if sources[file] == nil {
				extra[file] = true
				delete(sizeRows, file)
			}
		}
		for file := range coverageRows {
			if sources[file] == nil {
				extra[file] = true
				delete(coverageRows, file)
			}
		}
		selected := findings[:0]
		for _, finding := range findings {
			file := str(finding["file"])
			if sources[file] == nil {
				extra[file] = true
			} else {
				selected = append(selected, finding)
			}
		}
		findings = selected
		if len(extra) > 0 {
			analysis.addGap("", "Report paths outside production source population", record{"files": keys(extra)})
		}
	}
	modules := object(config["modules"])
	owners, moduleError := sourceOwners(sources, modules, analysis.classEdges)
	if moduleError != nil {
		analysis.addGap("modules", moduleError.Error(), nil)
	}
	groups := map[string]map[string][]string{"package": {}, "module": {}}
	for _, path := range keys(sources) {
		packageName := str(sources[path]["package"])
		groups["package"][packageName] = append(groups["package"][packageName], path)
		if owner, mapped := owners[path]; mapped && moduleError == nil {
			groups["module"][owner] = append(groups["module"][owner], path)
		}
	}
	for module := range modules {
		if _, found := groups["module"][module]; !found {
			groups["module"][module] = []string{}
		}
	}
	var graphNodes map[string]record
	if analysis.classEdges != nil {
		packageEdges := aggregate(analysis.classEdges, func(name string) (string, bool) { return packageOf(name), true })
		graphNodes = emitGraph(analysis, "class", analysis.classEdges)
		packageNodes := emitGraph(analysis, "package", packageEdges)
		emitMartin(analysis, sources, packageNodes, policy)
		if moduleError == nil {
			moduleEdges := aggregate(packageEdges, func(name string) (string, bool) {
				owner, found, _ := moduleFor(name, modules)
				return owner, found
			})
			emitGraph(analysis, "module", moduleEdges)
			emitModuleViews(analysis, packageEdges, modules, policy)
		}
	}
	byFile := analysis.emitComplexity(findings)
	paths := map[string]bool{}
	for _, population := range []map[string]record{sources, sizeRows, coverageRows} {
		for file := range population {
			paths[file] = true
		}
	}
	for file := range byFile {
		paths[file] = true
	}
	if history != nil {
		for file := range history.churn {
			paths[file] = true
		}
	}
	mappedNodes, unmapped := map[string][]record{}, keyDiff(graphNodes, mappings)
	for name, node := range graphNodes {
		if file, found := mappings[name]; found {
			mappedNodes[file] = append(mappedNodes[file], node)
		}
	}
	if len(unmapped) > 0 {
		analysis.addGap("mapping", "Dependency classes without a source mapping", record{"classes": unmapped})
	}
	fileMeasurements := map[string]map[string]record{}
	measurementsPolicy := object(policy["measurements"])
	mappingComplete := len(unmapped)+len(mappingGaps) == 0
	for _, file := range keys(paths) {
		fileMeasurements[file] = analysis.emitFile(file, sources[file] != nil, sizeRows[file], coverageRows[file], byFile[file], history,
			mappedNodes[file], mappingComplete, truthy(meta("complexity")["complete_mcc"]), measurementsPolicy)
	}
	for _, level := range []string{"package", "module"} {
		activity := groupActivity(analysis.commits, groups[level], measurementsPolicy)
		for group, paths := range groups[level] {
			analysis.emitGroup(level, group, paths, fileMeasurements, coverageRows, activity[group], history != nil, object(object(policy["signals"])["crap"]))
		}
	}
	if history != nil {
		analysis.emitHistory(history, sources, mappings, owners, mappingComplete, moduleError != nil)
	}
	for identifier := range catalog {
		if moduleError != nil && (strings.HasSuffix(identifier, "/module") || identifier == "external-affinity/package") {
			analysis.rows[identifier] = nil
			analysis.outcomes[identifier] = record{"status": "error", "reason": moduleError.Error()}
		}
		if err := sortedMeasurementRows(identifier, analysis.rows[identifier]); err != nil {
			return nil, err
		}
	}
	analysis.selections = prepareSelections(analysis, config, artifacts, policy)
	return analysis, nil
}

func sourceOwners(sources map[string]record, modules record, edges edgeWeights) (map[string]string, error) {
	owners := map[string]string{}
	for _, path := range keys(sources) {
		name, found, err := moduleFor(str(sources[path]["package"]), modules)
		if err != nil {
			return nil, err
		}
		if found {
			owners[path] = name
		}
	}
	nodes := map[string]bool{}
	for pair := range edges {
		nodes[pair.from], nodes[pair.to] = true, true
	}
	for _, name := range keys(nodes) {
		if _, _, err := moduleFor(packageOf(name), modules); err != nil {
			return owners, err
		}
	}
	return owners, nil
}

func (analysis *measurementAnalysis) emitComplexity(findings []record) map[string][]record {
	ruleMetrics := map[string]string{"CyclomaticComplexMethod": "cyclomatic-complexity/function", "CognitiveComplexMethod": "cognitive-complexity/function",
		"LongMethod": "method-length/function", "TooManyFunctions": "function-count/declaration", "LongParameterList": "parameter-list/declaration"}
	byFile := map[string][]record{}
	for _, finding := range findings {
		file, rule := str(finding["file"]), str(finding["rule"])
		reason := "Tool message contains no measured value"
		if rule == "LongParameterList" {
			reason = "Cannot count parameters from a complete supported declaration"
			if finding["value"] == nil && finding["suppressed"] == false {
				analysis.addGap("complexity", "Parameter count is unknown: obtain a complete supported declaration before applying the analyzer threshold",
					pick(finding, []string{"file", "record"}))
			}
		}
		byFile[file] = append(byFile[file], finding)
		analysis.add(ruleMetrics[rule], mergeRecords(finding, measurementNumber(finding["value"], reason)))
	}
	return byFile
}

var historyMetrics = []string{"change-frequency", "added-lines", "deleted-lines", "churn"}

func (analysis *measurementAnalysis) emitFile(file string, live bool, sizes, coverage record, findings []record, history *historyMeasurements, nodes []record, mappingComplete, completeMCC bool, policy record) map[string]record {
	rowFor := func(value any, reason string) record {
		row := measurementNumber(value, reason)
		row["file"] = file
		return row
	}
	analysis.add("code-lines/file", rowFor(sizes["Code"], "File was not measured by scc"))
	analysis.add("total-lines/file", rowFor(sizes["Lines"], "File was not measured by scc"))
	values := map[string]record{}
	var changes, churn any
	for index, metric := range historyMetrics {
		var value, binaries any
		if history != nil {
			totals := history.churn[file]
			value = []int{totals.frequency, totals.added, totals.deleted, totals.added + totals.deleted}[index]
			binaries = totals.binary
		}
		row := rowFor(value, "")
		row["live_production"] = live
		if index > 0 {
			row["binary_changes"] = binaries
		}
		values[metric] = row
		analysis.add(metric+"/file", row)
	}
	changes, churn = values["change-frequency"]["value"], values["churn"]["value"]
	var mcc any
	observed, total, sum := 0, 0, 0
	for _, finding := range findings {
		if finding["rule"] == "CyclomaticComplexMethod" {
			total++
			if finding["value"] != nil && finding["suppressed"] == false {
				observed++
				sum += integer(finding["value"])
			}
		}
	}
	if observed > 0 {
		mcc = sum
	}
	complete := completeMCC && observed > 0 && observed == total
	analysis.add("cyclomatic-complexity/file", mergeRecords(rowFor(mcc, "No measured MCC finding"), record{"population_complete": complete, "observed_functions": observed}))
	for _, kind := range []string{"line", "branch"} {
		counter := object(coverage[kind])
		if counter == nil {
			counter = record{"covered": nil, "total": nil, "value": nil, "status": "unknown", "reason": "File or counter was not measured"}
		}
		analysis.add(kind+"-coverage/file", mergeRecords(record{"file": file}, counter))
	}
	var crap any
	line := object(coverage["line"])["value"]
	if mcc != nil && line != nil {
		formula := object(policy["crap"])
		crap = math.Pow(numeric(mcc), numeric(formula["complexity_exponent"]))*math.Pow(1-numeric(line), numeric(formula["uncovered_exponent"])) + numeric(mcc)
	}
	crapRow := rowFor(crap, "Requires measured MCC and line coverage")
	crapRow["population_complete"] = complete
	if crap != nil && !complete {
		crapRow["status"] = "measured_subset"
	}
	values["crap"] = crapRow
	analysis.add("crap-file/file", crapRow)
	for _, spec := range []struct {
		metric, visibility string
		activity           any
	}{{"hotspot-in-frequency", "visibility-in", changes}, {"hotspot-out-frequency", "visibility-out", changes}, {"hotspot-in-churn", "visibility-in", churn}} {
		var maximum, value any
		for _, node := range nodes {
			if current := node[spec.visibility]; maximum == nil || numeric(current) > numeric(maximum) {
				maximum = current
			}
		}
		if maximum != nil && spec.activity != nil {
			value = numeric(maximum) * numeric(spec.activity)
		}
		row := mergeRecords(rowFor(value, "Requires history and mapped dependency classes"),
			record{"visibility": maximum, "activity": spec.activity, "mapping_complete": mappingComplete})
		if value != nil && !mappingComplete {
			row["status"] = "measured_subset"
		}
		analysis.add(spec.metric+"/file", row)
	}
	code := sizes["Code"]
	density := object(policy["changes_per_code"])
	minimumFrequency, minimumCode := integer(density["minimum_frequency"]), integer(density["minimum_code_lines"])
	var densityValue any
	notApplicable := !strings.HasSuffix(file, ".kt") || (changes != nil && integer(changes) < minimumFrequency) || (code != nil && integer(code) < minimumCode)
	if !notApplicable && changes != nil && code != nil {
		densityValue = numeric(density["code_line_unit"]) * numeric(changes) / numeric(code)
	}
	row := rowFor(densityValue, fmt.Sprintf("Requires Kotlin, frequency >= %d and code >= %d", minimumFrequency, minimumCode))
	if notApplicable {
		row["status"] = "not_applicable"
	}
	analysis.add("changes-per-code/file", row)
	return values
}

func (analysis *measurementAnalysis) emitGroup(level, group string, paths []string, fileMeasurements map[string]map[string]record, coverageRows map[string]record, activity [2]int, history bool, crapPolicy record) {
	for index, metric := range historyMetrics {
		var value, binary any
		if history {
			total, binaries := 0, 0
			for _, file := range paths {
				row := fileMeasurements[file][metric]
				total += integer(row["value"])
				binaries += integer(row["binary_changes"])
			}
			value, binary = total, binaries
		}
		row := mergeRecords(record{level: group, "files": paths}, measurementNumber(value, ""))
		if index > 0 {
			row["binary_changes"] = binary
		}
		analysis.add(metric+"/"+level, row)
	}
	for index, metric := range []string{"activity", "recent-activity"} {
		var value any
		if history {
			value = activity[index]
		}
		analysis.add(metric+"/"+level, mergeRecords(record{level: group}, measurementNumber(value, "")))
	}
	for _, kind := range []string{"line", "branch"} {
		measured, omitted, notApplicable := []string{}, []string{}, []string{}
		covered, total := 0, 0
		for _, file := range paths {
			row := object(coverageRows[file][kind])
			switch row["status"] {
			case "measured", "not_applicable":
				measured = append(measured, file)
				covered += integer(row["covered"])
				total += integer(row["total"])
				if row["status"] == "not_applicable" {
					notApplicable = append(notApplicable, file)
				}
			default:
				omitted = append(omitted, file)
			}
		}
		summary := record{"covered": nil, "total": nil, "value": nil, "status": "unknown", "reason": "No measured counters"}
		if len(measured) > 0 {
			summary, _ = coverageRatio(covered, total)
		}
		if len(omitted) > 0 {
			summary["status"] = "unknown"
			if summary["value"] != nil {
				summary["status"] = "measured_subset"
			}
		}
		analysis.add(kind+"-coverage/"+level, mergeRecords(summary, record{level: group, "included_files": measured,
			"omitted_files": omitted, "not_applicable_files": notApplicable}))
	}
	included, omitted, incomplete := []string{}, []string{}, []string{}
	var total float64
	above := 0
	for _, file := range paths {
		row := fileMeasurements[file]["crap"]
		if row["value"] == nil {
			omitted = append(omitted, file)
			continue
		}
		included = append(included, file)
		if row["population_complete"] != true {
			incomplete = append(incomplete, file)
		}
		value := numeric(row["value"])
		total += value
		if value > numeric(crapPolicy["minimum_value"]) {
			above++
		}
	}
	for index, metric := range []string{"crap-sum", "crap-mean", "crap-above-threshold"} {
		var value any
		if len(included) > 0 {
			value = []any{total, total / float64(len(included)), above}[index]
		}
		row := mergeRecords(measurementNumber(value, "No measured CRAP_file values"), record{level: group,
			"included_files": included, "omitted_files": omitted, "incomplete_files": incomplete})
		if value != nil && len(omitted)+len(incomplete) > 0 {
			row["status"] = "measured_subset"
		}
		analysis.add(metric+"/"+level, row)
	}
}

type churnMeasures struct{ frequency, added, deleted, binary int }
type historyMeasurements struct {
	churn    map[string]churnMeasures
	filtered map[string]int
	shared   edgeWeights
	window   record
}

func measureHistory(commits []record, policy record) *historyMeasurements {
	result := &historyMeasurements{map[string]churnMeasures{}, map[string]int{}, edgeWeights{}, record{"start": nil, "end": nil}}
	limit := integer(object(object(policy["measurements"])["history"])["maximum_changeset_size"])
	for _, commit := range commits {
		date := str(commit["date"])
		if result.window["start"] == nil || date < str(result.window["start"]) {
			result.window["start"] = date
		}
		if date > str(result.window["end"]) {
			result.window["end"] = date
		}
		changes := object(commit["changes"])
		paths := keys(changes)
		for index, path := range paths {
			change := object(changes[path])
			churn := result.churn[path]
			churn.frequency++
			churn.added += integer(change["added"])
			churn.deleted += integer(change["deleted"])
			if change["binary"] == true {
				churn.binary++
			}
			result.churn[path] = churn
			if len(paths) <= limit {
				result.filtered[path]++
				for _, other := range paths[index+1:] {
					result.shared[edge{path, other}]++
				}
			}
		}
	}
	return result
}

func groupActivity(commits []record, groups map[string][]string, policy record) map[string][2]int {
	result := map[string][2]int{}
	if len(commits) == 0 {
		return result
	}
	owners := map[string]string{}
	for name, paths := range groups {
		for _, path := range paths {
			owners[path] = name
		}
	}
	latest := ""
	for _, commit := range commits {
		latest = max(latest, str(commit["date"]))
	}
	date, _ := isotime(latest)
	cutoff := date.AddDate(0, 0, -integer(object(policy["history"])["recent_days"]))
	for _, commit := range commits {
		seen := map[string]bool{}
		withDate, _ := isotime(str(commit["date"]))
		for path := range object(commit["changes"]) {
			if owner, ok := owners[path]; ok && !seen[owner] {
				count := result[owner]
				count[0]++
				if !withDate.Before(cutoff) {
					count[1]++
				}
				result[owner], seen[owner] = count, true
			}
		}
	}
	return result
}

func (analysis *measurementAnalysis) emitHistory(history *historyMeasurements, sources map[string]record, mappings, owners map[string]string, mappingComplete, moduleError bool) {
	for _, commit := range analysis.commits {
		changes, rows := object(commit["changes"]), []record{}
		for _, file := range keys(changes) {
			rows = append(rows, mergeRecords(record{"file": file}, object(changes[file])))
		}
		analysis.add("changes/commit", record{"commit": commit["revision"], "date": commit["date"], "changeset_size": len(changes), "changes": rows})
	}
	fileEdges := map[edge]bool{}
	for pair := range analysis.classEdges {
		left, right := mappings[pair.from], mappings[pair.to]
		if left != "" && right != "" {
			fileEdges[edge{left, right}] = true
		}
	}
	for pair, support := range history.shared {
		left, right := pair.from, pair.to
		leftFrequency, rightFrequency := history.filtered[left], history.filtered[right]
		live := sources[left] != nil && sources[right] != nil
		crossPackage := live && sources[left]["package"] != sources[right]["package"]
		var crossModule any
		if leftOwner, known := owners[left]; known && !moduleError {
			if rightOwner, known := owners[right]; known {
				crossModule = leftOwner != rightOwner
			}
		}
		row := record{"left": left, "right": right, "left_frequency": leftFrequency, "right_frequency": rightFrequency,
			"shared": support, "average_frequency": float64(leftFrequency+rightFrequency) / 2, "value": 200 * support / (leftFrequency + rightFrequency),
			"status": "measured", "live_production": live, "cross_package": crossPackage, "cross_module": crossModule}
		analysis.add("coupling/file-pair", row)
		if crossPackage && strings.HasSuffix(left, ".kt") && strings.HasSuffix(right, ".kt") && analysis.classEdges != nil && !fileEdges[pair] && !fileEdges[edge{right, left}] {
			implicit := mergeRecords(row, record{"mapping_complete": mappingComplete && len(mappings) > 0})
			if !mappingComplete || len(mappings) == 0 {
				implicit["status"] = "measured_subset"
			}
			analysis.add("implicit-coupling/file-pair", implicit)
		}
	}
}

func todayUTC() time.Time { return time.Now().UTC().Truncate(24 * time.Hour) }
