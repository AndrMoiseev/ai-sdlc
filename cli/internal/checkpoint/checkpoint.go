package checkpoint

import (
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"reflect"
	"regexp"
	"slices"
	"strings"
)

type object = map[string]any
type request struct {
	op, project, kind, id, head, old, message string
	review                                    bool
	instruction, decision, changes            object
}

var validID = regexp.MustCompile(`^[a-z][a-z0-9]*(-[a-z0-9]+)*$`)

func nullable(s string) any {
	if s == "" {
		return nil
	}
	return s
}
func blank(q request) object {
	return object{"schema_version": 2, "operation": q.op, "work_kind": q.kind, "change_id": q.id, "status": "not_checked", "checkpoint_ref": nil, "head": nil, "accepted_commit": nil, "dirty": false, "changes": []change{}, "diagnostics": []object{}, "exit_code": 0}
}
func diagnose(r object, e error, code string, exit int) {
	r["status"] = code
	r["exit_code"] = exit
	r["diagnostics"] = append(r["diagnostics"].([]object), object{"code": code, "message": e.Error(), "next_action": "Inspect the repository again; preserve files and obtain a decision before recovery."})
}
func errCode(e error) string {
	var p *problem
	if errors.As(e, &p) {
		return p.code
	}
	return "git_error"
}
func (g repository) observe(r object) error {
	head, _, rc, e := g.command("", "", "rev-parse", "--verify", "HEAD")
	if e != nil {
		return e
	}
	head = strings.TrimSpace(head)
	if rc != 0 {
		head = ""
	}
	accepted, e := g.accepted()
	if e != nil {
		return e
	}
	changes, e := g.changes()
	if e != nil {
		return e
	}
	status := "ready"
	switch {
	case head == "":
		status = "unborn_head"
	case len(changes) > 0:
		status = "dirty"
	case accepted == "":
		status = "acceptance_required"
	case accepted != head:
		status = "head_mismatch"
	}
	for _, c := range changes {
		if slices.Contains([]string{"DD", "AU", "UD", "UA", "DU", "AA", "UU"}, c.Status) {
			status = "git_operation_in_progress"
		}
	}
	for _, file := range []string{"MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply", "sequencer", "BISECT_START"} {
		if _, e := os.Stat(filepath.Join(g.dir, file)); e == nil {
			status = "git_operation_in_progress"
			break
		}
	}
	if status == "acceptance_required" {
		dir := "changes"
		if r["work_kind"] == "refactoring" {
			dir = "refactoring"
		}
		if _, e := os.Lstat(filepath.Join(g.root, "sdd", dir, r["change_id"].(string))); os.IsNotExist(e) {
			refs, e := g.value("for-each-ref", "--format=%(refname)", fmt.Sprintf("refs/sdd/checkpoints/%s/%s/", r["work_kind"], r["change_id"]))
			if e != nil {
				return e
			}
			if refs == "" {
				status = "initialization_required"
			}
		}
	}
	r["head"] = nullable(head)
	r["accepted_commit"] = nullable(accepted)
	r["changes"] = changes
	r["dirty"] = len(changes) > 0
	r["status"] = status
	return nil
}
func expected(r object, head, old string) error {
	if head == "" || r["head"] != head || r["accepted_commit"] != nullable(old) {
		return fail("concurrent_change", "HEAD or accepted checkpoint differs from the expected observation")
	}
	if r["status"] == "git_operation_in_progress" {
		return fail("git_operation_in_progress", "Finish the ongoing Git operation before a checkpoint")
	}
	return nil
}
func fields(m object, keys ...string) bool {
	for _, k := range keys {
		v, _ := m[k].(string)
		if strings.TrimSpace(v) == "" {
			return false
		}
	}
	return true
}
func clean(r object, oid string) bool {
	return r["head"] == oid && r["dirty"] == false && r["status"] != "git_operation_in_progress"
}
func (g repository) finish(q request, r object, oid, msg string) error {
	if e := g.update(oid, q.old, strings.ReplaceAll(msg, "\n", " ")); e != nil {
		return e
	}
	r["ref_updated"] = true
	if e := g.observe(r); e != nil {
		return e
	}
	if !clean(r, oid) || r["accepted_commit"] != oid {
		return fail("concurrent_change", "Repository changed after checkpoint reference update")
	}
	r["status"] = map[string]string{"initialize": "initialized", "accept": "accepted", "create": "created"}[q.op]
	return nil
}
func (g repository) create(q request, r object) error {
	if q.old != q.head {
		return fail("acceptance_required", "Creation requires HEAD to equal the accepted checkpoint")
	}
	if !fields(q.instruction, "text", "source") {
		return fail("instruction_required", "An explicit work instruction with text and source is required")
	}
	if strings.TrimSpace(q.message) == "" {
		return fail("message_required", "Supply a nonempty commit message")
	}
	if _, ok := q.changes["paths"].([]any); !ok {
		return fail("changes_changed", "Supply the reviewed paths and tree from capture_changes")
	}
	reviewed, e := g.capture()
	if e != nil {
		return e
	}
	b, _ := json.Marshal(reviewed)
	var actual object
	json.Unmarshal(b, &actual)
	if !reflect.DeepEqual(actual, q.changes) {
		return fail("changes_changed", "Repository paths or content changed since review")
	}
	if r["dirty"] == false {
		if e := g.observe(r); e != nil {
			return e
		}
		if e := expected(r, q.head, q.old); e != nil {
			return e
		}
		if r["dirty"] == true {
			return fail("concurrent_change", "Repository changed during the empty transition")
		}
		r["status"] = "unchanged"
		return nil
	}
	if e := g.stage(reviewed.Paths, ""); e != nil {
		return e
	}
	tree, e := g.value("write-tree")
	if e != nil {
		return e
	}
	if tree != reviewed.Tree {
		return fail("changes_changed", "Staged tree differs from the reviewed tree; index preserved")
	}
	if e = g.observe(r); e != nil {
		return e
	}
	if e = expected(r, q.head, q.head); e != nil {
		return e
	}
	after, e := g.capture()
	if e != nil {
		return e
	}
	reviewed.IndexTree = reviewed.Tree
	if !reflect.DeepEqual(after, reviewed) {
		return fail("changes_changed", "Repository paths or content changed since review")
	}
	_, msg, rc, e := g.command("", "", "commit", "-m", q.message)
	if e != nil {
		return e
	}
	if e = g.observe(r); e != nil {
		return e
	}
	oid, _ := r["head"].(string)
	if oid != q.head {
		r["created_commit"] = nullable(oid)
	}
	if rc != 0 {
		return fail("commit_failed", msg)
	}
	if r["created_commit"] == nil {
		return fail("commit_failed", "Commit parent, tree, HEAD or cleanliness did not match the reviewed transition")
	}
	parents, e := g.value("rev-list", "--parents", "-n", "1", oid)
	if e != nil {
		return e
	}
	tree, e = g.value("rev-parse", oid+"^{tree}")
	if e != nil {
		return e
	}
	if !clean(r, oid) || parents != oid+" "+q.head || tree != reviewed.Tree {
		return fail("commit_created_unaccepted", "Commit parent, tree, HEAD or cleanliness did not match the reviewed transition")
	}
	return g.finish(q, r, oid, "SDD checkpoint")
}
func (g repository) write(q request, r object) error {
	if e := expected(r, q.head, q.old); e != nil {
		return e
	}
	switch q.op {
	case "initialize":
		if !fields(q.instruction, "text", "source") {
			return fail("instruction_required", "An explicit work instruction with text and source is required")
		}
		if r["status"] == "acceptance_required" {
			return fail("work_exists", "The work root or a checkpoint already exists; inspect and resume that work, or choose a free ID")
		}
		if r["status"] != "initialization_required" {
			return fail(r["status"].(string), "Initialize only a new work at a clean, unchanged HEAD before creating its directory")
		}
		return g.finish(q, r, q.head, "SDD initialization: "+q.instruction["source"].(string))
	case "accept":
		if !fields(q.decision, "id", "response", "source", "date") || q.decision["accepted_commit"] != q.head {
			return fail("decision_required", "Supply the explicit user decision and its exact accepted_commit")
		}
		if r["dirty"] == true {
			return fail("dirty", "Accepting HEAD does not accept uncommitted files")
		}
		if q.old == q.head {
			if e := g.observe(r); e != nil {
				return e
			}
			if e := expected(r, q.head, q.old); e != nil {
				return e
			}
			if r["dirty"] == true {
				return fail("concurrent_change", "Repository became dirty during acceptance")
			}
			r["status"] = "unchanged"
			return nil
		}
		return g.finish(q, r, q.head, fmt.Sprintf("SDD acceptance %s: %s", q.decision["id"], q.decision["source"]))
	default:
		return g.create(q, r)
	}
}
func execute(q request) object {
	r := blank(q)
	write := q.op != "inspect"
	if write {
		r["previous_accepted"] = nullable(q.old)
		r["created_commit"] = nil
		r["ref_updated"] = false
	}
	var e error
	var g repository
	opened := false
	switch {
	case q.kind != "change" && q.kind != "refactoring":
		e = fail("invalid_identity", "work_kind must be change or refactoring")
	case !validID.MatchString(q.id) || len(q.id) > 64:
		e = fail("invalid_identity", "change_id must be a lowercase kebab-case slug of at most 64 characters")
	default:
		g, e = open(q.project, q.kind, q.id)
	}
	if e == nil {
		r["checkpoint_ref"] = g.ref
		e = g.observe(r)
		opened = e == nil
	}
	if e == nil {
		if write {
			e = g.write(q, r)
		} else {
			if r["head"] != nil && r["accepted_commit"] != nil && r["head"] != r["accepted_commit"] {
				var diff string
				diff, e = g.value("diff", "--stat", r["accepted_commit"].(string), r["head"].(string), "--")
				if e == nil {
					r["difference"] = diff
				}
			}
			if e == nil && q.review && r["status"] != "unborn_head" && r["status"] != "git_operation_in_progress" {
				var v reviewed
				v, e = g.capture()
				if e == nil {
					r["reviewed_changes"] = v
				} else {
					r = blank(q)
				}
			}
		}
	}
	if e != nil {
		code := errCode(e)
		exit := 2
		if write {
			if opened {
				if oe := g.observe(r); oe != nil {
					r["diagnostics"] = append(r["diagnostics"].([]object), object{"code": "observation_failed", "message": oe.Error(), "next_action": "Run inspect again."})
				}
			}
			if r["ref_updated"] == true {
				code = "concurrent_change"
			} else if r["created_commit"] != nil {
				code = "commit_created_unaccepted"
			}
			if !slices.Contains([]string{"git_error", "git_unavailable", "not_repository", "invalid_checkpoint_ref", "unsupported_index_flags"}, code) {
				exit = 1
			}
		}
		diagnose(r, e, code, exit)
	}
	return r
}
func Inspect(project, kind, id string) map[string]any {
	return execute(request{op: "inspect", project: project, kind: kind, id: id})
}

func Run(args []string, stdout, stderr io.Writer) int {
	fs := flag.NewFlagSet("checkpoint", flag.ContinueOnError)
	fs.SetOutput(stderr)
	q := request{}
	if len(args) == 0 || !slices.Contains([]string{"inspect", "initialize", "accept", "create"}, args[0]) {
		fmt.Fprintln(stderr, "Usage: sdd checkpoint inspect|initialize|accept|create [options]")
		return 2
	}
	q.op = args[0]
	for key, target := range map[string]*string{"project-root": &q.project, "work-kind": &q.kind, "change": &q.id, "expected-head": &q.head, "expected-accepted": &q.old, "message": &q.message} {
		fs.StringVar(target, key, "", key)
	}
	fs.BoolVar(&q.review, "review-changes", false, "Capture reviewed paths and trees")
	decision := fs.String("decision", "", "Decision JSON")
	instruction := fs.String("instruction", "", "Instruction JSON")
	changes := fs.String("reviewed-changes", "", "Review JSON")
	if e := fs.Parse(args[1:]); e != nil {
		if e == flag.ErrHelp {
			return 0
		}
		return 2
	}
	if fs.NArg() != 0 || q.project == "" || q.id == "" || !slices.Contains([]string{"change", "refactoring"}, q.kind) || (q.op != "inspect" && q.head == "") || (q.op == "initialize" && *instruction == "") || (q.op == "accept" && (q.old == "" || *decision == "")) || (q.op == "create" && (q.old == "" || *instruction == "" || *changes == "" || q.message == "")) {
		fs.Usage()
		return 2
	}
	if q.op == "initialize" || q.old == "null" {
		q.old = ""
	}
	inputs := []struct {
		p string
		m *object
	}{}
	switch q.op {
	case "initialize":
		inputs = append(inputs, struct {
			p string
			m *object
		}{*instruction, &q.instruction})
	case "accept":
		inputs = append(inputs, struct {
			p string
			m *object
		}{*decision, &q.decision})
	case "create":
		inputs = []struct {
			p string
			m *object
		}{{*changes, &q.changes}, {*instruction, &q.instruction}}
	}
	var result object
	for _, input := range inputs {
		b, e := os.ReadFile(input.p)
		var v any
		if e == nil {
			e = json.Unmarshal(b, &v)
		}
		if e != nil {
			result = blank(q)
			diagnose(result, e, "input_error", 2)
			break
		}
		*input.m, _ = v.(map[string]any)
	}
	if result == nil {
		result = execute(q)
	}
	enc := json.NewEncoder(stdout)
	enc.SetIndent("", "  ")
	if e := enc.Encode(result); e != nil {
		fmt.Fprintln(stderr, e)
		return 2
	}
	return result["exit_code"].(int)
}
