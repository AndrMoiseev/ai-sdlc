package apply

import (
	"bytes"
	"context"
	"encoding/base64"
	"errors"
	"os"
	"os/exec"
	"sort"
	"strings"
	"time"

	"github.com/AndrMoiseev/ai-sdlc/cli/internal/childprocess"
)

func executeCheck(command any, cwd string, remaining float64) mapping {
	start := time.Now()
	stamp := now()
	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(remaining*float64(time.Second)))
	defer cancel()
	args := stringArray(command)
	cmd := exec.CommandContext(ctx, args[0], args[1:]...)
	cmd.Dir = cwd
	childprocess.Configure(cmd)
	cmd.WaitDelay = time.Second
	var out, errout bytes.Buffer
	cmd.Stdout = &out
	cmd.Stderr = &errout
	e := cmd.Run()
	var code any = 0
	outcome := "passed"
	var limitation any
	if ctx.Err() != nil {
		code = nil
		outcome = "unavailable"
		limitation = "timeout"
	} else if e != nil {
		var exit *exec.ExitError
		if errors.As(e, &exit) {
			code = exit.ExitCode()
			outcome = "failed"
		} else {
			code = nil
			outcome = "unavailable"
			limitation = "process_launch_error"
			errout.WriteString(e.Error())
		}
	}
	return mapping{"command": command, "cwd": cwd, "started_at": stamp, "duration_seconds": time.Since(start).Seconds(), "exit_code": code, "stdout_base64": base64.StdEncoding.EncodeToString(out.Bytes()), "stderr_base64": base64.StdEncoding.EncodeToString(errout.Bytes()), "stdout": strings.ToValidUTF8(out.String(), "\uFFFD"), "stderr": strings.ToValidUTF8(errout.String(), "\uFFFD"), "outcome": outcome, "limitation": limitation}
}
func procedureEvidence(state, task, c mapping, stage string, before mapping, directory string) (mapping, error) {
	id := str(c["id"])
	unavailable := func(reason string) mapping { return mapping{"outcome": "unavailable", "description": reason} }
	if checkHas(object(task["procedures"]), id) {
		return unavailable("procedure_pending"), nil
	}
	var latest mapping
	for _, v := range array(task["evidence"]) {
		item := object(v)
		if item["check_id"] == id && item["stage"] == stage && truth(item["procedure"]) {
			latest = item
		}
	}
	if latest == nil {
		return unavailable("procedure_missing"), nil
	}
	role := object(object(state["roles"])[str(latest["role_id"])])
	if latest["outcome"] == "abandoned" || role["status"] == "lost" {
		return unavailable("procedure_abandoned_or_role_lost"), nil
	}
	full, e := contained(directory, str(latest["log"]))
	if e != nil {
		return nil, e
	}
	b, e := os.ReadFile(full)
	if e != nil || digest(b) != latest["log_hash"] {
		return nil, reject("evidence_corrupt", "Procedure evidence changed")
	}
	val, e := decode(b)
	if e != nil {
		return nil, e
	}
	r := object(val)
	for _, k := range []string{"check_id", "role_id", "stage", "outcome"} {
		if !checkSame(r[k], latest[k]) {
			return nil, reject("evidence_basis", "Procedure evidence must name its exact check, role, stage and outcome")
		}
	}
	if _, e := authorizeExplorer(state, task, str(latest["role_id"]), stage, directory, false, false); e != nil {
		return nil, e
	}
	outcome := latest["outcome"]
	if !checkSame(before, r["before"]) || !checkSame(before, r["after"]) || !sameCheckExecution(object(r["registered_check"]), c) {
		outcome = "stale"
	}
	return mapping{"outcome": outcome, "procedure_log": latest["log"], "procedure_log_hash": latest["log_hash"]}, nil
}
func reusableChecks(state, task mapping, checks []any, stage string, before mapping, directory string) (map[string]mapping, map[string]any, error) {
	reuse := map[string]mapping{}
	refs := map[string]any{}
	if stage == "baseline" {
		return reuse, refs, nil
	}
	latest := map[string]mapping{}
	for _, v := range array(task["evidence"]) {
		item := object(v)
		if item["stage"] == stage && !truth(item["procedure"]) {
			latest[str(item["check_id"])] = item
		}
	}
	logs := map[string]mapping{}
	validated := map[string]bool{}
	for _, v := range checks {
		c := object(v)
		id := str(c["id"])
		item := latest[id]
		if item["outcome"] != "passed" {
			continue
		}
		rel := str(item["log"])
		r := logs[rel]
		if r == nil {
			full, e := contained(directory, rel)
			if e != nil {
				return nil, nil, e
			}
			raw, e := os.ReadFile(full)
			if e != nil || digest(raw) != item["log_hash"] {
				return nil, nil, reject("evidence_corrupt", rel)
			}
			data, e := decode(raw)
			if e != nil {
				return nil, nil, e
			}
			r = object(data)
			logs[rel] = r
		}
		registered := array(r["registered_checks"])
		orig := checkByID(registered, id)
		if r["run_id"] != state["run_id"] || !checkSame(before, r["before"]) || !checkSame(before, r["after"]) || orig == nil || !sameCheckExecution(orig, c) {
			continue
		}
		var out mapping
		for _, v := range array(r["outputs"]) {
			m := object(v)
			if m["check_id"] == id {
				out = m
				break
			}
		}
		run := object(c["setup"])
		if run == nil {
			run = object(c["run"])
		}
		if checkHas(run, "procedure") {
			proc, e := procedureEvidence(state, task, c, stage, before, directory)
			if e != nil {
				return nil, nil, e
			}
			if proc["outcome"] != "passed" || out["procedure_log"] != proc["procedure_log"] || out["procedure_log_hash"] != proc["procedure_log_hash"] {
				continue
			}
		}
		if out["outcome"] != "passed" || out["evidence_complete"] != true {
			return nil, nil, reject("evidence_incomplete", "The required check needs complete passing evidence")
		}
		if !validated[rel] {
			if e := validateCheckLog(state, r, registered, directory); e != nil {
				return nil, nil, e
			}
			validated[rel] = true
		}
		if _, e := authorizeExplorer(state, task, str(item["role_id"]), stage, directory, false, false); e != nil {
			return nil, nil, e
		}
		reuse[id] = item
		refs[id] = out["summary"]
	}
	return reuse, refs, nil
}
func runChecks(state, task, event, p mapping, directory string) (any, error) {
	if e := checkRegistryCurrent(state, task); e != nil {
		return nil, e
	}
	stage := str(p["stage"])
	if !includes([]string{"baseline", "self", "independent", "integration"}, stage) {
		return nil, reject("check_stage", "Unknown verification stage")
	}
	roleID := str(p["role_id"])
	role, e := authorizeExplorer(state, task, roleID, stage, directory, true, true)
	if e != nil {
		return nil, e
	}
	root := taskRoot(state, task)
	var before mapping
	if stage != "baseline" {
		if !includes([]string{"verifying", "reviewing", "accepted", "integrating"}, str(task["status"])) {
			return nil, reject("check_phase", "No frozen candidate")
		}
		before, e = checkSource(state, task)
		if e != nil {
			return nil, e
		}
		if truth(task["last_check_failed"]) && !truth(task["active_repair"]) {
			return nil, reject("repair_cycle_required", "A retry after failure must reserve a repair cycle")
		}
		if writerActive(state, task) {
			return nil, reject("writer_active", "All authors must stop before check execution")
		}
		if stage == "integration" && !truth(object(task["worktree"])["integrated"]) {
			return nil, reject("check_phase", "Integration checks require an integrated commit")
		}
	}
	if !truth(task["checks"]) {
		return nil, reject("checks_missing", "Register verification first")
	}
	if before == nil {
		before, e = snapshot(state, root)
		if e != nil {
			return nil, e
		}
		if e := cleanSource(before); e != nil {
			return nil, e
		}
	}
	if stage == "baseline" && (truth(task["baseline_checks"]) || !checkSame(task["start_snapshot"], before)) {
		return nil, reject("baseline_changed", "Capture the initial checks before any implementation edits")
	}
	budget, e := attemptBudget(state, task, role, checkValue(p, "timeout", 300))
	if e != nil {
		return nil, e
	}
	expires := checkNumber(budget["expires"])
	checks, e := registryChecks(state, task, directory)
	if e != nil {
		return nil, e
	}
	reuse, refs, e := reusableChecks(state, task, checks, stage, before, directory)
	if e != nil {
		return nil, e
	}
	executed, outputs, executedIDs, reusedEvidence := []any{}, []any{}, []any{}, []any{}
	captures := map[string]capturedCheck{}
	for _, v := range checks {
		c := object(v)
		id := str(c["id"])
		if item := reuse[id]; item != nil {
			reusedEvidence = append(reusedEvidence, item)
			continue
		}
		executed = append(executed, c)
		executedIDs = append(executedIDs, id)
		if e := requireDeterministic(c); e != nil {
			return nil, e
		}
		run := object(c["setup"])
		if run == nil {
			run = object(c["run"])
		}
		out := mapping{"check_id": id}
		outputs = append(outputs, out)
		switch {
		case expires <= unixSeconds():
			out["outcome"] = "unavailable"
			out["exit_code"] = nil
			out["limitation"] = "check_deadline"
			out["description"] = "The full check set deadline expired; command not started"
			continue
		case stage == "baseline" && checkHas(run, "setup_required"):
			out["outcome"] = "planned_absence"
			out["description"] = run["setup_required"]
			continue
		}
		if loc, ok := c["location"]; ok {
			full, e := contained(root, str(loc))
			if e != nil {
				return nil, e
			}
			if _, e = os.Stat(full); e != nil {
				out["outcome"] = "unavailable"
				out["description"] = "Required verification location is missing"
				out["location"] = loc
				continue
			}
		}
		if !checkHas(run, "command") {
			if checkHas(run, "procedure") {
				result, e := procedureEvidence(state, task, c, stage, before, directory)
				if e != nil {
					return nil, e
				}
				for k, v := range result {
					out[k] = v
				}
			} else {
				out["outcome"] = "unavailable"
				out["description"] = "No executable command for required procedure"
			}
			continue
		}
		if e := requireArgv(run["command"]); e != nil {
			return nil, e
		}
		cwd := root
		relative := str(checkValue(run, "cwd", c["cwd"]))
		if relative != "." {
			cwd, e = contained(root, relative)
			if e != nil {
				return nil, e
			}
		}
		cmd := executeCheck(run["command"], cwd, expires-unixSeconds())
		for k, v := range cmd {
			out[k] = v
		}
		out["configuration"] = checkValue(run, "configuration", c["configuration"])
		out["criteria"] = c["criteria"]
		reports, limits := captureCheckReports(out, true)
		captures[id] = capturedCheck{reports, limits}
		if expires <= unixSeconds() && out["outcome"] == "passed" {
			out["outcome"] = "unavailable"
			out["limitation"] = "check_deadline"
		}
	}
	after, e := snapshot(state, root)
	if e != nil {
		return nil, e
	}
	unchanged := checkSame(before, after)
	record := mapping{"schema_version": 1, "change_id": state["change_id"], "run_id": state["run_id"], "task_id": object(task["plan"])["id"], "role_id": roleID, "stage": stage, "before": before, "after": after, "outputs": outputs, "registry_revision": object(task["check_registry"])["revision"], "registered_checks": checkClone(executed)}
	if workKind(object(state["basis"])) == "refactoring" {
		record["work_kind"] = "refactoring"
	}
	rel := checkLogPath(state, task, event)
	full, e := contained(directory, rel)
	if e != nil {
		return nil, e
	}
	var summary any
	var log any
	var hash string
	if len(executed) > 0 {
		s, e := persistCheckRun(state, task, record, executed, captures, directory, str(event["event_id"]))
		if e != nil {
			return nil, e
		}
		summary = s
		if e = writeJSON(full, record); e != nil {
			return nil, e
		}
		log = rel
		b, e := os.ReadFile(full)
		if e != nil {
			return nil, e
		}
		hash = digest(b)
	}
	outcome := "passed"
	baselineOK := unchanged
	unavailable := false
	if !unchanged {
		outcome = "failed"
	}
	for _, v := range outputs {
		out := object(v)
		if out["outcome"] != "passed" {
			outcome = "failed"
		}
		unavailable = unavailable || out["outcome"] == "unavailable" || out["evidence_complete"] != true
		baselineOK = baselineOK && (out["outcome"] == "planned_absence" || out["outcome"] == "passed" && out["evidence_complete"] == true)
		refs[str(out["check_id"])] = out["summary"]
	}
	if unavailable {
		outcome = "unavailable"
	}
	if stage == "baseline" {
		task["baseline_checks"] = record
		if baselineOK {
			return mapping{"outcome": "baseline_recorded", "log": rel, "summary": summary}, nil
		}
		state["status"] = "blocked"
		state["blockers"] = append(array(state["blockers"]), mapping{"reason": "baseline_failed", "task_id": record["task_id"], "resume_condition": "Resolve or explicitly scope the pre-existing failure", "log": rel})
		task["failure"] = mapping{"budget": "baseline", "outcome": outcome}
	}
	for _, v := range outputs {
		out := object(v)
		observed := out["outcome"]
		if out["evidence_complete"] != true {
			observed = "unavailable"
		}
		if !unchanged {
			observed = "stale"
		}
		task["evidence"] = append(array(task["evidence"]), mapping{"check_id": out["check_id"], "stage": stage, "role_id": roleID, "outcome": observed, "log": rel, "log_hash": hash, "time": now(), "head": after["commit"]})
	}
	if stage == "independent" {
		task["last_check_failed"] = outcome != "passed"
		if truth(task["active_repair"]) && outcome != "unavailable" {
			task["repair_cycles"] = append(array(task["repair_cycles"]), mapping{"id": task["active_repair"], "outcome": outcome, "log": rel})
			task["active_repair"] = nil
		}
		if outcome != "passed" {
			task["failure"] = mapping{"budget": "test", "outcome": outcome}
			if outcome == "failed" {
				n := intValue(task["test_repair_cycles_started"]) + 1
				task["test_repair_cycles_started"] = n
				if n >= intValue(task["test_repair_limit"]) {
					blockBudget(state, task, "test_repair_limit_reached")
				}
			} else if outcome == "unavailable" {
				item := mapping{"reason": "required_check_unavailable", "task_id": record["task_id"], "resume_condition": "Restore required runner"}
				exists := false
				for _, b := range array(state["blockers"]) {
					exists = exists || checkSame(b, item)
				}
				if !exists {
					state["blockers"] = append(array(state["blockers"]), item)
				}
				state["status"] = "blocked"
			}
		}
	}
	if len(reuse) > 0 {
		store := execution{directory: directory}
		list := []mapping{}
		ordered := []any{}
		for _, v := range checks {
			id := str(object(v)["id"])
			ref := refs[id]
			m, e := store.readObject(ref)
			if e != nil {
				return nil, e
			}
			list = append(list, object(m))
			ordered = append(ordered, ref)
		}
		s := aggregateChecks(checks, list, unchanged)
		s["checks"] = ordered
		ids := []string{}
		for k := range reuse {
			ids = append(ids, k)
		}
		sort.Strings(ids)
		s["reused_check_ids"] = ids
		summary = s
	}
	return mapping{"outcome": outcome, "log": log, "summary": summary, "executed_check_ids": executedIDs, "reused_evidence": reusedEvidence}, nil
}
