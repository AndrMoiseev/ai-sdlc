package setup

import (
	"encoding/json"
	"errors"
	"fmt"
	"slices"
	"strconv"
)

var steps = []string{
	"common-tools", "jdk", "gradle", "junit5", "jacoco", "archunit",
	"ktlint", "detekt", "typespec", "collection", "mise-tasks", "roles",
}

func progress(args arguments) (object, error) {
	project, err := projectDirectory(args.value("project-root"), "Expected a project directory")
	if err != nil {
		return nil, err
	}
	complete, failed := args.value("complete"), args.value("failed")
	reset, changed := args.values("reset"), args.has("project-changed")
	if changed && complete == "" {
		return nil, errors.New("--project-changed requires a successfully completed step")
	}
	applicable := steps
	if args.has("applicable") {
		applicable = args.values("applicable")
	}
	if complete != "" && !slices.Contains(applicable, complete) {
		return nil, errors.New("Cannot complete a step outside the applicable scope")
	}
	codes := repeated(args, "check-exit-code")
	if complete == "ktlint" || complete == "detekt" {
		if len(codes) == 0 {
			return nil, fmt.Errorf("Provide --check-exit-code for each project %s check", complete)
		}
		for _, code := range codes {
			number, _ := strconv.Atoi(code)
			if number != 0 {
				failed, complete = complete, ""
				break
			}
		}
	} else if len(codes) != 0 {
		return nil, errors.New("--check-exit-code belongs to completion of ktlint or detekt")
	}
	if failed != "" && !slices.Contains(applicable, failed) {
		return nil, errors.New("Failed step outside the applicable scope")
	}
	if slices.Contains(reset, "all") && len(reset) != 1 {
		return nil, errors.New("Use 'all' alone or name known steps")
	}

	completed := []string{}
	readOrWrite := func() error {
		path, _, settings, order, err := settingsFile(project)
		if err != nil {
			return err
		}
		if settings["schema_version"] != json.Number("1") {
			return errors.New("Expected settings schema_version 1")
		}
		setup := object{}
		if value, exists := settings["setup"]; exists {
			setup = asObject(value)
			if setup == nil {
				return errors.New("Expected settings.setup to be an object")
			}
		}
		recorded := []string{}
		if value, exists := setup["completed_steps"]; exists {
			rows, valid := value.([]any)
			if !valid {
				return errors.New("Expected distinct step names in setup.completed_steps")
			}
			for _, row := range rows {
				step := asString(row)
				if step == "" || slices.Contains(recorded, step) {
					return errors.New("Expected distinct step names in setup.completed_steps")
				}
				recorded = append(recorded, step)
			}
		}
		for _, step := range recorded {
			if !slices.Contains(reset, "all") && !slices.Contains(reset, step) {
				completed = append(completed, step)
			}
		}
		if complete != "" && !slices.Contains(completed, complete) {
			completed = append(completed, complete)
		}
		if !slices.Equal(completed, recorded) {
			settings["setup"] = setup
			setup["completed_steps"] = completed
			return replaceFile(path, []byte(jsonText(settings, true, order)+"\n"))
		}
		return nil
	}
	if complete != "" || reset != nil {
		err = withLock(project, "progress", readOrWrite)
	} else {
		err = readOrWrite()
	}
	if err != nil {
		return nil, err
	}
	pending := []string{}
	for _, step := range steps {
		if slices.Contains(applicable, step) && !slices.Contains(completed, step) {
			pending = append(pending, step)
		}
	}
	var next any
	if len(pending) != 0 {
		next = pending[0]
	}
	return object{"completed_steps": completed, "pending_steps": pending, "next_step": next,
		"failed_step": optionalText(failed), "stop": failed != "" || changed || len(pending) == 0}, nil
}
