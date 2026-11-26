package setup

import (
	"errors"
	"fmt"
	"os"
)

func applyCommand(args arguments) (object, error) {
	value, err := readJSON(args.value("plan"))
	if err != nil {
		return nil, err
	}
	plan := asObject(value)
	request := asObject(plan["request"])
	if request == nil {
		return nil, errors.New("Provide the plan result, not the CLI envelope")
	}
	verified, err := makePlan(request)
	if err != nil {
		return nil, err
	}
	if !equal(verified, plan) {
		return nil, errors.New("Plan changed or was edited; regenerate the plan")
	}
	project := asString(asObject(request["inspection"])["project_root"])
	operations := verified["operations"].([]object)
	changed := []string{}
	if len(operations) != 0 {
		err := withLock(project, asString(plan["plan_id"]), func() error {
			return applyOperations(project, verified, replaceFile)
		})
		if err != nil {
			return nil, err
		}
		for _, operation := range operations {
			changed = append(changed, asString(operation["path"]))
		}
	}
	return object{"changed": changed, "plan_id": plan["plan_id"], "warnings": plan["warnings"]}, nil
}

func applyOperations(project string, plan object, replace func(string, []byte) error) error {
	type write struct {
		path   string
		before []byte
		hash   string
	}
	completed := []write{}
	apply := func() error {
		current, err := makePlan(asObject(plan["request"]))
		if err != nil {
			return err
		}
		if !equal(current, plan) {
			return errors.New("Inputs changed while acquiring setup lock")
		}
		for _, operation := range plan["operations"].([]object) {
			path, err := safeTarget(project, asString(operation["path"]))
			if err != nil {
				return err
			}
			before, err := optionalBytes(path)
			if err != nil {
				return err
			}
			var hash any
			if before != nil {
				hash = digest(before)
			}
			if hash != operation["before_sha256"] {
				return fmt.Errorf("File changed before write: %s", path)
			}
			if err := replace(path, []byte(asString(operation["after"]))); err != nil {
				return err
			}
			completed = append(completed, write{path, before, asString(operation["after_sha256"])})
		}
		for _, entry := range completed {
			raw, err := os.ReadFile(entry.path)
			if err != nil {
				return fileError(err)
			}
			if digest(raw) != entry.hash {
				return fmt.Errorf("Post-write check failed: %s", entry.path)
			}
		}
		return nil
	}
	cause := apply()
	if cause == nil {
		return nil
	}
	conflicts := []string{}
	for i := len(completed) - 1; i >= 0; i-- {
		entry := completed[i]
		current, err := os.ReadFile(entry.path)
		if err == nil && digest(current) == entry.hash {
			if entry.before == nil {
				err = os.Remove(entry.path)
			} else {
				err = replace(entry.path, entry.before)
			}
			if err == nil {
				continue
			}
		}
		conflicts = append(conflicts, entry.path)
	}
	if len(conflicts) > 0 {
		return fmt.Errorf("%s; rollback needs manual reconciliation: %s", cause, pythonList(conflicts))
	}
	return fmt.Errorf("%s; completed file writes rolled back", cause)
}
