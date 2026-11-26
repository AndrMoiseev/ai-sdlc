package apply

import (
	_ "embed"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

//go:embed dashboard.html
var dashboardTemplate string

type executionWave struct {
	id, status, label string
	number, accepted  int
	dependsOn, tasks  []string
	blocked           []string
}

func renderDirectory(directory string) (mapping, error) {
	e, err := openExecution(directory)
	if err != nil {
		return nil, err
	}
	return e.render()
}

func sameMembers(left, right []string) bool {
	if len(left) != len(right) {
		return false
	}
	for _, item := range left {
		if !includes(right, item) {
			return false
		}
	}
	return true
}

func plannedWaves(state mapping) ([]executionWave, error) {
	tasks := object(state["tasks"])
	ordered := taskOrder(tasks)
	grouped := make([]executionWave, 0)
	seen := make(map[string]bool)
	for len(seen) < len(tasks) {
		var id string
		for _, key := range ordered {
			if seen[key] {
				continue
			}
			ready := true
			for _, dependency := range stringArray(object(object(tasks[key])["plan"])["depends_on"]) {
				if !seen[dependency] {
					ready = false
					break
				}
			}
			if ready {
				id = key
				break
			}
		}
		if id == "" {
			return nil, fmt.Errorf("wave_dependencies: cyclic or missing task dependency")
		}
		seen[id] = true
		plan := object(object(tasks[id])["plan"])
		deps := stringArray(plan["depends_on"])
		target := -1
		for index, wave := range grouped {
			if !sameMembers(wave.dependsOn, deps) {
				continue
			}
			conflict := false
			for _, other := range wave.tasks {
				if incompatible(plan, object(object(tasks[other])["plan"])) {
					conflict = true
					break
				}
			}
			if !conflict {
				target = index
				break
			}
		}
		if target == -1 {
			number := len(grouped) + 1
			dependencies := []string{}
			for _, other := range ordered {
				if includes(deps, other) {
					dependencies = append(dependencies, other)
				}
			}
			grouped = append(grouped, executionWave{id: fmt.Sprintf("wave-%d", number), number: number, dependsOn: dependencies, blocked: []string{}})
			target = len(grouped) - 1
		}
		grouped[target].tasks = append(grouped[target].tasks, id)
	}
	return grouped, nil
}

var waitingLabels = map[string]string{
	"run": "Execution paused; see blockers", "dependencies": "Waiting for acceptance",
	"conflict": "Cannot run alongside", "files": "Shared files occupied by", "resources": "Shared resources occupied by",
}

func waitingReasons(state mapping, id string) ([]any, []string) {
	reasons, text := []any{}, []string{}
	add := func(kind string, tasks []string) {
		reasons = append(reasons, mapping{"kind": kind, "tasks": tasks})
		label := waitingLabels[kind]
		if len(tasks) != 0 {
			label += ": " + strings.Join(tasks, ", ")
		}
		text = append(text, label)
	}
	tasks := object(state["tasks"])
	task := object(tasks[id])
	if task["status"] != "pending" {
		return reasons, text
	}
	if state["status"] != "active" || truth(state["blockers"]) {
		add("run", []string{})
	}
	plan := object(task["plan"])
	dependencies, conflicts, sharedFiles, sharedResources := []string{}, []string{}, []string{}, []string{}
	for _, dependency := range stringArray(plan["depends_on"]) {
		if object(tasks[dependency])["status"] != "accepted" {
			dependencies = append(dependencies, dependency)
		}
	}
	for _, key := range taskOrder(tasks) {
		other := object(tasks[key])
		if key == id || other["status"] == "accepted" {
			continue
		}
		if activeTask(other) {
			if incompatible(plan, object(other["plan"])) {
				conflicts = append(conflicts, key)
			}
			if ownedIntersection(stringArray(task["paths"]), stringArray(other["paths"]), true) {
				sharedFiles = append(sharedFiles, key)
			}
		}
		if ownedIntersection(stringArray(object(task["worktree"])["resources"]), stringArray(object(other["worktree"])["resources"]), false) {
			sharedResources = append(sharedResources, key)
		}
	}
	for _, group := range []struct {
		kind string
		ids  []string
	}{{"dependencies", dependencies}, {"conflict", conflicts}, {"files", sharedFiles}, {"resources", sharedResources}} {
		if len(group.ids) > 0 {
			add(group.kind, group.ids)
		}
	}
	return reasons, text
}

func localCriteria(state, task mapping) []string {
	plan := object(task["plan"])
	if covers, exists := plan["covers"]; exists {
		return stringArray(covers)
	}
	result := []string{}
	for _, id := range sortedKeys(object(state["acceptance"])) {
		if record := object(object(state["acceptance"])[id]); record["task"] == plan["id"] {
			result = append(result, str(record["id"]))
		}
	}
	return result
}

func technicalDebt(state mapping) []any {
	result := []any{}
	tasks := object(state["tasks"])
	for _, id := range taskOrder(tasks) {
		task := object(tasks[id])
		for _, value := range array(task["reviews"]) {
			review := object(value)
			for index, raw := range array(review["findings"]) {
				finding := object(raw)
				if finding["severity"] != "recommendation" {
					continue
				}
				entry := mapping{}
				for key, value := range finding {
					entry[key] = value
				}
				entry["finding_id"] = fmt.Sprintf("%s/%s/%s/%d", id, review["round_id"], review["lens_id"], index+1)
				entry["task_id"], entry["round_id"], entry["lens_id"] = id, review["round_id"], review["lens_id"]
				result = append(result, entry)
			}
		}
	}
	return result
}

func dashboardProjection(state mapping, directory string) (mapping, error) {
	waves, err := plannedWaves(state)
	if err != nil {
		return nil, err
	}
	tasks := object(state["tasks"])
	next := available(state)
	accepted, projected, projectedWaves := 0, []any{}, []any{}
	waitingByID := make(map[string][]any)
	for _, id := range taskOrder(tasks) {
		task := object(tasks[id])
		plan := object(task["plan"])
		if task["status"] == "accepted" {
			accepted++
		}
		commits, evidence := []string{}, []any{}
		for _, commit := range array(task["commits"]) {
			commits = append(commits, str(object(commit)["sha"]))
		}
		for _, proof := range array(task["evidence"]) {
			evidence = append(evidence, selectFields(object(proof), "stage", "outcome", "log"))
		}
		waiting, text := waitingReasons(state, id)
		waitingByID[id] = waiting
		projected = append(projected, mapping{
			"id": id, "status": task["status"], "criteria": localCriteria(state, task), "attempt": task["attempt"],
			"review":  fmt.Sprintf("%v/%v", task["review_rounds_started"], task["review_limit"]),
			"repair":  fmt.Sprintf("%v/%v", task["test_repair_cycles_started"], task["test_repair_limit"]),
			"commits": commits, "evidence": evidence, "blockers": task["blockers"], "depends_on": stringArray(plan["depends_on"]),
			"cannot_parallel_with": stringArray(plan["cannot_parallel_with"]), "waiting": waiting, "waiting_text": text,
			"verification": taskVerification(state, task, directory),
		})
	}
	for _, wave := range waves {
		inProgress, waitingDependencies, ready := false, false, false
		for _, taskID := range wave.tasks {
			task := object(tasks[taskID])
			if task["status"] == "accepted" {
				wave.accepted++
			}
			if task["status"] == "blocked" || truth(task["blockers"]) {
				wave.blocked = append(wave.blocked, taskID)
			}
			inProgress = inProgress || activeTask(task) && task["status"] != "blocked"
			ready = ready || includes(next, taskID) && len(waitingByID[taskID]) == 0
		}
		for _, dep := range wave.dependsOn {
			waitingDependencies = waitingDependencies || object(tasks[dep])["status"] != "accepted"
		}
		switch {
		case wave.accepted == len(wave.tasks):
			wave.status, wave.label = "completed", "Completed"
		case inProgress:
			wave.status, wave.label = "in_progress", "In progress"
		case waitingDependencies:
			wave.status, wave.label = "waiting_dependencies", "Waiting for dependencies"
		case ready:
			wave.status, wave.label = "ready", "Ready to launch"
		default:
			wave.status, wave.label = "waiting", "Waiting to launch"
		}
		projectedWaves = append(projectedWaves, mapping{"id": wave.id, "number": wave.number, "depends_on": wave.dependsOn,
			"tasks": wave.tasks, "accepted": wave.accepted, "blocked": wave.blocked, "status": wave.status, "label": wave.label})
	}
	data := selectFields(state, "change_id", "run_id", "revision", "updated_at", "status", "blockers", "final")
	if kind, exists := state["work_kind"]; exists {
		data["work_kind"] = kind
	}
	data["schema_version"], data["accepted"], data["total"] = 1, accepted, len(tasks)
	data["tasks"], data["waves"], data["next"] = projected, projectedWaves, next
	data["explorer_assignments"], data["technical_debt"] = explorerAssignments(state), technicalDebt(state)
	return data, nil
}

func (e *execution) render() (mapping, error) {
	state, err := e.projectState(true)
	if err != nil {
		return nil, err
	}
	data, err := dashboardProjection(state, e.directory)
	if err != nil {
		return nil, err
	}
	serialized := strings.NewReplacer("<", "\\u003c", ">", "\\u003e", "&", "\\u0026").Replace(string(ascii([]byte(dashboardJSON(data, "dashboard")))))
	summary, debt := dashboardMarkdown(data)
	html := strings.NewReplacer("__SNAPSHOT__", serialized, "__STATIC_TASKS__", staticWaves(data),
		"__CHANGE__", escapeHTML(str(data["change_id"])), "__SAVED_AT__", escapeHTML(str(data["updated_at"]))).Replace(strings.ReplaceAll(dashboardTemplate, "\r\n", "\n"))
	for _, output := range []struct{ name, contents string }{
		{"technical-debt.md", debt}, {"summary.md", summary},
		{"dashboard-state.js", "window.sddApplyUpdate(" + serialized + ");\n"}, {"dashboard.html", html},
	} {
		if err := atomicWrite(filepath.Join(e.directory, output.name), []byte(output.contents)); err != nil {
			return nil, err
		}
	}
	return mapping{"dashboard": filepath.Join(e.directory, "dashboard.html"), "summary": filepath.Join(e.directory, "summary.md"),
		"technical_debt": filepath.Join(e.directory, "technical-debt.md"), "revision": data["revision"]}, nil
}

func joined(items any, fallback string) string {
	values := stringArray(items)
	if len(values) == 0 {
		return fallback
	}
	return strings.Join(values, ", ")
}

func dashboardMarkdown(data mapping) (string, string) {
	summary := []string{"# " + str(data["change_id"]),
		fmt.Sprintf("Run: %s · revision %v", data["run_id"], data["revision"]),
		fmt.Sprintf("%s · accepted %v/%v", data["status"], data["accepted"], data["total"]),
		"Snapshot: " + str(data["updated_at"]), "",
		"Waves group planned parallel work. Task dependencies require acceptance; launch checks still apply. Integration is sequential.", ""}
	for _, value := range array(data["waves"]) {
		wave := object(value)
		summary = append(summary, fmt.Sprintf("- Wave %v: %s; after acceptance: %s; %s; accepted %v/%d",
			wave["number"], joined(wave["tasks"], ""), joined(wave["depends_on"], "none"), wave["label"], wave["accepted"], len(stringArray(wave["tasks"]))))
	}
	summary = append(summary, "")
	for _, value := range array(data["tasks"]) {
		task := object(value)
		summary = append(summary, fmt.Sprintf("- %s: %s; review %s; failed independent checks %s; commits %s",
			task["id"], task["status"], task["review"], task["repair"], joined(task["commits"], "none")))
		for _, reason := range stringArray(task["waiting_text"]) {
			summary = append(summary, "  - "+reason)
		}
		proofs := object(task["verification"])
		for _, stage := range sortedKeys(proofs) {
			proof := object(proofs[stage])
			summary = append(summary, fmt.Sprintf("  - %s: execution %s; conclusion %s", stage, object(proof["execution"])["status"], object(proof["conclusion"])["status"]))
		}
	}
	for _, value := range array(data["explorer_assignments"]) {
		role := object(value)
		summary = append(summary, fmt.Sprintf("- Explorer %s: scope %s; %s; stage %s; %s", role["role_id"],
			orText(object(role["scope"])["task"], "run"), role["kind"], orText(role["stage"], "research"), role["status"]))
	}
	summary = append(summary, "", "Blockers: "+dashboardJSON(data["blockers"], "blockers"))
	debt := []string{"# Technical debt", "", "Recorded review findings; fixes require explicit user approval after plan completion.", ""}
	findings := array(data["technical_debt"])
	for _, raw := range findings {
		finding := object(raw)
		debt = append(debt, "## "+str(finding["finding_id"]), "", "Path: "+str(finding["path"]),
			"Problem: "+str(finding["problem"]), "Proposed fix: "+str(finding["resolution"]), "")
	}
	if len(findings) == 0 {
		debt = append(debt, "No technical debt recorded.")
	}
	summary = append(summary, "", fmt.Sprintf("Technical debt: %d finding(s). [Journal](technical-debt.md).", len(findings)))
	return strings.Join(summary, "\n") + "\n", strings.Join(debt, "\n") + "\n"
}

var projectionOrder = map[string]string{
	"dashboard":            "explorer_assignments schema_version work_kind change_id run_id revision updated_at status accepted total tasks waves blockers next final technical_debt",
	"server":               "url run_id",
	"explorer_assignments": "role_id scope kind stage status successor_of",
	"scope":                "project work task",
	"tasks":                "id status criteria attempt review repair commits evidence blockers depends_on cannot_parallel_with waiting waiting_text verification",
	"waves":                "id number depends_on tasks accepted blocked status label",
	"evidence":             "stage outcome log",
	"waiting":              "kind tasks",
	"blockers":             "reason task_id resume_condition material missing",
	"missing":              "task_id criteria reason",
	"final":                "head time accepted_criteria missing evidence verification_results unassessed_criteria recommendations decisions commits result",
	"execution":            "status references checks",
	"conclusion":           "status id role_id",
	"references":           "check_id log sha256",
	"checks":               "check_id criteria location status reason",
	"check_report":         "schema_version stage work_kind change_id errors warnings checkpoint_status discussion_status review_status approval_status tasks progress",
	"checkpoint_status":    "schema_version operation status work_kind change_id checkpoint_ref head accepted_commit dirty changes diagnostics exit_code",
	"discussion_status":    "open_questions blocking_questions complete provenance",
	"review_status":        "required_lenses coverage reports complete unresolved_findings unfinished_fixes reused_decisions",
	"coverage":             "consistency simplicity premortem plan",
	"approval_status":      "approved ready applicability work_authorizations provenance",
	"changes":              "status path",
	"diagnostics":          "code message",
	"errors":               "code path element_id message",
	"warnings":             "code path element_id message",
}

func projectionKeys(value mapping, field string) []string {
	keys := strings.Fields(projectionOrder[field])
	if field == "tasks" && value["available_by_graph"] != nil {
		keys = []string{"available_by_graph", "cannot_parallel_with", "parallel_safety"}
	}
	if field == "baseline" || field == "self" || field == "independent" || field == "integration" {
		keys = []string{"execution", "conclusion"}
	}
	result := make([]string, 0, len(value))
	for _, key := range keys {
		if _, exists := value[key]; exists {
			result = append(result, key)
		}
	}
	for _, key := range sortedKeys(value) {
		if !includes(keys, key) {
			result = append(result, key)
		}
	}
	return result
}

func dashboardJSON(value any, field string) string {
	switch value := value.(type) {
	case mapping:
		parts := make([]string, 0, len(value))
		for _, key := range projectionKeys(value, field) {
			name, _ := jsonBytes(key, "")
			parts = append(parts, string(name)+": "+dashboardJSON(value[key], key))
		}
		return "{" + strings.Join(parts, ", ") + "}"
	case []any:
		items := make([]string, 0, len(value))
		for _, item := range value {
			items = append(items, dashboardJSON(item, field))
		}
		return "[" + strings.Join(items, ", ") + "]"
	case []string:
		items := make([]string, 0, len(value))
		for _, item := range value {
			items = append(items, dashboardJSON(item, field))
		}
		return "[" + strings.Join(items, ", ") + "]"
	default:
		raw, _ := jsonBytes(value, "")
		return string(raw)
	}
}

func orText(value any, fallback string) string {
	if text := str(value); text != "" {
		return text
	}
	return fallback
}

func escapeHTML(value string) string {
	return strings.NewReplacer("&", "&amp;", "<", "&lt;", ">", "&gt;", "\"", "&quot;", "'", "&#x27;").Replace(value)
}

func staticWaves(data mapping) string {
	tasks := make(map[string]mapping)
	for _, value := range array(data["tasks"]) {
		task := object(value)
		tasks[str(task["id"])] = task
	}
	var result strings.Builder
	result.WriteString("<section><h2>Run explorers</h2>")
	for _, value := range array(data["explorer_assignments"]) {
		role := object(value)
		if object(role["scope"])["task"] == nil {
			fmt.Fprintf(&result, "<p>%s · %s · %s</p>", escapeHTML(str(role["role_id"])), escapeHTML(orText(role["stage"], "research")), escapeHTML(str(role["status"])))
		}
	}
	result.WriteString("</section>")
	for _, value := range array(data["waves"]) {
		wave := object(value)
		dependencies := []string{}
		for _, id := range stringArray(wave["depends_on"]) {
			dependencies = append(dependencies, fmt.Sprintf(`<a class="dependency" href="#%s">%s · %s</a>`, encodeFragment("task-"+id), escapeHTML(id), escapeHTML(str(tasks[id]["status"]))))
		}
		after := "No dependencies"
		if len(dependencies) > 0 {
			after = strings.Join(dependencies, " ")
		}
		fmt.Fprintf(&result, `<section class="wave" data-wave="%s"><div class="wave-heading"><h2>Wave %v</h2><span class="badge">%s</span><span class="muted">%v / %d accepted</span></div><div class="dependencies">After acceptance: %s</div><div class="wave-tasks">`,
			wave["id"], wave["number"], wave["label"], wave["accepted"], len(stringArray(wave["tasks"])), after)
		for _, id := range stringArray(wave["tasks"]) {
			task := tasks[id]
			fmt.Fprintf(&result, `<article id="%s" tabindex="-1"><h3>%s</h3><p class="badge">%s</p>`, escapeHTML("task-"+id), escapeHTML(id), escapeHTML(str(task["status"])))
			for _, waiting := range stringArray(task["waiting_text"]) {
				fmt.Fprintf(&result, `<p class="waiting">%s</p>`, escapeHTML(waiting))
			}
			proofs := object(task["verification"])
			for _, stage := range sortedKeys(proofs) {
				proof := object(proofs[stage])
				fmt.Fprintf(&result, "<p>%s · Execution %s · Conclusion %s</p>", escapeHTML(stage), escapeHTML(str(object(proof["execution"])["status"])), escapeHTML(str(object(proof["conclusion"])["status"])))
			}
			for _, value := range array(data["explorer_assignments"]) {
				role := object(value)
				if object(role["scope"])["task"] == id {
					fmt.Fprintf(&result, "<p>Explorer %s · %s · %s · %s</p>", escapeHTML(str(role["role_id"])), escapeHTML(str(role["kind"])),
						escapeHTML(orText(role["stage"], "research")), escapeHTML(str(role["status"])))
				}
			}
			fmt.Fprintf(&result, "<p>Review %s · Failed independent checks %s</p></article>", escapeHTML(str(task["review"])), escapeHTML(str(task["repair"])))
		}
		result.WriteString("</div></section>")
	}
	return result.String()
}

func encodeFragment(value string) string {
	var result strings.Builder
	for _, b := range []byte(value) {
		if b >= 'A' && b <= 'Z' || b >= 'a' && b <= 'z' || b >= '0' && b <= '9' || strings.ContainsRune("-_.~", rune(b)) {
			result.WriteByte(b)
		} else {
			fmt.Fprintf(&result, "%%%02X", b)
		}
	}
	return result.String()
}

func existingFile(path string) bool {
	info, err := os.Stat(path)
	return err == nil && info.Mode().IsRegular()
}
