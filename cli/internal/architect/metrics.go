package architect

import (
	"fmt"
	"io"
)

func runMetrics(command string, args options, stdin io.Reader, stdout io.Writer) error {
	switch command {
	case "policy":
		return policyCommand(args, stdout)
	case "collection-settings":
		root, err := resolve(args.get("repository"))
		if err != nil {
			return err
		}
		value, err := projectCollection(root)
		if err != nil {
			return err
		}
		return printJSON(stdout, value, false)
	case "configure":
		return configure(args, stdin, stdout)
	case "collect":
		return collectCommand(args, stdout)
	case "evidence":
		return evidenceCommand(args, stdout)
	case "rank":
		return rankCommand(args, stdout)
	case "status":
		return statusCommand(args, stdout)
	default:
		return fmt.Errorf("Unknown metrics command: %s", command)
	}
}

func saveMetricJSON(path, repository string, value any) error {
	output, err := reportOutput(path, repository, false)
	if err != nil {
		return err
	}
	if exists(output) {
		return fmt.Errorf("Output already exists: %s; choose a new name", output)
	}
	data, err := encodeJSON(value, true)
	if err != nil {
		return err
	}
	return writeText(output, data, true, true)
}
