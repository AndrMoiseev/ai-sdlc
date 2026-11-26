package apply

import (
	"bytes"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"runtime"
	"strings"
)

var objectHash = regexp.MustCompile(`^[0-9a-f]{64}$`)
var workID = regexp.MustCompile(`^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$`)

type execution struct {
	directory string
	manifest  mapping
}

// Resolve paths through the nearest existing ancestor so new files cannot
// escape through a symlink in any existing segment of the requested path.
func resolvePath(path string) (string, error) {
	full, err := filepath.Abs(path)
	if err != nil {
		return "", err
	}
	ancestor := full
	for {
		resolved, err := filepath.EvalSymlinks(ancestor)
		if err == nil {
			relative, err := filepath.Rel(ancestor, full)
			if err != nil {
				return "", err
			}
			return filepath.Join(resolved, relative), nil
		}
		if _, statErr := os.Lstat(ancestor); statErr == nil {
			return "", err
		}
		if !errors.Is(err, os.ErrNotExist) {
			return "", err
		}
		parent := filepath.Dir(ancestor)
		if parent == ancestor {
			return "", err
		}
		ancestor = parent
	}
}

func contained(root, name string) (string, error) {
	directory, err := resolvePath(root)
	if err != nil {
		return "", err
	}
	target := name
	if !filepath.IsAbs(target) {
		target = filepath.Join(directory, name)
	}
	path, err := resolvePath(target)
	if err != nil {
		return "", err
	}
	relative, err := filepath.Rel(directory, path)
	if err != nil || relative == "." || relative == ".." || strings.HasPrefix(relative, ".."+string(filepath.Separator)) {
		return "", reject("path_escape", name)
	}
	for _, component := range strings.Split(filepath.ToSlash(relative), "/") {
		if strings.EqualFold(component, ".git") {
			return "", reject("git_path", name)
		}
	}
	return path, nil
}

func samePath(left, right string) bool {
	if runtime.GOOS == "windows" {
		return strings.EqualFold(left, right)
	}
	return left == right
}

func workKind(value mapping) string {
	if kind, exists := value["work_kind"]; exists {
		return str(kind)
	}
	return "change"
}

func executionPath(basis mapping) (string, error) {
	kind := workKind(basis)
	root := "changes"
	switch kind {
	case "change":
	case "refactoring":
		root = "refactoring"
	default:
		return "", reject("state_root", "Unsupported work kind")
	}
	change := str(basis["change_id"])
	if !workID.MatchString(change) || len(change) > 64 {
		return "", reject("state_root", "Invalid work identity")
	}
	directory, err := contained(str(basis["project_root"]), filepath.Join("sdd", root, change, "execution"))
	if err != nil {
		return "", err
	}
	changeRoot, err := resolvePath(str(basis["change_root"]))
	if err != nil {
		return "", err
	}
	if !samePath(filepath.Dir(directory), changeRoot) {
		return "", reject("state_root", "State is outside its registered execution root")
	}
	return directory, nil
}

func openExecution(directory string) (*execution, error) {
	value, err := readJSON(filepath.Join(directory, "state.json"))
	if err != nil {
		return nil, err
	}
	manifest := object(value)
	if intValue(manifest["schema_version"]) != 3 {
		return nil, reject("state_version", "Expected execution state schema 3; preserve legacy execution and explicitly reconcile its approved plan before migration")
	}
	actual := manifest["integrity"]
	delete(manifest, "integrity")
	expected := digest(manifest)
	manifest["integrity"] = actual
	if str(actual) != expected {
		return nil, reject("state_corrupt", "State integrity mismatch")
	}
	opened := &execution{directory: directory, manifest: manifest}
	basis, err := opened.openReference(manifest["basis"])
	if err != nil {
		return nil, err
	}
	if str(manifest["change_id"]) != str(object(basis)["change_id"]) || workKind(manifest) != workKind(object(basis)) {
		return nil, reject("state_root", "State work identity differs from its basis")
	}
	expectedDirectory, err := executionPath(object(basis))
	if err != nil {
		return nil, err
	}
	actualDirectory, err := resolvePath(directory)
	if err != nil {
		return nil, err
	}
	if !samePath(actualDirectory, expectedDirectory) {
		return nil, reject("state_root", "State is outside its registered execution root")
	}
	revision, ok := integer(manifest["revision"])
	if !ok || revision < 0 {
		return nil, reject("history_corrupt", "Invalid revision")
	}
	if revision != 0 {
		head, err := opened.readObject(manifest["event_head"])
		if err != nil {
			return nil, err
		}
		if intValue(object(head)["revision"]) != revision || manifest["event_index"] == nil {
			return nil, reject("history_corrupt", "History head mismatch")
		}
	} else if manifest["event_head"] != nil || manifest["event_index"] != nil {
		return nil, reject("history_corrupt", "Unexpected history")
	}
	switch str(manifest["status"]) {
	case "active", "blocked", "completed":
	default:
		return nil, reject("state_schema", "Unknown execution status")
	}
	mode, modeSet := manifest["mode"]
	if modeSet && str(mode) != "parallel" || truth(manifest["pending_mode"]) {
		return nil, reject("unsupported_execution_mode", "Only parallel execution is supported; preserve this state and use its original skill version to reconcile it")
	}
	tasks, err := opened.openReference(manifest["tasks"])
	if err != nil {
		return nil, err
	}
	for _, value := range object(tasks) {
		task, err := opened.openReference(value)
		if err != nil {
			return nil, err
		}
		switch str(object(task)["status"]) {
		case "pending", "running", "verifying", "reviewing", "integrating", "repairing", "committing", "blocked", "accepted":
		default:
			return nil, reject("state_schema", "Unknown task state")
		}
	}
	return opened, nil
}

func (e *execution) objectPath(reference any) (string, error) {
	ref := object(reference)
	hash, size := str(ref["sha256"]), ref["bytes"]
	length, isInt := integer(size)
	kind := str(ref["kind"])
	if len(ref) != 4 || !objectHash.MatchString(hash) || !isInt || length < 0 ||
		(kind != "object" && kind != "array" && kind != "string") ||
		str(ref["path"]) != "objects/"+hash[:2]+"/"+hash+".json" {
		return "", reject("object_reference", "Invalid execution object reference")
	}
	return contained(e.directory, str(ref["path"]))
}

func (e *execution) readObject(reference any) (any, error) {
	path, err := e.objectPath(reference)
	if err != nil {
		return nil, err
	}
	ref := object(reference)
	raw, err := os.ReadFile(path)
	if errors.Is(err, os.ErrNotExist) {
		return nil, reject("object_missing", "Execution object is missing: "+str(ref["path"]))
	}
	if err != nil {
		return nil, fileError(err, path)
	}
	if len(raw) != intValue(ref["bytes"]) || digest(raw) != str(ref["sha256"]) {
		return nil, reject("object_corrupt", str(ref["path"]))
	}
	value, err := decode(raw)
	if err != nil {
		return nil, err
	}
	kind := ""
	switch value.(type) {
	case mapping:
		kind = "object"
	case []any:
		kind = "array"
	case string:
		kind = "string"
	}
	if kind != str(ref["kind"]) {
		return nil, reject("object_corrupt", "Object type mismatch")
	}
	return value, nil
}

func objectReference(value any) (any, bool) {
	fields := object(value)
	reference, exists := fields["$object"]
	return reference, len(fields) == 1 && exists
}

func (e *execution) openReference(value any) (any, error) {
	if ref, exists := objectReference(value); exists {
		return e.readObject(ref)
	}
	return value, nil
}

func (e *execution) hydrate(value any, seen map[string]bool) (any, error) {
	if reference, exists := objectReference(value); exists {
		hash := str(object(reference)["sha256"])
		if seen[hash] {
			return nil, reject("object_corrupt", "Cyclic execution object reference")
		}
		resolved, err := e.readObject(reference)
		if err != nil {
			return nil, err
		}
		seen[hash] = true
		value, err = e.hydrate(resolved, seen)
		delete(seen, hash)
		return value, err
	}
	switch value := value.(type) {
	case mapping:
		resolved := make(mapping, len(value))
		for key, item := range value {
			field, err := e.hydrate(item, seen)
			if err != nil {
				return nil, err
			}
			resolved[key] = field
		}
		return resolved, nil
	case []any:
		resolved := make([]any, len(value))
		for index, item := range value {
			element, err := e.hydrate(item, seen)
			if err != nil {
				return nil, err
			}
			resolved[index] = element
		}
		return resolved, nil
	default:
		return value, nil
	}
}

func (e *execution) readState() (mapping, error) {
	value, err := e.hydrate(e.manifest, make(map[string]bool))
	return object(value), err
}

func (e *execution) put(value any) (mapping, error) {
	raw, err := canonical(value)
	if err != nil {
		return nil, err
	}
	hash := digest(raw)
	kind := "string"
	switch value.(type) {
	case mapping:
		kind = "object"
	case []any:
		kind = "array"
	}
	reference := mapping{"path": "objects/" + hash[:2] + "/" + hash + ".json", "bytes": len(raw), "sha256": hash, "kind": kind}
	path, err := e.objectPath(reference)
	if err != nil {
		return nil, err
	}
	existing, err := os.ReadFile(path)
	switch {
	case errors.Is(err, os.ErrNotExist):
		err = atomicWrite(path, raw)
	case err == nil && !bytes.Equal(existing, raw):
		err = reject("object_corrupt", str(reference["path"]))
	}
	return reference, err
}

var externalFields = map[string]bool{
	"prior_result": true, "baseline": true, "start_snapshot": true, "freeze_base": true,
	"snapshot": true, "working_patch": true, "index_patch": true, "evidence": true, "reviews": true,
	"commits": true, "repair_cycles": true, "budget_decisions": true, "worktree_history": true,
	"check_registry": true, "roles": true, "verification_results": true, "scope_history": true, "reused_reviews": true,
}

func (e *execution) pack(value any, field string, root bool) (any, error) {
	if reference, exists := objectReference(value); exists {
		_, err := e.objectPath(reference)
		return value, err
	}
	switch data := value.(type) {
	case mapping:
		packed := make(mapping, len(data))
		for key, item := range data {
			var err error
			packed[key], err = e.pack(item, key, false)
			if err != nil {
				return nil, err
			}
		}
		value = packed
	case []any:
		packed := make([]any, len(data))
		for index, item := range data {
			var err error
			packed[index], err = e.pack(item, "", false)
			if err != nil {
				return nil, err
			}
		}
		value = packed
	case string:
	default:
		return value, nil
	}
	control := field == "basis" || field == "tasks" || strings.HasPrefix(field, "TASK-")
	source := field == "source" && object(value)["files"] != nil && object(value)["digest"] != nil
	if !root && !control && truth(value) {
		raw, err := canonical(value)
		if err != nil {
			return nil, err
		}
		if externalFields[field] || source || len(raw) > 4096 {
			ref, err := e.put(value)
			return mapping{"$object": ref}, err
		}
	}
	return value, nil
}

func (e *execution) save(state mapping) error {
	value, err := e.pack(state, "", true)
	if err != nil {
		return err
	}
	manifest := object(value)
	delete(manifest, "integrity")
	manifest["integrity"] = digest(manifest)
	return writeJSON(filepath.Join(e.directory, "state.json"), manifest)
}

func missingKey(key string) error { return fmt.Errorf("%s", pythonQuote(key)) }
