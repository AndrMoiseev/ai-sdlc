package apply

import (
	"fmt"
	"os"
	"slices"
	"strings"
)

// Registry history is copied when a revision is recorded. Later setup changes
// must never mutate a prior revision or the before/after of a transition.
func checkClone(v any) any {
	raw, err := canonical(v)
	if err != nil {
		panic(err)
	}
	value, err := decode(raw)
	if err != nil {
		panic(err)
	}
	return value
}
func checkSame(a, b any) bool { return digest(a) == digest(b) }
func checkValue(m mapping, k string, def any) any {
	if v, ok := m[k]; ok {
		return v
	}
	return def
}
func checkHas(m mapping, k string) bool { _, ok := m[k]; return ok }

type checkSet map[string]bool

func checkIDs(v any) checkSet {
	s := checkSet{}
	for _, k := range stringArray(v) {
		s[k] = true
	}
	return s
}
func (c checkSet) add(d checkSet) {
	for k := range d {
		c[k] = true
	}
}
func (c checkSet) subset(d checkSet) bool {
	for k := range c {
		if !d[k] {
			return false
		}
	}
	return true
}
func checkList(v any, unique bool) bool {
	a, ok := v.([]any)
	if !ok {
		return false
	}
	seen := checkSet{}
	for _, item := range a {
		s, ok := item.(string)
		if !ok || s == "" || unique && seen[s] {
			return false
		}
		seen[s] = true
	}
	return true
}
func checkFields(m mapping, required, optional string) bool {
	if m == nil {
		return false
	}
	a := strings.Fields(required)
	for _, k := range a {
		if !checkHas(m, k) {
			return false
		}
	}
	a = append(a, strings.Fields(optional)...)
	for k := range m {
		if !slices.Contains(a, k) {
			return false
		}
	}
	return true
}
func checkByID(a []any, id string) mapping {
	for _, v := range a {
		m := object(v)
		if m["id"] == id {
			return m
		}
	}
	return nil
}
func checkCriteria(a []any) checkSet {
	out := checkSet{}
	for _, v := range a {
		out.add(checkIDs(object(v)["criteria"]))
	}
	return out
}
func taskCheckCriteria(state, task mapping) checkSet {
	plan := object(task["plan"])
	if workKind(object(state["basis"])) != "refactoring" {
		return checkIDs(plan["covers"])
	}
	criteria := checkIDs(plan["preserves"])
	for k, v := range object(state["acceptance"]) {
		if object(v)["task"] == plan["id"] {
			criteria[k] = true
		}
	}
	return criteria
}
func requireDeterministic(check mapping) error {
	run := object(check["run"])
	k := check["execution_kind"]
	if !checkHas(check, "execution_kind") && !checkHas(run, "procedure") {
		k = "deterministic"
	}
	switch k {
	case "deterministic":
		return nil
	case "manual", "behavioral":
		return reject("check_kind", "sdd-apply executes deterministic checks only; manual and behavioral checks are outside task review")
	default:
		return fmt.Errorf("execution_kind must be deterministic, behavioral or manual; procedures require an explicit type")
	}
}
func requireArgv(v any) error {
	args, ok := v.([]any)
	if ok && len(args) > 0 && strings.TrimSpace(str(args[0])) != "" {
		valid := true
		for _, arg := range args {
			s, ok := arg.(string)
			valid = valid && ok && !strings.ContainsRune(s, 0)
		}
		if valid {
			return nil
		}
	}
	return reject("command_format", "command must be an argument array, e.g. ['pytest', '-q']; migrate legacy strings explicitly without changing approved checks")
}
func appendRegistry(task, event mapping) {
	registry := object(task["check_registry"])
	if registry == nil {
		registry = mapping{"revision": 0, "confirmed_revision": 0, "history": []any{}}
		task["check_registry"] = registry
	}
	rev := intValue(registry["revision"]) + 1
	registry["revision"] = rev
	entry := mapping{"revision": rev, "event_id": event["event_id"], "operation": event["type"], "checks": checkClone(task["checks"])}
	if truth(registry["transition"]) {
		entry["transition"] = checkClone(registry["transition"])
	}
	registry["history"] = append(array(registry["history"]), entry)
}
func checkRegistryCurrent(state, task mapping) error {
	if workKind(object(state["basis"])) != "refactoring" {
		return nil
	}
	r := object(task["check_registry"])
	h := array(r["history"])
	n := len(h)
	invalid := reject("registry_changed", "Verification registry changed without an authorized revision")
	if n == 0 || intValue(r["revision"]) != n {
		return invalid
	}
	for i, v := range h {
		if intValue(object(v)["revision"]) != i+1 {
			return invalid
		}
	}
	last := object(h[n-1])
	if !checkSame(last["checks"], task["checks"]) {
		return invalid
	}
	confirmed, ok := integer(checkValue(r, "confirmed_revision", 0))
	if !ok || confirmed < 0 || confirmed > n {
		return reject("registry_changed", "Invalid confirmed registry revision")
	}
	if !checkSame(last["transition"], r["transition"]) {
		return reject("registry_changed", "Registry transition differs from its immutable snapshot")
	}
	if !taskCheckCriteria(state, task).subset(checkCriteria(array(task["checks"]))) {
		return reject("criteria_uncovered", "Local acceptance and preservation checks remain mandatory")
	}
	return nil
}
func reservedChecks(state, task mapping, checks []any) error {
	if workKind(object(state["basis"])) != "refactoring" {
		return nil
	}
	reserved := checkSet{}
	for k := range object(state["verification"]) {
		reserved[k] = true
	}
	add := func(a []any) {
		for _, v := range a {
			reserved[str(object(v)["id"])] = true
		}
	}
	add(array(object(state["final_checks"])["checks"]))
	for k, item := range object(state["tasks"]) {
		if k == str(object(task["plan"])["id"]) {
			continue
		}
		other := object(item)
		for _, v := range array(object(other["plan"])["verification"]) {
			reserved[k+"/"+str(object(v)["id"])] = true
		}
		add(array(other["checks"]))
		for _, row := range array(object(other["check_registry"])["history"]) {
			add(array(object(row)["checks"]))
		}
	}
	for _, v := range checks {
		if reserved[str(object(v)["id"])] {
			return reject("duplicate_check", "Check ID belongs to another task; use an authorized registry revision to change its obligation")
		}
	}
	return nil
}
func addedCheck(c mapping) mapping {
	m := mapping{}
	for k, v := range c {
		m[k] = v
	}
	m["setup"] = nil
	m["cwd"] = checkValue(m, "cwd", ".")
	m["configuration"] = checkValue(m, "configuration", mapping{})
	return m
}
func registerChecks(state, task, event, p mapping) (any, error) {
	if task["status"] != "pending" || truth(task["checks"]) {
		return nil, reject("registry_frozen", "Register once before execution")
	}
	checks := []any{}
	plan := object(task["plan"])
	refactor := workKind(object(state["basis"])) == "refactoring"
	for i, v := range array(plan["verification"]) {
		c := object(v)
		id := fmt.Sprintf("plan-%d", i+1)
		if refactor {
			id = str(plan["id"]) + "/" + str(c["id"])
		}
		m := addedCheck(mapping{"id": id, "criteria": c["criteria"], "source": "tasks.md", "location": c["location"], "run": c["run"]})
		if k, ok := c["execution_kind"]; ok {
			m["execution_kind"] = k
		}
		checks = append(checks, m)
	}
	if !checkFields(object(p["inventory"]), "instructions ci", "") {
		return nil, reject("inventory_required", "Record inspected project instruction and CI files, including an explicit empty inventory")
	}
	for _, v := range array(p["additional"]) {
		c := object(v)
		if !truth(c["id"]) || !truth(c["source"]) || !truth(c["run"]) {
			return nil, reject("check_schema", "Additional required checks need ID, source and exact run")
		}
		checks = append(checks, addedCheck(c))
	}
	seen := checkSet{}
	for _, v := range checks {
		id := str(object(v)["id"])
		if seen[id] {
			return nil, reject("duplicate_check", "Duplicate check ID")
		}
		seen[id] = true
	}
	for _, v := range checks {
		c := object(v)
		run := object(c["run"])
		if len(run) != 1 || (!checkHas(run, "command") && !checkHas(run, "procedure") && !checkHas(run, "setup_required")) {
			return nil, reject("check_schema", "run requires one command, procedure or setup_required key")
		}
		if e := requireDeterministic(c); e != nil {
			return nil, e
		}
		if refactor && (!truth(c["criteria"]) || !checkIDs(c["criteria"]).subset(taskCheckCriteria(state, task))) {
			return nil, reject("check_schema", "Bind checks to local acceptance or preserved criteria")
		}
		if checkHas(run, "command") {
			if e := requireArgv(run["command"]); e != nil {
				return nil, e
			}
		}
	}
	if e := reservedChecks(state, task, checks); e != nil {
		return nil, e
	}
	task["checks"] = checks
	task["inventory"] = p["inventory"]
	appendRegistry(task, event)
	return mapping{"checks": checks}, checkRegistryCurrent(state, task)
}
func setupCheck(state, task, event, p mapping) (any, error) {
	if err := checkRegistryCurrent(state, task); err != nil {
		return nil, err
	}
	c := checkByID(array(task["checks"]), str(p["check_id"]))
	run := object(c["run"])
	if c == nil || !checkHas(run, "setup_required") && !checkHas(run, "procedure") || c["setup"] != nil {
		return nil, reject("setup_not_planned", "Only planned, unresolved setup or procedure may be registered")
	}
	if e := requireDeterministic(c); e != nil {
		return nil, e
	}
	if task["status"] != "running" && task["status"] != "repairing" {
		return nil, reject("setup_phase", "Prepare checks within their task")
	}
	if !truth(p["command"]) || !truth(p["description"]) || !truth(task["baseline_checks"]) {
		return nil, reject("setup_evidence", "Need baseline check inventory and preparation description")
	}
	if e := requireArgv(p["command"]); e != nil {
		return nil, e
	}
	after, e := snapshot(state, taskRoot(state, task))
	if e != nil {
		return nil, e
	}
	c["setup"] = mapping{"command": p["command"], "cwd": checkValue(p, "cwd", "."), "configuration": checkValue(p, "configuration", mapping{}), "description": p["description"], "before": task["start_snapshot"], "after": after}
	appendRegistry(task, event)
	return mapping{"setup": c}, nil
}
func extendChecks(state, task, event, p mapping, directory string) (any, error) {
	if task["status"] != "verifying" || truth(task["active_review"]) {
		return nil, reject("extension_phase", "Extend checks after both review lenses finish")
	}
	if _, e := checkSource(state, task); e != nil {
		return nil, e
	}
	if truth(p["verification_result"]) == truth(p["review_round"]) {
		return nil, reject("extension_evidence", "Reference the verification lens conclusion or its more_checks round")
	}
	additions := array(p["additional"])
	if truth(p["verification_result"]) {
		result, err := applicableVerification(state, task, directory, "")
		if err != nil {
			return nil, err
		}
		if result == nil || p["verification_result"] != result["id"] || (result["outcome"] != "failed" && result["outcome"] != "unavailable") {
			return nil, reject("extension_evidence", "Reference the current failed or unavailable verification lens conclusion")
		}
		requested := checkSet{}
		for _, v := range array(result["criteria_results"]) {
			m := object(v)
			if m["outcome"] != "passed" && truth(m["check_request"]) {
				requested[str(m["criterion_id"])] = true
			}
		}
		valid := len(additions) > 0
		for _, v := range additions {
			c := object(v)
			valid = valid && truth(c["criteria"]) && checkList(c["criteria"], false) && checkIDs(c["criteria"]).subset(requested)
		}
		if !valid {
			return nil, reject("extension_evidence", "Bind each addition to a criterion with a concrete verification lens check request")
		}
	} else {
		current := object(roundResults(task, nil)["verification"])
		if current["verdict"] != "more_checks" || len(additions) == 0 || p["review_round"] != current["round_id"] {
			return nil, reject("extension_evidence", "Reference the review requesting additional checks")
		}
	}
	if e := reservedChecks(state, task, additions); e != nil {
		return nil, e
	}
	for _, v := range additions {
		c := object(v)
		run := object(c["run"])
		if !truth(c["id"]) || !truth(c["source"]) || len(run) != 1 || !checkHas(run, "command") && !checkHas(run, "procedure") || !checkList(c["criteria"], false) || !truth(c["criteria"]) || !checkIDs(c["criteria"]).subset(taskCheckCriteria(state, task)) {
			return nil, reject("check_schema", "Add exact runnable checks with scoped AC")
		}
		if checkByID(array(task["checks"]), str(c["id"])) != nil {
			return nil, reject("duplicate_check", "Existing checks cannot be replaced")
		}
		if e := requireDeterministic(c); e != nil {
			return nil, e
		}
		if checkHas(run, "command") {
			if e := requireArgv(run["command"]); e != nil {
				return nil, e
			}
		} else {
			path := str(run["procedure"])
			if strings.TrimSpace(path) == "" {
				return nil, reject("check_schema", "Procedure path required")
			}
			file, e := contained(taskRoot(state, task), path)
			if e != nil {
				return nil, e
			}
			if info, e := os.Stat(file); e != nil || !info.Mode().IsRegular() {
				return nil, reject("procedure_unavailable", path)
			}
		}
		task["checks"] = append(array(task["checks"]), addedCheck(c))
	}
	appendRegistry(task, event)
	return mapping{"checks": task["checks"]}, nil
}
