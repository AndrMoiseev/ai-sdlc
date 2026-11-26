package apply

import (
	"fmt"
	"path"
	"sort"
	"strings"
)

func planDefinitions(plan mapping, kind string) []any {
	checks := []any{}
	for i, v := range array(plan["verification"]) {
		c := object(v)
		id := fmt.Sprintf("plan-%d", i+1)
		if kind == "refactoring" {
			id = str(plan["id"]) + "/" + str(c["id"])
		}
		m := addedCheck(mapping{"id": id, "criteria": c["criteria"], "source": "tasks.md", "location": c["location"], "run": c["run"]})
		if k, ok := c["execution_kind"]; ok {
			m["execution_kind"] = k
		}
		checks = append(checks, m)
	}
	return checks
}
func changedDefinitions(a, b []any) checkSet {
	out := checkSet{}
	for _, list := range [][]any{a, b} {
		for _, v := range list {
			id := str(object(v)["id"])
			if !checkSame(checkByID(a, id), checkByID(b, id)) {
				out[id] = true
			}
		}
	}
	return out
}
func projection(m mapping, fields string) mapping {
	out := mapping{}
	for _, k := range strings.Fields(fields) {
		if v, ok := m[k]; ok {
			if _, ok := v.([]any); ok {
				a := stringArray(v)
				sort.Strings(a)
				out[k] = a
			} else {
				out[k] = v
			}
		}
	}
	return out
}
func revisedTaskChecks(state, old, plan, basis, event mapping) (mapping, error) {
	fresh := object(checkClone(old))
	r := object(old["check_registry"])
	tr := object(r["transition"])
	pending := truth(tr) && intValue(r["revision"]) > intValue(r["confirmed_revision"])
	oldPlan := object(old["plan"])
	if pending {
		criteria := checkCriteria(array(old["checks"]))
		for _, k := range []string{"before", "after"} {
			criteria.add(checkCriteria(array(tr[k])))
		}
		permission := object(tr["basis"])
		criteria.add(checkIDs(permission["transitional_criteria"]))
		valid := checkSame(oldPlan["scope"], plan["scope"])
		for _, k := range []string{"preserves", "covers"} {
			valid = valid && checkSame(sortedSet(checkIDs(oldPlan[k])), sortedSet(checkIDs(plan[k])))
		}
		for k := range criteria {
			fields := "id task lifetime until_task replaced_by"
			valid = valid && checkSame(projection(object(object(state["acceptance"])[k]), fields), projection(checkByID(array(basis["acceptance"]), k), fields))
		}
		for _, k := range stringArray(permission["test_changes"]) {
			a, b := checkByID(array(oldPlan["test_changes"]), k), checkByID(array(plan["test_changes"]), k)
			fields := "id action criteria replacement_criteria decision"
			valid = valid && a != nil && b != nil && checkSame(projection(a, fields), projection(b, fields))
		}
		if !valid {
			return nil, reject("pending_registry_conflict", "Reconcile the pending registry transition at its valid basis or adjust the approved plan before revised_plan")
		}
	}
	before, after := planDefinitions(oldPlan, workKind(basis)), planDefinitions(plan, workKind(basis))
	changed := changedDefinitions(before, after)
	if truth(old["checks"]) && len(changed) > 0 {
		if pending {
			return nil, reject("pending_registry_conflict", "Preserve the pending registry transition before changing plan checks")
		}
		for _, h := range array(r["history"]) {
			t := object(object(h)["transition"])
			for id := range changedDefinitions(array(t["before"]), array(t["after"])) {
				if changed[id] {
					return nil, reject("registry_plan_conflict", "Preserve evolved check definitions; reconcile their approved transition before changing the plan")
				}
			}
		}
		for _, v := range array(old["checks"]) {
			k := str(object(v)["id"])
			if changed[k] && checkByID(before, k) == nil {
				return nil, reject("duplicate_check", "Revised plan check ID conflicts with a registered project obligation")
			}
		}
		checks := without(fresh["checks"], func(c mapping) bool { return changed[str(c["id"])] })
		for _, v := range after {
			if changed[str(object(v)["id"])] {
				checks = append(checks, v)
			}
		}
		fresh["checks"] = checks
		appendRegistry(fresh, event)
		h := array(object(fresh["check_registry"])["history"])
		object(h[len(h)-1])["basis_commit"] = basis["head"]
	}
	return fresh, nil
}
func followups(state, plans, p mapping) ([]any, error) {
	a, ok := checkValue(p, "completed_followups", []any{}).([]any)
	if !ok {
		return nil, reject("completed_followup", "completed_followups must be a list")
	}
	completed, targets := checkSet{}, checkSet{}
	resolved := []any{}
	tasks := object(state["tasks"])
	for _, v := range a {
		m := object(v)
		prior, target := str(m["completed_task"]), str(m["followup_task"])
		if !checkFields(m, "completed_task followup_task", "") || prior == "" || target == "" {
			return nil, reject("completed_followup", "Map the completed_task to its new followup_task")
		}
		t := object(tasks[prior])
		if t["status"] != "accepted" || !truth(t["commits"]) || truth(t["active_review"]) || truth(t["active_repair"]) {
			return nil, reject("completed_followup", "Only an accepted task without active work can receive a follow-up")
		}
		if completed[prior] || targets[target] || tasks[target] != nil || !includes(stringArray(object(plans[target])["depends_on"]), prior) {
			return nil, reject("completed_followup", "Each mapping needs a distinct newly appended dependent task")
		}
		n := len(resolved)
		for _, v := range array(state["blockers"]) {
			b := object(v)
			if b["task_id"] == prior && (b["reason"] == "review_limit_reached" || b["reason"] == "test_repair_limit_reached") {
				resolved = append(resolved, b)
			}
		}
		if n == len(resolved) {
			return nil, reject("completed_followup", "Name an existing completed-task budget stop")
		}
		completed[prior] = true
		targets[target] = true
	}
	return resolved, nil
}
func acceptedScope(state, plans, p mapping) (mapping, error) {
	a, ok := checkValue(p, "accepted_scope", []any{}).([]any)
	if !ok {
		return nil, reject("scope_decision", "accepted_scope must list explicit user decisions")
	}
	out := mapping{}
	for _, v := range a {
		d := object(v)
		id := str(d["task_id"])
		if !checkFields(d, "task_id text source", "") || !meaningful(id) || !meaningful(d["text"]) || !meaningful(d["source"]) {
			return nil, reject("scope_decision", "Record the actual user acceptance text, source and task ID")
		}
		t := object(object(state["tasks"])[id])
		w := object(t["worktree"])
		if out[id] != nil || t == nil || plans[id] == nil || t["status"] == "accepted" || !truth(t["candidate_commit"]) || w == nil || truth(w["integrated"]) || truth(w["removed"]) {
			return nil, reject("scope_candidate", "Freeze and retain the unfinished task result in its worktree before revising its scope")
		}
		if truth(t["procedures"]) || checkSame(t["plan"], plans[id]) {
			return nil, reject("scope_decision", "Finish pending checks and reformulate the task for the accepted scope")
		}
		s, e := snapshot(state, str(w["path"]))
		if e != nil {
			return nil, e
		}
		if e = cleanSource(s); e != nil {
			return nil, e
		}
		if s["commit"] != object(t["candidate_commit"])["sha"] {
			return nil, reject("scope_candidate", "The recorded current result must remain unchanged")
		}
		out[id] = d
	}
	return out, nil
}
func wholeDefinitions(records []any) []any {
	out := []any{}
	for _, v := range records {
		c := object(v)
		m := addedCheck(mapping{"id": c["id"], "criteria": c["criteria"], "source": "tasks.md", "location": c["location"], "run": c["run"], "setup_task": c["setup_task"]})
		if x, ok := c["execution_kind"]; ok {
			m["execution_kind"] = x
		}
		out = append(out, m)
	}
	return out
}
func revisedWhole(state, basis, event mapping) (mapping, error) {
	r := object(state["final_checks"])
	if !truth(r) {
		return nil, nil
	}
	r = object(checkClone(r))
	h := array(r["history"])
	if len(h) == 0 || intValue(r["revision"]) != len(h) || !checkSame(object(h[len(h)-1])["checks"], r["checks"]) {
		return nil, reject("final_registry_missing", "Register whole-result checks without a task owner")
	}
	if workKind(basis) != "refactoring" {
		return r, nil
	}
	prior := []any{}
	for _, v := range object(state["verification"]) {
		prior = append(prior, v)
	}
	before, after := wholeDefinitions(prior), wholeDefinitions(array(basis["verification"]))
	var additional []any
	for _, v := range array(r["checks"]) {
		id := str(object(v)["id"])
		if checkByID(before, id) == nil {
			if checkByID(after, id) != nil {
				return nil, reject("duplicate_check", "Approved whole check ID conflicts with a registered project obligation")
			}
			additional = append(additional, v)
		}
	}
	reserved := checkSet{}
	reserve := func(v any) {
		for _, c := range array(v) {
			reserved[str(object(c)["id"])] = true
		}
	}
	for _, v := range object(state["tasks"]) {
		t := object(v)
		reserve(t["checks"])
		for _, v := range array(object(t["check_registry"])["history"]) {
			m := object(v)
			reserve(m["checks"])
			reserve(object(m["transition"])["before"])
			reserve(object(m["transition"])["after"])
		}
	}
	for _, v := range array(basis["tasks"]) {
		m := object(v)
		for _, c := range array(m["verification"]) {
			reserved[str(m["id"])+"/"+str(object(c)["id"])] = true
		}
	}
	checks := []any{}
	for _, v := range after {
		id := str(object(v)["id"])
		if reserved[id] {
			return nil, reject("duplicate_check", "Approved whole check ID conflicts with a task registry or transition")
		}
		if old := checkByID(array(r["checks"]), id); old != nil && checkSame(checkByID(before, id), v) {
			v = old
		}
		checks = append(checks, v)
	}
	checks = append(checks, additional...)
	if !checkSame(checks, r["checks"]) {
		r["checks"] = checks
		n := intValue(r["revision"]) + 1
		r["revision"] = n
		r["history"] = append(h, mapping{"revision": n, "event_id": event["event_id"], "basis_commit": basis["head"], "checks": checkClone(checks)})
	}
	return r, nil
}
func replacePlan(state, event mapping, directory string) (any, error) {
	p := object(event["payload"])
	for _, v := range object(state["roles"]) {
		if object(v)["status"] == "active" {
			return nil, reject("active_roles", "Finish or reconcile active roles before replacing the basis")
		}
	}
	previousBasis := object(state["basis"])
	basis, e := validate(mapping{"project_root": previousBasis["project_root"], "change": state["change_id"], "instruction": p["instruction"], "work_kind": workKind(previousBasis)})
	if e != nil {
		return nil, e
	}
	if basis["head"] == previousBasis["head"] {
		return nil, reject("plan_unchanged", "Use resume when the approved basis is unchanged")
	}
	plans := mapping{}
	for _, v := range array(basis["tasks"]) {
		plans[str(object(v)["id"])] = v
	}
	scope, e := acceptedScope(state, plans, p)
	if e != nil {
		return nil, e
	}
	oldTasks := object(state["tasks"])
	completed := []any{}
	last := 0
	for _, k := range sortedKeys(oldTasks) {
		t := object(oldTasks[k])
		if t["status"] == "accepted" {
			if !checkSame(plans[k], t["plan"]) {
				return nil, reject("completed_task_changed", "Preserve completed task "+k+" unchanged; append follow-up work as a new task")
			}
			completed = append(completed, k)
		}
		last = max(last, intValue(object(t["plan"])["number"]), intValue(object(plans[k])["number"]))
	}
	appended := false
	for _, v := range array(basis["tasks"]) {
		plan := object(v)
		if oldTasks[str(plan["id"])] != nil {
			if appended {
				return nil, reject("new_tasks_append_only", "Append new tasks after all existing tasks")
			}
		} else {
			appended = true
			if intValue(plan["number"]) <= last {
				return nil, reject("new_tasks_append_only", "Number new tasks after the existing plan")
			}
		}
	}
	resolved, e := followups(state, plans, p)
	if e != nil {
		return nil, e
	}
	retained := mapping{}
	for k, v := range oldTasks {
		old := object(v)
		if plans[k] == nil {
			if truth(old["checks"]) {
				return nil, reject("registered_task_removed", "Preserve tasks with registered obligations in the revised plan")
			}
			continue
		}
		if old["status"] != "accepted" {
			r, e := revisedTaskChecks(state, old, object(plans[k]), basis, event)
			if e != nil {
				return nil, e
			}
			retained[k] = r
		}
	}
	whole, e := revisedWhole(state, basis, event)
	if e != nil {
		return nil, e
	}
	previous := str(state["run_id"])
	hasScope := len(scope) > 0
	archive := revisionArchive(previous, str(event["event_id"]), hasScope)
	store := execution{directory: directory}
	writePacked := func(rel string, m mapping) error {
		file, e := contained(directory, rel)
		if e != nil {
			return e
		}
		packed, e := store.pack(m, "", true)
		if e != nil {
			return e
		}
		return writeJSON(file, packed)
	}
	if e = writePacked(archive, state); e != nil {
		return nil, e
	}
	if !hasScope {
		id, e := randomID()
		if e != nil {
			return nil, e
		}
		state["run_id"] = id
		state["previous_run"] = previous
	}
	state["basis"] = basis
	if workKind(basis) == "refactoring" {
		state["work_kind"] = "refactoring"
		for _, k := range []string{"acceptance", "verification"} {
			m := mapping{}
			for _, v := range array(basis[k]) {
				m[str(object(v)["id"])] = v
			}
			state[k] = m
		}
	}
	if whole != nil {
		whole["procedures"] = mapping{}
		whole["failures"] = mapping{}
		state["final_checks"] = whole
	}
	tasks := mapping{}
	state["tasks"] = tasks
	for _, v := range array(basis["tasks"]) {
		plan := object(v)
		id := str(plan["id"])
		old := object(oldTasks[id])
		if old["status"] == "accepted" {
			tasks[id] = old
			continue
		}
		fresh := newTask(plan)
		if old != nil {
			packed, e := store.pack(old, "", true)
			if e != nil {
				return nil, e
			}
			ref, e := store.put(packed)
			if e != nil {
				return nil, e
			}
			historical := mapping{"$object": ref}
			ret := object(retained[id])
			if scope[id] != nil {
				fresh = ret
				fresh["scope_history"] = append(array(fresh["scope_history"]), mapping{"decision": scope[id], "prior_result": historical, "archive": archive})
				fresh["plan"] = plan
				fresh["status"] = "verifying"
				fresh["active_review"] = nil
				fresh["last_check_failed"] = false
				for _, k := range []string{"transfer", "active_reviewers", "review_basis"} {
					delete(fresh, k)
				}
			} else {
				for _, k := range strings.Fields("review_limit review_rounds_started review_rounds_completed test_repair_limit test_repair_cycles_started active_repair repair_cycles budget_decisions commits") {
					fresh[k] = old[k]
				}
				fresh["prior_result"] = historical
				for _, k := range strings.Fields("checks inventory check_registry evidence verification_results roles last_check_failed") {
					if v, ok := ret[k]; ok {
						fresh[k] = v
					}
				}
			}
		}
		tasks[id] = fresh
	}
	state["blockers"] = without(state["blockers"], func(b mapping) bool {
		if truth(p["completed_followups"]) {
			for _, v := range resolved {
				if checkSame(b, v) {
					return true
				}
			}
			return false
		}
		return b["reason"] != "review_limit_reached" && b["reason"] != "test_repair_limit_reached"
	})
	state["status"] = "active"
	if truth(state["blockers"]) {
		state["status"] = "blocked"
	}
	state["baseline"], e = snapshot(state, "")
	if e != nil {
		return nil, e
	}
	state["final"] = nil
	input := path.Join("runs", str(state["run_id"]), "input.json")
	reassess := "Completed tasks preserved; unfinished tasks require reassessment"
	if hasScope {
		input = path.Join(path.Dir(archive), "input.json")
		reassess = "User-selected current results retain execution evidence; revised criteria require fresh assessment"
	}
	if e = writePacked(input, basis); e != nil {
		return nil, e
	}
	out := mapping{"run_id": state["run_id"], "previous_run": previous, "preserved_tasks": completed, "accepted_scope": sortedKeys(scope), "archive": archive, "reassessment": reassess}
	if len(resolved) > 0 {
		out["resolved_completed_repairs"] = mapping{"mapping": p["completed_followups"], "removed_blockers": resolved, "authorization": p["instruction"]}
	}
	return out, nil
}
