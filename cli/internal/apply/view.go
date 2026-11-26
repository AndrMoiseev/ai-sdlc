package apply

import (
	"sort"
	"strings"
	"sync"
)

func stringArray(value any) []string {
	if strings, ok := value.([]string); ok {
		return strings
	}
	items := array(value)
	result := make([]string, 0, len(items))
	for _, item := range items {
		result = append(result, str(item))
	}
	return result
}

func includes(items []string, value string) bool {
	for _, item := range items {
		if item == value {
			return true
		}
	}
	return false
}

func taskOrder(tasks mapping) []string {
	ordered := sortedKeys(tasks)
	sort.SliceStable(ordered, func(i, j int) bool {
		return intValue(object(object(tasks[ordered[i]])["plan"])["number"]) <
			intValue(object(object(tasks[ordered[j]])["plan"])["number"])
	})
	return ordered
}

func activeTask(task mapping) bool {
	return task["status"] != "pending" && task["status"] != "accepted"
}

func incompatible(left, right mapping) bool {
	return includes(stringArray(left["cannot_parallel_with"]), str(right["id"])) ||
		includes(stringArray(right["cannot_parallel_with"]), str(left["id"]))
}

func available(state mapping) []string {
	result := []string{}
	if state["status"] != "active" || truth(state["blockers"]) {
		return result
	}
	tasks := object(state["tasks"])
	for _, id := range taskOrder(tasks) {
		task := object(tasks[id])
		if task["status"] != "pending" {
			continue
		}
		plan := object(task["plan"])
		admissible := true
		for _, dependency := range stringArray(plan["depends_on"]) {
			if object(tasks[dependency])["status"] != "accepted" {
				admissible = false
				break
			}
		}
		for otherID, value := range tasks {
			other := object(value)
			if otherID != id && activeTask(other) && incompatible(plan, object(other["plan"])) {
				admissible = false
				break
			}
		}
		if admissible {
			result = append(result, id)
		}
	}
	return result
}

func (e *execution) schedulerState() (mapping, error) {
	state := selectFields(e.manifest, "status", "blockers")
	if state["status"] != "active" || truth(state["blockers"]) {
		return state, nil
	}
	tasks, err := e.openReference(e.manifest["tasks"])
	if err != nil {
		return nil, err
	}
	result := make(mapping)
	for id, raw := range object(tasks) {
		value, err := e.openReference(raw)
		if err != nil {
			return nil, err
		}
		task := object(value)
		plan, err := e.openReference(task["plan"])
		if err != nil {
			return nil, err
		}
		result[id] = mapping{"status": task["status"], "plan": plan}
	}
	state["tasks"] = result
	return state, nil
}

func explorerAssignments(state mapping) []any {
	roles := object(state["roles"])
	order := sortedKeys(roles)
	sort.SliceStable(order, func(i, j int) bool {
		return intValue(object(roles[order[i]])["registered_revision"]) < intValue(object(roles[order[j]])["registered_revision"])
	})
	results := []any{}
	latest := map[[3]string]int{}
	for _, id := range order {
		role := object(roles[id])
		if role["kind"] != "explorer" {
			continue
		}
		assign := object(role["assignment"])
		key := [3]string{str(role["task_id"]), str(assign["kind"]), str(assign["stage"])}
		value := selectFields(role, "role_id", "status", "successor_of")
		for field, item := range selectFields(assign, "scope", "kind", "stage") {
			value[field] = item
		}
		if index, exists := latest[key]; exists {
			results[index] = value
		} else {
			latest[key] = len(results)
			results = append(results, value)
		}
	}
	return results
}

func (e *execution) projectState(dashboard bool) (mapping, error) {
	state, err := e.hydratedFields(e.manifest, "change_id", "run_id", "revision", "status", "updated_at", "blockers")
	if err != nil {
		return nil, err
	}
	basis, err := e.openReference(e.manifest["basis"])
	if err != nil {
		return nil, err
	}
	state["basis"] = basis
	if dashboard {
		state["final"], err = e.hydrate(e.manifest["final"], make(map[string]bool))
	} else {
		state["final"], err = e.openReference(e.manifest["final"])
	}
	if err != nil {
		return nil, err
	}
	if kind, exists := e.manifest["work_kind"]; exists {
		state["work_kind"] = kind
	}
	for _, field := range []string{"acceptance", "verification"} {
		if raw, exists := e.manifest[field]; exists {
			state[field], err = e.hydrate(raw, make(map[string]bool))
			if err != nil {
				return nil, err
			}
		}
	}
	taskManifest, err := e.openReference(e.manifest["tasks"])
	if err != nil {
		return nil, err
	}
	tasks := mapping{}
	fields := []string{"plan", "status", "attempt", "blockers", "review_limit", "review_rounds_started", "review_rounds_completed",
		"active_review", "test_repair_limit", "test_repair_cycles_started", "active_repair", "checks", "check_registry",
		"evidence", "verification_results", "procedures", "baseline_checks", "baseline_event"}
	if dashboard {
		fields = append(fields, "paths", "commits", "reviews")
	}
	for id, value := range object(taskManifest) {
		raw, err := e.openReference(value)
		if err != nil {
			return nil, err
		}
		taskRecord := object(raw)
		task, err := e.hydratedFields(taskRecord, fields...)
		if err != nil {
			return nil, err
		}
		worktree, err := e.openReference(taskRecord["worktree"])
		if err != nil {
			return nil, err
		}
		task["worktree"] = worktree
		if truth(object(worktree)["integrated"]) && truth(task["evidence"]) {
			task["transfer"], err = e.hydrate(taskRecord["transfer"], make(map[string]bool))
			if err != nil {
				return nil, err
			}
		}
		tasks[id] = task
	}
	state["tasks"] = tasks
	roleManifest, err := e.openReference(e.manifest["roles"])
	if err != nil {
		return nil, err
	}
	roles := mapping{}
	for id, value := range object(roleManifest) {
		raw, err := e.openReference(value)
		if err != nil {
			return nil, err
		}
		role, err := e.hydratedFields(object(raw), "role_id", "status", "task_id", "context_id", "kind", "registered_revision", "assignment", "successor_of")
		if err != nil {
			return nil, err
		}
		roles[id] = role
	}
	state["roles"] = roles
	return state, nil
}

func (e *execution) hydratedFields(source mapping, fields ...string) (mapping, error) {
	result := mapping{}
	for _, key := range fields {
		raw, exists := source[key]
		if !exists {
			continue
		}
		value, err := e.hydrate(raw, make(map[string]bool))
		if err != nil {
			return nil, err
		}
		result[key] = value
	}
	return result, nil
}

func (e *execution) compact() (mapping, error) {
	state, err := e.projectState(false)
	if err != nil {
		return nil, err
	}
	tasks := mapping{}
	for id, value := range object(state["tasks"]) {
		task := object(value)
		result := selectFields(task, "status", "attempt", "blockers", "review_limit", "review_rounds_started",
			"review_rounds_completed", "active_review", "test_repair_limit", "test_repair_cycles_started", "active_repair")
		result["verification"] = taskVerification(state, task, e.directory)
		tasks[id] = result
	}
	roles := mapping{}
	for id, value := range object(state["roles"]) {
		role := object(value)
		if role["status"] == "active" {
			roles[id] = selectFields(role, "task_id", "kind", "context_id")
		}
	}
	result := selectFields(state, "change_id", "run_id", "revision", "status", "updated_at", "blockers")
	if kind, exists := state["work_kind"]; exists {
		result["work_kind"] = kind
	}
	result["view"], result["view_version"] = "compact", 1
	result["tasks"], result["active_roles"], result["explorer_assignments"] = tasks, roles, explorerAssignments(state)
	result["completion"] = nil
	if final := object(state["final"]); truth(final) {
		result["completion"] = selectFields(final, "result", "head")
	}
	result["available_tasks"] = available(state)
	result["artifacts"] = mapping{"state": "state.json", "run": "runs/" + str(state["run_id"])}
	return result, nil
}

func taskVerification(state, task mapping, directory string) mapping {
	stages := map[string]bool{}
	for _, field := range []string{"evidence", "verification_results"} {
		for _, item := range array(task[field]) {
			stages[str(object(item)["stage"])] = true
		}
	}
	if truth(task["baseline_checks"]) {
		stages["baseline"] = true
	}
	for _, procedure := range object(task["procedures"]) {
		stages[str(object(procedure)["stage"])] = true
	}
	// All proof stages in this projection observe the same live task source.
	readSource := sync.OnceValues(func() (mapping, error) {
		return snapshot(state, taskRoot(state, task))
	})
	readBasis := sync.OnceValues(func() (mapping, error) {
		source, err := readSource()
		if err != nil {
			return nil, err
		}
		return explorerBasisAtSource(state, task, source, "checks", directory)
	})
	result := mapping{}
	for stage := range stages {
		if stage != "final" && stage != "" {
			result[stage] = checkProgress(state, task, stage, readSource, readBasis)
		}
	}
	return result
}

func checkProgress(state, task mapping, stage string, readSource, readBasis func() (mapping, error)) mapping {
	executed := mapping{"status": "missing", "references": []any{}, "checks": []any{}}
	conclusion := mapping{"status": "missing", "id": nil, "role_id": nil}
	result := mapping{"execution": executed, "conclusion": conclusion}
	if stage == "baseline" || stage == "self" {
		conclusion["status"] = "not_applicable"
	}
	if baseline := object(task["baseline_checks"]); stage == "baseline" && truth(baseline) {
		status := "planned_absence"
		if len(array(baseline["outputs"])) > 0 {
			status = "passed"
		}
		for _, value := range array(baseline["outputs"]) {
			switch object(value)["outcome"] {
			case "passed":
			case "planned_absence":
				if status == "passed" {
					status = "planned_absence"
				}
			default:
				status = "failed"
			}
		}
		current, err := readSource()
		if err != nil || baseline["run_id"] != state["run_id"] || digest(current) != digest(baseline["before"]) {
			status = "stale"
		}
		executed["status"] = status
		if log := object(task["baseline_event"])["log"]; truth(log) {
			executed["references"] = []any{mapping{"log": log}}
		}
		return result
	}
	var assessment mapping
	for _, value := range array(task["verification_results"]) {
		if item := object(value); item["stage"] == stage {
			assessment = item
		}
	}
	if assessment != nil {
		conclusion = selectFields(assessment, "id", "role_id")
		conclusion["status"] = assessment["outcome"]
		result["conclusion"] = conclusion
	}
	latest := make(map[string]mapping)
	for _, value := range array(task["evidence"]) {
		if item := object(value); item["stage"] == stage {
			latest[str(item["check_id"])] = item
		}
	}
	if len(latest) == 0 && assessment == nil && !truth(task["procedures"]) {
		return result
	}
	var current mapping
	if task["status"] == "accepted" && assessment != nil {
		current = object(assessment["basis"])
	} else {
		var err error
		current, err = readBasis()
		if err != nil {
			executed["status"] = "unavailable"
			if assessment != nil {
				conclusion["status"] = "stale"
			}
			return result
		}
		if stage == "independent" && truth(object(task["worktree"])["integrated"]) && truth(task["transfer"]) {
			current = copyMapping(current)
			current["source"] = object(task["transfer"])["snapshot"]
		}
	}
	statuses := map[string]bool{}
	for _, value := range array(current["checks"]) {
		check := object(value)
		id := str(check["id"])
		item := latest[id]
		pending := object(object(task["procedures"])[id])
		status, reason := "missing", "evidence_missing"
		if pending != nil && pending["stage"] == stage {
			status, reason = "pending", "procedure_pending"
		} else if item != nil {
			role := object(object(state["roles"])[str(item["role_id"])])
			assignment := object(object(role["assignment"])["basis"])
			assigned := selectedCheck(array(assignment["checks"]), id)
			status = str(item["outcome"])
			switch {
			case role["status"] == "lost":
				status = "unavailable"
			case digest(assignment["source"]) != digest(current["source"]) || assignment["run_id"] != current["run_id"] || !sameCheckExecution(assigned, check):
				status = "stale"
			case truth(item["procedure"]) && status == "passed":
				status = "pending"
			}
			reason = status
			if status == "pending" {
				reason = "procedure_superseded"
			}
			executed["references"] = append(array(executed["references"]), mapping{"check_id": id, "log": item["log"], "sha256": item["log_hash"]})
		}
		statuses[status] = true
		executed["checks"] = append(array(executed["checks"]), mapping{
			"check_id": id, "criteria": check["criteria"], "location": check["location"], "status": status, "reason": reason,
		})
	}
	if len(statuses) > 0 {
		executed["status"] = "passed"
		for _, status := range []string{"failed", "unavailable", "stale", "abandoned", "pending", "missing", "skipped", "unstable"} {
			if statuses[status] {
				executed["status"] = status
				break
			}
		}
	}
	if assessment != nil {
		role := object(object(state["roles"])[str(assessment["role_id"])])
		if role["status"] != "active" && role["status"] != "finished" || digest(current) != digest(assessment["basis"]) ||
			assessment["attempts_hash"] != digest(attempts(task, stage)) ||
			conclusion["status"] == "passed" && executed["status"] != "passed" {
			conclusion["status"] = "stale"
		}
	}
	return result
}

func selectedCheck(checks []any, id string) mapping {
	for _, value := range checks {
		if check := object(value); check["id"] == id {
			return check
		}
	}
	return nil
}

func ownedIntersection(left, right []string, fold bool) bool {
	for _, first := range left {
		for _, second := range right {
			if first == second || fold && strings.EqualFold(first, second) {
				return true
			}
		}
	}
	return false
}
