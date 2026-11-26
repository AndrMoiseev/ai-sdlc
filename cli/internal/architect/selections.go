package architect

import (
	"fmt"
	"sort"
	"strings"
)

var evidenceFamilies = map[string]string{
	"cycle": "dependency_structure", "boundary": "dependency_structure", "coupling": "change_patterns", "hotspot": "change_patterns",
	"complexity": "code_risk", "coverage": "code_risk", "crap": "code_risk", "shape": "code_risk",
}

type measuredRow struct {
	identifier string
	row        record
}

func prepareSelections(analysis *measurementAnalysis, config, artifacts, policy record) map[string][]record {
	rankings, signals := []record{}, []record{}
	filters, evidencePolicy := object(policy["signals"]), object(policy["evidence"])
	filter := func(section, key string) any { return object(filters[section])[key] }
	signal := func(family, condition string, measured ...measuredRow) {
		limited := false
		refs := []record{}
		for _, value := range measured {
			identifier, row := value.identifier, value.row
			refs = append(refs, reference(identifier, row))
			limited = limited || row["status"] == "measured_subset" || row["population_complete"] == false
			for _, input := range catalog[identifier].inputs {
				if metadata := object(artifacts[input]); metadata != nil {
					limited = limited || metadata["status"] != "complete" || !truthy(metadata["tool"]) || !truthy(metadata["version"]) || !truthy(metadata["command"])
				}
			}
		}
		weights := mergeRecords(object(object(evidencePolicy["weights"])[family]))
		suitability := "usable"
		if limited {
			suitability = "limited"
			for criterion, weight := range weights {
				if numeric(weight) > numeric(evidencePolicy["limited_weight_cap"]) {
					weights[criterion] = evidencePolicy["limited_weight_cap"]
				}
			}
		}
		signals = append(signals, record{"family": family, "condition": condition, "references": refs,
			"suitability": suitability, "evidence_weights": weights})
	}
	thresholds := map[string]struct {
		family, key string
	}{"cyclomatic-complexity/function": {"complexity", "cyclomatic_minimum"},
		"cognitive-complexity/function": {"complexity", "cognitive_minimum"}, "method-length/function": {"shape", "method_length_minimum"},
		"function-count/declaration": {"shape", "function_count_minimum"}, "parameter-list/declaration": {"shape", "parameter_list_minimum"},
		"crap-file/file": {"crap", "minimum_value"}, "distance/package": {"boundary", "distance_minimum"}}
	for _, identifier := range keys(catalog) {
		if analysis.outcomes[identifier]["status"] != "complete" {
			continue
		}
		rows := analysis.rows[identifier]
		measured := []record{}
		for _, row := range rows {
			if _, valid := decimal(row["value"]); valid && !truthy(row["suppressed"]) {
				measured = append(measured, row)
			}
		}
		ordered := append([]record{}, measured...)
		sort.SliceStable(ordered, func(i, j int) bool { return numeric(ordered[i]["value"]) > numeric(ordered[j]["value"]) })
		for index, row := range ordered {
			rankings = append(rankings, mergeRecords(reference(identifier, row), record{"condition": "value descending; ties by record key", "position": index + 1}))
		}
		if strings.HasPrefix(identifier, "cyclic-components/") {
			minimum := integer(filter("cycle", "minimum_members"))
			for _, row := range rows {
				if len(stringsOf(row["members"])) >= minimum {
					signal("cycle", fmt.Sprintf("members >= %d", minimum), measuredRow{identifier, row})
				}
			}
		}
		if threshold, exists := thresholds[identifier]; exists {
			limit := filter(threshold.family, threshold.key)
			operator := ">="
			if threshold.family == "crap" {
				operator = ">"
			}
			for _, row := range measured {
				if numeric(row["value"]) > numeric(limit) || (operator == ">=" && numeric(row["value"]) == numeric(limit)) {
					signal(threshold.family, "value "+operator+" "+display(limit), measuredRow{identifier, row})
				}
			}
		}
		if strings.HasPrefix(identifier, "hotspot-") {
			minimumScore, top := filter("hotspot", "minimum_score"), integer(filter("hotspot", "top_count"))
			for _, row := range ordered[:min(len(ordered), top)] {
				if numeric(row["value"]) > numeric(minimumScore) {
					signal("hotspot", fmt.Sprintf("value > %s; top %d", display(minimumScore), top), measuredRow{identifier, row})
				}
			}
			if identifier == "hotspot-in-frequency/file" {
				frequency, visibility := filter("hotspot", "minimum_frequency"), filter("hotspot", "minimum_visibility")
				for _, row := range measured {
					if numeric(row["activity"]) >= numeric(frequency) && numeric(row["visibility"]) >= numeric(visibility) {
						signal("hotspot", fmt.Sprintf("frequency >= %s and visibility_in >= %s", display(frequency), display(visibility)), measuredRow{identifier, row})
					}
				}
			}
		}
		if identifier == "coupling/file-pair" || identifier == "implicit-coupling/file-pair" {
			frequency, shared, degree := filter("coupling", "minimum_average_frequency"), filter("coupling", "minimum_shared_commits"), filter("coupling", "minimum_degree")
			for _, row := range measured {
				if row["cross_package"] == true && numeric(row["average_frequency"]) >= numeric(frequency) && numeric(row["shared"]) >= numeric(shared) && numeric(row["value"]) >= numeric(degree) {
					condition := fmt.Sprintf("cross_package and average_frequency >= %s and shared >= %s and degree >= %s", display(frequency), display(shared), display(degree))
					signal("coupling", condition, measuredRow{identifier, row})
				}
			}
		}
	}
	activity, coverage := "change-frequency/file", "line-coverage/file"
	if analysis.outcomes[activity]["status"] == "complete" && analysis.outcomes[coverage]["status"] == "complete" {
		byFile := map[string]record{}
		for _, row := range analysis.rows[activity] {
			byFile[str(row["file"])] = row
		}
		frequency, maximum := filter("coverage", "minimum_frequency"), filter("coverage", "maximum_line_coverage")
		for _, row := range analysis.rows[coverage] {
			changed := byFile[str(row["file"])]
			if changed["value"] != nil && numeric(changed["value"]) >= numeric(frequency) && row["value"] != nil && numeric(row["value"]) < numeric(maximum) {
				condition := fmt.Sprintf("frequency >= %s and line coverage < %s", display(frequency), display(maximum))
				signal("coverage", condition, measuredRow{activity, changed}, measuredRow{coverage, row})
			}
		}
	}
	return prepareCandidateGroups(analysis, config, policy, signals, rankings)
}

type candidateGroup struct {
	identity string
	scope    record
	seeds    []string
	attached map[string]bool
	overlaps []record
	families record
	score    int
	result   record
}

func prepareCandidateGroups(analysis *measurementAnalysis, config, policy record, rawSignals, rankings []record) map[string][]record {
	unique := map[string]record{}
	for _, signal := range rawSignals {
		refs := signal["references"].([]record)
		sort.Slice(refs, func(i, j int) bool { return keyText(refs[i]) < keyText(refs[j]) })
		unique[keyText(signal)] = signal
	}
	signals, bySignal := []record{}, map[string]record{}
	for index, key := range keys(unique) {
		signal := unique[key]
		identity := fmt.Sprintf("signal-%04d", index+1)
		signal["signal"] = identity
		signals = append(signals, signal)
		bySignal[identity] = signal
	}
	measurements := map[[2]string]measuredRow{}
	for identifier, spec := range catalog {
		if analysis.outcomes[identifier]["status"] == "complete" {
			for _, row := range analysis.rows[identifier] {
				measurements[[2]string{spec.path, keyText(pick(row, spec.key))}] = measuredRow{identifier, row}
			}
		}
	}
	sources, classes, packages, modules := map[string]bool{}, map[string]string{}, map[string][]string{}, map[string][]string{}
	moduleError := false
	for _, row := range analysis.rows["source-files/file"] {
		file, packageName := str(row["file"]), str(row["package"])
		sources[file] = true
		packages[packageName] = append(packages[packageName], file)
		owner, known, err := moduleFor(packageName, object(config["modules"]))
		if err != nil {
			moduleError = true
		} else if known {
			modules[owner] = append(modules[owner], file)
		}
	}
	if moduleError {
		clear(modules)
	}
	for _, row := range analysis.rows["class-files/class"] {
		classes[str(row["class"])] = str(row["file"])
	}
	provisional, scopes := map[string]*candidateGroup{}, map[string]record{}
	for _, signal := range signals {
		identity := str(signal["signal"])
		refs := signal["references"].([]record)
		files, unresolved := map[string]bool{}, map[string]record{}
		for _, ref := range refs {
			observation := measurements[[2]string{str(ref["path"]), keyText(ref["key"])}]
			level := strings.SplitN(observation.identifier, "/", 2)[1]
			row := observation.row
			if file, found := row["file"]; found {
				files[str(file)] = true
				continue
			}
			if level == "file-pair" {
				files[str(row["left"])], files[str(row["right"])] = true, true
				continue
			}
			members := row["members"]
			if members == nil {
				members = []any{pickDefault(row, "node", row[level])}
			}
			for _, member := range stringsOf(members) {
				var known []string
				switch level {
				case "class":
					if file, mapped := classes[member]; mapped {
						known = []string{file}
					}
				case "package":
					known = packages[member]
				default:
					known = modules[member]
				}
				if len(known) == 0 {
					missing := record{"level": level, "object": member}
					unresolved[keyText(missing)] = missing
				}
				for _, path := range known {
					files[path] = true
				}
			}
		}
		scope := record{"files": keys(files)}
		if len(unresolved) > 0 {
			var values []record
			for _, key := range keys(unresolved) {
				values = append(values, unresolved[key])
			}
			scope["unresolved_objects"], scope["measurement_objects"] = values, refs
		}
		key := keyText(scope)
		group := provisional[key]
		if group == nil {
			group = &candidateGroup{scope: scope, attached: map[string]bool{}, overlaps: []record{}, families: record{}}
			provisional[key] = group
		}
		group.seeds = append(group.seeds, identity)
		group.attached[identity] = true
		scopes[identity] = scope
	}
	groups, byGroup := []*candidateGroup{}, map[string]*candidateGroup{}
	membership := map[string]map[string]bool{}
	for index, key := range keys(provisional) {
		group := provisional[key]
		group.identity = fmt.Sprintf("group-%04d", index+1)
		groups = append(groups, group)
		byGroup[group.identity] = group
		for _, path := range stringsOf(group.scope["files"]) {
			if membership[path] == nil {
				membership[path] = map[string]bool{}
			}
			membership[path][group.identity] = true
		}
	}
	for identity, scope := range scopes {
		paths := stringsOf(scope["files"])
		if len(paths) == 0 || scope["unresolved_objects"] != nil {
			continue
		}
		for groupID := range membership[paths[0]] {
			group := byGroup[groupID]
			contained := group.scope["unresolved_objects"] == nil
			for _, path := range paths[1:] {
				contained = contained && membership[path][groupID]
			}
			if contained {
				group.attached[identity] = true
			}
		}
	}
	intersections := map[edge][]string{}
	for _, path := range keys(membership) {
		identities := keys(membership[path])
		for index, left := range identities {
			for _, right := range identities[index+1:] {
				pair := edge{left, right}
				intersections[pair] = append(intersections[pair], path)
			}
		}
	}
	for pair, files := range intersections {
		left, right := byGroup[pair.from], byGroup[pair.to]
		left.overlaps = append(left.overlaps, record{"group": pair.to, "shared_files": files})
		right.overlaps = append(right.overlaps, record{"group": pair.from, "shared_files": files})
	}
	investigation := object(policy["investigation"])
	for _, group := range groups {
		group.evaluate(bySignal, sources, object(investigation["family_points"]))
	}
	queue := investigationQueue(groups, integer(investigation["candidate_group_limit"]))
	candidates := []record{}
	for _, group := range groups {
		candidates = append(candidates, group.result)
	}
	return map[string][]record{"rankings": rankings, "signals": signals, "candidate-groups": candidates, "investigation-queue": queue}
}

func signalReferences(identities []string) []record {
	refs := []record{}
	for _, identity := range identities {
		refs = append(refs, selectionReference("signals", "signal", identity))
	}
	return refs
}

func (group *candidateGroup) evaluate(signals map[string]record, sources map[string]bool, points record) {
	attached := keys(group.attached)
	limited := []string{}
	for _, identity := range attached {
		signal := signals[identity]
		name := evidenceFamilies[str(signal["family"])]
		family := object(group.families[name])
		if family == nil {
			family = record{"points": 0, "signals": []record{}}
			group.families[name] = family
		}
		family["points"] = max(integer(family["points"]), integer(points[str(signal["suitability"])]))
		family["signals"] = append(family["signals"].([]record), selectionReference("signals", "signal", identity))
		if signal["suitability"] != "usable" {
			limited = append(limited, identity)
		}
	}
	for _, family := range group.families {
		group.score += integer(object(family)["points"])
	}
	paths := stringsOf(group.scope["files"])
	missing := []string{}
	for _, path := range paths {
		if !sources[path] {
			missing = append(missing, path)
		}
	}
	limitations := []record{}
	if len(missing) > 0 {
		limitations = append(limitations, record{"reason": "Files are absent from the current source inventory", "files": missing})
	}
	if group.scope["unresolved_objects"] != nil {
		limitations = append(limitations, record{"reason": "Source mapping is incomplete; keep original measurement objects"})
	}
	if len(limited) > 0 {
		limitations = append(limitations, record{"reason": "Limited measurement evidence", "signals": limited})
	}
	sort.Slice(group.overlaps, func(i, j int) bool { return str(group.overlaps[i]["group"]) < str(group.overlaps[j]["group"]) })
	group.result = record{"group": group.identity, "scope": group.scope, "seed_signals": signalReferences(group.seeds),
		"signals": signalReferences(attached), "evidence_families": group.families, "investigation_score": group.score,
		"source_available": len(paths) > 0 && len(missing) == 0 && group.scope["unresolved_objects"] == nil, "limitations": limitations, "overlaps": group.overlaps}
}

func investigationQueue(groups []*candidateGroup, limit int) []record {
	queue := []record{}
	ordered := append([]*candidateGroup{}, groups...)
	sort.SliceStable(ordered, func(i, j int) bool { return ordered[i].score > ordered[j].score })
	covered, selectedCount := map[string]string{}, 0
	for index, group := range ordered {
		coveredBy := map[string]bool{}
		allCovered := true
		for _, seed := range group.seeds {
			if identity, found := covered[seed]; found {
				coveredBy[identity] = true
			} else {
				allCovered = false
			}
		}
		selected, reason := false, "Seed signals already included in selected groups; inspect before splitting"
		if !allCovered {
			clear(coveredBy)
			if selectedCount >= limit {
				reason = "Candidate group limit reached; absence from the shortlist is not evidence of safety"
			} else {
				selected, reason = true, "Next uncovered group by investigation score; equal scores use canonical scope order"
				selectedCount++
				for identity := range group.attached {
					if _, exists := covered[identity]; !exists {
						covered[identity] = group.identity
					}
				}
			}
		}
		queue = append(queue, record{"candidate_group": selectionReference("candidate-groups", "group", group.identity),
			"position": index + 1, "investigation_score": group.score, "selected": selected, "reason": reason,
			"covered_by": keys(coveredBy), "evidence_families": group.families})
	}
	return queue
}
