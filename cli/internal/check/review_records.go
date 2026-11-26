package check

import (
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"slices"
	"strings"
	"time"
)

var oidPattern = regexp.MustCompile(`^(?:[0-9a-f]{40}|[0-9a-f]{64})$`)
var runID = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9_-]*$`)
var commonFields = []string{"schema_version", "change_id", "document_type", "language", "work_kind"}

// A review file can fail independently of the other files. Only structured
// document diagnostics are recovered at this boundary.
type reviewProblem struct {
	msg, code, path string
	element         any
	fatal           bool
}

func require(ok bool, msg string) {
	if !ok {
		panic(reviewProblem{msg: msg})
	}
}
func guarded(fn func()) (problem *reviewProblem) {
	defer func() {
		if v := recover(); v != nil {
			p, ok := v.(reviewProblem)
			if !ok {
				panic(v)
			}
			problem = &p
		}
	}()
	fn()
	return nil
}
func reviewFields(v any, keys string, opt ...string) object {
	m, ok := v.(map[string]any)
	require(ok, "Expected a mapping")
	required := strings.Fields(keys)
	missing := []string{}
	for _, key := range required {
		if !has(m, key) {
			missing = append(missing, key)
		}
	}
	slices.Sort(missing)
	require(len(missing) == 0, "Missing fields: "+documentList(missing))
	require(hasFields(m, required, opt), "Unknown fields")
	return m
}
func stamp(v any) time.Time {
	require(nonemptyText(v), "Timestamp must be quoted text")
	raw := word(v)
	for _, layout := range []string{time.RFC3339Nano, "2006-01-02 15:04:05Z07:00", "2006-01-02T15:04Z07:00", "2006-01-02T15:04:05-0700"} {
		if t, e := time.Parse(layout, raw); e == nil {
			return t
		}
	}
	for _, layout := range []string{"2006-01-02", "2006-01-02T15:04:05", "2006-01-02 15:04:05"} {
		if _, e := time.Parse(layout, raw); e == nil {
			require(false, "Timestamp needs a timezone")
		}
	}
	panic(reviewProblem{msg: "Invalid timestamp"})
}
func commitOID(v any, size int) {
	s := word(v)
	require(oidPattern.MatchString(s), "Expected a full Git commit OID")
	require(size == 0 || len(s) == size, "Commit OID must match the repository object format")
}
func reviewPath(root string, v any, exists bool) string {
	raw := word(v)
	p, e := containedPath(root, raw)
	if e != nil {
		panic(reviewProblem{msg: e.Message, path: e.Path, code: e.Code})
	}
	if exists {
		info, e := os.Stat(p)
		require(e == nil && info.Mode().IsRegular(), "Missing referenced file: "+raw)
	}
	return p
}
func reviewDoc(path, kind, id, work string) document {
	d, e := parseDocument(path, kind, work)
	if e != nil {
		panic(reviewProblem{msg: e.message, code: e.code, path: path, element: e.elementID, fatal: e.unreadable})
	}
	m := d.metadata
	if has(m, "change_id") {
		require(m["change_id"] == id, "Document change identity mismatch")
	}
	if work == "refactoring" {
		require(m["change_id"] == id, "Explicit refactoring change identity required")
	}
	if has(m, "language") {
		require(nonemptyText(m["language"]), "Language must be text")
	}
	return d
}
func exists(p string) bool    { _, err := os.Stat(p); return err == nil }
func textList(v any) []string { a, _ := stringList(v); return a }
func choose(m object, k string, v any) any {
	if n, ok := m[k]; ok {
		return n
	}
	return v
}
func readQuestions(root, id, kind string, questions map[string]object) {
	p := reviewPath(root, "questions.md", false)
	if !exists(p) {
		return
	}
	d := reviewDoc(p, "questions", id, kind)
	reviewFields(d.metadata, "schema_version change_id document_type language", "work_kind")
	for _, q := range d.records {
		reviewFields(q, "sdd_record id text blocking status", "reason", "return_at", "resolution")
		k := word(q["id"])
		require(q["sdd_record"] == "question" && validDocumentID(k, "Q"), "Invalid question record")
		if questions[k] != nil {
			panic(reviewProblem{msg: "Duplicate question ID across discussion files: " + k, element: k})
		}
		_, ok := q["blocking"].(bool)
		require(nonemptyText(q["text"]) && ok && listed(q["status"], "open", "resolved"), "Invalid question fields")
		if q["status"] == "open" && q["blocking"] == false {
			require(nonemptyText(q["reason"]) && nonemptyText(q["return_at"]), "Deferred question needs reason and return_at")
		}
		if q["status"] == "resolved" {
			require(nonemptyText(q["resolution"]), "Resolved question needs a resolution reference")
		}
		if has(q, "resolution") {
			s := word(q["resolution"])
			require(nonemptyText(s), "Resolution reference must be text")
			require(!strings.ContainsRune(s, 0), "Resolution reference must not contain NUL")
			path, fragment, split := strings.Cut(s, "#")
			require(!split || nonemptyText(fragment), "Resolution fragment must be nonempty")
			reviewPath(root, path, true)
		}
		questions[k] = q
	}
}
func readState(root, id, kind string, users, questions map[string]object) {
	machine := reviewPath(root, "state.yaml", false)
	prose := reviewPath(root, "state.md", false)
	s, d := readDocumentText(machine)
	if d != nil {
		panic(reviewProblem{msg: d.message, path: machine})
	}
	m, d := parseYAMLMapping(s)
	if d != nil {
		panic(reviewProblem{msg: d.message, path: machine})
	}
	if d = validateDocumentMetadata(m, "state", kind); d != nil {
		panic(reviewProblem{msg: d.message, code: d.code, path: machine, fatal: d.code == "migration_required"})
	}
	require(validDocumentSlug(m["change_id"]) && nonemptyText(m["language"]), "state.yaml requires change_id and language")
	require(m["change_id"] == id, "Checkpoint change_id does not match its work root")
	require(hasFields(m, strings.Fields("schema_version work_kind document_type change_id language phase flow awaiting updated_at document_links review_links approval_refs next_question checks"), nil), "state.yaml requires exactly the version 2 checkpoint fields")
	body, d := readDocumentText(prose)
	if d != nil {
		panic(reviewProblem{msg: d.message, path: prose})
	}
	first, _, _ := strings.Cut(body, "\n")
	if strings.TrimSpace(first) == "---" {
		panic(reviewProblem{msg: "state.md must contain prose without YAML frontmatter", path: prose})
	}
	if containsMachineRecord(body) {
		panic(reviewProblem{msg: "state.md cannot contain machine records; questions belong in questions.md", path: prose})
	}
	require(listed(m["phase"], "discovery", "drafting", "review", "user_review", "planning", "approved"), "Invalid state phase")
	require(listed(m["awaiting"], "none", "clarification", "review_consent", "planning_command", "final_approval"), "Invalid awaiting value")
	stamp(m["updated_at"])
	for _, k := range []string{"document_links", "review_links"} {
		require(validTexts(m[k], true), "State links must be unique text lists")
		for _, p := range textList(m[k]) {
			reviewPath(root, p, true)
		}
	}
	require(validTexts(m["approval_refs"], true), "approval_refs must be a list")
	for _, k := range textList(m["approval_refs"]) {
		require(users[k] != nil, "State refers to missing USER decision")
	}
	require(listed(m["flow"], "explore", "draft", "revise", "explain", "review", "user-review", "plan", "resume"), "Invalid state flow")
	if m["next_question"] != nil {
		q := questions[word(m["next_question"])]
		require(q != nil, "State refers to missing question")
		require(q["status"] == "open", "Next question must be open")
	}
	c := reviewFields(m["checks"], "structure")
	require(listed(c["structure"], "not_run", "passed", "failed"), "Invalid structure check status")
}
func userRecord(r object, root, id, kind string, size int, findings map[string]object) {
	reviewFields(r, "sdd_record id kind scope response date work_kind change_id", "message", "status", "supersedes", "action", "reason", "return_at", "completion", "basis_commit", "accepted_commit")
	require(r["work_kind"] == kind, "Authorization work kind mismatch")
	require(r["change_id"] == id, "Authorization change identity mismatch")
	require(r["sdd_record"] == "user", "Expected USER record")
	require(validDocumentID(word(r["id"]), "USER"), "Invalid USER id")
	k := word(r["kind"])
	require(listed(k, "review_consent", "finding_disposition", "review_waiver", "document_approval", "planning_command", "state_acceptance"), "Invalid authorization kind")
	require(nonemptyText(r["response"]), "Explicit response required")
	require(!has(r, "message") || nonemptyText(r["message"]), "Message reference must be text")
	stamp(r["date"])
	require(listed(choose(r, "status", "active"), "active", "completed", "cancelled"), "Invalid authorization status")
	require(validTexts(choose(r, "supersedes", []any{}), true), "supersedes must be a unique list")
	disposition := has(r, "action") || has(r, "reason") || has(r, "return_at") || has(r, "completion")
	if k == "state_acceptance" {
		reviewFields(r["scope"], "")
		require(nonemptyText(r["message"]), "State acceptance requires the decision source")
		require(!has(r, "basis_commit"), "State acceptance uses accepted_commit")
		commitOID(r["accepted_commit"], size)
		require(!disposition, "Disposition fields on state acceptance")
		return
	}
	require(!has(r, "accepted_commit"), "Only state acceptance uses accepted_commit")
	commitOID(r["basis_commit"], size)
	extra := map[string]string{"review_consent": "run_id lenses", "review_waiver": "lenses", "finding_disposition": "findings", "planning_command": "work"}[k]
	scope := reviewFields(r["scope"], "stage "+extra)
	require(scope["stage"] == "review", "Invalid authorization stage")
	if has(scope, "lenses") {
		a := textList(scope["lenses"])
		require(validTexts(scope["lenses"], true) && len(a) > 0, "Explicit lenses required")
		for _, s := range a {
			require(changeID.MatchString(s), "Invalid lens id")
		}
	}
	if has(scope, "run_id") {
		require(runID.MatchString(word(scope["run_id"])), "Explicit run required")
	}
	if has(scope, "work") {
		require(nonemptyText(scope["work"]), "Bounded work description required")
	}
	if k != "finding_disposition" {
		require(!disposition, "Disposition fields on unrelated authorization")
		return
	}
	targets := textList(scope["findings"])
	require(validTexts(scope["findings"], true) && len(targets) > 0, "Explicit findings required")
	for _, target := range targets {
		require(findings[target] != nil, "Unknown full finding key")
	}
	require(listed(r["action"], "fix", "reject", "defer"), "Invalid disposition")
	for _, k := range []string{"reason", "return_at"} {
		require(!has(r, k) || nonemptyText(r[k]), k+" must be text when supplied")
	}
	completed, ok := choose(r, "completion", []any{}).([]any)
	require(ok, "completion must be a list")
	seen := ids{}
	for _, c := range completed {
		m := reviewFields(c, "finding path")
		key := word(m["finding"])
		require(r["action"] == "fix" && slices.Contains(targets, key) && !seen[key], "Completion outside unique fix scope")
		reviewPath(root, m["path"], true)
		seen[key] = true
	}
}
func completedFindings(r object) ids {
	seen := ids{}
	a, _ := r["completion"].([]any)
	for _, v := range a {
		m, _ := v.(map[string]any)
		seen[word(m["finding"])] = true
	}
	return seen
}
func loadLenses(project string) []string {
	a := []string{"consistency", "simplicity", "premortem"}
	root := reviewPath(project, "sdd/arch-lenses", false)
	p := reviewPath(root, "index.md", false)
	if !exists(p) {
		return a
	}
	d, err := parseDocument(p, "", "change")
	if err != nil {
		panic(reviewProblem{msg: err.message, path: p, code: err.code, fatal: err.unreadable})
	}
	reviewFields(d.metadata, "schema_version lenses", "document_type", "language")
	items, ok := d.metadata["lenses"].([]any)
	require(ok, "lenses must be a list")
	for _, v := range items {
		m := reviewFields(v, "id title path")
		id := word(m["id"])
		require(validDocumentSlug(id), "Invalid lens id")
		require(!slices.Contains(a, id) && id != "plan", "Duplicate or reserved lens id")
		require(nonemptyText(m["title"]) && nonemptyText(m["path"]), "Lens title/path required")
		reviewPath(root, m["path"], true)
		a = append(a, id)
	}
	return a
}
func validateReport(d document, path, root string, size int) (map[string]object, []string) {
	m := d.metadata
	reviewFields(m, "schema_version run_id stage lens_id result started_at finished_at reviewed_commit limitations", commonFields...)
	require(m["stage"] == "review", "Invalid report stage")
	require(m["run_id"] == filepath.Base(filepath.Dir(path)) && m["lens_id"] == strings.TrimSuffix(filepath.Base(path), ".md"), "Report identity disagrees with path")
	require(runID.MatchString(word(m["run_id"])), "Invalid run id")
	require(changeID.MatchString(word(m["lens_id"])), "Invalid lens id")
	require(listed(m["result"], "completed_no_findings", "completed_with_findings", "incomplete"), "Invalid report result")
	if m["reviewed_commit"] != nil || m["result"] != "incomplete" {
		commitOID(m["reviewed_commit"], size)
	}
	end := stamp(m["finished_at"])
	require(!end.Before(stamp(m["started_at"])), "Report ends before start")
	require(validTexts(m["limitations"], true), "limitations must be a text list")
	local := map[string]object{}
	order := []string{}
	for _, r := range d.records {
		reviewFields(r, "sdd_record id source target severity problem impact suggestion")
		require(r["sdd_record"] == "finding", "Reports only contain findings")
		id := word(r["id"])
		require(validDocumentID(id, "FIND"), "Invalid finding id")
		require(local[id] == nil, "Duplicate finding id")
		require(listed(r["severity"], "blocker", "recommendation"), "Invalid finding severity")
		for _, k := range strings.Fields("source problem impact suggestion") {
			require(nonemptyText(r[k]), "Finding text required")
		}
		target := reviewFields(r["target"], "path", "element_id")
		reviewPath(root, target["path"], false)
		require(!has(target, "element_id") || nonemptyText(target["element_id"]), "Target element_id must be text")
		local[id] = r
		order = append(order, id)
	}
	require(m["result"] != "completed_no_findings" || len(local) == 0, "No-findings report has findings")
	require(m["result"] != "completed_with_findings" || len(local) > 0, "With-findings report has no findings")
	return local, order
}
func issueAt(path, code, msg string, element any) object {
	return object{"code": code, "message": msg, "path": path, "element_id": element}
}
func reviewKey(m object) string { return fmt.Sprintf("%s/%s", m["run_id"], m["lens_id"]) }
