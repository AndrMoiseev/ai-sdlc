package apply

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/AndrMoiseev/ai-sdlc/cli/internal/agent"
	"github.com/AndrMoiseev/ai-sdlc/cli/internal/check"
)

func workRoot(kind string) string {
	if kind == "refactoring" {
		return "refactoring"
	}
	return "changes"
}

func discoverWork(project string, kind, change any) (string, string, error) {
	candidates, descriptions := []mapping{}, []string{}
	if change != nil && (!workID.MatchString(str(change)) || len(str(change)) > 64) {
		return "", "", fmt.Errorf("Invalid change_id")
	}
	for _, candidateKind := range []string{"change", "refactoring"} {
		if kind != nil && candidateKind != kind {
			continue
		}
		parent, err := contained(project, filepath.Join("sdd", workRoot(candidateKind)))
		if err != nil {
			return "", "", err
		}
		entries, err := os.ReadDir(parent)
		if os.IsNotExist(err) {
			continue
		}
		if err != nil {
			return "", "", err
		}
		for _, entry := range entries {
			id := entry.Name()
			if !workID.MatchString(id) || len(id) > 64 || change != nil && id != change {
				continue
			}
			root, err := contained(parent, id)
			if err != nil {
				return "", "", err
			}
			if info, err := os.Stat(root); err != nil || !info.IsDir() {
				continue
			}
			hasPlan := existingFile(filepath.Join(root, "tasks.md"))
			if kind != nil && change == nil && !hasPlan {
				continue
			}
			candidates = append(candidates, mapping{"work_kind": candidateKind, "change_id": id})
			descriptions = append(descriptions, fmt.Sprintf("{'work_kind': %s, 'change_id': %s, 'change_root': %s, 'has_plan': %s}",
				pythonQuote(candidateKind), pythonQuote(id), pythonQuote(root), pythonRepr(hasPlan)))
		}
	}
	if len(candidates) != 1 {
		return "", "", reject("ambiguous_change", "Select work by work_kind and change_id: ["+strings.Join(descriptions, ", ")+"]")
	}
	return str(candidates[0]["work_kind"]), str(candidates[0]["change_id"]), nil
}

func validate(args mapping) (mapping, error) {
	projectRoot, err := fieldString(args, "project_root")
	if err != nil {
		return nil, err
	}
	absolute, err := filepath.Abs(projectRoot)
	if err != nil {
		return nil, err
	}
	project, err := filepath.EvalSymlinks(absolute)
	if err != nil {
		return nil, fileError(err, absolute)
	}
	instruction := object(args["instruction"])
	if !truth(instruction["text"]) || !truth(instruction["source"]) {
		return nil, reject("execution_instruction", "Record the user's explicit execution instruction and its source; plan approval alone does not authorize execution")
	}
	kind, exists := args["work_kind"]
	if !exists {
		kind = "change"
	}
	if kind != nil && kind != "change" && kind != "refactoring" {
		return nil, reject("work_kind", "Expected change, refactoring or null for discovery")
	}
	change := str(args["change"])
	if kind == nil || args["change"] == nil {
		discoveredKind, discoveredID, err := discoverWork(project, kind, args["change"])
		if err != nil {
			return nil, err
		}
		kind, change = discoveredKind, discoveredID
	}
	if !workID.MatchString(change) || len(change) > 64 {
		return nil, fmt.Errorf("change_id must be lowercase-kebab-case, at most 64 characters")
	}
	changeRoot, err := contained(project, filepath.Join("sdd", workRoot(str(kind)), change))
	if err != nil {
		return nil, err
	}
	plan := filepath.Join(changeRoot, "tasks.md")
	if !existingFile(plan) {
		return nil, reject("missing_plan", "Return to sdd-spec for an approved plan")
	}
	report, exit := check.Run(project, change, "plan", str(kind))
	reportRaw, err := jsonBytes(report, "")
	if err != nil {
		return nil, err
	}
	decoded, err := decode(reportRaw)
	if err != nil {
		return nil, err
	}
	report = object(decoded)
	if exit != 0 {
		var ordered bytes.Buffer
		if err := json.Indent(&ordered, []byte(dashboardJSON(report, "check_report")), "", "  "); err != nil {
			return nil, err
		}
		return nil, reject("sdd_check", ordered.String()+"\n")
	}
	if intValue(report["schema_version"]) != 2 || object(report["approval_status"])["ready"] != true {
		return nil, reject("approval_missing", "Document bundle including the plan: "+pythonRecord(report, "check_report"))
	}
	checkpoint := object(report["checkpoint_status"])
	if checkpoint["status"] != "ready" {
		return nil, reject("checkpoint_not_ready", "accept a clean checkpoint before execution: "+pythonRecord(checkpoint, "checkpoint_status"))
	}
	for _, warning := range array(report["warnings"]) {
		if object(warning)["code"] == "state_recovery" {
			return nil, reject("state_recovery", "Recover sdd-spec checkpoint first")
		}
	}
	records, err := check.TaskRecords(plan, str(kind))
	if err != nil {
		return nil, err
	}
	basis := mapping{"schema_version": 2, "project_root": project, "work_kind": kind, "change_id": change, "change_root": changeRoot, "instruction": instruction}
	normative, err := filepath.Rel(project, changeRoot)
	if err != nil {
		return nil, err
	}
	unmerged, err := gitText(project, "ls-files", "--unmerged")
	if err != nil {
		return nil, err
	}
	if unmerged != "" {
		return nil, reject("unmerged_index", "Resolve the existing Git conflict before execution")
	}
	source, err := gitStatus(project, []string{filepath.ToSlash(filepath.Join(normative, "execution"))}, false)
	if err != nil {
		return nil, err
	}
	if !truth(source["branch"]) {
		return nil, reject("git_failed", "Execution requires a named branch")
	}
	for _, ident := range []string{"GIT_AUTHOR_IDENT", "GIT_COMMITTER_IDENT"} {
		if _, err := gitText(project, "var", ident); err != nil {
			return nil, err
		}
	}
	if source["head"] != checkpoint["head"] || len(stringArray(source["dirty_paths"])) != 0 {
		return nil, reject("checkpoint_changed", "Checkpoint changed during admission; inspect and retry")
	}
	basis["head"], basis["branch"], basis["tasks"] = source["head"], source["branch"], []any{}
	if kind == "refactoring" {
		basis["acceptance"], basis["verification"] = []any{}, []any{}
	}
	for _, record := range records {
		field := str(record["sdd_record"])
		if field == "task" {
			field = "tasks"
		}
		if prior, exists := basis[field]; exists && array(prior) != nil {
			basis[field] = append(array(prior), record)
		}
	}
	return basis, nil
}

func newTask(plan mapping) mapping {
	return mapping{"plan": plan, "status": "pending", "attempt": 0, "evidence": []any{}, "verification_results": []any{},
		"reviews": []any{}, "commits": []any{}, "blockers": []any{}, "review_limit": 3, "review_rounds_started": 0,
		"review_rounds_completed": 0, "active_review": nil, "test_repair_limit": 5, "test_repair_cycles_started": 0,
		"active_repair": nil, "repair_cycles": []any{}, "budget_decisions": []any{}, "checks": []any{}, "worktree": nil,
		"roles": []any{}, "paths": []any{}}
}

func initialize(args mapping) (any, error) {
	basis, err := validate(args)
	if err != nil {
		return nil, err
	}
	if !truth(args["isolation"]) {
		return nil, reject("isolation_required", "Execution requires isolated task worktrees")
	}
	directory, err := executionPath(basis)
	if err != nil {
		return nil, err
	}
	if !samePath(filepath.Dir(directory), str(basis["change_root"])) {
		return nil, reject("change_root", "Input root mismatch")
	}
	e := &execution{directory: directory}
	_, err = withLock(directory, func() (any, error) {
		if _, err := os.Stat(filepath.Join(directory, "state.json")); err == nil {
			return nil, reject("already_started", "Use resume for existing execution")
		} else if !os.IsNotExist(err) {
			return nil, err
		}
		run, err := randomID()
		if err != nil {
			return nil, err
		}
		tasks := mapping{}
		for _, record := range array(basis["tasks"]) {
			task := object(record)
			tasks[str(task["id"])] = newTask(task)
		}
		state := mapping{"schema_version": 3, "change_id": basis["change_id"], "run_id": run, "revision": 0, "status": "active",
			"basis": basis, "tasks": tasks, "roles": mapping{}, "event_head": nil, "event_index": nil,
			"blockers": []any{}, "updated_at": now(), "final": nil, "execution_head": basis["head"]}
		if workKind(basis) == "refactoring" {
			state["work_kind"] = "refactoring"
			for _, kind := range []string{"acceptance", "verification"} {
				byID := mapping{}
				for _, raw := range array(basis[kind]) {
					record := object(raw)
					byID[str(record["id"])] = record
				}
				state[kind] = byID
			}
		}
		state["baseline"], err = snapshot(state, "")
		if err != nil {
			return nil, err
		}
		packed, err := e.pack(basis, "", true)
		if err != nil {
			return nil, err
		}
		if err := writeJSON(filepath.Join(directory, "runs", run, "input.json"), packed); err != nil {
			return nil, err
		}
		return nil, e.save(state)
	})
	if err != nil {
		return nil, err
	}
	opened, err := openExecution(directory)
	if err != nil {
		return nil, err
	}
	if _, err := opened.render(); err != nil {
		return nil, err
	}
	return opened.manifest, nil
}

func (e *execution) resolveAgent(args mapping) (any, error) {
	kind, err := fieldString(args, "kind")
	if err != nil {
		return nil, err
	}
	host, err := fieldString(args, "host")
	if err != nil {
		return nil, err
	}
	basis, err := e.openReference(e.manifest["basis"])
	if err != nil {
		return nil, err
	}
	options := mapping{}
	for _, name := range []string{"parent_model", "parent_effort", "native_inheritance", "user_agent_dir", "available_agents"} {
		if value, exists := args[name]; exists {
			options[name] = value
		}
	}
	return agent.Resolve(str(object(basis)["project_root"]), "sdd-apply."+kind, host, options)
}
