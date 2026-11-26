package apply

import (
	"os"
	"sort"
	"strings"
)

func stageFor(task mapping) string {
	if truth(object(task["worktree"])["integrated"]) {
		return "integration"
	}
	return "independent"
}

func currentTaskSource(state, task mapping) (mapping, error) {
	if !includes([]string{"verifying", "reviewing", "integrating", "committing", "accepted"}, str(task["status"])) {
		return nil, reject("check_phase", "Prepare the task commit before verification")
	}
	if err := checkRegistryCurrent(state, task); err != nil {
		return nil, err
	}
	if workKind(object(state["basis"])) == "refactoring" && !truth(task["baseline_checks"]) {
		return nil, reject("baseline_missing", "Capture existing checks before freezing a refactoring result")
	}
	source, err := snapshot(state, taskRoot(state, task))
	if err != nil {
		return nil, err
	}
	return source, cleanSource(source)
}

func attempts(task mapping, stage string) mapping {
	evidence, procedures := []any{}, mapping{}
	for _, value := range array(task["evidence"]) {
		if orText(object(value)["stage"], "final") == stage {
			evidence = append(evidence, value)
		}
	}
	for id, value := range object(task["procedures"]) {
		if orText(object(value)["stage"], "final") == stage {
			procedures[id] = value
		}
	}
	return mapping{"evidence": evidence, "procedures": procedures}
}

func taskCriteria(state, task mapping) []string {
	criteria := map[string]bool{}
	for _, id := range localCriteria(state, task) {
		criteria[id] = true
	}
	if workKind(object(state["basis"])) == "refactoring" {
		for _, id := range stringArray(object(task["plan"])["preserves"]) {
			criteria[id] = true
		}
	}
	result := []string{}
	for id := range criteria {
		result = append(result, id)
	}
	sort.Strings(result)
	return result
}

func independentRole(state, task mapping, roleID, kind string) (mapping, error) {
	role := object(object(state["roles"])[roleID])
	if role["kind"] != kind || role["task_id"] != object(task["plan"])["id"] || role["status"] != "active" {
		return nil, reject("role_unavailable", "Active independent role required")
	}
	if role["fresh"] != true || authorContext(state, task, role["context_id"]) {
		return nil, reject("role_not_independent", "Author context cannot independently verify or review")
	}
	return role, nil
}

func authorContext(state, task mapping, context any) bool {
	taskID := object(task["plan"])["id"]
	for _, value := range object(state["roles"]) {
		role := object(value)
		if role["kind"] == "executor" && role["task_id"] == taskID && digest(role["context_id"]) == digest(context) {
			return true
		}
	}
	return false
}

func verificationReviewer(state, task mapping, roleID string, active bool) (mapping, error) {
	role := object(object(state["roles"])[roleID])
	if active {
		if _, err := independentRole(state, task, roleID, "reviewer"); err != nil {
			return nil, err
		}
	}
	if role["kind"] != "reviewer" || role["lens_id"] != "verification" || role["task_id"] != object(task["plan"])["id"] ||
		role["status"] != "active" && (active || role["status"] != "finished") {
		return nil, reject("role_unavailable", "Conclusion requires the independent verification reviewer")
	}
	if role["fresh"] != true || authorContext(state, task, role["context_id"]) {
		return nil, reject("role_not_independent", "Author cannot supply a conclusion")
	}
	return role, nil
}

func evidenceLog(directory string, evidence mapping, missingCode string) (mapping, error) {
	name := str(evidence["log"])
	path, err := contained(directory, name)
	if err != nil {
		return nil, err
	}
	if !existingFile(path) {
		return nil, reject(missingCode, name)
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	if digest(raw) != evidence["log_hash"] {
		return nil, reject("evidence_corrupt", name)
	}
	decoded, err := decode(raw)
	if err != nil {
		return nil, err
	}
	return object(decoded), nil
}

func latestEvidence(task mapping, stage string, checks []any) (map[string]mapping, []string) {
	latest := make(map[string]mapping)
	order := []string{}
	items := array(task["evidence"])
	for index := len(items) - 1; index >= 0; index-- {
		item := object(items[index])
		if truth(item["procedure"]) {
			continue
		}
		itemStage := orText(item["stage"], "final")
		if stage != "" && itemStage != stage || stage == "" && itemStage != "independent" && itemStage != "integration" {
			continue
		}
		id := str(item["check_id"])
		if latest[id] == nil && selectedCheck(checks, id) != nil {
			order = append(order, id)
			latest[id] = item
		}
	}
	return latest, order
}

func evidenceRefs(state, task mapping, stage, directory string) ([]any, error) {
	checks, err := registryChecks(state, task, directory)
	if err != nil {
		return nil, err
	}
	latest, order := latestEvidence(task, stage, checks)
	sort.Strings(order)
	result := []any{}
	for _, id := range order {
		item := latest[id]
		record, err := evidenceLog(directory, item, "evidence_missing")
		if err != nil {
			return nil, err
		}
		result = append(result, mapping{"check_id": id, "log": item["log"], "sha256": item["log_hash"],
			"check_run_id": record["check_run_id"], "summary": record["summary"]})
	}
	return result, nil
}

func verificationPacket(state, task mapping, directory, stage string) (mapping, error) {
	basis, err := explorerBasis(state, task, "checks", stage, directory)
	if err != nil {
		return nil, err
	}
	refs, err := evidenceRefs(state, task, stage, directory)
	if err != nil {
		return nil, err
	}
	return mapping{"stage": stage, "basis": basis, "criteria": taskCriteria(state, task), "evidence_refs": refs}, nil
}

func registeredChecks(state, record mapping) ([]any, error) {
	checks := array(record["registered_checks"])
	role := object(object(state["roles"])[str(record["role_id"])])
	assignment := object(role["assignment"])
	checkIDs := map[string]bool{}
	valid := len(checks) != 0 && intValue(record["registry_revision"]) == intValue(assignment["registry_revision"])
	for _, value := range checks {
		check := object(value)
		id := str(check["id"])
		previous := selectedCheck(array(object(assignment["basis"])["checks"]), id)
		if checkIDs[id] || digest(previous) != digest(check) {
			valid = false
		}
		checkIDs[id] = true
	}
	if !valid {
		return nil, reject("evidence_basis", "Recorded checks must belong to the original complete Explorer assignment")
	}
	return checks, nil
}

func outputFor(log mapping, id string) mapping {
	for _, value := range array(log["outputs"]) {
		if output := object(value); output["check_id"] == id {
			return output
		}
	}
	return nil
}

func validateProcedureLogs(directory string, log mapping, message string) error {
	for _, value := range array(log["outputs"]) {
		output := object(value)
		if !truth(output["procedure_log"]) {
			continue
		}
		path, err := contained(directory, str(output["procedure_log"]))
		if err != nil {
			return err
		}
		raw, err := os.ReadFile(path)
		if err != nil || digest(raw) != output["procedure_log_hash"] {
			return reject("evidence_corrupt", message)
		}
	}
	return nil
}

func validTaskEvidence(state, task mapping, directory, stage string) ([]any, error) {
	source, err := currentTaskSource(state, task)
	if err != nil {
		return nil, err
	}
	return validTaskEvidenceAtSource(state, task, source, directory, stage)
}

func validTaskEvidenceAtSource(state, task, source mapping, directory, stage string) ([]any, error) {
	checks, err := registryChecks(state, task, directory)
	if err != nil {
		return nil, err
	}
	latest, order := latestEvidence(task, stage, checks)
	if len(checks) == 0 || len(order) != len(checks) {
		return nil, reject("required_checks", "Every required command/procedure must pass")
	}
	matches := []any{}
	validated := map[string]bool{}
	for _, id := range order {
		item := latest[id]
		if item["outcome"] != "passed" {
			return nil, reject("required_checks", "Latest required check is failed, unavailable or stale")
		}
		log, err := evidenceLog(directory, item, "evidence_corrupt")
		if err != nil {
			return nil, err
		}
		original, err := registeredChecks(state, log)
		if err != nil {
			return nil, err
		}
		check, prior := selectedCheck(checks, id), selectedCheck(original, id)
		if !sameCheckExecution(check, prior) {
			return nil, reject("evidence_basis", "Evidence must use the current check command, configuration and dependencies")
		}
		output := outputFor(log, id)
		if output == nil || output["outcome"] != item["outcome"] || !truth(output["evidence_complete"]) {
			return nil, reject("evidence_incomplete", "The required check needs complete passing evidence")
		}
		if log["task_id"] != object(task["plan"])["id"] || log["role_id"] != item["role_id"] || log["stage"] != item["stage"] ||
			digest(log["after"]) != digest(log["before"]) || object(log["before"])["commit"] != item["head"] {
			return nil, reject("evidence_basis", "Evidence must name this task and its unchanged recorded source")
		}
		if log["run_id"] != state["run_id"] || digest(log["before"]) != digest(source) {
			return nil, reject("evidence_basis", "Evidence must name the current run and source")
		}
		hash := str(item["log_hash"])
		if !validated[hash] {
			if err := validateCheckLog(state, log, original, directory); err != nil {
				return nil, err
			}
			if err := validateProcedureLogs(directory, log, "Procedure log changed"); err != nil {
				return nil, err
			}
			validated[hash] = true
		}
		role, err := authorizeExplorer(state, task, str(item["role_id"]), str(item["stage"]), directory, false, false)
		if err != nil {
			return nil, err
		}
		if !truth(role["fresh"]) || authorContext(state, task, role["context_id"]) {
			return nil, reject("role_not_independent", "Evidence author is not independent")
		}
		run := object(check["setup"])
		if run == nil {
			run = object(check["run"])
		}
		if truth(run["procedure"]) {
			var last mapping
			for _, value := range array(task["evidence"]) {
				record := object(value)
				if truth(record["procedure"]) && record["check_id"] == id && record["stage"] == item["stage"] {
					last = record
				}
			}
			if last == nil || last["outcome"] != "passed" || last["log"] != output["procedure_log"] || last["log_hash"] != output["procedure_log_hash"] {
				return nil, reject("required_checks", "The latest procedure must pass and be included in the current complete check run")
			}
		}
		matches = append(matches, item)
	}
	return matches, nil
}

func validateEvidenceRefs(state, task mapping, stage string, basis mapping, refs []any, directory string) error {
	seen := map[string]bool{}
	for _, value := range refs {
		ref := object(value)
		path := str(ref["log"])
		if seen[path] {
			continue
		}
		seen[path] = true
		record, err := evidenceLog(directory, mapping{"log": path, "log_hash": ref["sha256"]}, "evidence_missing")
		if err != nil {
			return err
		}
		if record["run_id"] != state["run_id"] || record["task_id"] != object(task["plan"])["id"] ||
			record["stage"] != stage || digest(record["before"]) != digest(basis["source"]) || digest(record["after"]) != digest(basis["source"]) {
			return reject("verification_basis", "Conclusion evidence must belong to this task, stage and unchanged source")
		}
		role, err := authorizeExplorer(state, task, str(record["role_id"]), stage, directory, false, false)
		if err != nil {
			return err
		}
		if role["fresh"] != true || authorContext(state, task, role["context_id"]) {
			return reject("role_not_independent", "Conclusion evidence must come from an independent explorer")
		}
		original, err := registeredChecks(state, record)
		if err != nil {
			return err
		}
		for _, check := range array(basis["checks"]) {
			prior := selectedCheck(original, str(object(check)["id"]))
			if prior != nil && !sameCheckExecution(prior, object(check)) {
				return reject("verification_basis", "Check execution inputs changed")
			}
		}
		if err := validateCheckLog(state, record, original, directory); err != nil {
			return err
		}
		if err := validateProcedureLogs(directory, record, "Referenced procedure evidence changed"); err != nil {
			return err
		}
	}
	return nil
}

func applicableVerification(state, task mapping, directory, stage string) (mapping, error) {
	return applicableVerificationAtSource(state, task, nil, directory, stage)
}

func applicableVerificationAtSource(state, task, source mapping, directory, stage string) (mapping, error) {
	if stage == "" {
		stage = stageFor(task)
	}
	var result mapping
	for _, raw := range array(task["verification_results"]) {
		if value := object(raw); value["stage"] == stage {
			result = value
		}
	}
	if result == nil {
		return nil, reject("verification_missing", "A current verification lens conclusion is required")
	}
	if source == nil {
		var err error
		source, err = currentTaskSource(state, task)
		if err != nil {
			return nil, err
		}
	}
	basis, err := explorerBasisAtSource(state, task, source, "checks", directory)
	if err != nil {
		return nil, err
	}
	if digest(result["basis"]) != digest(basis) || result["attempts_hash"] != digest(attempts(task, stage)) {
		return nil, reject("verification_stale", "Source, registry or applicable check attempt changed after the conclusion")
	}
	refs, err := evidenceRefs(state, task, stage, directory)
	if err != nil {
		return nil, err
	}
	if digest(result["evidence_refs"]) != digest(refs) {
		return nil, reject("verification_stale", "Conclusion must reference the latest exact evidence")
	}
	if _, err := verificationReviewer(state, task, str(result["role_id"]), false); err != nil {
		return nil, err
	}
	if err := validateEvidenceRefs(state, task, stage, basis, refs, directory); err != nil {
		return nil, err
	}
	return result, nil
}

func requirePassed(state, task mapping, directory, stage string) ([]any, error) {
	source, err := currentTaskSource(state, task)
	if err != nil {
		return nil, err
	}
	return requirePassedAtSource(state, task, source, directory, stage)
}

func requirePassedAtSource(state, task, source mapping, directory, stage string) ([]any, error) {
	if stage == "" {
		stage = stageFor(task)
	}
	evidence, err := validTaskEvidenceAtSource(state, task, source, directory, stage)
	if err != nil {
		return nil, err
	}
	result, err := applicableVerificationAtSource(state, task, source, directory, stage)
	if err != nil {
		return nil, err
	}
	if result["outcome"] != "passed" {
		return nil, reject("verification_failed", "Every applicable criterion must have a passed conclusion")
	}
	return evidence, nil
}

func verificationResultEvent(state, task, event mapping, directory string) (any, error) {
	payload := object(event["payload"])
	stage := str(payload["stage"])
	if task == nil || stage == "final" {
		return nil, reject("verification_stage", "Use task verification; final assessment has been removed")
	}
	if stage != stageFor(task) {
		return nil, reject("verification_stage", "Use the current independent/integration stage")
	}
	if _, err := verificationReviewer(state, task, str(payload["role_id"]), true); err != nil {
		return nil, err
	}
	if !truth(task["active_review"]) || object(task["active_reviewers"])["verification"] != payload["role_id"] {
		return nil, reject("review_not_started", "Reserve the verification lens after successful project checks")
	}
	source, err := currentTaskSource(state, task)
	if err != nil {
		return nil, err
	}
	basis, err := explorerBasisAtSource(state, task, source, "checks", directory)
	if err != nil {
		return nil, err
	}
	if digest(payload["basis"]) != digest(basis) {
		return nil, reject("verification_basis", "Use the current source, manifest and complete registry basis")
	}
	refs, err := evidenceRefs(state, task, stage, directory)
	if err != nil {
		return nil, err
	}
	if array(payload["evidence_refs"]) == nil || digest(payload["evidence_refs"]) != digest(refs) {
		return nil, reject("verification_evidence", "Reference the latest exact check runs, log digests and summaries")
	}
	if err := validateEvidenceRefs(state, task, stage, basis, refs, directory); err != nil {
		return nil, err
	}
	results := array(payload["criteria_results"])
	if results == nil {
		return nil, reject("verification_criteria", "Provide criterion results")
	}
	identifiers := []string{}
	seen := map[string]bool{}
	for _, value := range results {
		item := object(value)
		if item == nil {
			return nil, reject("verification_criteria", "Provide criterion results")
		}
		id, valid := item["criterion_id"].(string)
		if !valid || seen[id] {
			return nil, reject("verification_criteria", "Cover every applicable criterion exactly once, without foreign criteria")
		}
		seen[id] = true
		identifiers = append(identifiers, id)
	}
	if !sameMembers(identifiers, taskCriteria(state, task)) {
		return nil, reject("verification_criteria", "Cover every applicable criterion exactly once, without foreign criteria")
	}
	outcome := "passed"
	for _, value := range results {
		item := object(value)
		status := str(item["outcome"])
		if !includes([]string{"passed", "failed", "unavailable"}, status) || !meaningful(item["reason"]) || !nonemptyStrings(item["references"]) {
			return nil, reject("verification_criteria", "Each criterion needs an outcome, reason and inspected source/evidence references")
		}
		if request, exists := item["check_request"]; exists && (status == "passed" || !meaningful(request)) {
			return nil, reject("verification_request", "A concrete additional check request belongs to an unconfirmed criterion")
		}
		if status == "failed" || status == "unavailable" && outcome != "failed" {
			outcome = status
		}
	}
	limitations := array(payload["limitations"])
	if limitations == nil || !truth(payload["trace"]) {
		return nil, reject("verification_schema", "Record limitations and actual verification reviewer trace")
	}
	for _, value := range limitations {
		if _, ok := value.(string); !ok {
			return nil, reject("verification_schema", "Record limitations and actual verification reviewer trace")
		}
	}
	if outcome == "passed" {
		if _, err := validTaskEvidenceAtSource(state, task, source, directory, stage); err != nil {
			return nil, err
		}
	}
	result := copyMapping(payload)
	result["id"], result["outcome"], result["round_id"] = event["event_id"], outcome, task["active_review"]
	result["attempts_hash"], result["time"] = digest(attempts(task, stage)), now()
	task["verification_results"] = append(array(task["verification_results"]), result)
	return mapping{"verification_result": result}, nil
}

func sameCheckExecution(left, right mapping) bool {
	if left == nil || right == nil {
		return false
	}
	l, r := copyMapping(left), copyMapping(right)
	for _, field := range strings.Fields("criteria source") {
		delete(l, field)
		delete(r, field)
	}
	return digest(l) == digest(r)
}
