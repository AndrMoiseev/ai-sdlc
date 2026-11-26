package apply

import (
	"fmt"
	"sort"
	"time"
)

func now() string {
	current := time.Now().UTC().Truncate(time.Microsecond)
	if current.Nanosecond() != 0 {
		return current.Format("2006-01-02T15:04:05.000000+00:00")
	}
	return current.Format("2006-01-02T15:04:05+00:00")
}

func (e *execution) lookup(index any, id string) (mapping, error) {
	key := digest(id)
	for depth := 0; index != nil; depth++ {
		node, err := e.readObject(index)
		if err != nil {
			return nil, err
		}
		fields := object(node)
		if eventID, exists := fields["event_id"]; exists {
			if str(eventID) != id {
				return nil, nil
			}
			entry, err := e.readObject(fields["entry"])
			return object(entry), err
		}
		if depth >= len(key) || object(fields["children"]) == nil {
			return nil, reject("history_corrupt", "Invalid event index depth")
		}
		index = object(fields["children"])[string(key[depth])]
	}
	return nil, nil
}

func (e *execution) indexEvent(index any, id string, entry any, depth int) (mapping, error) {
	if index == nil {
		return e.put(mapping{"event_id": id, "entry": entry})
	}
	if depth >= 64 {
		return nil, reject("history_corrupt", "Event ID hash collision")
	}
	node, err := e.readObject(index)
	if err != nil {
		return nil, err
	}
	fields := object(node)
	children := object(fields["children"])
	if previous, exists := fields["event_id"]; exists {
		if str(previous) == id {
			return nil, reject("event_conflict", "Event ID already committed")
		}
		children = mapping{string(digest(previous)[depth]): index}
	}
	if children == nil {
		return nil, reject("history_corrupt", "Invalid event index")
	}
	key := string(digest(id)[depth])
	child, err := e.indexEvent(children[key], id, entry, depth+1)
	if err != nil {
		return nil, err
	}
	children[key] = child
	return e.put(mapping{"children": children})
}

func (e *execution) appendEvent(state, event mapping, result any) error {
	entry, err := e.pack(mapping{
		"event_id": event["event_id"], "fingerprint": digest(event), "event": event,
		"revision": state["revision"], "previous": state["event_head"], "result": result, "time": state["updated_at"],
	}, "", true)
	if err != nil {
		return err
	}
	reference, err := e.put(entry)
	if err != nil {
		return err
	}
	index, err := e.indexEvent(state["event_index"], str(event["event_id"]), reference, 0)
	if err != nil {
		return err
	}
	state["event_index"], state["event_head"] = index, reference
	return nil
}

func (e *execution) auditObjects(value any, seen map[string]bool) error {
	if reference, exists := objectReference(value); exists {
		if _, err := e.objectPath(reference); err != nil {
			return err
		}
		hash := str(object(reference)["sha256"])
		if seen[hash] {
			return nil
		}
		seen[hash] = true
		stored, err := e.readObject(reference)
		if err != nil {
			return err
		}
		return e.auditObjects(stored, seen)
	}
	switch value := value.(type) {
	case mapping:
		for _, key := range sortedKeys(value) {
			if err := e.auditObjects(value[key], seen); err != nil {
				return err
			}
		}
	case []any:
		for _, item := range value {
			if err := e.auditObjects(item, seen); err != nil {
				return err
			}
		}
	}
	return nil
}

func (e *execution) audit() (mapping, error) {
	state := e.manifest
	currentObjects := map[string]bool{}
	if err := e.auditObjects(state, currentObjects); err != nil {
		return nil, err
	}
	seen := map[string]bool{}
	ids := map[string]bool{}
	revision := intValue(state["revision"])
	count := revision
	for current := state["event_head"]; current != nil; revision-- {
		raw, err := e.readObject(current)
		if err != nil {
			return nil, err
		}
		entry := object(raw)
		if revision <= 0 || intValue(entry["revision"]) != revision {
			return nil, reject("history_corrupt", "Event chain mismatch")
		}
		id := str(entry["event_id"])
		event, err := e.hydrate(entry["event"], make(map[string]bool))
		if err != nil {
			return nil, err
		}
		if ids[id] || str(object(event)["event_id"]) != id || str(entry["fingerprint"]) != digest(event) {
			return nil, reject("history_corrupt", "Invalid event identity")
		}
		indexed, err := e.lookup(state["event_index"], id)
		if err != nil {
			return nil, err
		}
		if indexed == nil || digest(indexed) != digest(entry) {
			return nil, reject("history_corrupt", "Event index disagrees with chain")
		}
		ids[id] = true
		if err := e.auditObjects(entry, seen); err != nil {
			return nil, err
		}
		current = entry["previous"]
	}
	if revision != 0 {
		return nil, reject("history_corrupt", "History length mismatch")
	}
	indexed := map[string]bool{}
	pending := []any{state["event_index"]}
	for len(pending) > 0 {
		reference := pending[len(pending)-1]
		pending = pending[:len(pending)-1]
		if reference == nil {
			continue
		}
		raw, err := e.readObject(reference)
		if err != nil {
			return nil, err
		}
		node := object(raw)
		if value, exists := node["event_id"]; exists {
			id := str(value)
			if indexed[id] {
				return nil, reject("history_corrupt", "Duplicate index leaf")
			}
			indexed[id] = true
		} else {
			children := object(node["children"])
			if children == nil {
				return nil, reject("history_corrupt", "Invalid event index")
			}
			for _, child := range children {
				pending = append(pending, child)
			}
		}
	}
	if len(indexed) != len(ids) {
		return nil, reject("history_corrupt", "Uncommitted event in index")
	}
	for id := range indexed {
		if !ids[id] {
			return nil, reject("history_corrupt", "Uncommitted event in index")
		}
	}
	return mapping{"revision": state["revision"], "events": count, "current_objects": len(currentObjects), "status": "verified"}, nil
}

func sortedKeys(value mapping) []string {
	keys := make([]string, 0, len(value))
	for key := range value {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	return keys
}

func fieldString(value mapping, key string) (string, error) {
	raw, exists := value[key]
	if !exists {
		return "", missingKey(key)
	}
	text, ok := raw.(string)
	if !ok {
		return "", fmt.Errorf("%s must be a string", key)
	}
	return text, nil
}
