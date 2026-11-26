package check

import (
	"bytes"
	"io/fs"
	"os"
	"path/filepath"
	"slices"
	"strings"

	"github.com/AndrMoiseev/ai-sdlc/cli/internal/checkpoint"
	"github.com/yuin/goldmark"
	"github.com/yuin/goldmark/ast"
	"github.com/yuin/goldmark/text"
)

func containsMachineRecord(body string) bool {
	source := []byte(body)
	root := goldmark.DefaultParser().Parse(text.NewReader(source))
	found := false
	ast.Walk(root, func(n ast.Node, enter bool) (ast.WalkStatus, error) {
		f, ok := n.(*ast.FencedCodeBlock)
		if !enter || !ok || f.Info == nil || strings.TrimSpace(string(f.Info.Segment.Value(source))) != "yaml" {
			return ast.WalkContinue, nil
		}
		var b bytes.Buffer
		for i := 0; i < f.Lines().Len(); i++ {
			line := f.Lines().At(i)
			b.Write(line.Value(source))
		}
		m, d := parseYAMLMapping(b.String())
		if d != nil && d.code != "yaml_mapping" {
			panic(reviewProblem{msg: d.message, code: d.code})
		}
		if has(m, "sdd_record") {
			found = true
			return ast.WalkStop, nil
		}
		return ast.WalkContinue, nil
	})
	return found
}

// Reports, recorded decisions, and the Git observation have separate validity.
func reviewStatus(project, root, id string, report object) *checkError {
	kind := report["work_kind"].(string)
	checkpointReport := checkpoint.Inspect(project, kind, id)
	head := word(checkpointReport["head"])
	reports, findings, users := map[string]object{}, map[string]object{}, map[string]object{}
	findingOrder, userOrder, reportOrder := []string{}, []string{}, []string{}
	errs, warnings := []object{}, []object{}
	var fatal *checkError
	collect := func(path, code string, fn func()) bool {
		p := guarded(fn)
		if p == nil {
			return true
		}
		if p.fatal {
			fatal = &checkError{Code: p.code, Message: p.msg, Path: p.path, Exit: 2}
		} else {
			errs = append(errs, issueAt(path, code, p.msg, nil))
		}
		return false
	}
	required := []string{"consistency", "simplicity", "premortem"}
	collect(filepath.Join(project, "sdd", "arch-lenses", "index.md"), "lens_index", func() { required = loadLenses(project) })
	if fatal != nil {
		return fatal
	}
	hasPlan := false
	if p, e := requiredFile(root, "tasks.md"); e == nil && p != "" {
		hasPlan = true
		required = append(required, "plan")
	}
	reviewDir, e := containedPath(root, "review")
	if e != nil {
		return e
	}
	paths, _ := fs.Glob(os.DirFS(reviewDir), "*/*.md")
	cache := map[string]string{}
	for _, name := range paths {
		path := filepath.Join(reviewDir, filepath.FromSlash(name))
		collect(path, "review_structure", func() {
			rel, _ := filepath.Rel(root, path)
			p := reviewPath(root, filepath.ToSlash(rel), true)
			doc := reviewDoc(p, "review", id, kind)
			local, order := validateReport(doc, path, root, len(head))
			m := doc.metadata
			key := reviewKey(m)
			oid := word(m["reviewed_commit"])
			evidence := cache[oid]
			if evidence == "" {
				evidence = "evidence_unavailable"
				if oid != "" {
					if oid == head {
						evidence = "current"
					} else if checkpoint.CommitExists(project, oid) {
						evidence = "changed_since_review"
					}
				}
				cache[oid] = evidence
			}
			if evidence != "current" {
				warnings = append(warnings, issueAt(path, evidence, "Review evidence is unavailable or differs from HEAD; assess the consequences without revoking existing work authorization.", nil))
			}
			reports[key] = object{"stage": m["stage"], "lens_id": m["lens_id"], "result": m["result"], "evidence": evidence, "reviewed_commit": m["reviewed_commit"]}
			reportOrder = append(reportOrder, key)
			for _, k := range order {
				findings[key+"/"+k] = local[k]
				findingOrder = append(findingOrder, key+"/"+k)
			}
		})
		if fatal != nil {
			return fatal
		}
	}
	runCommits := map[string]any{}
	for _, key := range reportOrder {
		run, _, _ := strings.Cut(key, "/")
		oid := reports[key]["reviewed_commit"]
		if prev, ok := runCommits[run]; ok && prev != oid {
			errs = append(errs, issueAt(filepath.Join(reviewDir, key), "review_structure", "Run used different reviewed commits", nil))
			for k, r := range reports {
				if strings.HasPrefix(k, run+"/") {
					r["result"] = "incomplete"
				}
			}
		}
		runCommits[run] = oid
	}
	summary, e := containedPath(root, "review/summary.md")
	if e != nil {
		return e
	}
	reuse := map[string]string{}
	if exists(summary) {
		collect(summary, "review_structure", func() {
			doc := reviewDoc(summary, "summary", id, kind)
			reviewFields(doc.metadata, "schema_version findings", commonFields...)
			a, ok := doc.metadata["findings"].([]any)
			require(ok, "Summary findings must be a list")
			for _, v := range a {
				m := reviewFields(v, "finding related_to duplicates", "decision_from", "decision_basis")
				require(validTexts(m["related_to"], true) && validTexts(m["duplicates"], true), "Summary links must be lists")
				key := word(m["finding"])
				require(findings[key] != nil, "Unknown full finding key")
				for _, k := range append(textList(m["related_to"]), textList(m["duplicates"])...) {
					require(findings[k] != nil, "Unknown full finding key")
				}
				if has(m, "decision_from") || has(m, "decision_basis") {
					from := word(m["decision_from"])
					require(nonemptyText(from) && slices.Contains(textList(m["duplicates"]), from) && from != key, "Reused decision must identify a distinct duplicate finding")
					require(nonemptyText(m["decision_basis"]), "Explain why meaning, grounds and scope of the repeated finding are unchanged")
					require(reuse[key] == "", "Duplicate decision reuse declaration")
					reuse[key] = from
				}
			}
		})
		if fatal != nil {
			return fatal
		}
	}
	decisions, e := containedPath(root, "review/decisions.md")
	if e != nil {
		return e
	}
	if exists(decisions) {
		collect(decisions, "authorization_structure", func() {
			d := reviewDoc(decisions, "decisions", id, kind)
			reviewFields(d.metadata, "schema_version", commonFields...)
			for _, r := range d.records {
				collect(decisions, "authorization_structure", func() {
					userRecord(r, root, id, kind, len(head), findings)
					key := word(r["id"])
					require(users[key] == nil, "Duplicate USER id")
					users[key] = r
					userOrder = append(userOrder, key)
				})
			}
		})
		if fatal != nil {
			return fatal
		}
	}
	superseded := ids{}
	for _, k := range userOrder {
		r := users[k]
		for _, old := range textList(r["supersedes"]) {
			if users[old] == nil || old == k {
				errs = append(errs, issueAt(decisions, "authorization_structure", "Invalid superseded USER reference", nil))
			} else if !stamp(users[old]["date"]).Before(stamp(r["date"])) {
				errs = append(errs, issueAt(decisions, "authorization_structure", "Superseding decision must be later", nil))
			} else {
				superseded[old] = true
			}
		}
	}
	dispositions := map[string]object{}
	origins := map[string]string{}
	cancelled := ids{}
	applicable, waived := ids{}, ids{}
	work := object{}
	approved := false
	for _, key := range userOrder {
		r := users[key]
		if superseded[key] {
			continue
		}
		scope, _ := r["scope"].(map[string]any)
		targets := textList(scope["findings"])
		if r["status"] == "cancelled" {
			if r["kind"] == "finding_disposition" {
				for _, k := range targets {
					cancelled[k] = true
				}
			}
			continue
		}
		applicable[key] = true
		switch r["kind"] {
		case "finding_disposition":
			for _, k := range targets {
				if dispositions[k] != nil {
					errs = append(errs, issueAt(decisions, "authorization_structure", "Conflicting active dispositions require supersedes", nil))
				}
				dispositions[k] = r
				origins[k] = k
			}
			if choose(r, "status", "active") == "active" && r["action"] == "fix" {
				completed := completedFindings(r)
				remaining := []string{}
				for _, k := range targets {
					if !completed[k] {
						remaining = append(remaining, k)
					}
				}
				if len(remaining) > 0 {
					work[key] = object{"stage": scope["stage"], "findings": remaining}
				}
			}
		case "review_waiver":
			for _, k := range textList(scope["lenses"]) {
				waived[k] = true
			}
		case "document_approval":
			approved = true
		case "planning_command":
			if choose(r, "status", "active") == "active" {
				work[key] = scope
			}
		}
	}
	// A cancelled disposition cannot be revived by a duplicate finding.
	for k := range cancelled {
		delete(reuse, k)
	}
	reused := object{}
	derived := map[string]object{}
	for len(reuse) > 0 {
		progress := false
		for k, from := range reuse {
			if dispositions[k] != nil || derived[k] != nil {
				delete(reuse, k)
			} else if r := dispositions[from]; r != nil {
				derived[k] = r
				reused[k] = origins[from]
				delete(reuse, k)
			} else if r := derived[from]; r != nil {
				derived[k] = r
				reused[k] = reused[from]
				delete(reuse, k)
			} else if reuse[from] == "" {
				delete(reuse, k)
			} else {
				continue
			}
			progress = true
		}
		if !progress {
			errs = append(errs, issueAt(summary, "authorization_structure", "Cyclic decision reuse", nil))
			derived = map[string]object{}
			reused = object{}
			break
		}
	}
	for k, r := range derived {
		dispositions[k] = r
		origins[k] = word(reused[k])
	}
	unresolved, unfinished := []string{}, []string{}
	for _, k := range findingOrder {
		r := dispositions[k]
		if r == nil {
			unresolved = append(unresolved, k)
		} else if r["action"] == "fix" && !completedFindings(r)[origins[k]] {
			unfinished = append(unfinished, k)
		}
	}
	coverage := map[string]string{}
	complete := true
	for _, k := range required {
		status := "missing"
		for _, r := range reports {
			if r["lens_id"] == k {
				if r["result"] != "incomplete" {
					status = "completed"
					break
				}
				status = "incomplete"
			}
		}
		if status != "completed" && waived[k] {
			status = "waived"
		}
		coverage[k] = status
		if status != "completed" && status != "waived" {
			complete = false
		}
	}
	questions := map[string]object{}
	discussion := true
	if p := guarded(func() { readQuestions(root, id, kind, questions) }); p != nil {
		discussion = false
		errs = append(errs, issueAt(filepath.Join(root, "questions.md"), "questions_structure", p.msg, p.element))
	}
	if p := guarded(func() { readState(root, id, kind, users, questions) }); p != nil {
		if p.code == "migration_required" {
			return &checkError{Code: p.code, Message: p.msg, Path: p.path, Exit: 2}
		}
		discussion = false
		path := p.path
		if path == "" {
			path = filepath.Join(root, "state.yaml")
		}
		warnings = append(warnings, issueAt(path, "state_recovery", p.msg, p.element))
	}
	open, blocking := []string{}, []string{}
	for k, q := range questions {
		if q["status"] == "open" {
			open = append(open, k)
			if q["blocking"] == true {
				blocking = append(blocking, k)
			}
		}
	}
	slices.Sort(open)
	slices.Sort(blocking)
	discussion = discussion && len(open) == 0
	report["errors"] = append(report["errors"].([]object), errs...)
	report["warnings"] = append(report["warnings"].([]object), warnings...)
	report["checkpoint_status"] = checkpointReport
	report["review_status"] = object{"required_lenses": required, "coverage": coverage, "reports": reports, "complete": complete, "unresolved_findings": unresolved, "unfinished_fixes": unfinished, "reused_decisions": reused}
	report["discussion_status"] = object{"open_questions": open, "blocking_questions": blocking, "complete": discussion, "provenance": "Structural checks of available question records only; decision journal authorship and semantic completeness are not verified."}
	report["approval_status"] = object{"approved": approved, "ready": approved && hasPlan && discussion && len(report["errors"].([]object)) == 0, "applicability": applicable, "work_authorizations": work, "provenance": "Recorded decisions; user authorship and change provenance are not verified."}
	return nil
}
