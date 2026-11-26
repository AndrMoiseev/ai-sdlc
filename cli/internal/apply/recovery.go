package apply

import (
	"os"
	"path"
	"sort"
	"strings"
)

func without(items any, remove func(mapping) bool) []any {
	out := []any{}
	for _, v := range array(items) {
		if !remove(object(v)) {
			out = append(out, v)
		}
	}
	return out
}
func sortedSet(s checkSet) []string {
	out := []string{}
	for k := range s {
		out = append(out, k)
	}
	sort.Strings(out)
	return out
}
func basisProblem(s mapping) string {
	if checkHas(s, "manifest") || intValue(s["schema_version"]) != 2 {
		return "Reconcile legacy document manifests into the current execution basis"
	}
	if !gitOID.MatchString(str(s["head"])) {
		return "Execution basis needs its admission commit OID"
	}
	return ""
}
func finalizeExecution(state, p mapping) (any, error) {
	basis := object(state["basis"])
	root := str(basis["project_root"])
	head, e := gitText(root, "rev-parse", "HEAD")
	if e != nil {
		return nil, e
	}
	blockers := without(state["blockers"], func(b mapping) bool {
		return b["reason"] == "final_incomplete" || b["reason"] == "completion_incomplete"
	})
	state["blockers"] = blockers
	missing := []any{}
	for _, v := range blockers {
		b := object(v)
		missing = append(missing, mapping{"reason": b["reason"], "criteria": []any{}, "task_id": b["task_id"]})
	}
	s, e := snapshot(state, root)
	if e == nil {
		e = cleanSource(s)
	}
	if e == nil && (head != state["execution_head"] || s["branch"] != basis["branch"]) {
		e = reject("execution_reconciliation", "Reconcile the execution branch before completion")
	}
	if e != nil {
		missing = append(missing, mapping{"criteria": []any{}, "reason": e.Error()})
	}
	tasks := object(state["tasks"])
	accepted := checkSet{}
	evidence, conclusions := []any{}, []any{}
	recs := technicalDebt(state)
	commits := mapping{}
	for _, k := range sortedKeys(tasks) {
		t := object(tasks[k])
		criteria := taskCriteria(state, t)
		sort.Strings(criteria)
		commits[k] = t["commits"]
		if t["status"] != "accepted" || !truth(t["commits"]) {
			missing = append(missing, mapping{"task_id": k, "criteria": criteria, "reason": "task_not_accepted"})
			continue
		}
		var err error
		for _, v := range array(t["commits"]) {
			if err = confirmCommit(state, t, object(v)); err != nil {
				break
			}
		}
		var result mapping
		for _, v := range array(t["verification_results"]) {
			r := object(v)
			if r["stage"] == "independent" || r["stage"] == "integration" {
				result = r
			}
		}
		if err == nil && result["outcome"] != "passed" {
			err = reject("verification_missing", "Accepted task must retain its passed conclusion")
		}
		if err == nil {
			err = reviewed(t)
		}
		if err != nil {
			missing = append(missing, mapping{"task_id": k, "criteria": criteria, "reason": err.Error()})
			continue
		}
		for _, c := range criteria {
			accepted[c] = true
		}
		for _, v := range array(t["evidence"]) {
			if object(v)["stage"] == result["stage"] {
				evidence = append(evidence, v)
			}
		}
		entry := copyMapping(result)
		entry["task_id"] = k
		conclusions = append(conclusions, entry)
	}
	for _, v := range missing {
		for _, k := range stringArray(object(v)["criteria"]) {
			delete(accepted, k)
		}
	}
	decisions := p["recommendation_decisions"]
	if decisions == nil {
		ds := []any{}
		for _, v := range recs {
			ds = append(ds, mapping{"finding_id": object(v)["finding_id"], "action": "defer", "reason": "Await explicit user approval after plan completion"})
		}
		decisions = ds
	}
	a, ok := decisions.([]any)
	if !ok {
		return nil, reject("recommendation_decisions", "Decisions must be objects")
	}
	wanted := checkSet{}
	for _, v := range recs {
		wanted[str(object(v)["finding_id"])] = true
	}
	valid := len(a) == len(recs)
	for _, v := range a {
		d := object(v)
		if d == nil {
			return nil, reject("recommendation_decisions", "Decisions must be objects")
		}
		key := str(d["finding_id"])
		valid = valid && wanted[key] && truth(d["reason"]) && (d["action"] == "defer" || d["action"] == "reject")
		delete(wanted, key)
	}
	if !valid {
		return nil, reject("recommendation_decisions", "Identify each finding; defer debt or record rejection. Fixes require explicit user approval as follow-up after completion")
	}
	unassessed := checkSet{}
	for _, v := range object(state["verification"]) {
		for k := range checkIDs(object(v)["criteria"]) {
			if !accepted[k] {
				unassessed[k] = true
			}
		}
	}
	result, status := "complete", "completed"
	if len(missing) > 0 {
		result, status = "partial", "blocked"
		state["blockers"] = append(blockers, mapping{"reason": "completion_incomplete", "resume_condition": "Accept remaining tasks or reconcile execution state", "missing": missing})
	}
	final := mapping{"head": head, "time": now(), "accepted_criteria": sortedSet(accepted), "missing": missing, "evidence": evidence, "verification_results": conclusions, "unassessed_criteria": sortedSet(unassessed), "recommendations": recs, "decisions": decisions, "commits": commits, "result": result}
	state["final"] = final
	state["status"] = status
	return final, nil
}
func recoveredRegistries(state mapping) (mapping, error) {
	out := mapping{}
	if workKind(object(state["basis"])) != "refactoring" {
		return out, nil
	}
	for id, v := range object(state["tasks"]) {
		t := object(v)
		r := object(t["check_registry"])
		if len(r) == 0 {
			continue
		}
		if e := checkRegistryCurrent(state, t); e != nil {
			return nil, e
		}
		confirmed := intValue(r["confirmed_revision"])
		checks := any([]any{})
		if confirmed > 0 {
			checks = object(array(r["history"])[confirmed-1])["checks"]
		}
		var pending any
		if truth(r["transition"]) && intValue(r["revision"]) > confirmed {
			pending = r["transition"]
		}
		out[id] = mapping{"revision": r["revision"], "confirmed_revision": confirmed, "confirmed_checks": checks, "pending_transition": pending}
	}
	return out, nil
}
func abandonProcedures(state, task, prev, next, res, event mapping, directory string) error {
	pending := object(task["procedures"])
	expected := checkSet{}
	for k, v := range pending {
		if object(v)["role_id"] == prev["role_id"] {
			expected[k] = true
		}
	}
	supplied := checkValue(res, "abandon_procedures", []any{})
	if !checkList(supplied, true) || !checkSame(sortedSet(expected), sortedSet(checkIDs(supplied))) {
		return reject("procedure_reconciliation", "Explicitly list every unfinished predecessor check in abandon_procedures")
	}
	for _, k := range sortedSet(expected) {
		attempt := object(pending[k])
		record := copyMapping(attempt)
		record["check_id"] = k
		record["outcome"] = "abandoned"
		record["successor"] = next["role_id"]
		record["resolution"] = res
		record["trace"] = object(event["payload"])["host_trace"]
		rel := strings.TrimSuffix(checkLogPath(state, task, event), ".json") + "-" + digest(k)[:16] + ".json"
		p, e := contained(directory, rel)
		if e != nil {
			return e
		}
		if e = writeJSON(p, record); e != nil {
			return e
		}
		raw, e := os.ReadFile(p)
		if e != nil {
			return e
		}
		task["evidence"] = append(array(task["evidence"]), mapping{"check_id": k, "stage": attempt["stage"], "role_id": prev["role_id"], "outcome": "abandoned", "procedure": true, "log": rel, "log_hash": digest(raw), "head": object(attempt["before"])["commit"]})
		delete(pending, k)
		state["final"] = nil
	}
	return nil
}
func resumeExecution(state, event mapping, directory string) (any, error) {
	p := object(event["payload"])
	regs, e := recoveredRegistries(state)
	if e != nil {
		return nil, e
	}
	issues := []any{}
	if problem := basisProblem(object(state["basis"])); problem != "" {
		issues = append(issues, mapping{"reason": "normative_drift", "detail": problem, "resume_condition": "Reconcile the approved plan through revised_plan; preserve current work"})
	} else {
		state["blockers"] = without(state["blockers"], func(b mapping) bool { return b["reason"] == "normative_drift" })
	}
	source, e := executionSource(state)
	if e != nil {
		return nil, e
	}
	state["blockers"] = without(state["blockers"], func(b mapping) bool {
		return b["reason"] == "execution_dirty" || b["reason"] == "execution_head_changed"
	})
	if len(stringArray(source["dirty_paths"])) > 0 {
		issues = append(issues, mapping{"reason": "execution_dirty", "paths": source["dirty_paths"], "resume_condition": "Preserve changes; obtain the user's commit or discard decision and restore a clean main tree"})
	}
	if source["head"] != state["execution_head"] {
		issues = append(issues, mapping{"reason": "execution_head_changed", "head": source["head"], "expected_head": state["execution_head"], "resume_condition": "Inspect the new HEAD and record compatibility with the execution instruction; changed scope requires revised_plan"})
	}
	if source["branch"] != object(state["basis"])["branch"] {
		issues = append(issues, mapping{"reason": "branch_changed", "resume_condition": "Restore execution branch"})
	}
	_, ok := p["live_contexts"].([]any)
	if !truth(p["host_trace"]) || !ok {
		return nil, reject("host_observation", "Supply actual host role liveness observation")
	}
	roles, tasks := object(state["roles"]), object(state["tasks"])
	for _, key := range sortedKeys(roles) {
		r := object(roles[key])
		if r["status"] != "active" || includes(stringArray(p["live_contexts"]), str(r["context_id"])) {
			continue
		}
		r["status"] = "lost"
		t := object(tasks[str(r["task_id"])])
		issue := mapping{"reason": "lost_role", "role_id": r["role_id"], "task_id": r["task_id"]}
		if t == nil && r["kind"] == "explorer" {
			issue["resume_condition"] = "Register a fresh run-level successor of the same role kind"
			issues = append(issues, issue)
		}
		if t != nil && (t["status"] != "pending" && t["status"] != "accepted" || r["kind"] == "explorer") {
			if t["status"] != "blocked" && t["status"] != "pending" && t["status"] != "accepted" {
				t["before_block"] = t["status"]
				t["status"] = "blocked"
			}
			issue["resume_condition"] = "Register a fresh successor with preserved files and task packet"
			t["blockers"] = append(array(t["blockers"]), issue)
			issues = append(issues, issue)
		}
	}
	for _, v := range issues {
		found := false
		for _, b := range array(state["blockers"]) {
			found = found || checkSame(b, v)
		}
		if !found {
			state["blockers"] = append(array(state["blockers"]), v)
		}
	}
	for _, v := range array(p["resolutions"]) {
		r := object(v)
		reason := str(r["reason"])
		if !truth(r["evidence"]) || includes([]string{"review_limit_reached", "test_repair_limit_reached", "normative_drift", "spec_conflict"}, reason) {
			return nil, reject("resume_resolution", "Use the dedicated operation for this blocker")
		}
		if reason == "execution_dirty" {
			return nil, reject("resume_resolution", "A dirty main tree must be reconciled before resuming")
		}
		if reason == "execution_head_changed" {
			if len(stringArray(source["dirty_paths"])) > 0 || r["head"] != source["head"] || r["compatible"] != true {
				return nil, reject("resume_acceptance", "Record inspected evidence and compatibility for this exact clean HEAD")
			}
			state["execution_head"] = source["head"]
			issues = without(issues, func(b mapping) bool { return b["reason"] == reason })
		}
		var lost any
		var successor mapping
		if reason == "lost_role" {
			successor = object(roles[str(r["successor"])])
			if successor["status"] != "active" || !truth(successor["successor_of"]) || successor["task_id"] != r["task_id"] {
				return nil, reject("successor_required", "Register a fresh successor first")
			}
			lost = checkValue(r, "role_id", successor["successor_of"])
			prev := object(roles[str(lost)])
			if prev["status"] != "lost" || successor["successor_of"] != lost || prev["task_id"] != successor["task_id"] || prev["kind"] != successor["kind"] || prev["lens_id"] != successor["lens_id"] {
				return nil, reject("successor_required", "Successor must replace the named lost role with the same task and kind")
			}
			found := false
			for _, v := range array(state["blockers"]) {
				b := object(v)
				found = found || (b["reason"] == reason && b["task_id"] == r["task_id"] && b["role_id"] == lost)
			}
			if !found {
				return nil, reject("successor_required", "No unresolved loss for this role")
			}
			if prev["task_id"] != nil {
				if e := abandonProcedures(state, object(tasks[str(prev["task_id"])]), prev, successor, r, event, directory); e != nil {
					return nil, e
				}
			}
		}
		resolved := func(b mapping) bool {
			return b["reason"] == reason && checkValue(b, "task_id", r["task_id"]) == r["task_id"] && (lost == nil || b["role_id"] == lost)
		}
		state["blockers"] = without(state["blockers"], func(b mapping) bool { return b["task_id"] == r["task_id"] && resolved(b) })
		t := object(tasks[str(r["task_id"])])
		if t != nil {
			if reason == "lost_role" {
				if successor["kind"] == "executor" {
					t["executor"] = successor["role_id"]
				}
				if successor["kind"] == "reviewer" && truth(t["active_review"]) {
					l := str(successor["lens_id"])
					reviewers := object(t["active_reviewers"])
					if reviewers[l] == lost {
						reviewers[l] = successor["role_id"]
					}
				}
			}
			t["blockers"] = without(t["blockers"], resolved)
			if !truth(t["blockers"]) && t["status"] == "blocked" {
				target := checkValue(t, "before_block", "running")
				if target == "accepted" {
					if _, e := validTaskEvidence(state, t, directory, ""); e != nil {
						return nil, e
					}
					if e := reviewed(t); e != nil {
						return nil, e
					}
					commits := array(t["commits"])
					if len(commits) == 0 {
						return nil, reject("commit_required", "Accepted task needs confirmed commits")
					}
					if e := confirmCommit(state, t, object(commits[len(commits)-1])); e != nil {
						return nil, e
					}
				}
				t["status"] = target
			}
		}
	}
	state["status"] = "active"
	if truth(state["blockers"]) {
		state["status"] = "blocked"
	}
	stale := []any{}
	for _, id := range sortedKeys(tasks) {
		t := object(tasks[id])
		w := object(t["worktree"])
		if t["status"] != "accepted" && w != nil && !truth(w["integrated"]) && !truth(w["removed"]) && w["base"] != source["head"] {
			stale = append(stale, mapping{"task_id": id, "path": w["path"], "base": w["base"], "head": source["head"], "next": "worktree_refresh"})
		}
	}
	out := mapping{"status": state["status"], "issues": issues, "preserved_roles": roles, "stale_worktrees": stale}
	if len(regs) > 0 {
		out["check_registries"] = regs
	}
	return out, nil
}
func recoveryEvent(state, task, event mapping, directory string) (any, error) {
	switch event["type"] {
	case "resume":
		return resumeExecution(state, event, directory)
	case "revised_plan":
		return replacePlan(state, event, directory)
	default:
		return finalizeExecution(state, object(event["payload"]))
	}
}
func revisionArchive(run, event string, scope bool) string {
	if scope {
		return path.Join("runs", run, "plan-revisions", event, "state.json")
	}
	return path.Join("runs", run, "superseded-state.json")
}
