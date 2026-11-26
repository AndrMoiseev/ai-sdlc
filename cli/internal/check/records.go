package check

import "fmt"

// TaskRecords returns the machine records from a tasks document after schema validation.
func TaskRecords(path, workKind string) ([]map[string]any, error) {
	d, issue := parseDocument(path, "tasks", workKind)
	if issue != nil {
		return nil, fmt.Errorf("%s", issue.message)
	}
	return d.records, nil
}
