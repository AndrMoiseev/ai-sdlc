package apply

import (
	"encoding/json"
	"errors"
	"math"
	"os"
	"path"
	"strconv"
	"time"
)

func checkSource(state, task mapping) (mapping, error) {
	if !includes([]string{"verifying", "reviewing", "integrating", "committing", "accepted"}, str(task["status"])) {
		return nil, reject("check_phase", "Prepare the task commit before verification")
	}
	if e := checkRegistryCurrent(state, task); e != nil {
		return nil, e
	}
	if workKind(object(state["basis"])) == "refactoring" && !truth(task["baseline_checks"]) {
		return nil, reject("baseline_missing", "Capture existing checks before freezing a refactoring result")
	}
	s, e := snapshot(state, taskRoot(state, task))
	if e == nil {
		e = cleanSource(s)
	}
	return s, e
}
func unixSeconds() float64 { return float64(time.Now().UnixMicro()) / 1e6 }
func checkNumber(v any) float64 {
	switch n := v.(type) {
	case float64:
		return n
	case int:
		return float64(n)
	case json.Number:
		f, _ := n.Float64()
		return f
	}
	return math.NaN()
}
func attemptBudget(state, task, role mapping, timeout any) (mapping, error) {
	limit := checkNumber(timeout)
	if math.IsNaN(limit) || math.IsInf(limit, 0) || limit <= 0 {
		return nil, reject("check_timeout", "Use a positive finite batch timeout")
	}
	assignment := object(role["assignment"])
	limits := object(assignment["limits"])
	maximum := checkNumber(checkValue(limits, "timeout", timeout))
	if math.IsNaN(maximum) || math.IsInf(maximum, 0) || maximum <= 0 {
		return nil, reject("check_timeout", "Assignment timeout must be positive and finite")
	}
	cycles := mapping{str(object(task["plan"])["id"]): checkValue(task, "test_repair_cycles_started", 0)}
	var previous mapping
	for _, v := range object(state["roles"]) {
		c := object(v)
		budget := object(c["check_budget"])
		if budget == nil || !checkSame(budget["repair_cycles"], cycles) {
			continue
		}
		a := object(c["assignment"])
		equal := true
		for _, k := range []string{"scope", "stage", "basis"} {
			equal = equal && checkSame(a[k], assignment[k])
		}
		if equal && (previous == nil || checkNumber(budget["expires"]) < checkNumber(previous["expires"])) {
			previous = budget
		}
	}
	started := unixSeconds()
	if previous != nil {
		started = checkNumber(previous["started"])
	}
	expires := started + math.Min(limit, maximum)
	if previous != nil {
		expires = math.Min(expires, checkNumber(previous["expires"]))
	}
	if limits["deadline"] != nil {
		v, ok := limits["deadline"].(string)
		if !ok {
			return nil, reject("check_timeout", "Absolute deadline must be ISO-8601 text")
		}
		t, e := time.Parse(time.RFC3339Nano, v)
		if e != nil {
			return nil, errors.New("check_timeout: Invalid absolute deadline")
		}
		expires = math.Min(expires, float64(t.UnixMicro())/1e6)
	}
	role["check_budget"] = mapping{"started": started, "expires": expires, "repair_cycles": cycles}
	return mapping{"started": started, "expires": expires}, nil
}
func checkLogPath(state, task, event mapping) string {
	return path.Join("runs", str(state["run_id"]), "tasks", str(object(task["plan"])["id"]), strconv.Itoa(intValue(task["attempt"])), str(event["event_id"])+".json")
}
func beginProcedure(state, task, event, p mapping, directory string) (any, error) {
	if e := checkRegistryCurrent(state, task); e != nil {
		return nil, e
	}
	stage := str(p["stage"])
	if !includes([]string{"baseline", "self", "independent", "integration"}, stage) {
		return nil, reject("procedure_stage", "Unknown stage")
	}
	checks, e := registryChecks(state, task, directory)
	if e != nil {
		return nil, e
	}
	id := str(p["check_id"])
	c := checkByID(checks, id)
	run := object(c["run"])
	if c == nil || !checkHas(run, "procedure") || truth(c["setup"]) {
		return nil, reject("procedure_check", "Use the registered procedure without replacing it")
	}
	if e := requireDeterministic(c); e != nil {
		return nil, e
	}
	role, e := authorizeExplorer(state, task, str(p["role_id"]), stage, directory, true, true)
	if e != nil {
		return nil, e
	}
	if truth(task["last_check_failed"]) && !truth(task["active_repair"]) {
		return nil, reject("repair_cycle_required", "A retry after failure must reserve a repair cycle")
	}
	history := array(task["evidence"])
	root := taskRoot(state, task)
	if stage != "self" {
		for i := len(history) - 1; i >= 0; i-- {
			item := object(history[i])
			if !truth(item["procedure"]) || item["check_id"] != id || item["stage"] != stage {
				continue
			}
			h, e := gitText(root, "rev-parse", "HEAD")
			if e != nil {
				return nil, e
			}
			if h == item["head"] && item["outcome"] != "passed" && item["outcome"] != "abandoned" && !truth(task["active_repair"]) {
				return nil, reject("repair_cycle_required", "A failed procedure retry must reserve a repair cycle")
			}
			break
		}
	}
	if stage != "baseline" {
		if _, e := checkSource(state, task); e != nil {
			return nil, e
		}
		if writerActive(state, task) {
			return nil, reject("writer_active", "All authors must stop before procedure execution")
		}
	}
	if stage == "integration" && !truth(object(task["worktree"])["integrated"]) {
		return nil, reject("check_phase", "Integration procedures require an integrated commit")
	}
	file, e := contained(root, str(run["procedure"]))
	if e != nil {
		return nil, e
	}
	if st, e := os.Stat(file); e != nil || !st.Mode().IsRegular() {
		return nil, reject("procedure_unavailable", file)
	}
	pending := object(task["procedures"])
	if pending == nil {
		pending = mapping{}
		task["procedures"] = pending
	}
	if checkHas(pending, id) {
		return nil, reject("procedure_active", "Finish the existing procedure attempt")
	}
	before, e := snapshot(state, root)
	if e != nil {
		return nil, e
	}
	if e := cleanSource(before); e != nil {
		return nil, e
	}
	if stage == "baseline" && (truth(task["baseline_checks"]) || !checkSame(before, task["start_snapshot"])) {
		return nil, reject("baseline_changed", "Capture baseline before implementation edits")
	}
	budget, e := attemptBudget(state, task, role, checkValue(p, "timeout", 300))
	if e != nil {
		return nil, e
	}
	remaining := checkNumber(budget["expires"]) - unixSeconds()
	if remaining <= 0 {
		return nil, reject("check_deadline", "The assigned check attempt deadline expired")
	}
	attempt := mapping{"check_id": id, "registered_check": checkClone(c), "role_id": p["role_id"], "stage": stage, "before": before, "path": file, "started_at": now(), "check_deadline": budget, "remaining_timeout": remaining}
	pending[id] = attempt
	return attempt, nil
}
func finishProcedure(state, task, event, p mapping, directory string) (any, error) {
	id := str(p["check_id"])
	pending := object(task["procedures"])
	attempt := object(pending[id])
	if attempt == nil || !checkSame(p["role_id"], attempt["role_id"]) {
		return nil, reject("procedure_owner", "Match the registered procedure attempt")
	}
	stage := str(attempt["stage"])
	if e := requireDeterministic(object(attempt["registered_check"])); e != nil {
		return nil, e
	}
	if _, e := authorizeExplorer(state, task, str(p["role_id"]), stage, directory, true, false); e != nil {
		return nil, e
	}
	outcome := str(p["outcome"])
	if !includes([]string{"passed", "failed", "unavailable", "skipped", "unstable"}, outcome) || !truth(p["steps"]) || !truth(p["trace"]) {
		return nil, reject("procedure_evidence", "Actual steps, outcome and host trace required")
	}
	root := taskRoot(state, task)
	after, e := snapshot(state, root)
	if e != nil {
		return nil, e
	}
	deadline := checkNumber(object(attempt["check_deadline"])["expires"])
	expired := deadline <= unixSeconds()
	if !checkSame(after, attempt["before"]) {
		outcome = "stale"
	} else if expired {
		outcome = "unavailable"
	}
	record := copyMapping(attempt)
	record["schema_version"] = 1
	record["change_id"] = state["change_id"]
	record["run_id"] = state["run_id"]
	record["after"] = after
	record["steps"] = p["steps"]
	record["trace"] = p["trace"]
	record["outcome"] = outcome
	record["reported_outcome"] = p["outcome"]
	if expired {
		record["limitation"] = "check_deadline"
	}
	relative := checkLogPath(state, task, event)
	full, e := contained(directory, relative)
	if e != nil {
		return nil, e
	}
	if e = writeJSON(full, record); e != nil {
		return nil, e
	}
	raw, e := os.ReadFile(full)
	if e != nil {
		return nil, e
	}
	head, e := gitText(root, "rev-parse", "HEAD")
	if e != nil {
		return nil, e
	}
	item := mapping{"check_id": p["check_id"], "stage": stage, "role_id": p["role_id"], "outcome": outcome, "log": relative, "log_hash": digest(raw), "time": now(), "head": head, "procedure": true}
	task["evidence"] = append(array(task["evidence"]), item)
	delete(pending, id)
	return item, nil
}
func verificationEvent(state, task, event mapping, directory string) (any, error) {
	if task == nil {
		return nil, reject("task_required", "Task required")
	}
	p := object(event["payload"])
	if p["stage"] == "final" {
		return nil, reject("check_stage", "Final checks have been removed")
	}
	switch event["type"] {
	case "checks_register":
		return registerChecks(state, task, event, p)
	case "checks_revise":
		return reviseChecks(state, task, event, p, directory)
	case "checks_extend":
		return extendChecks(state, task, event, p, directory)
	case "check_setup":
		return setupCheck(state, task, event, p)
	case "procedure_begin":
		return beginProcedure(state, task, event, p, directory)
	case "procedure_result":
		return finishProcedure(state, task, event, p, directory)
	default:
		return runChecks(state, task, event, p, directory)
	}
}
