package architect

import (
	"embed"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"reflect"
	"regexp"
	"strings"
	"time"
)

//go:embed assets/*
var assets embed.FS

func assetObject(name string) (record, error) {
	data, err := assets.ReadFile("assets/" + name)
	if err != nil {
		return nil, err
	}
	doc, err := parseDocument(data, "")
	return object(doc.value), err
}

func validateStateShape(value any, rule, schema record, location string) error {
	if reference := str(rule["$ref"]); reference != "" {
		return validateStateShape(value, object(object(schema["$defs"])[filepath.Base(reference)]), schema, location)
	}
	kinds := stringsOf(rule["type"])
	if name := str(rule["type"]); name != "" {
		kinds = []string{name}
	}
	var kind string
	switch value := value.(type) {
	case map[string]any:
		kind = "object"
	case []any:
		kind = "array"
	case string:
		kind = "string"
	case json.Number:
		if !strings.ContainsAny(string(value), ".eE") {
			kind = "integer"
		}
	case nil:
		kind = "null"
	}
	if !contains(kinds, kind) {
		return fmt.Errorf("%s: expected %s", location, strings.Join(kinds, " or "))
	}
	if constant, ok := rule["const"]; ok && value != constant {
		return fmt.Errorf("%s: expected %s", location, display(constant))
	}
	if choices := stringsOf(rule["enum"]); len(choices) > 0 && !contains(choices, str(value)) {
		return fmt.Errorf("%s: expected one of %s", location, pythonList(choices))
	}
	if pattern := str(rule["pattern"]); pattern != "" && kind == "string" {
		valid := strings.TrimSpace(str(value)) != ""
		if pattern != `\S` {
			valid, _ = regexp.MatchString(pattern, str(value))
		}
		if !valid {
			return fmt.Errorf("%s: invalid or empty string", location)
		}
	}
	if kind == "object" {
		objectValue, properties := object(value), object(rule["properties"])
		required := map[string]bool{}
		for _, key := range stringsOf(rule["required"]) {
			required[key] = true
		}
		if missing, unknown := keyDiff(required, objectValue), keyDiff(objectValue, properties); len(missing)+len(unknown) > 0 {
			return fmt.Errorf("%s: missing keys %s; unknown keys %s", location, pythonList(missing), pythonList(unknown))
		}
		for _, key := range keys(objectValue) {
			if err := validateStateShape(objectValue[key], object(properties[key]), schema, location+"."+key); err != nil {
				return err
			}
		}
	}
	if kind == "array" {
		for index, item := range items(value) {
			if err := validateStateShape(item, object(rule["items"]), schema, fmt.Sprintf("%s[%d]", location, index)); err != nil {
				return err
			}
		}
	}
	return nil
}

type assignmentDirectory map[string]record

func (assignments assignmentDirectory) chainLast(row record, active string) record {
	for row != nil && str(row["id"]) != active {
		next := str(object(row["assessment"])["next_assignment"])
		if next == "" {
			break
		}
		row = assignments[next]
	}
	return row
}

func validateAuditState(value any) (assignmentDirectory, error) {
	schema, err := assetObject("audit-state.schema.json")
	if err != nil {
		return nil, err
	}
	if err := validateStateShape(value, schema, schema, "state"); err != nil {
		return nil, err
	}
	state := object(value)
	rows, assignments := items(state["assignments"]), assignmentDirectory{}
	for _, item := range rows {
		row := object(item)
		identity := str(row["id"])
		if _, found := assignments[identity]; found {
			return nil, fmt.Errorf("Duplicate assignment ID")
		}
		assignments[identity] = row
	}
	for _, item := range rows {
		row := object(item)
		identity := str(row["id"])
		assessment, observation := object(row["assessment"]), object(row["host_observation"])
		status, successor := str(assessment["status"]), str(assessment["next_assignment"])
		if status != "pending" && assessment["reason"] == nil {
			return nil, fmt.Errorf("%s: an assessment needs its reason", identity)
		}
		if successor != "" && (status != "follow_up" || assignments[successor] == nil) {
			return nil, fmt.Errorf("%s: next_assignment must name a recorded follow-up", identity)
		}
		seen := map[string]bool{identity: true}
		for successor != "" {
			if seen[successor] {
				return nil, fmt.Errorf("%s: cyclic assignment follow-up", identity)
			}
			seen[successor] = true
			if assignments[successor] == nil {
				return nil, fmt.Errorf("%s: unknown next_assignment %s", identity, successor)
			}
			successor = str(object(assignments[successor]["assessment"])["next_assignment"])
		}
		if observation["state"] != "unknown" && (observation["worker_id"] == nil || observation["observed_at"] == nil || observation["source"] == nil) {
			return nil, fmt.Errorf("%s: known host state needs worker, time and source", identity)
		}
		if (observation["observed_at"] == nil) != (observation["source"] == nil) {
			return nil, fmt.Errorf("%s: host observation time and source belong together", identity)
		}
		if timestamp, ok := observation["observed_at"].(string); ok && !validObservationTime(timestamp) {
			return nil, fmt.Errorf("%s: observed_at must be a UTC ISO timestamp ending in Z", identity)
		}
	}
	active := str(state["active_assignment"])
	next := object(state["next_step"])
	for _, identity := range []string{active, str(next["assignment"])} {
		if identity != "" && assignments[identity] == nil {
			return nil, fmt.Errorf("Unknown assignment reference: %s", identity)
		}
	}
	if active != "" && object(assignments[active]["assessment"])["status"] != "pending" {
		return nil, fmt.Errorf("The active assignment must have a pending assessment")
	}
	if state["phase"] == "publication" && state["route"] != "full" {
		return nil, fmt.Errorf("Only the full route has a publication phase")
	}
	if state["phase"] == "complete" {
		if active != "" || next != nil || len(items(state["remaining"]))+len(items(state["blockers"]))+len(items(object(state["plan"])["remaining"])) > 0 {
			return nil, fmt.Errorf("Complete state cannot contain active or unfinished work")
		}
		for _, item := range rows {
			row := object(item)
			if object(assignments.chainLast(row, "")["assessment"])["status"] != "accepted" {
				return nil, fmt.Errorf("%s: complete state needs an accepted result or completed follow-up", row["id"])
			}
		}
	} else if next == nil {
		return nil, fmt.Errorf("Unfinished work needs a next_step")
	}
	return assignments, nil
}

func validObservationTime(timestamp string) bool {
	if !strings.HasSuffix(timestamp, "Z") {
		return false
	}
	for _, layout := range []string{
		"2006-01-02T15:04:05Z", "2006-01-02T15:04Z", "2006-01-02T15Z", "20060102T150405Z", "20060102T1504Z", "20060102T15Z",
	} {
		if parsed, err := time.Parse(layout, timestamp); err == nil && parsed.Year() > 0 {
			return true
		}
	}
	return false
}

func auditDirectory(path string) (string, error) {
	path, err := filepath.Abs(path)
	if err != nil {
		return "", err
	}
	parent := filepath.Dir(path)
	for _, expected := range []string{"audits", "tech-debt", "memory"} {
		if filepath.Base(parent) != expected {
			return "", fmt.Errorf("Use <project-root>/memory/tech-debt/audits/<date-time>/")
		}
		parent = filepath.Dir(parent)
	}
	return reportOutput(path, parent, true)
}

func runAuditState(command string, args options, stdin io.Reader, stdout io.Writer) (int, error) {
	directory, err := auditDirectory(args.get("report-dir"))
	if err != nil {
		return 1, err
	}
	target := filepath.Join(directory, "state.json")
	var doc jsonDocument
	if command == "write" {
		doc, err = inputDocument(args, stdin, "Duplicate JSON key")
	} else {
		if args.has("input") {
			return 1, fmt.Errorf("--input belongs to write")
		}
		if err := checkStatePath(target, directory); err != nil {
			return 1, err
		}
		doc, err = readDocument(target, "Duplicate JSON key")
	}
	if err != nil {
		return 1, err
	}
	assignments, err := validateAuditState(doc.value)
	if err != nil {
		return 1, err
	}
	state := object(doc.value)
	if command == "read" {
		_, err := stdout.Write(doc.text)
		return 0, err
	}
	if command == "check" || state["phase"] == "complete" {
		issues, err := inspectAuditState(directory, state, assignments)
		if err != nil {
			return 1, err
		}
		if command == "check" {
			code := 0
			if len(issues) > 0 {
				code = 1
			}
			return code, printJSON(stdout, struct {
				Valid  bool     `json:"valid"`
				Issues []string `json:"issues"`
			}{code == 0, issues}, true)
		}
		if len(issues) > 0 {
			return 1, fmt.Errorf("Cannot complete audit: %s", strings.Join(issues, "; "))
		}
	}
	if err := checkStatePath(target, directory); err != nil {
		return 1, err
	}
	if err := writeState(target, directory, doc.text); err != nil {
		return 1, err
	}
	return 0, printJSON(stdout, record{"state": target}, false)
}

func inputDocument(args options, stdin io.Reader, duplicateMessage string) (jsonDocument, error) {
	if args.has("input") {
		return readDocument(filepath.Clean(args.get("input")), duplicateMessage)
	}
	data, err := io.ReadAll(stdin)
	if err != nil {
		return jsonDocument{}, err
	}
	return parseDocument(data, duplicateMessage)
}

func checkStatePath(target, directory string) error {
	resolved, err := resolve(target)
	if err != nil {
		return err
	}
	if !within(resolved, directory) {
		return fmt.Errorf("state.json must stay inside its audit directory")
	}
	return nil
}

func writeState(target, directory string, data []byte) error {
	if err := os.MkdirAll(directory, 0755); err != nil {
		return fileError(err)
	}
	file, err := os.CreateTemp(directory, ".state-*.json")
	if err != nil {
		return fileError(err)
	}
	defer os.Remove(file.Name())
	if _, err := file.Write(data); err != nil {
		file.Close()
		return fileError(err)
	}
	if err := file.Sync(); err != nil {
		file.Close()
		return fileError(err)
	}
	if err := file.Close(); err != nil {
		return fileError(err)
	}
	return fileError(os.Rename(file.Name(), target))
}

func inspectAuditState(directory string, state record, assignments assignmentDirectory) ([]string, error) {
	issues := []string{}
	require := func(path string, directoryExpected bool) error {
		resolved, err := resolveAuditRecord(directory, path)
		if err != nil {
			return err
		}
		if directoryExpected && !isDir(resolved) {
			issues = append(issues, "Missing directory: "+path)
		}
		if !directoryExpected && !isFile(resolved) {
			issues = append(issues, "Missing file: "+path)
		}
		return nil
	}
	readRecord := func(path string, required bool) (record, error) {
		resolved, err := resolveAuditRecord(directory, path)
		if err != nil && !required {
			return nil, err
		}
		if err == nil && !required && !isFile(resolved) {
			return nil, nil
		}
		var result record
		if err == nil {
			var doc jsonDocument
			doc, err = readDocument(resolved, "Duplicate JSON key")
			if err == nil {
				result = object(doc.value)
				if result == nil {
					err = fmt.Errorf("expected a JSON object")
				}
			}
		}
		if err != nil {
			issues = append(issues, path+": "+err.Error())
		}
		return result, nil
	}
	basis, plan := object(state["basis"]), object(state["plan"])
	for _, path := range stringsOf(basis["source_paths"]) {
		if err := require(path, true); err != nil {
			return nil, err
		}
	}
	var paths []any
	paths = append(paths, basis["configuration"], basis["collection_plan"])
	paths = append(paths, items(basis["artifacts"])...)
	paths = append(paths, plan["path"])
	paths = append(paths, items(plan["matched_tasks"])...)
	paths = append(paths, items(plan["added_tasks"])...)
	for _, path := range paths {
		if path != nil {
			if err := require(str(path), false); err != nil {
				return nil, err
			}
		}
	}
	active := str(state["active_assignment"])
	publicationAccepted := false
	for _, item := range items(state["assignments"]) {
		row := object(item)
		identity, assessment, observation := str(row["id"]), object(row["assessment"]), object(row["host_observation"])
		prefix := "assignments/" + identity + "/"
		request, _ := readRecord(prefix+"request.json", true)
		launch, err := readRecord(prefix+"launch.json", observation["worker_id"] != nil)
		if err != nil {
			return nil, err
		}
		result, err := readRecord(prefix+"result.json", assessment["status"] != "pending")
		if err != nil {
			return nil, err
		}
		add := func(message string) { issues = append(issues, identity+": "+message) }
		if launch != nil {
			worker := str(launch["worker_id"])
			if strings.TrimSpace(worker) == "" {
				add("recover the launch worker_id from the host")
			} else if worker != observation["worker_id"] {
				add("host observation worker_id does not match launch")
			}
		}
		if request != nil {
			assigned := object(request["assignment"])
			if assigned == nil {
				add("request needs an assignment object")
			}
			scope := assigned["scope"]
			if !sameKeys(object(scope), []string{"project", "task", "work"}) {
				add("request needs project/work/task scope")
			}
			if request["report"] != state["report"] || assigned["id"] != identity {
				add("request identity does not match state")
			}
			if active == identity && request["phase"] != state["phase"] {
				add("active request phase does not match state")
			}
			if result != nil {
				match := result["assignment_id"] == identity && reflect.DeepEqual(result["scope"], scope)
				for _, key := range []string{"report", "phase", "role"} {
					entry, found := request[key]
					match = match && found && reflect.DeepEqual(result[key], entry)
				}
				if !match {
					add("result identity/scope does not match request")
				}
			}
		}
		if result != nil {
			if !contains([]string{"completed", "partial", "blocked"}, str(result["status"])) {
				add("unknown worker result status")
			}
			artifacts := items(result["artifacts"])
			valid := artifacts != nil
			for _, path := range artifacts {
				valid = valid && strings.TrimSpace(str(path)) != ""
			}
			if !valid {
				add("result artifacts must be a list of primary file paths")
			} else {
				for _, path := range artifacts {
					if err := require(str(path), false); err != nil {
						return nil, err
					}
				}
				if assessment["status"] == "accepted" && len(artifacts) == 0 {
					add("acceptance needs primary output paths")
				}
			}
			if launch == nil {
				add("result has no saved launch")
			}
		}
		if assessment["status"] == "accepted" {
			if result == nil || result["status"] != "completed" || result["writing_stopped"] != true {
				add("acceptance needs a completed result with writing_stopped=true")
			}
			if observation["state"] != "stopped" {
				add("acceptance needs a recorded host stop observation")
			}
			publicationAccepted = publicationAccepted || request["phase"] == "publication"
		}
		if ((active != "" && active != identity) || assessment["next_assignment"] != nil) && launch != nil && observation["state"] != "stopped" {
			add("confirm the previous writer stopped before a successor")
		}
		if (active != "" || state["phase"] == "publication") && active != identity {
			last := assignments.chainLast(row, active)
			if object(last["assessment"])["status"] != "accepted" && last["id"] != active {
				add("assess the previous assignment or link its follow-up before continuing")
			}
		}
	}
	if state["phase"] == "publication" || state["phase"] == "complete" {
		if err := require("report.md", false); err != nil {
			return nil, err
		}
		if plan["path"] == nil {
			issues = append(issues, "Report delivery needs the current plan path")
		}
		if len(items(plan["remaining"])) > 0 {
			issues = append(issues, "Finish plan updates before publication")
		}
	}
	if state["phase"] == "complete" && state["route"] == "full" && !publicationAccepted {
		issues = append(issues, "Complete full audit needs the accepted publication assignment")
	}
	return issues, nil
}

func resolveAuditRecord(directory, path string) (string, error) {
	resolved, err := resolve(joinPath(directory, path))
	if err != nil {
		return "", err
	}
	if strings.HasPrefix(path, "assignments/") && !within(resolved, directory) {
		return "", fmt.Errorf("Assignment records must stay inside the audit directory")
	}
	return resolved, nil
}

func sameKeys(value record, required []string) bool {
	if len(value) != len(required) {
		return false
	}
	for _, key := range required {
		if _, found := value[key]; !found {
			return false
		}
	}
	return true
}
