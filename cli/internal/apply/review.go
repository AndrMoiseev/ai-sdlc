package apply

import "sort"

var reviewLenses = []string{"code", "verification"}

func roundResults(task mapping, round any) mapping {
	if !truth(round) {
		round = task["active_review"]
		if revisions := array(task["reviews"]); !truth(round) && len(revisions) != 0 {
			round = object(revisions[len(revisions)-1])["round_id"]
		}
	}
	results := mapping{}
	for _, value := range array(task["reviews"]) {
		review := object(value)
		if review["round_id"] == round {
			results[str(review["lens_id"])] = review
		}
	}
	for lens, original := range object(object(task["reused_reviews"])[str(round)]) {
		if results[lens] != nil {
			continue
		}
		for _, value := range array(task["reviews"]) {
			review := object(value)
			if review["round_id"] == original && review["lens_id"] == lens {
				results[lens] = review
				break
			}
		}
	}
	return results
}

func reviewed(task mapping) error {
	results := roundResults(task, nil)
	if truth(task["active_review"]) || len(results) != len(reviewLenses) {
		return reject("review_missing", "Every required independent review lens must pass")
	}
	for _, lens := range reviewLenses {
		if object(results[lens])["verdict"] != "pass" {
			return reject("review_missing", "Every required independent review lens must pass")
		}
	}
	return nil
}

func codeReviewBasis(task, checksBasis mapping) mapping {
	source := selectFields(checksBasis, "run_id", "change_id", "source", "manifest")
	return mapping{"source": source, "plan": task["plan"], "paths": task["paths"]}
}

func taskReviewBasis(state, task, source mapping, directory string) (mapping, error) {
	stage := stageFor(task)
	basis, err := explorerBasisAtSource(state, task, source, "checks", directory)
	if err != nil {
		return nil, err
	}
	return mapping{"checks": basis, "attempts_hash": digest(attempts(task, stage))}, nil
}

func startReview(state, task, event mapping, directory string) (any, error) {
	if !includes([]string{"verifying", "reviewing", "integrating"}, str(task["status"])) {
		return nil, reject("review_phase", "Verification precedes review")
	}
	payload := object(event["payload"])
	role, err := independentRole(state, task, str(payload["role_id"]), "reviewer")
	if err != nil {
		return nil, err
	}
	source, err := currentTaskSource(state, task)
	if err != nil {
		return nil, err
	}
	if _, err := validTaskEvidenceAtSource(state, task, source, directory, ""); err != nil {
		return nil, err
	}
	lens := str(role["lens_id"])
	basis, err := taskReviewBasis(state, task, source, directory)
	if err != nil {
		return nil, err
	}
	if truth(task["active_review"]) {
		if digest(task["review_basis"]) != digest(basis) {
			return nil, reject("review_stale", "Review lenses require the same check run and source")
		}
		if object(task["active_reviewers"])[lens] != nil || roundResults(task, nil)[lens] != nil {
			return nil, reject("review_active", "Resume or reuse the existing review lens instead of reserving twice")
		}
	} else {
		prior := roundResults(task, nil)
		code := object(prior["code"])
		reusable := false
		if code["verdict"] == "pass" && object(prior["verification"])["verdict"] == "more_checks" {
			current := codeReviewBasis(task, object(basis["checks"]))
			reusable = digest(code["basis"]) == digest(current)
		}
		if reusable && lens != "verification" {
			return nil, reject("review_reusable", "Reuse the unchanged code verdict and start the verification lens")
		}
		rounds := intValue(task["review_rounds_started"])
		if rounds >= intValue(task["review_limit"]) {
			return blockBudget(state, task, "review_limit_reached")
		}
		task["active_review"], task["review_rounds_started"] = event["event_id"], rounds+1
		if reusable {
			reused := object(task["reused_reviews"])
			if reused == nil {
				reused = mapping{}
				task["reused_reviews"] = reused
			}
			reused[str(task["active_review"])] = mapping{"code": code["round_id"]}
		}
		task["active_reviewers"], task["review_basis"] = mapping{}, basis
	}
	object(task["active_reviewers"])[lens] = payload["role_id"]
	task["status"] = "reviewing"
	return mapping{"round": task["review_rounds_started"], "lens_id": lens,
		"reused_lenses": sortedKeys(object(object(task["reused_reviews"])[str(task["active_review"])]))}, nil
}

func reviewResult(state, task, event mapping, directory string) (any, error) {
	payload := object(event["payload"])
	role, err := independentRole(state, task, str(payload["role_id"]), "reviewer")
	if err != nil {
		return nil, err
	}
	lens := str(role["lens_id"])
	if !truth(task["active_review"]) || object(task["active_reviewers"])[lens] != payload["role_id"] {
		return nil, reject("review_not_started", "Reserve this review lens first")
	}
	source, err := currentTaskSource(state, task)
	if err != nil {
		return nil, err
	}
	basis, err := taskReviewBasis(state, task, source, directory)
	if err != nil {
		return nil, err
	}
	if digest(task["review_basis"]) != digest(basis) {
		return nil, reject("review_stale", "Source, registry or check run changed during review")
	}
	if _, exists := payload["candidate"]; exists {
		return nil, reject("review_schema", "Review results no longer accept candidate references")
	}
	verdict := str(payload["verdict"])
	if !includes([]string{"pass", "changes", "more_checks"}, verdict) || array(payload["findings"]) == nil {
		return nil, reject("review_schema", "Verdict and findings required")
	}
	if !truth(payload["trace"]) {
		return nil, reject("review_evidence", "Retain the actual reviewer trace")
	}
	var conclusion mapping
	if lens == "verification" {
		if !truth(payload["test_integrity"]) {
			return nil, reject("review_evidence", "Verification owns assertion strength and test integrity")
		}
		conclusion, err = applicableVerificationAtSource(state, task, source, directory, "")
		if err != nil {
			return nil, err
		}
		if conclusion["role_id"] != payload["role_id"] || conclusion["round_id"] != task["active_review"] {
			return nil, reject("verification_missing", "Submit this lens's current criterion conclusion")
		}
		if verdict == "pass" && conclusion["outcome"] != "passed" {
			return nil, reject("verification_failed", "Unconfirmed criteria prevent a passing verification lens")
		}
	} else if _, integrity := payload["test_integrity"]; integrity || verdict == "more_checks" {
		return nil, reject("review_scope", "Code review owns architecture and code quality; route test evidence gaps to verification")
	}
	findings := []any{}
	blockers := false
	for _, value := range array(payload["findings"]) {
		finding := object(value)
		if finding == nil {
			return nil, reject("finding_schema", "Finding must be an object")
		}
		for _, key := range []string{"severity", "criteria", "path", "problem", "resolution"} {
			if _, ok := finding[key]; !ok {
				return nil, reject("finding_schema", "Findings need AC, file and resolution condition")
			}
		}
		if finding["severity"] != "blocker" && finding["severity"] != "recommendation" {
			return nil, reject("finding_severity", "Unknown severity")
		}
		proof := object(finding["proof"])
		proofKind := str(proof["kind"])
		if lens == "code" && (proofKind == "acceptance" || truth(finding["criteria"])) || lens == "verification" && proofKind == "architecture" {
			return nil, reject("review_scope", "Acceptance and test evidence belong to verification; architecture belongs to code")
		}
		output := copyMapping(finding)
		output["reported_severity"], output["severity"] = finding["severity"], "recommendation"
		if includes([]string{"acceptance", "architecture", "project_rule"}, proofKind) && meaningful(proof["source"]) && meaningful(proof["violation"]) {
			output["severity"] = "blocker"
			blockers = true
		}
		findings = append(findings, output)
	}
	if verdict == "pass" && blockers {
		return nil, reject("review_blocker", "Pass conflicts with proven violations")
	}
	reportedVerdict := verdict
	if verdict == "changes" && !blockers && (lens == "code" || conclusion["outcome"] == "passed") {
		verdict = "pass"
	}
	result := copyMapping(payload)
	result["lens_id"], result["verdict"], result["reported_verdict"], result["findings"] = lens, verdict, reportedVerdict, findings
	result["round_id"], result["round"] = task["active_review"], task["review_rounds_started"]
	if lens == "code" {
		result["basis"] = codeReviewBasis(task, object(basis["checks"]))
	}
	task["reviews"] = append(array(task["reviews"]), result)
	role["status"] = "finished"
	round := roundResults(task, nil)
	if len(round) != len(reviewLenses) {
		pending := []string{}
		for _, lensID := range reviewLenses {
			if round[lensID] == nil {
				pending = append(pending, lensID)
			}
		}
		sort.Strings(pending)
		return mapping{"verdict": verdict, "status": "reviewing", "pending_lenses": pending}, nil
	}
	verdict = "pass"
	for _, value := range round {
		status := str(object(value)["verdict"])
		if status == "changes" || status == "more_checks" && verdict != "changes" {
			verdict = status
		}
	}
	if verdict == "pass" {
		if _, err := requirePassedAtSource(state, task, source, directory, ""); err != nil {
			return nil, err
		}
	}
	task["review_rounds_completed"], task["active_review"] = intValue(task["review_rounds_completed"])+1, nil
	switch verdict {
	case "pass":
		task["status"] = "committing"
		if object(task["worktree"]) != nil && !truth(object(task["worktree"])["integrated"]) {
			task["status"] = "integrating"
		}
	case "more_checks":
		task["status"] = "verifying"
	case "changes":
		task["failure"] = mapping{"budget": "review", "outcome": "changes_requested"}
		if intValue(task["review_rounds_started"]) >= intValue(task["review_limit"]) {
			_, _ = blockBudget(state, task, "review_limit_reached")
		}
	}
	return mapping{"verdict": verdict, "status": task["status"]}, nil
}
