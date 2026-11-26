package apply

import (
	"fmt"
	"strings"
)

func evidenceReference(value any) mapping {
	raw, _ := canonical(value)
	hash := digest(raw)
	kind := "string"
	switch value.(type) {
	case mapping:
		kind = "object"
	case []any, []string:
		kind = "array"
	}
	return mapping{"path": "objects/" + hash[:2] + "/" + hash + ".json", "sha256": hash, "bytes": len(raw), "kind": kind}
}

func checkLogIdentity(state, record mapping, checks []any) (mapping, error) {
	roleID := str(record["role_id"])
	if roleID == "" {
		return nil, reject("unknown_role", "Evidence role identity is invalid")
	}
	role := object(object(state["roles"])[roleID])
	if !truth(role) {
		return nil, reject("unknown_role", "Evidence role is missing or invalid")
	}
	before := record["before"]
	if _, ok := record["before"]; !ok {
		before = record["basis"]
	}
	return mapping{
		"work_kind": workKind(object(state["basis"])), "work_id": state["change_id"], "run_id": state["run_id"],
		"task_id": record["task_id"], "assignment_id": roleID, "check_run_id": record["check_run_id"],
		"role_id": roleID, "stage": record["stage"], "role_trace": selectFields(role, "context_id", "host", "launch_ref", "agent_selection", "model_observation"),
		"basis_before": evidenceReference(before), "basis_after": evidenceReference(record["after"]),
		"registry_revision": record["registry_revision"], "registry": evidenceReference(checks),
	}, nil
}

func checkLogCWD(state, record, check mapping) (string, error) {
	root := str(object(state["basis"])["project_root"])
	task := object(object(state["tasks"])[str(record["task_id"])])
	if worktree := object(task["worktree"]); worktree != nil && includes([]string{"baseline", "self", "independent"}, str(record["stage"])) {
		root = str(worktree["path"])
	}
	run := object(check["setup"])
	if run == nil {
		run = object(check["run"])
	}
	relative := orText(run["cwd"], orText(check["cwd"], "."))
	if relative == "." {
		return root, nil
	}
	return contained(root, relative)
}

func configuredReports(command any, configuration mapping) ([]any, error) {
	reports := []any{}
	seen := make(map[[2]string]bool)
	if value, exists := configuration["structured_reports"]; exists && array(value) == nil {
		return nil, fmt.Errorf("structured_reports must be a list")
	}
	for _, item := range array(configuration["structured_reports"]) {
		record := object(item)
		_, valid := record["required"].(bool)
		format, path := str(record["format"]), str(record["path"])
		if len(record) != 3 || format == "" || path == "" || !valid {
			return nil, fmt.Errorf("Structured report needs format, path and boolean required")
		}
		key := [2]string{format, path}
		if seen[key] {
			return nil, fmt.Errorf("Duplicate structured report")
		}
		seen[key] = true
		reports = append(reports, copyMapping(record))
	}
	argv := stringArray(command)
	for index, arg := range argv {
		name, path, explicit := strings.Cut(arg, "=")
		if name != "--junitxml" && name != "--junit-xml" {
			continue
		}
		if !explicit && index+1 < len(argv) {
			path = argv[index+1]
		}
		if path == "" {
			return nil, fmt.Errorf("Missing registered JUnit path")
		}
		var existing mapping
		for _, item := range reports {
			report := object(item)
			if report["format"] == "pytest-junit" && report["path"] == path {
				existing = report
				break
			}
		}
		if existing != nil {
			existing["required"] = true
		} else {
			reports = append(reports, mapping{"format": "pytest-junit", "path": path, "required": true})
		}
	}
	return reports, nil
}

func validateCheckLog(state, record mapping, checks []any, directory string) error {
	if !truth(record["summary"]) || !truth(record["check_run_id"]) {
		return reject("evidence_missing", "Machine summary and check run identity are required")
	}
	store := &execution{directory: directory}
	raw, err := store.readObject(record["summary"])
	if err != nil {
		return err
	}
	aggregate := object(raw)
	expected, err := checkLogIdentity(state, record, checks)
	if err != nil {
		return err
	}
	if digest(aggregate["identity"]) != digest(expected) {
		return reject("evidence_basis", "Summary belongs to another basis or role")
	}
	for _, field := range []string{"basis_before", "basis_after", "registry"} {
		if _, err := store.readObject(expected[field]); err != nil {
			return err
		}
	}
	if aggregate["source_unchanged"] != true {
		return reject("evidence_incomplete", "Required raw or structured evidence is unavailable")
	}
	ids, outputIDs, references := []string{}, []string{}, []any{}
	for _, value := range checks {
		ids = append(ids, str(object(value)["id"]))
	}
	for _, value := range array(record["outputs"]) {
		output := object(value)
		outputIDs = append(outputIDs, str(output["check_id"]))
		references = append(references, output["summary"])
	}
	if digest(aggregate["requested_check_ids"]) != digest(ids) || digest(aggregate["missing_check_ids"]) != digest([]any{}) {
		return reject("evidence_basis", "Summary registry differs")
	}
	if digest(aggregate["checks"]) != digest(references) {
		return reject("evidence_basis", "Summary check references differ from run")
	}
	if digest(outputIDs) != digest(ids) {
		return reject("evidence_basis", "Every registered check must appear exactly once")
	}
	for index, value := range array(record["outputs"]) {
		if err := validateCheckOutput(store, state, record, object(checks[index]), object(value), expected); err != nil {
			return err
		}
	}
	return nil
}

func validateCheckOutput(store *execution, state, record, check, output, expected mapping) error {
	if err := requireDeterministic(check); err != nil {
		return err
	}
	run := object(check["setup"])
	if run == nil {
		run = object(check["run"])
	}
	configuration := checkValue(run, "configuration", checkValue(check, "configuration", mapping{}))
	cwd, err := checkLogCWD(state, record, check)
	if err != nil {
		return err
	}
	if digest(output["command"]) != digest(run["command"]) || digest(output["configuration"]) != digest(configuration) || output["cwd"] != cwd {
		return reject("evidence_command", "Summary must preserve the exact registered command, cwd and configuration")
	}
	raw, err := store.readObject(output["summary"])
	if err != nil {
		return err
	}
	machine := object(raw)
	identity := copyMapping(expected)
	identity["check_id"] = output["check_id"]
	identity["configuration"] = evidenceReference(checkValue(output, "configuration", mapping{}))
	for key, value := range identity {
		if digest(machine[key]) != digest(value) {
			return reject("evidence_basis", "Check summary belongs to another basis")
		}
	}
	if _, err := store.readObject(machine["configuration"]); err != nil {
		return err
	}
	if machine["outcome"] != output["outcome"] || digest(machine["exit_code"]) != digest(output["exit_code"]) || digest(machine["command"]) != digest(output["command"]) {
		return reject("evidence_incomplete", "Summary does not preserve command evidence")
	}
	streams := object(machine["artifacts"])
	if _, usesCommand := output["command"]; usesCommand && (streams["stdout"] == nil || streams["stderr"] == nil) {
		return reject("evidence_missing", "Command raw streams are required")
	}
	for stream, reference := range streams {
		content, err := store.readObject(reference)
		if err != nil {
			return err
		}
		raw := object(content)
		if digest(raw["identity"]) != digest(identity) || raw["stream"] != stream {
			return reject("evidence_basis", "Raw evidence belongs to another run")
		}
	}
	reports := array(machine["structured_reports"])
	declared, err := configuredReports(output["command"], object(output["configuration"]))
	if err != nil {
		return err
	}
	actual := []any{}
	for _, value := range reports {
		actual = append(actual, selectFields(object(value), "format", "path", "required"))
	}
	if digest(actual) != digest(declared) {
		return reject("evidence_basis", "Structured reports must match their exact registered declarations")
	}
	for _, value := range reports {
		report := object(value)
		if !truth(report["reference"]) {
			continue
		}
		content, err := store.readObject(report["reference"])
		if err != nil {
			return err
		}
		raw := object(content)
		if digest(raw["identity"]) != digest(identity) || raw["stream"] != "structured_report" || raw["path"] != report["path"] ||
			raw["format"] != report["format"] || raw["resolved_path"] != report["resolved_path"] {
			return reject("evidence_basis", "Structured report belongs to another run")
		}
	}
	return nil
}
