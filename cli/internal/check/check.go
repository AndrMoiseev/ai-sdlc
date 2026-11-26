// Package check validates the documents of an ordinary SDD change.
package check

import (
	"os"
	"path/filepath"
	"regexp"
)

type checkError struct {
	Code, Message, Path string
	Exit                int
}

var changeID = regexp.MustCompile("^[a-z][a-z0-9]*(-[a-z0-9]+)*$")

func unsupported(path, feature string) *checkError {
	return &checkError{Code: "unsupported_input", Message: "This version of sdd check does not support " + feature, Path: path, Exit: 2}
}

// Run returns the public JSON report and the process exit code.
func Run(project, change, stage, workKind string) (map[string]any, int) {
	report := map[string]any{
		"schema_version": 2, "stage": stage, "work_kind": workKind, "change_id": change,
		"errors": []map[string]any{}, "warnings": []map[string]any{},
	}
	for _, key := range []string{"checkpoint_status", "discussion_status", "review_status", "approval_status"} {
		report[key] = map[string]string{"status": "not_checked"}
	}
	failure := func(err *checkError) (map[string]any, int) {
		path := err.Path
		if path == "" {
			path = project
		}
		report["errors"] = append(report["errors"].([]map[string]any), map[string]any{
			"code": err.Code, "path": path, "element_id": nil, "message": err.Message,
		})
		return report, err.Exit
	}
	if workKind != "change" && workKind != "refactoring" {
		return failure(&checkError{Code: "unsupported_work_kind", Message: "Expected change or refactoring", Exit: 1})
	}
	if !changeID.MatchString(change) || len(change) > 64 {
		return failure(&checkError{Code: "invalid_change", Message: "change_id must be lowercase-kebab-case, at most 64 characters", Exit: 1})
	}
	absolute, err := filepath.Abs(project)
	if err != nil {
		return failure(&checkError{Code: "input_unreadable", Message: err.Error(), Exit: 2})
	}
	canonical, err := filepath.EvalSymlinks(absolute)
	if err != nil {
		return failure(&checkError{Code: "input_unreadable", Message: err.Error(), Exit: 2})
	}
	workDir := "changes"
	if workKind == "refactoring" {
		workDir = "refactoring"
	}
	root, pathErr := containedPath(canonical, "sdd/"+workDir+"/"+change)
	if pathErr != nil {
		return failure(pathErr)
	}
	if filepath.Base(root) != change {
		return failure(unsupported(root, "a change directory redirected to a different change ID"))
	}
	structure, documentErr := validateDocuments(canonical, root, stage, workKind)
	if documentErr != nil {
		return failure(documentErr)
	}
	for key, value := range structure {
		report[key] = value
	}
	if err := reviewStatus(canonical, root, change, report); err != nil {
		return failure(err)
	}
	if len(report["errors"].([]map[string]any)) != 0 {
		return report, 1
	}
	return report, 0
}

func fileError(path string, err error) *checkError {
	message := err.Error()
	if os.IsNotExist(err) {
		message = missingFileMessage(path)
	}
	return &checkError{Code: "unreadable_input", Message: message, Path: path, Exit: 2}
}
