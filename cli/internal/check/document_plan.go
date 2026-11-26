package check

import (
	"os"
	"path/filepath"
	"slices"
	"sort"
	"strings"
)

type taskGraph struct {
	dependencies map[string][]string
	conflicts    map[string]map[string]bool
	done         map[string]bool
}

func (validation *documentValidation) validatePlan(project, planPath string) (map[string]any, map[string]int) {
	owners := make(map[string][]string)
	graph := taskGraph{
		dependencies: make(map[string][]string),
		conflicts:    make(map[string]map[string]bool),
		done:         make(map[string]bool),
	}
	var tasks, criteria []string
	for _, id := range validation.order {
		switch validation.records[id].kind {
		case "task":
			tasks = append(tasks, id)
			graph.conflicts[id] = make(map[string]bool)
		case "acceptance":
			criteria = append(criteria, id)
		}
	}
	numbers := make(map[int]bool)
	for _, id := range tasks {
		task := validation.records[id]
		covers := validation.references(task, "covers", "AC", true)
		for _, criterion := range covers {
			owners[criterion] = append(owners[criterion], id)
		}
		dependencies := validation.references(task, "depends_on", "TASK", false)
		var conflicts []string
		if _, present := task.fields["cannot_parallel_with"]; present {
			conflicts = validation.references(task, "cannot_parallel_with", "TASK", false)
		}
		for _, related := range [][]string{dependencies, conflicts} {
			for _, target := range related {
				if target == id {
					validation.problem(task, "self_reference", "Task may not reference itself")
				}
			}
		}
		graph.dependencies[id] = dependencies
		for _, target := range conflicts {
			graph.conflicts[id][target] = true
			graph.conflicts[target][id] = true
		}
		if number, ok := task.fields["number"].(int); ok && number > 0 && number <= len(tasks) {
			numbers[number] = true
		}
		switch task.fields["status"] {
		case "done":
			graph.done[id] = true
		case "pending", "in_progress", "blocked":
		default:
			validation.problem(task, "task_status", "Unknown task status")
		}
		validation.validateTaskVerification(project, task, covers)
	}
	for _, criterion := range criteria {
		assigned := owners[criterion]
		if len(assigned) != 1 {
			validation.problem(validation.records[criterion], "task_coverage", "Expected one task owner, got "+documentList(assigned))
		}
	}
	if len(numbers) != len(tasks) {
		validation.issue("task_numbers", "Task numbers must be a permutation of 1..N", planPath, nil)
	}
	if remaining := graph.tasksBlockedByCycle(); len(remaining) != 0 {
		validation.issue("task_cycle", "Dependency cycle or tasks downstream of cycle: "+documentList(remaining), planPath, nil)
	}
	available := make([]string, 0)
	cannotParallelWith := make(map[string][]string, len(tasks))
	for _, id := range tasks {
		cannotParallelWith[id] = sortedIDs(graph.conflicts[id])
		if validation.records[id].fields["status"] == "pending" && graph.allDependenciesDone(id) {
			available = append(available, id)
		}
	}
	sort.Strings(available)
	return map[string]any{
		"available_by_graph":   available,
		"cannot_parallel_with": cannotParallelWith,
		"parallel_safety":      "Requires reviewer assessment of shared files and other conflicts",
	}, map[string]int{"done": len(graph.done), "total": len(tasks)}
}

func (graph taskGraph) allDependenciesDone(id string) bool {
	for _, dependency := range graph.dependencies[id] {
		if !graph.done[dependency] {
			return false
		}
	}
	return true
}

func (graph taskGraph) tasksBlockedByCycle() []string {
	indegrees := make(map[string]int)
	dependents := make(map[string][]string)
	ready := make([]string, 0)
	for id, dependencies := range graph.dependencies {
		indegrees[id] = len(dependencies)
		if len(dependencies) == 0 {
			ready = append(ready, id)
		}
		for _, dependency := range dependencies {
			dependents[dependency] = append(dependents[dependency], id)
		}
	}
	for index := 0; index < len(ready); index++ {
		for _, dependent := range dependents[ready[index]] {
			indegrees[dependent]--
			if indegrees[dependent] == 0 {
				ready = append(ready, dependent)
			}
		}
	}
	var remaining []string
	for id, indegree := range indegrees {
		if indegree != 0 {
			remaining = append(remaining, id)
		}
	}
	sort.Strings(remaining)
	return remaining
}

func sortedIDs(values map[string]bool) []string {
	sorted := make([]string, 0, len(values))
	for value := range values {
		sorted = append(sorted, value)
	}
	sort.Strings(sorted)
	return sorted
}

func (validation *documentValidation) validateTaskVerification(project string, task changeRecord, covers []string) {
	checks, _ := task.fields["verification"].([]any)
	if len(checks) == 0 {
		validation.problem(task, "verification", "verification must be a nonempty list")
	}
	verified := make(map[string]bool)
	for _, value := range checks {
		check, ok := value.(map[string]any)
		if !ok || !hasFields(check, []string{"criteria", "test_description", "location", "run"}, []string{"execution_kind"}) {
			validation.problem(task, "verification", "Each verification requires criteria, test_description, location and run")
			continue
		}
		run, _ := check["run"].(map[string]any)
		kind, present := check["execution_kind"]
		_, procedure := run["procedure"]
		if !present && !procedure {
			kind = "deterministic"
		}
		switch kind {
		case "deterministic", "behavioral", "manual":
		default:
			validation.problem(task, "execution_kind", "execution_kind must be deterministic, behavioral or manual; procedures require an explicit type")
		}
		criteria, ok := stringList(check["criteria"])
		if !ok || len(criteria) == 0 || !subset(criteria, covers) {
			validation.problem(task, "verification_criteria", "Verification criteria must be a nonempty subset of covers")
		} else {
			for _, criterion := range criteria {
				verified[criterion] = true
			}
		}
		if !nonemptyText(check["test_description"]) {
			validation.problem(task, "verification", "test_description must be nonempty text")
		}
		if err := checkVerificationLocation(project, check["location"]); err != nil {
			validation.problem(task, err.Code, err.Message)
		}
		validation.validateVerificationRun(project, task, run)
	}
	missing := make(map[string]bool)
	for _, criterion := range covers {
		if !verified[criterion] {
			missing[criterion] = true
		}
	}
	if len(missing) > 0 {
		validation.problem(task, "verification_coverage", "Missing verification for: "+documentList(sortedIDs(missing)))
	}
}

func subset(values, allowed []string) bool {
	for _, value := range values {
		if !slices.Contains(allowed, value) {
			return false
		}
	}
	return true
}

func checkVerificationLocation(project string, value any) *checkError {
	location, _ := value.(string)
	if location == "" || location != strings.TrimSpace(location) || strings.ContainsAny(location, "*?[]#;|&<>`\"") || strings.IndexFunc(location, func(r rune) bool { return r < 32 }) >= 0 {
		return &checkError{Code: "verification_location", Message: "location must be one relative file/directory path without selectors, anchors or shell syntax", Exit: 1}
	}
	canonical, err := containedPath(project, location)
	if err != nil {
		return err
	}
	relative, _ := filepath.Rel(project, canonical)
	if relative == "." || slices.Contains(strings.Split(strings.ToLower(filepath.ToSlash(relative)), "/"), ".git") {
		return &checkError{Code: "verification_location", Message: "location must identify a file/directory below the project root, outside .git", Exit: 1}
	}
	return nil
}

func (validation *documentValidation) validateVerificationRun(project string, task changeRecord, run map[string]any) {
	if len(run) == 1 {
		for kind, value := range run {
			switch kind {
			case "command":
				command, ok := stringList(value)
				if !ok || len(command) == 0 || !nonemptyText(command[0]) || strings.IndexByte(strings.Join(command, ""), 0) >= 0 {
					validation.problem(task, "verification_run", "command must be an argument array, e.g. ['pytest', '-q']; migrate legacy strings explicitly")
				}
				return
			case "procedure", "setup_required":
				if !nonemptyText(value) {
					validation.problem(task, "verification_run", "procedure and setup_required require nonempty text")
				} else if kind == "procedure" {
					path, _, _ := strings.Cut(value.(string), "#")
					canonical, err := containedPath(project, path)
					if err != nil {
						validation.problem(task, err.Code, err.Message)
					} else if info, statErr := os.Stat(canonical); statErr != nil || !info.Mode().IsRegular() {
						validation.problem(task, "missing_path", "Missing referenced file: "+path)
					}
				}
				return
			}
		}
	}
	validation.problem(task, "verification_run", "run requires exactly one command, procedure or setup_required")
}
