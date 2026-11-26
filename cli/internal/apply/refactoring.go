package apply

import (
	"bytes"
	"path/filepath"
	"strings"

	"github.com/yuin/goldmark"
	"github.com/yuin/goldmark/ast"
	mdtext "github.com/yuin/goldmark/text"
	"go.yaml.in/yaml/v3"
)

func recordsAtHead(basis mapping, name string) ([]mapping, error) {
	paths, err := documentPaths(basis)
	if err != nil {
		return nil, err
	}
	if !includes(paths, name) {
		return nil, reject("basis_paths", "Document is outside the plan at project HEAD")
	}
	root := str(basis["project_root"])
	path, err := contained(str(basis["change_root"]), name)
	if err != nil {
		return nil, err
	}
	relative, err := filepath.Rel(root, path)
	if err != nil {
		return nil, err
	}
	revisionPath := "HEAD:" + filepath.ToSlash(relative)
	source := gitCommand(root, nil, "show", revisionPath).stdout
	source = bytes.TrimPrefix(source, []byte{0xef, 0xbb, 0xbf})
	if len(bytes.TrimSpace(source)) == 0 {
		return nil, reject("basis_document_missing", "Plan document unavailable at project HEAD: "+name)
	}
	doc := goldmark.DefaultParser().Parse(mdtext.NewReader(source))
	records := []mapping{}
	err = ast.Walk(doc, func(node ast.Node, enter bool) (ast.WalkStatus, error) {
		fence, isFence := node.(*ast.FencedCodeBlock)
		if !enter || !isFence || fence.Info == nil || strings.TrimSpace(string(fence.Info.Text(source))) != "yaml" {
			return ast.WalkContinue, nil
		}
		var data bytes.Buffer
		lines := fence.Lines()
		for index := 0; index < lines.Len(); index++ {
			line := lines.At(index)
			data.Write(line.Value(source))
		}
		var record any
		if err := yaml.Unmarshal(data.Bytes(), &record); err != nil {
			return ast.WalkStop, err
		}
		if result := object(record); result["sdd_record"] != nil {
			records = append(records, result)
		}
		return ast.WalkContinue, nil
	})
	return records, err
}

func refactoringContext(state, task mapping, directory string) (mapping, error) {
	basis := object(state["basis"])
	design, err := recordsAtHead(basis, "design.md")
	if err != nil {
		return nil, err
	}
	plan := object(task["plan"])
	criteria := append(taskCriteria(state, task), stringArray(plan["contributes_to"])...)
	testChanges := checkValue(plan, "test_changes", []any{})
	decisions := []string{}
	for _, value := range array(testChanges) {
		change := object(value)
		criteria = append(criteria, stringArray(change["criteria"])...)
		criteria = append(criteria, stringArray(change["replacement_criteria"])...)
		if decision := str(change["decision"]); decision != "" {
			decisions = append(decisions, decision)
		}
	}
	related, acceptance := []any{}, []any{}
	for _, record := range design {
		if includes(criteria, str(record["id"])) || includes(decisions, str(record["id"])) ||
			record["sdd_record"] == "decision" && ownedIntersection(criteria, stringArray(record["criteria"]), false) {
			related = append(related, record)
		}
	}
	for _, id := range sortedKeys(object(state["acceptance"])) {
		value := object(object(state["acceptance"])[id])
		if value["task"] == plan["id"] {
			acceptance = append(acceptance, value)
		}
	}
	sources := mapping{}
	for _, name := range []string{"proposal.md", "design.md", "tasks.md"} {
		sources[name] = filepath.Join(str(basis["change_root"]), name)
	}
	evolution := mapping{"groups": testChanges, "checks": []any{}, "transition": nil, "confirmed_revision": nil}
	var registryView, baselineView any
	if registry := object(task["check_registry"]); truth(registry) {
		checks, err := registryChecks(state, task, directory)
		if err != nil {
			return nil, err
		}
		evolution["checks"], evolution["transition"], evolution["confirmed_revision"] = checks, registry["transition"], registry["confirmed_revision"]
		history := []any{}
		for _, value := range array(registry["history"]) {
			entry := object(value)
			summary := selectFields(entry, "revision", "event_id", "operation")
			summary["checks_hash"] = digest(entry["checks"])
			history = append(history, summary)
		}
		registryView = mapping{"revision": registry["revision"], "history": history}
	}
	if baseline := object(task["baseline_checks"]); truth(baseline) {
		outputs := []any{}
		for _, value := range array(baseline["outputs"]) {
			summary := mapping{}
			for _, key := range []string{"check_id", "outcome", "command", "exit_code"} {
				if item, exists := object(value)[key]; exists {
					summary[key] = item
				}
			}
			outputs = append(outputs, summary)
		}
		baselineView = mapping{"role_id": baseline["role_id"], "registry_revision": baseline["registry_revision"],
			"log": object(task["baseline_event"])["log"], "outputs": outputs}
	}
	return mapping{"scope": plan["scope"], "acceptance": acceptance, "preserves": plan["preserves"], "contributes_to": plan["contributes_to"],
		"preservation_reason": plan["preservation_reason"], "test_changes": testChanges, "test_evolution": evolution, "design": related,
		"sources": sources, "check_registry": registryView, "baseline": baselineView,
		"whole_result": "contributes_to records scope of contribution; local acceptance does not prove the whole result"}, nil
}
