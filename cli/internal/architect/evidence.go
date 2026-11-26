package architect

import (
	"fmt"
	"io"
	"path/filepath"
)

func evidenceCommand(args options, stdout io.Writer) error {
	repository := args.get("repository")
	basis, err := reportOutput(args.get("collection"), repository, false)
	if err != nil {
		return err
	}
	root, err := resolve(repository)
	if err != nil {
		return err
	}
	directory := filepath.Dir(basis)
	if filepath.Base(basis) != "collection.json" || filepath.Dir(directory) != filepath.Join(root, "memory", "tech-debt", "audits") {
		return fmt.Errorf("Select collection.json in its audit directory")
	}
	output, err := reportOutput(args.get("output"), repository, false)
	if err != nil {
		return err
	}
	if !within(output, directory) {
		return fmt.Errorf("Save evidence in the same audit as the collection")
	}
	collection, err := readObject(basis)
	if err != nil {
		return err
	}
	if collection["status"] != "complete" {
		return fmt.Errorf("Evidence requires a completed collection")
	}
	var result record
	if args.has("group") {
		result, err = groupEvidence(collection, directory, args.get("group"))
	} else {
		for _, query := range []string{"files", "co-change", "dependencies"} {
			if args.has(query) {
				result, err = selectedEvidence(collection, directory, query, args[query])
				break
			}
		}
	}
	if err != nil {
		return err
	}
	if err := saveMetricJSON(output, repository, result); err != nil {
		return err
	}
	return printJSON(stdout, record{"output": output}, false)
}

func groupEvidence(collection record, directory, identity string) (record, error) {
	selection := func(name, field string, wanted []any) ([]record, error) {
		path := "selections/" + name + ".jsonl"
		descriptor := object(object(collection["selections"])[name])
		if descriptor == nil {
			return nil, fmt.Errorf("%s", quoted(name))
		}
		if descriptor["status"] != "complete" || descriptor["path"] != path {
			return nil, fmt.Errorf("Selection is unavailable: %s", name)
		}
		return readKeyedRows(directory, path, []string{field}, wanted)
	}
	groups, err := selection("candidate-groups", "group", []any{record{"group": identity}})
	if err != nil {
		return nil, err
	}
	group := groups[0]
	var signalKeys []any
	for _, value := range items(group["signals"]) {
		ref := object(value)
		if ref["path"] != "selections/signals.jsonl" {
			return nil, fmt.Errorf("Invalid signal reference in %s: %s", identity, pythonValue(value))
		}
		signalKeys = append(signalKeys, ref["key"])
	}
	signals, err := selection("signals", "signal", signalKeys)
	if err != nil {
		return nil, err
	}
	if signals == nil {
		signals = []record{}
	}
	var refs []record
	for _, signal := range signals {
		for _, ref := range items(signal["references"]) {
			refs = append(refs, object(ref))
		}
	}
	measurements, err := resolveMeasurements(refs, collection, directory)
	if err != nil {
		return nil, err
	}
	return record{"origin": selectionReference("candidate-groups", "group", identity), "candidate_group": group,
		"signals": signals, "measurements": measurements}, nil
}

func selectedEvidence(collection record, directory, query string, paths []string) (record, error) {
	files := map[string]bool{}
	for _, path := range paths {
		path, err := projectPath(path, "evidence file")
		if err != nil {
			return nil, err
		}
		files[path] = true
	}
	result := record{"files": keys(files)}
	switch query {
	case "files":
		measurements, outputs := []record{}, record{}
		for _, name := range []string{"source-files/file", "change-frequency/file", "line-coverage/file"} {
			rows, outcome, err := metricRows(collection, directory, name)
			if err != nil {
				return nil, err
			}
			outputs[name] = outcome
			for _, row := range rows {
				if files[str(row["file"])] {
					measurements = append(measurements, record{"reference": reference(name, row), "row": row})
				}
			}
		}
		result["outputs"], result["measurements"] = outputs, measurements
	case "co-change":
		if len(files) != 2 {
			return nil, fmt.Errorf("Co-change needs two distinct project-relative files")
		}
		name := "changes/commit"
		limit := object(object(object(collection["analysis_policy"])["measurements"])["history"])["maximum_changeset_size"]
		rows, outcome, err := metricRows(collection, directory, name)
		if err != nil {
			return nil, err
		}
		commits := []record{}
		for _, row := range rows {
			var changes []record
			for _, item := range items(row["changes"]) {
				change := object(item)
				if files[str(change["file"])] {
					changes = append(changes, change)
				}
			}
			if len(changes) == 2 {
				commits = append(commits, record{"reference": reference(name, row), "date": row["date"],
					"changeset_size": row["changeset_size"], "changes": changes, "included_in_coupling": numeric(row["changeset_size"]) <= numeric(limit)})
			}
		}
		result["output"], result["maximum_changeset_size"], result["commits"] = outcome, limit, commits
	case "dependencies":
		mappings, mappingOutcome, err := metricRows(collection, directory, "class-files/class")
		if err != nil {
			return nil, err
		}
		edges, edgeOutcome, err := metricRows(collection, directory, "dependencies/class")
		if err != nil {
			return nil, err
		}
		byClass, mappedFiles, unmapped := record{}, map[string]bool{}, map[string]bool{}
		for _, row := range mappings {
			byClass[str(row["class"])] = row["file"]
			mappedFiles[str(row["file"])] = true
		}
		selected := []record{}
		for _, edge := range edges {
			from, to := str(edge["from"]), str(edge["to"])
			for _, endpoint := range []string{from, to} {
				if byClass[endpoint] == nil {
					unmapped[endpoint] = true
				}
			}
			if files[str(byClass[from])] || files[str(byClass[to])] {
				selected = append(selected, record{"reference": reference("dependencies/class", edge), "from_file": byClass[from], "to_file": byClass[to]})
			}
		}
		mappingGaps := 0
		for _, gap := range items(collection["gaps"]) {
			if object(gap)["artifact"] == "mapping" {
				mappingGaps++
			}
		}
		result["outputs"] = record{"class-files/class": mappingOutcome, "dependencies/class": edgeOutcome}
		result["edges"], result["files_without_mapped_classes"] = selected, keyDiff(files, mappedFiles)
		result["mapping_gap_count"], result["unmapped_graph_class_count"] = mappingGaps, len(unmapped)
	}
	return result, nil
}
