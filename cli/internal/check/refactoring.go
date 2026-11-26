package check

import (
	"bytes"
	"net/url"
	"os"
	"path/filepath"
	"slices"
	"strings"
	"unicode"

	"github.com/yuin/goldmark"
	"github.com/yuin/goldmark/ast"
	"github.com/yuin/goldmark/text"
)

type object = map[string]any
type ids = map[string]bool

func word(v any) string                   { s, _ := v.(string); return s }
func listed(v any, values ...string) bool { return slices.Contains(values, word(v)) }
func has(m object, k string) bool         { _, ok := m[k]; return ok }
func requiredFile(root string, v any) (string, *checkError) {
	raw := word(v)
	if !nonemptyText(raw) {
		return "", &checkError{Code: "invalid_path", Message: "Expected a nonempty project-relative path", Exit: 1}
	}
	raw, _, _ = strings.Cut(raw, "#")
	p, e := containedPath(root, raw)
	if e != nil {
		return "", e
	}
	if info, e := os.Stat(p); e != nil || !info.Mode().IsRegular() {
		return "", &checkError{Code: "missing_path", Message: "Missing referenced file: " + raw, Exit: 1}
	}
	return p, nil
}
func baseline(project string, v any) ([]string, map[string]string, *checkError) {
	path, e := requiredFile(project, v)
	if e != nil {
		return nil, nil, e
	}
	body, diag := readDocumentText(path)
	if diag != nil {
		return nil, nil, &checkError{Code: diag.code, Message: diag.message, Path: path, Exit: 2}
	}
	source := []byte(body)
	root := goldmark.DefaultParser().Parse(text.NewReader(source))
	headings := []string{}
	records := map[string]string{}
	ast.Walk(root, func(n ast.Node, entering bool) (ast.WalkStatus, error) {
		if !entering {
			return ast.WalkContinue, nil
		}
		switch v := n.(type) {
		case *ast.Heading:
			headings = append(headings, string(v.Text(source)))
		case *ast.FencedCodeBlock:
			if v.Info == nil || strings.TrimSpace(string(v.Info.Segment.Value(source))) != "yaml" {
				break
			}
			var b bytes.Buffer
			for i := 0; i < v.Lines().Len(); i++ {
				l := v.Lines().At(i)
				b.Write(l.Value(source))
			}
			r, diag := parseYAMLMapping(b.String())
			if diag != nil {
				if diag.code != "yaml_mapping" {
					e = &checkError{Code: diag.code, Message: diag.message, Path: path, Exit: 1}
					return ast.WalkStop, nil
				}
			} else if kind := word(r["sdd_record"]); kind != "" {
				records[word(r["id"])] = kind
			}
		}
		return ast.WalkContinue, nil
	})
	return headings, records, e
}
func (v *documentValidation) kinds(kind string) ids {
	m := ids{}
	for _, id := range v.order {
		if v.records[id].kind == kind {
			m[id] = true
		}
	}
	return m
}
func union(a, b ids) ids {
	m := ids{}
	for k := range a {
		m[k] = true
	}
	for k := range b {
		m[k] = true
	}
	return m
}
func uncovered(a, b ids) []string {
	m := ids{}
	for k := range a {
		if !b[k] {
			m[k] = true
		}
	}
	return sortedIDs(m)
}
func (v *documentValidation) localRefs(r changeRecord, key string, value any, allowed ids, nonempty bool) []string {
	a, ok := stringList(value)
	if !ok || (nonempty && len(a) == 0) {
		s := ""
		if nonempty {
			s = "nonempty "
		}
		v.problem(r, "reference_list", key+" must be a "+s+"list of local IDs")
		return nil
	}
	seen := ids{}
	for _, k := range a {
		if seen[k] {
			v.problem(r, "duplicate_reference", "Duplicate links in "+key)
			break
		}
		seen[k] = true
	}
	var result []string
	for _, k := range a {
		if !allowed[k] {
			v.problem(r, "missing_reference", key+": unresolved or wrong-kind reference "+k)
		} else {
			result = append(result, k)
		}
	}
	return result
}
func validTexts(a any, unique bool) bool {
	v, ok := stringList(a)
	if !ok {
		return false
	}
	seen := ids{}
	for _, s := range v {
		if !nonemptyText(s) || (unique && seen[s]) {
			return false
		}
		seen[s] = true
	}
	return true
}
func (v *documentValidation) refSource(project string, r changeRecord) *checkError {
	src, ok := r.fields["source"].(map[string]any)
	diag := func(message string) { v.problem(r, "source", message) }
	if !ok {
		diag("preservation requires source")
		return nil
	}
	handle := func(e *checkError) *checkError {
		if e != nil && e.Exit == 1 {
			v.problem(r, e.Code, e.Message)
			return nil
		}
		return e
	}
	switch src["kind"] {
	case "specification":
		if !hasFields(src, []string{"kind", "path", "requirement"}, nil) || !nonemptyText(src["requirement"]) {
			diag("specification source requires path and requirement")
			return nil
		}
		headers, records, e := baseline(project, src["path"])
		if e != nil {
			return handle(e)
		}
		target := word(src["requirement"])
		if !slices.Contains(headers, target) && records[target] == "" {
			v.problem(r, "source_requirement", "Baseline requirement ID or exact heading was not found")
		}
	case "evidence":
		if !hasFields(src, []string{"kind", "baseline_missing", "references", "observed", "assumptions"}, nil) || src["baseline_missing"] != true {
			diag("Evidence must explicitly declare baseline_missing: true")
			return nil
		}
		if !nonemptyText(src["observed"]) || !nonemptyText(src["assumptions"]) {
			diag("Evidence requires observed behavior and assumptions")
			return nil
		}
		refs, ok := src["references"].([]any)
		if !ok || len(refs) == 0 {
			diag("Evidence requires references")
			return nil
		}
		for _, ref := range refs {
			if !nonemptyText(ref) {
				diag("Evidence references must be nonempty strings")
				return nil
			}
			u, err := url.Parse(word(ref))
			if err == nil && (u.Scheme == "https" || u.Scheme == "http") && u.Host != "" {
				continue
			}
			if _, e := requiredFile(project, ref); e != nil {
				return handle(e)
			}
		}
	default:
		diag("Unknown source kind")
	}
	return nil
}
func (v *documentValidation) supersedes(project string, r changeRecord) *checkError {
	links, _ := r.fields["supersedes"].([]any)
	if len(links) == 0 {
		v.problem(r, "supersedes", "supersedes must be a nonempty list of path/id or path/anchor links")
	}
	for _, entry := range links {
		l, _ := entry.(map[string]any)
		if !hasFields(l, []string{"path", "id"}, nil) && !hasFields(l, []string{"path", "anchor"}, nil) {
			v.problem(r, "supersedes", "Each supersedes link requires path and either id or anchor")
			continue
		}
		hs, records, e := baseline(project, l["path"])
		if e != nil {
			if e.Exit == 2 {
				return e
			}
			v.problem(r, e.Code, e.Message)
			continue
		}
		if has(l, "id") {
			id := word(l["id"])
			if !validDocumentID(id, "DEC") || records[id] != "decision" {
				v.problem(r, "supersedes", "Superseded DEC was not found at path")
			}
		} else {
			anchor := word(l["anchor"])
			found := false
			for _, h := range hs {
				slug := strings.Map(func(c rune) rune {
					if unicode.IsLetter(c) || unicode.IsNumber(c) || c == '_' || c == '-' {
						return unicode.ToLower(c)
					}
					if c == ' ' {
						return '-'
					}
					return -1
				}, h)
				found = found || h == anchor || slug == anchor
			}
			if !found || !nonemptyText(anchor) {
				v.problem(r, "supersedes", "Superseded heading/anchor was not found at path")
			}
		}
	}
	return nil
}
func (v *documentValidation) refactoring(project, root, stage string) (object, *checkError) {
	criteria := v.kinds("criterion")
	results, preservation := ids{}, ids{}
	parents := taskGraph{dependencies: map[string][]string{}}
	for k := range criteria {
		switch v.records[k].fields["purpose"] {
		case "result":
			results[k] = true
			parents.dependencies[k] = nil
		case "preservation":
			preservation[k] = true
		}
	}
	design := filepath.Join(root, "design.md")
	if len(results) == 0 {
		v.issue("missing_results", "Design requires at least one result criterion", design, nil)
	}
	for _, id := range v.order {
		if !criteria[id] {
			continue
		}
		r := v.records[id]
		f := r.fields
		for _, key := range []string{"conditions", "expected"} {
			if !nonemptyText(f[key]) {
				v.problem(r, "record_text", key+" must be nonempty text")
			}
		}
		if a, ok := stringList(f["scope"]); !ok || len(a) == 0 || !validTexts(f["scope"], false) {
			v.problem(r, "criterion_scope", "scope must be a nonempty list of described areas")
		}
		if !results[id] && !preservation[id] {
			v.problem(r, "criterion_purpose", "purpose must be result or preservation")
		}
		if preservation[id] || has(f, "source") {
			if e := v.refSource(project, r); e != nil {
				return nil, e
			}
		}
		if has(f, "parent") {
			parent := word(f["parent"])
			if !results[id] || !results[parent] {
				v.problem(r, "criterion_parent", "parent must link a result to another local result criterion")
			} else if id == parent {
				v.problem(r, "self_reference", "Criterion may not parent itself")
			} else {
				parents.dependencies[id] = []string{parent}
			}
		}
	}
	if cycle := parents.tasksBlockedByCycle(); len(cycle) > 0 {
		v.issue("parent_cycle", "Criterion parent cycle: "+documentList(cycle), design, nil)
	}
	for _, id := range v.order {
		r := v.records[id]
		if r.kind == "decision" {
			v.localRefs(r, "criteria", r.fields["criteria"], criteria, true)
			if has(r.fields, "supersedes") {
				if e := v.supersedes(project, r); e != nil {
					return nil, e
				}
			}
		}
	}
	out := object{"warnings": []object{}}
	if stage == "plan" {
		out["tasks"], out["progress"] = v.refPlan(project, filepath.Join(root, "tasks.md"), results, preservation)
	}
	out["errors"] = v.errors
	return out, nil
}
func (v *documentValidation) refCheck(project string, r changeRecord, c object, allowed ids, whole bool) []string {
	required := []string{"criteria", "location", "run", "test_description"}
	optional := []string{"execution_kind"}
	if whole {
		optional = append(optional, "setup_task")
	} else {
		required = []string{"criteria", "id", "location", "run", "test_description"}
	}
	if !hasFields(c, required, optional) {
		v.problem(r, "verification", "Verification requires "+documentList(required))
		return nil
	}
	if !whole && !validDocumentSlug(c["id"]) {
		v.problem(r, "verification_id", "Verification id must be a stable lowercase-kebab-case slug")
	}
	run, _ := c["run"].(map[string]any)
	kind := c["execution_kind"]
	if !has(c, "execution_kind") && !has(run, "procedure") {
		kind = "deterministic"
	}
	if !listed(kind, "deterministic", "behavioral", "manual") {
		v.problem(r, "execution_kind", "execution_kind must be deterministic, behavioral or manual; procedures require an explicit type")
	}
	refs := v.localRefs(r, "verification.criteria", c["criteria"], allowed, true)
	if !nonemptyText(c["test_description"]) {
		v.problem(r, "verification", "test_description must be nonempty text")
	}
	if e := checkVerificationLocation(project, c["location"]); e != nil {
		v.problem(r, e.Code, e.Message)
	}
	if len(run) == 1 && has(run, "command") {
		a, ok := stringList(run["command"])
		if !ok || len(a) == 0 || !nonemptyText(a[0]) || strings.Contains(strings.Join(a, ""), "\x00") {
			v.problem(r, "verification_run", "command must be a nonempty argument array with a nonempty executable and no NUL")
		}
	} else {
		v.validateVerificationRun(project, r, run)
	}
	if whole {
		if has(run, "setup_required") && !has(c, "setup_task") {
			v.problem(r, "setup_task", "A whole-work setup_required check requires setup_task")
		}
		if has(c, "setup_task") && v.records[word(c["setup_task"])].kind != "task" {
			v.problem(r, "setup_task", "setup_task must name an existing local task")
		}
	}
	return refs
}
func (v *documentValidation) taskScope(project string, r changeRecord) {
	a, _ := r.fields["scope"].([]any)
	if len(a) == 0 {
		v.problem(r, "task_scope", "scope must be a nonempty list of modules and known relative paths")
	}
	for _, entry := range a {
		area, _ := entry.(map[string]any)
		if !hasFields(area, []string{"module"}, []string{"paths"}) || !nonemptyText(area["module"]) {
			v.problem(r, "task_scope", "Each scope requires module and optional paths")
			continue
		}
		if has(area, "paths") {
			paths, ok := stringList(area["paths"])
			if !ok || len(paths) == 0 || !validTexts(area["paths"], false) {
				v.problem(r, "task_scope", "scope.paths must be a nonempty list of project-relative paths")
				continue
			}
			for _, path := range paths {
				if _, e := containedPath(project, path); e != nil {
					v.problem(r, e.Code, e.Message)
				}
			}
		}
	}
}
func (v *documentValidation) refPlan(project, path string, results, preservation ids) (object, map[string]int) {
	tasks, local, whole := v.kinds("task"), v.kinds("acceptance"), v.kinds("verification")
	criteria := union(results, preservation)
	graph := taskGraph{dependencies: map[string][]string{}, conflicts: map[string]ids{}, done: ids{}}
	owners, verified := map[string]ids{}, map[string]ids{}
	for id := range tasks {
		owners[id] = ids{}
		verified[id] = ids{}
		graph.conflicts[id] = ids{}
	}
	persistent := ids{}
	for _, id := range v.order {
		if !local[id] {
			continue
		}
		r := v.records[id]
		f := r.fields
		owner := word(f["task"])
		if !tasks[owner] {
			v.problem(r, "acceptance_task", "Local acceptance must belong to an existing local task")
		} else {
			owners[owner][id] = true
		}
		for _, k := range []string{"conditions", "expected"} {
			if !nonemptyText(f[k]) {
				v.problem(r, "record_text", k+" must be nonempty text")
			}
		}
		if !listed(f["lifetime"], "persistent", "transitional") {
			v.problem(r, "acceptance_lifetime", "lifetime must be persistent or transitional")
		}
		if f["lifetime"] == "persistent" {
			persistent[id] = true
		}
		if f["lifetime"] == "transitional" {
			if !has(f, "until_task") || !has(f, "replaced_by") {
				v.problem(r, "acceptance_transition", "Transitional acceptance requires until_task and nonempty replaced_by")
			}
		} else if has(f, "until_task") || has(f, "replaced_by") {
			v.problem(r, "acceptance_transition", "Only transitional local acceptance may have until_task/replaced_by")
		}
	}
	contributions := ids{}
	nums := map[int]bool{}
	allLocalVerified := ids{}
	for _, id := range v.order {
		if !tasks[id] {
			continue
		}
		r := v.records[id]
		f := r.fields
		v.taskScope(project, r)
		for _, k := range v.localRefs(r, "contributes_to", f["contributes_to"], results, true) {
			contributions[k] = true
		}
		allowed := union(owners[id], nil)
		for _, k := range v.localRefs(r, "preserves", f["preserves"], preservation, false) {
			allowed[k] = true
		}
		if a, ok := stringList(f["preserves"]); ok && len(a) == 0 && !nonemptyText(f["preservation_reason"]) {
			v.problem(r, "preservation_reason", "Empty preserves requires a nonempty preservation_reason for semantic review")
		}
		if has(f, "preservation_reason") && !nonemptyText(f["preservation_reason"]) {
			v.problem(r, "record_text", "preservation_reason must be nonempty text")
		}
		deps := v.localRefs(r, "depends_on", f["depends_on"], tasks, false)
		graph.dependencies[id] = deps
		conflicts := []string{}
		if has(f, "cannot_parallel_with") {
			conflicts = v.localRefs(r, "cannot_parallel_with", f["cannot_parallel_with"], tasks, false)
		}
		for _, k := range append(slices.Clone(deps), conflicts...) {
			if k == id {
				v.problem(r, "self_reference", "Task may not reference itself")
			}
		}
		for _, k := range conflicts {
			graph.conflicts[id][k] = true
			graph.conflicts[k][id] = true
		}
		if !listed(f["status"], "pending", "in_progress", "done", "blocked") {
			v.problem(r, "task_status", "Unknown task status")
		}
		if f["status"] == "done" {
			graph.done[id] = true
		}
		if len(owners[id]) == 0 {
			v.problem(r, "local_acceptance", "Each task requires at least one local acceptance criterion")
		}
		if n, ok := f["number"].(int); ok && n > 0 && n <= len(tasks) {
			nums[n] = true
		}
		checks, _ := f["verification"].([]any)
		if len(checks) == 0 {
			v.problem(r, "verification", "verification must be a nonempty list")
		}
		seen := ids{}
		for _, entry := range checks {
			c, _ := entry.(map[string]any)
			for _, k := range v.refCheck(project, r, c, allowed, false) {
				verified[id][k] = true
				allLocalVerified[k] = true
			}
			if k, ok := c["id"].(string); ok {
				if seen[k] {
					v.problem(r, "verification_id", "Duplicate verification id: "+k)
				}
				seen[k] = true
			}
		}
		if m := uncovered(allowed, verified[id]); len(m) > 0 {
			v.problem(r, "verification_coverage", "Missing local/preservation verification for: "+documentList(m))
		}
		if has(f, "test_changes") {
			v.testChanges(r, union(criteria, local), preservation)
		}
	}
	if m := uncovered(results, contributions); len(m) > 0 {
		v.issue("contribution_coverage", "No task contributes to result criteria: "+documentList(m), path, nil)
	}
	if len(nums) != len(tasks) {
		v.issue("task_numbers", "Task numbers must be a permutation of 1..N", path, nil)
	}
	if cycle := graph.tasksBlockedByCycle(); len(cycle) > 0 {
		v.issue("task_cycle", "Dependency cycle or tasks downstream of cycle: "+documentList(cycle), path, nil)
	}
	replacement := taskGraph{dependencies: map[string][]string{}}
	for id := range local {
		replacement.dependencies[id] = nil
	}
	for _, id := range v.order {
		if !local[id] {
			continue
		}
		r := v.records[id]
		if r.fields["lifetime"] != "transitional" {
			continue
		}
		targets := v.localRefs(r, "replaced_by", r.fields["replaced_by"], union(criteria, local), true)
		for _, t := range targets {
			if local[t] {
				replacement.dependencies[id] = append(replacement.dependencies[id], t)
			}
		}
		until := word(r.fields["until_task"])
		if !tasks[until] {
			v.problem(r, "until_task", "until_task must name an existing local task")
			continue
		}
		anc := ids{}
		pending := slices.Clone(graph.dependencies[until])
		for len(pending) > 0 {
			k := pending[len(pending)-1]
			pending = pending[:len(pending)-1]
			if !anc[k] {
				anc[k] = true
				pending = append(pending, graph.dependencies[k]...)
			}
		}
		if owner := word(r.fields["task"]); until == owner || !anc[owner] {
			v.problem(r, "until_task_reachability", "until_task must be another task downstream of the acceptance owner")
		}
		anc[until] = true
		for _, t := range targets {
			if t == id {
				v.problem(r, "self_reference", "A criterion cannot replace itself")
			}
			owner := word(v.records[t].fields["task"])
			if !anc[owner] || !verified[owner][t] {
				v.problem(r, "replacement_verification", "Replacement "+t+" needs a check owned by until_task or a dependency predecessor; final-only evidence is insufficient")
			}
		}
	}
	if cycle := replacement.tasksBlockedByCycle(); len(cycle) > 0 {
		v.issue("replacement_cycle", "Criterion replacement cycle: "+documentList(cycle), path, nil)
	}
	wholeVerified := ids{}
	for _, id := range v.order {
		if !whole[id] {
			continue
		}
		r := v.records[id]
		c := object{}
		for k, value := range r.fields {
			if k != "id" && k != "sdd_record" {
				c[k] = value
			}
		}
		for _, k := range v.refCheck(project, r, c, union(criteria, persistent), true) {
			wholeVerified[k] = true
		}
	}
	if len(whole) == 0 {
		v.issue("whole_verification", "Plan requires at least one whole-work verification record", path, nil)
	}
	if m := uncovered(criteria, wholeVerified); len(m) > 0 {
		v.issue("whole_coverage", "Missing whole-work verification for: "+documentList(m), path, nil)
	}
	if len(uncovered(persistent, union(allLocalVerified, wholeVerified))) > 0 {
		v.issue("persistent_coverage", "Persistent local results require applicable task or whole-work checks", path, nil)
	}
	available := []string{}
	conflicts := map[string][]string{}
	for k := range tasks {
		if v.records[k].fields["status"] == "pending" && graph.allDependenciesDone(k) {
			available = append(available, k)
		}
		conflicts[k] = sortedIDs(graph.conflicts[k])
	}
	slices.Sort(available)
	return object{"available_by_graph": available, "cannot_parallel_with": conflicts, "parallel_safety": "Requires reviewer assessment of shared files and other conflicts"}, map[string]int{"done": len(graph.done), "total": len(tasks)}
}
func (v *documentValidation) testChanges(r changeRecord, criteria, preservation ids) {
	changes, ok := r.fields["test_changes"].([]any)
	if !ok {
		v.problem(r, "test_changes", "test_changes must be a list")
		return
	}
	seen := ids{}
	for _, entry := range changes {
		c, _ := entry.(map[string]any)
		if !hasFields(c, []string{"id", "action", "group", "criteria", "reason"}, []string{"decision", "replacement_criteria"}) {
			v.problem(r, "test_changes", "A test change requires id/action/group/criteria/reason and optional decision/replacement_criteria")
			continue
		}
		id := word(c["id"])
		if !validDocumentSlug(id) || seen[id] {
			v.problem(r, "test_change_id", "Test-change IDs must be unique stable slugs within their task")
		}
		seen[id] = true
		if !listed(c["action"], "add", "adapt", "move", "remove") {
			v.problem(r, "test_changes", "Unknown test-change action")
		}
		if !nonemptyText(c["group"]) || !nonemptyText(c["reason"]) {
			v.problem(r, "test_changes", "Test group and reason must be nonempty text")
		}
		affected := v.localRefs(r, "test_changes.criteria", c["criteria"], criteria, true)
		var replacements []string
		if has(c, "replacement_criteria") {
			replacements = v.localRefs(r, "replacement_criteria", c["replacement_criteria"], criteria, false)
		}
		decision := v.records[word(c["decision"])].kind == "decision"
		if has(c, "decision") && !decision {
			v.problem(r, "test_change_decision", "decision must name a local DEC")
		}
		if c["action"] == "remove" && len(replacements) == 0 {
			if !decision {
				v.problem(r, "test_change_basis", "Removal requires replacement_criteria or an architectural decision retiring the old boundary")
			}
			if slices.ContainsFunc(affected, func(k string) bool { return preservation[k] }) {
				v.problem(r, "test_change_preservation", "Removing a preservation check requires replacement criteria; a DEC alone cannot retire the obligation")
			}
		}
	}
}
