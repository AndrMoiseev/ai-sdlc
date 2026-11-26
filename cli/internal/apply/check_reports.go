package apply

import (
	"bytes"
	"encoding/base64"
	"encoding/xml"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

var countFields = []string{"collected", "passed", "failed", "skipped", "xfailed", "xpassed"}

func unknownCounts() mapping {
	counts := mapping{"unknown_fields": countFields}
	for _, k := range countFields {
		counts[k] = nil
	}
	return counts
}

type junitCase struct {
	Failure *struct{} `xml:"failure"`
	Error   *struct{} `xml:"error"`
	Skipped *struct {
		Type string `xml:"type,attr"`
	} `xml:"skipped"`
}
type junitSuite struct {
	Name    xml.Name `xml:"-"`
	XMLName xml.Name
	Cases   []junitCase  `xml:"testcase"`
	Suites  []junitSuite `xml:"testsuite"`
	Attrs   []xml.Attr   `xml:",any,attr"`
}

func junitCounts(raw []byte) (mapping, error) {
	upper := bytes.ToUpper(raw)
	if bytes.Contains(upper, []byte("<!DOCTYPE")) || bytes.Contains(upper, []byte("<!ENTITY")) {
		return nil, errors.New("JUnit declarations are unsupported")
	}
	var root junitSuite
	if e := xml.Unmarshal(raw, &root); e != nil {
		return nil, errors.New("Invalid JUnit XML")
	}
	var suites []junitSuite
	switch root.XMLName.Local {
	case "testsuite":
		suites = []junitSuite{root}
	case "testsuites":
		suites = root.Suites
	default:
		return nil, errors.New("Expected JUnit testsuite or testsuites")
	}
	if len(suites) == 0 {
		return nil, errors.New("JUnit contains no testsuite")
	}
	counts := unknownCounts()
	for _, k := range []string{"passed", "failed", "skipped", "xfailed"} {
		counts[k] = 0
	}
	counts["unknown_fields"] = []string{"collected", "xpassed"}
	for len(suites) > 0 {
		suite := suites[0]
		suites = suites[1:]
		if len(suite.Suites) > 0 {
			suites = append(suites, suite.Suites...)
			continue
		}
		measured := map[string]int{"tests": len(suite.Cases)}
		for _, c := range suite.Cases {
			if c.Failure != nil {
				measured["failures"]++
			}
			if c.Error != nil {
				measured["errors"]++
			}
			if c.Skipped != nil {
				measured["skipped"]++
			}
			k := "passed"
			if c.Failure != nil || c.Error != nil {
				k = "failed"
			} else if c.Skipped != nil {
				if c.Skipped.Type == "pytest.xfail" {
					k = "xfailed"
				} else {
					k = "skipped"
				}
			}
			counts[k] = intValue(counts[k]) + 1
		}
		for _, a := range suite.Attrs {
			k := a.Name.Local
			if !includes([]string{"tests", "errors", "failures", "skipped"}, k) {
				continue
			}
			v, e := strconv.Atoi(a.Value)
			if e != nil || v < 0 {
				return nil, errors.New("Invalid JUnit count: " + k)
			}
			if v != measured[k] {
				if k == "tests" {
					return nil, errors.New("JUnit test count does not match testcase records")
				}
				return nil, fmt.Errorf("JUnit %s count does not match testcase records", k)
			}
		}
	}
	return counts, nil
}
func captureCheckReports(output mapping, read bool) (reports []mapping, limits []any) {
	specs, e := configuredReports(output["command"], object(output["configuration"]))
	if e != nil {
		return nil, []any{mapping{"reason": e.Error()}}
	}
	for _, value := range specs {
		r := object(value)
		r["resolved_path"] = nil
		if !read {
			r["error"] = "Report was not captured after command"
		} else {
			p := str(r["path"])
			if !filepath.IsAbs(p) {
				p = filepath.Join(str(output["cwd"]), p)
			}
			if resolved, e := resolvePath(p); e == nil {
				p = resolved
			}
			r["resolved_path"] = p
			raw, e := os.ReadFile(p)
			if e != nil {
				r["error"] = fileError(e, p).Error()
			} else {
				r["raw"] = raw
			}
		}
		reports = append(reports, r)
	}
	return reports, []any{}
}

type capturedCheck struct {
	reports []mapping
	limits  []any
}

func storeCheckSummary(store *execution, identity, output, check mapping, captured capturedCheck) (mapping, mapping, error) {
	id := copyMapping(identity)
	id["check_id"] = output["check_id"]
	config, e := store.put(output["configuration"])
	if e != nil {
		return nil, nil, e
	}
	id["configuration"] = config
	refs := mapping{}
	if checkHas(output, "command") {
		for _, stream := range []string{"stdout", "stderr"} {
			encoding := "base64"
			content := output[stream+"_base64"]
			if content == nil {
				encoding = "text"
				content = checkValue(output, stream, "")
			}
			ref, e := store.put(mapping{"identity": id, "stream": stream, "encoding": encoding, "content": content})
			if e != nil {
				return nil, nil, e
			}
			refs[stream] = ref
		}
	}
	if truth(output["procedure_log"]) {
		ref, e := store.put(mapping{"identity": id, "stream": "procedure", "log": output["procedure_log"], "sha256": output["procedure_log_hash"]})
		if e != nil {
			return nil, nil, e
		}
		refs["procedure"] = ref
	}
	summary := copyMapping(id)
	reports := []any{}
	limits := append([]any{}, captured.limits...)
	complete := len(limits) == 0 && output["outcome"] != "unavailable" && output["outcome"] != "planned_absence"
	counts := unknownCounts()
	parsed := []mapping{}
	for _, r := range captured.reports {
		raw, ok := r["raw"].([]byte)
		delete(r, "raw")
		r["reference"] = nil
		if ok {
			ref, e := store.put(mapping{"identity": id, "stream": "structured_report", "format": r["format"], "path": r["path"], "resolved_path": r["resolved_path"], "encoding": "base64", "content": base64.StdEncoding.EncodeToString(raw)})
			if e != nil {
				return nil, nil, e
			}
			r["reference"] = ref
			if r["format"] == "pytest-junit" {
				c, e := junitCounts(raw)
				if e != nil {
					r["error"] = e.Error()
				} else {
					r["test_counts"] = c
					parsed = append(parsed, c)
				}
			}
		}
		if r["error"] != nil {
			limits = append(limits, mapping{"report": r["path"], "reason": r["error"]})
			if r["required"] == true {
				complete = false
			}
		}
		reports = append(reports, r)
	}
	if len(parsed) > 0 {
		unknown := []string{}
		for _, k := range countFields {
			sum := 0
			ok := true
			for _, c := range parsed {
				if c[k] == nil {
					ok = false
					break
				}
				sum += intValue(c[k])
			}
			if ok {
				counts[k] = sum
			} else {
				unknown = append(unknown, k)
			}
		}
		counts["unknown_fields"] = unknown
	}
	stream := "stdout"
	if truth(output["stderr"]) {
		stream = "stderr"
	}
	value := []rune(str(output[stream]))
	offset := max(0, len(value)-4096)
	excerpt := mapping{"stream": stream, "reference": refs[stream], "text": string(value[offset:]), "offset": offset, "line": 1 + strings.Count(string(value[:offset]), "\n"), "truncated": offset > 0}
	for _, k := range []string{"check_id", "command", "procedure", "cwd", "started_at", "duration_seconds", "exit_code", "outcome"} {
		summary[k] = output[k]
	}
	summary["schema_version"] = 1
	summary["limitation"] = checkValue(output, "limitation", output["description"])
	summary["limitations"] = limits
	summary["test_counts"] = counts
	summary["evidence_complete"] = complete
	summary["artifacts"] = refs
	summary["structured_reports"] = reports
	summary["excerpt"] = excerpt
	ref, e := store.put(summary)
	return summary, ref, e
}
func aggregateChecks(checks []any, summaries []mapping, unchanged bool) mapping {
	requested, completed, missing := []any{}, []any{}, []any{}
	done := checkSet{}
	outcomes := mapping{}
	complete := unchanged
	for _, s := range summaries {
		id := str(s["check_id"])
		outcomes[id] = s["outcome"]
		if s["outcome"] != "unavailable" && s["outcome"] != "planned_absence" {
			completed = append(completed, id)
			done[id] = true
		}
		complete = complete && s["evidence_complete"] == true
	}
	for _, v := range checks {
		id := str(object(v)["id"])
		requested = append(requested, id)
		if !done[id] {
			missing = append(missing, id)
		}
	}
	return mapping{"requested_check_ids": requested, "completed_check_ids": completed, "missing_check_ids": missing, "outcomes": outcomes, "source_unchanged": unchanged, "evidence_complete": complete && len(missing) == 0}
}
func persistCheckRun(state, task, record mapping, checks []any, captures map[string]capturedCheck, directory, id string) (mapping, error) {
	store := &execution{directory: directory}
	role := object(object(state["roles"])[str(record["role_id"])])
	trace := mapping{}
	for _, k := range strings.Fields("context_id host launch_ref agent_selection model_observation") {
		trace[k] = role[k]
	}
	identity := mapping{"work_kind": workKind(object(state["basis"])), "work_id": state["change_id"], "run_id": state["run_id"], "task_id": record["task_id"], "assignment_id": record["role_id"], "check_run_id": id, "role_id": record["role_id"], "stage": record["stage"], "role_trace": trace, "registry_revision": record["registry_revision"]}
	for _, entry := range []struct {
		k string
		v any
	}{{"basis_before", record["before"]}, {"basis_after", record["after"]}, {"registry", checks}} {
		ref, e := store.put(entry.v)
		if e != nil {
			return nil, e
		}
		identity[entry.k] = ref
	}
	summaries := []mapping{}
	refs := []any{}
	for _, v := range array(record["outputs"]) {
		out := object(v)
		id := str(out["check_id"])
		c := checkByID(checks, id)
		run := object(c["setup"])
		if run == nil {
			run = object(c["run"])
		}
		if checkHas(run, "command") && !checkHas(out, "command") {
			out["command"] = run["command"]
		}
		if !checkHas(out, "cwd") {
			root := taskRoot(state, task)
			rel := str(checkValue(run, "cwd", c["cwd"]))
			if rel != "." {
				var e error
				root, e = contained(root, rel)
				if e != nil {
					return nil, e
				}
			}
			out["cwd"] = root
		}
		if !checkHas(out, "procedure") {
			out["procedure"] = run["procedure"]
		}
		if !checkHas(out, "configuration") {
			out["configuration"] = checkValue(run, "configuration", checkValue(c, "configuration", mapping{}))
		}
		cap, ok := captures[id]
		if !ok {
			cap.reports, cap.limits = captureCheckReports(out, false)
		}
		m, ref, e := storeCheckSummary(store, identity, out, c, cap)
		if e != nil {
			return nil, e
		}
		summaries = append(summaries, m)
		refs = append(refs, ref)
		out["summary"] = ref
		out["evidence_complete"] = m["evidence_complete"]
		for _, k := range strings.Fields("stdout stderr stdout_base64 stderr_base64") {
			delete(out, k)
		}
	}
	agg := aggregateChecks(checks, summaries, checkSame(record["before"], record["after"]))
	agg["schema_version"] = 1
	agg["identity"] = identity
	agg["checks"] = refs
	agg["diagnosis"] = nil
	ref, e := store.put(agg)
	if e != nil {
		return nil, e
	}
	record["summary"] = ref
	record["check_run_id"] = id
	packed, e := store.pack(agg, "", true)
	if e != nil {
		return nil, e
	}
	m := object(packed)
	m["reference"] = ref
	return m, nil
}
