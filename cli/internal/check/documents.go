package check

import (
	"io/fs"
	"os"
	"path/filepath"
	"slices"
	"strings"
)

type changeRecord struct {
	path, id, kind string
	fields         map[string]any
}

type documentValidation struct {
	errors     []map[string]any
	warnings   []map[string]any
	project    string
	inputError *checkError
	records    map[string]changeRecord
	order      []string
}

func (validation *documentValidation) issue(code, message, path string, elementID any) {
	validation.errors = append(validation.errors, map[string]any{
		"code": code, "path": path, "element_id": elementID, "message": message,
	})
}

func (validation *documentValidation) problem(record changeRecord, code, message string) {
	validation.issue(code, message, record.path, record.id)
}

func validateDocuments(project, root, stage, workKind string) (map[string]any, *checkError) {
	validation := documentValidation{project: project, errors: []map[string]any{}, warnings: []map[string]any{}, records: make(map[string]changeRecord)}
	paths, err := documentPaths(root, stage, workKind)
	if err != nil {
		return nil, err
	}
	if workKind == "change" && (len(paths) == 2 || (len(paths) == 3 && stage == "plan")) {
		validation.issue("missing_specs", "At least one capability spec is required", filepath.Join(root, "specs"), nil)
	}
	var records []changeRecord
	for _, path := range paths {
		relative, _ := filepath.Rel(root, path)
		resolved, pathError := containedPath(root, filepath.ToSlash(relative))
		if pathError != nil {
			if pathError.Exit == 2 {
				return nil, pathError
			}
			validation.issue(pathError.Code, pathError.Message, path, nil)
			continue
		}
		expectedType := strings.TrimSuffix(filepath.Base(path), ".md")
		document, diagnostic := parseDocument(resolved, expectedType, workKind)
		if diagnostic != nil {
			if diagnostic.unreadable {
				return nil, &checkError{Code: diagnostic.code, Message: diagnostic.message, Path: path, Exit: 2}
			}
			validation.issue(diagnostic.code, diagnostic.message, path, diagnostic.elementID)
			continue
		}
		if document.metadata["change_id"] != filepath.Base(root) {
			validation.issue("document_identity", "Document type/change_id does not match its location", path, nil)
			continue
		}
		if expectedType == "spec" {
			capability, _ := filepath.Rel(filepath.Join(root, "specs"), filepath.Dir(path))
			if document.metadata["capability"] != filepath.ToSlash(capability) {
				validation.issue("capability", "Capability does not match spec directory", path, nil)
				continue
			}
		}
		for _, fields := range document.records {
			records = append(records, changeRecord{path: path, id: fields["id"].(string), kind: fields["sdd_record"].(string), fields: fields})
		}
	}
	for _, record := range records {
		if _, present := validation.records[record.id]; present {
			validation.problem(record, "duplicate_id", "ID occurs in multiple documents: "+record.id)
			if workKind == "refactoring" {
				continue
			}
		} else {
			validation.order = append(validation.order, record.id)
		}
		validation.records[record.id] = record
	}
	if workKind == "refactoring" {
		return validation.refactoring(project, root, stage)
	}
	if err := validation.traceDocuments(); err != nil {
		return nil, err
	}
	result := map[string]any{"warnings": validation.warnings}
	if stage == "plan" {
		result["tasks"], result["progress"] = validation.validatePlan(project, filepath.Join(root, "tasks.md"))
	}
	result["errors"] = validation.errors
	return result, nil
}

func documentPaths(root, stage, workKind string) ([]string, *checkError) {
	paths := []string{filepath.Join(root, "proposal.md"), filepath.Join(root, "design.md")}
	if workKind == "refactoring" {
		if stage == "plan" {
			paths = append(paths, filepath.Join(root, "tasks.md"))
		}
		return paths, nil
	}
	specs, err := containedPath(root, "specs")
	if err != nil {
		return nil, err
	}
	if specs != filepath.Join(root, "specs") {
		return nil, unsupported(specs, "a symbolic link at the specs directory")
	}
	walkError := filepath.WalkDir(specs, func(path string, entry fs.DirEntry, err error) error {
		if path == specs && os.IsNotExist(err) {
			return nil
		}
		if err != nil {
			return err
		}
		if entry.Name() == "spec.md" {
			paths = append(paths, path)
		}
		return nil
	})
	if walkError != nil {
		return nil, fileError(specs, walkError)
	}
	if stage == "plan" {
		paths = append(paths, filepath.Join(root, "tasks.md"))
	}
	return paths, nil
}

func (validation *documentValidation) traceDocuments() *checkError {
	children := make(map[string]bool)
	for _, id := range validation.order {
		record := validation.records[id]
		switch record.kind {
		case "acceptance":
			requirement, _ := record.fields["requirement"].(string)
			if validation.records[requirement].kind != "requirement" {
				validation.problem(record, "acceptance_requirement", "Acceptance requires one local requirement: "+documentValue(record.fields["requirement"]))
			} else {
				children[requirement] = true
			}
			for _, field := range []string{"conditions", "expected"} {
				if !nonemptyText(record.fields[field]) {
					validation.problem(record, "acceptance_text", field+" must be nonempty text")
				}
			}
		case "decision":
			validation.references(record, "requirements", "REQ", true)
			if validation.inputError != nil {
				return validation.inputError
			}
		case "requirement":
			operation, _ := record.fields["operation"].(string)
			if !slices.Contains([]string{"add", "modify", "remove"}, operation) {
				validation.problem(record, "operation", "operation must be add, modify or remove")
			}
			if source, present := record.fields["source"]; present || operation == "modify" || operation == "remove" {
				if _, mapping := source.(map[string]any); !mapping {
					validation.problem(record, "source", "modify/remove requires source")
				} else {
					if e := validation.refSource(validation.project, record); e != nil {
						return e
					}
				}
			}
		}
	}
	for _, id := range validation.order {
		record := validation.records[id]
		if record.kind == "requirement" && !children[id] {
			validation.problem(record, "requirement_without_acceptance", "Requirement must have at least one acceptance criterion")
		}
	}
	return nil
}

func stringList(value any) ([]string, bool) {
	items, ok := value.([]any)
	if !ok {
		return nil, false
	}
	result := make([]string, 0, len(items))
	for _, item := range items {
		text, ok := item.(string)
		if !ok {
			return nil, false
		}
		result = append(result, text)
	}
	return result, true
}

func (validation *documentValidation) references(record changeRecord, field, prefix string, nonempty bool) []string {
	values, ok := stringList(record.fields[field])
	if !ok || (nonempty && len(values) == 0) {
		description := "list of IDs"
		if nonempty {
			description = "nonempty " + description
		}
		validation.problem(record, "reference_list", field+" must be a "+description)
		return nil
	}
	seen := make(map[string]bool, len(values))
	for _, value := range values {
		if seen[value] {
			validation.problem(record, "duplicate_reference", "Duplicate links in "+field)
			break
		}
		seen[value] = true
	}
	var valid []string
	for _, value := range values {
		if strings.Contains(value, "/") {
			if field == "requirements" {
				validation.externalReference(record, value, prefix)
				if validation.inputError != nil {
					return nil
				}
			} else {
				validation.problem(record, "external_reference", field+" requires local "+prefix+" IDs: "+value)
			}
		} else if !validDocumentID(value, prefix) || validation.records[value].id == "" {
			validation.problem(record, "missing_reference", field+": unresolved "+prefix+" reference "+value)
		} else {
			valid = append(valid, value)
		}
	}
	return valid
}

func (v *documentValidation) externalReference(record changeRecord, value, prefix string) {
	other, remote, _ := strings.Cut(value, "/")
	if !validDocumentSlug(other) {
		v.problem(record, "invalid_change", "change_id must be lowercase-kebab-case, at most 64 characters")
		return
	}
	root, e := containedPath(v.project, "sdd/changes/"+other)
	if e != nil {
		v.problem(record, e.Code, e.Message)
		return
	}
	if !validDocumentID(remote, prefix) {
		v.problem(record, "invalid_reference", "Invalid external reference: "+value)
		return
	}
	paths, e := documentPaths(root, "documents", "change")
	if e != nil {
		v.inputError = e
		return
	}
	for _, p := range paths[2:] {
		rel, _ := filepath.Rel(root, p)
		resolved, e := containedPath(root, filepath.ToSlash(rel))
		if e != nil {
			v.problem(record, e.Code, e.Message)
			return
		}
		doc, d := parseDocument(resolved, "spec", "change")
		if d != nil {
			if d.unreadable {
				v.inputError = &checkError{Code: d.code, Message: d.message, Path: resolved, Exit: 2}
			} else {
				v.problem(record, d.code, d.message)
			}
			return
		}
		for _, r := range doc.records {
			if r["id"] == remote {
				v.warnings = append(v.warnings, issueAt(record.path, "external_context", "External context does not satisfy local traceability: "+value, record.id))
				return
			}
		}
	}
	v.problem(record, "missing_reference", "Unresolved external reference: "+value)
}
