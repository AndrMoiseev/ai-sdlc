package apply

import (
	"errors"
	"os"
	"path/filepath"
)

type effectJournal struct {
	path   string
	record mapping
}

func effectPath(directory string, state, event mapping) (string, error) {
	return contained(directory, filepath.ToSlash(filepath.Join("runs", str(state["run_id"]), "effects", str(event["event_id"])+".json")))
}

func prepareEffect(directory string, state, event mapping, operation string, precondition mapping) (*effectJournal, error) {
	path, err := effectPath(directory, state, event)
	if err != nil {
		return nil, err
	}
	request := mapping{"operation": operation, "task_id": event["task_id"], "event": event, "precondition": precondition}
	if _, err := os.Stat(path); err == nil {
		value, err := readJSON(path)
		if err != nil {
			return nil, err
		}
		record := object(value)
		previous := object(record["request"])
		if previous["operation"] != operation || digest(previous["event"]) != digest(event) {
			return nil, reject("effect_conflict", "An effect ID cannot be reused")
		}
		return &effectJournal{path, record}, nil
	} else if !errors.Is(err, os.ErrNotExist) {
		return nil, err
	}
	record := mapping{"schema_version": 1, "request": request, "fingerprint": digest(request), "phase": "prepared", "result": nil}
	if err := writeJSON(path, record); err != nil {
		return nil, err
	}
	return &effectJournal{path, record}, nil
}

func (j *effectJournal) precondition() mapping {
	return object(object(j.record["request"])["precondition"])
}

func (j *effectJournal) observe(result any) (any, error) {
	j.record["phase"], j.record["result"] = "observed", result
	if err := writeJSON(j.path, j.record); err != nil {
		return nil, err
	}
	return result, nil
}

func pendingEffects(directory string, state mapping, operation string) ([]mapping, error) {
	effects := filepath.Join(directory, "runs", str(state["run_id"]), "effects")
	entries, err := os.ReadDir(effects)
	if errors.Is(err, os.ErrNotExist) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	records := []mapping{}
	for _, entry := range entries {
		if filepath.Ext(entry.Name()) != ".json" {
			continue
		}
		value, err := readJSON(filepath.Join(effects, entry.Name()))
		if err != nil {
			return nil, err
		}
		record := object(value)
		if record["phase"] == "prepared" && object(record["request"])["operation"] == operation {
			records = append(records, record)
		}
	}
	return records, nil
}
