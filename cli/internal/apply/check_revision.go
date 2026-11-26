package apply

import (
	"sort"
	"strings"
)

func registryChecks(state, task mapping, directory string) ([]any, error) {
	if workKind(object(state["basis"])) != "refactoring" {
		return array(task["checks"]), nil
	}
	type confirmation struct {
		revision int
		task     mapping
	}
	var confirmed []confirmation
	for id, v := range object(state["tasks"]) {
		other := object(v)
		r := object(other["check_registry"])
		n := intValue(r["confirmed_revision"])
		if n == 0 {
			continue
		}
		if err := checkRegistryCurrent(state, other); err != nil {
			return nil, err
		}
		e, err := openExecution(directory)
		if err != nil {
			return nil, err
		}
		entry, err := e.lookup(e.manifest["event_index"], str(r["confirmation_event"]))
		if err != nil {
			return nil, err
		}
		ev := object(entry["event"])
		if ev["type"] != "accept" || ev["task_id"] != id {
			return nil, reject("registry_confirmation_missing", "Confirmed registry requires its recorded acceptance event")
		}
		confirmed = append(confirmed, confirmation{intValue(entry["revision"]), other})
	}
	sort.Slice(confirmed, func(i, j int) bool { return confirmed[i].revision < confirmed[j].revision })
	index := map[string]mapping{}
	order := []string{}
	put := func(c mapping) {
		id := str(c["id"])
		if _, ok := index[id]; !ok {
			order = append(order, id)
		}
		index[id] = c
	}
	overlay := func(h []any) {
		for _, entry := range h {
			tr := object(object(entry)["transition"])
			before, after := array(tr["before"]), array(tr["after"])
			for _, v := range before {
				id := str(object(v)["id"])
				if checkByID(after, id) == nil {
					delete(index, id)
					for i, k := range order {
						if k == id {
							order = append(order[:i], order[i+1:]...)
							break
						}
					}
				}
			}
			for _, v := range after {
				c := object(v)
				if !checkSame(checkByID(before, str(c["id"])), c) {
					put(c)
				}
			}
		}
	}
	for _, item := range confirmed {
		r := object(item.task["check_registry"])
		n := intValue(r["confirmed_revision"])
		h := array(r["history"])
		for _, v := range array(object(h[n-1])["checks"]) {
			put(object(v))
		}
		overlay(h[:n])
	}
	if task["status"] != "accepted" {
		for _, v := range array(task["checks"]) {
			put(object(v))
		}
		overlay(array(object(task["check_registry"])["history"]))
	}
	out := []any{}
	for _, id := range order {
		out = append(out, index[id])
	}
	return out, nil
}
func authorizedRevision(state, task, p mapping, before, after []any) error {
	basis := object(p["basis"])
	if len(basis) == 0 || !checkFields(basis, "", "test_changes transitional_criteria") {
		return reject("revision_basis", "Name approved test_changes or transitional acceptance criteria")
	}
	anyBasis := false
	for _, v := range basis {
		if !checkList(v, true) {
			return reject("revision_basis", "Name approved test_changes or transitional acceptance criteria")
		}
		anyBasis = anyBasis || truth(v)
	}
	if !anyBasis {
		return reject("revision_basis", "Name approved test_changes or transitional acceptance criteria")
	}
	permission, replacements, retired := checkSet{}, checkSet{}, checkSet{}
	changes := []mapping{}
	for _, k := range stringArray(basis["test_changes"]) {
		m := checkByID(array(object(task["plan"])["test_changes"]), k)
		if m == nil {
			return reject("revision_basis", "Unknown task test-change permission")
		}
		changes = append(changes, m)
		permission.add(checkIDs(m["criteria"]))
		replacements.add(checkIDs(m["replacement_criteria"]))
	}
	for _, k := range stringArray(basis["transitional_criteria"]) {
		c := object(object(state["acceptance"])[k])
		if c["lifetime"] != "transitional" || c["until_task"] != object(task["plan"])["id"] {
			return reject("revision_basis", "Only the approved terminating task can retire a transitional criterion")
		}
		retired[k] = true
		permission[k] = true
		replacements.add(checkIDs(c["replaced_by"]))
	}
	affected, changed := checkSet{}, checkSet{}
	for _, list := range [][]any{before, after} {
		for _, v := range list {
			id := str(object(v)["id"])
			if !checkSame(checkByID(before, id), checkByID(after, id)) {
				changed[id] = true
				affected.add(checkIDs(object(v)["criteria"]))
			}
		}
	}
	if len(changed) == 0 {
		return reject("revision_unchanged", "New registry contents must differ")
	}
	m := object(p["mapping"])
	valid := len(m) == len(changed)
	for k := range changed {
		valid = valid && strings.TrimSpace(str(m[k])) != ""
	}
	if !valid {
		return reject("revision_mapping", "Map every changed check to its approved group and actual affected tests")
	}
	permission.add(replacements)
	if !affected.subset(permission) {
		return reject("revision_scope", "Changed check exceeds the approved group or transition")
	}
	for id := range changed {
		old, new := checkByID(before, id), checkByID(after, id)
		if old != nil {
			criteria := checkIDs(old["criteria"])
			ok := criteria.subset(retired)
			for _, c := range changes {
				ok = ok || criteria.subset(checkIDs(c["criteria"])) && (c["action"] == "adapt" || c["action"] == "move" || c["action"] == "remove")
			}
			if !ok {
				return reject("revision_scope", "Adding a check does not authorize removing or adapting an existing check")
			}
		}
		if new != nil {
			criteria := checkIDs(new["criteria"])
			ok := criteria.subset(replacements)
			for _, c := range changes {
				allows := checkIDs(c["criteria"])
				allows.add(checkIDs(c["replacement_criteria"]))
				ok = ok || criteria.subset(allows)
			}
			if !ok {
				return reject("revision_scope", "Replacement check needs an approved criterion")
			}
		}
	}
	covered, prior, preserved := checkCriteria(after), checkCriteria(before), checkSet{}
	for _, v := range object(state["tasks"]) {
		preserved.add(checkIDs(object(object(v)["plan"])["preserves"]))
	}
	names := checkSet{}
	for k := range affected {
		if preserved[k] {
			names[k] = true
		}
	}
	actual := checkIDs(p["preserves"])
	if !checkList(p["preserves"], true) || len(names) != len(actual) || !names.subset(actual) {
		return reject("revision_preservation", "Name the exact preserved obligations affected by this revision")
	}
	for k := range prior {
		if preserved[k] && !covered[k] {
			return reject("criteria_uncovered", "Preservation and replacing-state checks remain mandatory")
		}
	}
	if !replacements.subset(covered) {
		return reject("criteria_uncovered", "Preservation and replacing-state checks remain mandatory")
	}
	for _, c := range changes {
		if c["action"] == "remove" && truth(c["decision"]) {
			for k := range checkIDs(c["criteria"]) {
				if !preserved[k] {
					retired[k] = true
				}
			}
		}
	}
	for k := range prior {
		if !covered[k] && !retired[k] {
			return reject("criteria_uncovered", "A persistent obligation keeps its identity when its test moves")
		}
	}
	for _, v := range before {
		m := object(v)
		if checkByID(after, str(m["id"])) == nil && m["source"] != "tasks.md" && len(changes) == 0 {
			return reject("revision_scope", "Project checks require an explicit approved test-change group")
		}
	}
	return nil
}
func reviseChecks(state, task, event, p mapping, directory string) (any, error) {
	if workKind(object(state["basis"])) != "refactoring" {
		return nil, reject("revision_work_kind", "Registry revisions are for approved refactoring work")
	}
	if task["status"] != "running" && task["status"] != "repairing" || !truth(task["baseline_checks"]) {
		return nil, reject("revision_phase", "Capture baseline; revise within the running or reserved repair task")
	}
	if truth(task["last_check_failed"]) && !truth(task["active_repair"]) {
		return nil, reject("repair_cycle_required", "Reserve repair before revising a failed set")
	}
	if object(object(state["roles"])[str(task["executor"])])["status"] != "active" {
		return nil, reject("writer_active", "Assigned executor must own the revision")
	}
	if e := checkRegistryCurrent(state, task); e != nil {
		return nil, e
	}
	r := object(task["check_registry"])
	if n, ok := integer(p["registry_revision"]); !ok || n != intValue(r["revision"]) {
		return nil, reject("registry_revision_conflict", "Re-read the current registry revision")
	}
	before, e := registryChecks(state, task, directory)
	if e != nil {
		return nil, e
	}
	if !checkSame(before, p["before"]) {
		return nil, reject("registry_revision_conflict", "Exact previous applicable check records required")
	}
	after := array(p["after"])
	if len(after) == 0 {
		return nil, reject("check_schema", "Exact new check records required")
	}
	for _, v := range after {
		if object(v) == nil {
			return nil, reject("check_schema", "Exact new check records required")
		}
	}
	allowed := taskCheckCriteria(state, task)
	allowed.add(checkCriteria(before))
	seen := checkSet{}
	var newChecks []any
	for _, v := range after {
		c := object(v)
		id := str(c["id"])
		_, cwd := c["cwd"].(string)
		if !checkFields(c, "id criteria source run cwd configuration setup", "location execution_kind") || id == "" || str(c["source"]) == "" || !truth(c["criteria"]) || !checkList(c["criteria"], true) || !checkIDs(c["criteria"]).subset(allowed) || !cwd || object(c["configuration"]) == nil {
			return nil, reject("check_schema", "New checks require complete scoped command records")
		}
		if e := requireDeterministic(c); e != nil {
			return nil, e
		}
		seen[id] = true
		old := checkByID(before, id)
		if old == nil {
			newChecks = append(newChecks, c)
		}
		if checkSame(c, old) {
			continue
		}
		run := object(c["run"])
		if c["setup"] != nil || len(run) != 1 || !checkHas(run, "command") && !checkHas(run, "procedure") {
			return nil, reject("check_schema", "A replacement requires an exact command or an existing procedure")
		}
		if checkHas(run, "command") {
			if e := requireArgv(run["command"]); e != nil {
				return nil, e
			}
		} else if strings.TrimSpace(str(run["procedure"])) == "" {
			return nil, reject("check_schema", "Procedure path required")
		}
		for _, k := range []string{"cwd", "location"} {
			if val, ok := c[k]; ok && !(k == "cwd" && val == ".") {
				if _, e := contained(taskRoot(state, task), str(val)); e != nil {
					return nil, e
				}
			}
		}
	}
	if len(seen) != len(after) {
		return nil, reject("duplicate_check", "Duplicate revised check ID")
	}
	if e := reservedChecks(state, task, newChecks); e != nil {
		return nil, e
	}
	if strings.TrimSpace(str(p["reason"])) == "" {
		return nil, reject("revision_basis", "Record the reason for changed applicability")
	}
	if e := authorizedRevision(state, task, p, before, after); e != nil {
		return nil, e
	}
	own := []any{}
	for _, v := range after {
		c := object(v)
		id := str(c["id"])
		if checkByID(array(task["checks"]), id) != nil || !checkSame(checkByID(before, id), c) {
			own = append(own, checkClone(c))
		}
	}
	task["checks"] = own
	transition := object(checkClone(p))
	transition["event_id"] = event["event_id"]
	r["transition"] = transition
	appendRegistry(task, event)
	if e := checkRegistryCurrent(state, task); e != nil {
		return nil, e
	}
	state["final"] = nil
	checks, e := registryChecks(state, task, directory)
	return mapping{"registry_revision": r["revision"], "status": "pending_confirmation", "checks": checks}, e
}
