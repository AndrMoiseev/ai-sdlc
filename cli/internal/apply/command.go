// Package apply implements the deterministic execution API of sdd.
package apply

import (
	"bytes"
	_ "embed"
	"fmt"
	"io"
	"os"
	"strings"
)

//go:embed help.json
var helpCatalogue []byte

const usage = "Usage: sdd apply (--request FILE | --help-operation [NAME] | --help-event TYPE)"

func Run(args []string, _ io.Reader, stdout, stderr io.Writer) int {
	if len(args) == 1 && (args[0] == "--help" || args[0] == "-h") {
		fmt.Fprintln(stdout, usage)
		return 0
	}
	request, err, valid := parseRequest(args)
	if !valid {
		fmt.Fprintln(stderr, usage)
		return 2
	}
	var result any
	if err == nil {
		result, err = dispatch(request, stdout)
	}
	reply := mapping{"ok": true, "result": result}
	exitCode, indent := 0, "  "
	if err != nil {
		code := "invalid_request"
		if refused, ok := err.(rejection); ok {
			code = refused.code
		}
		reply = mapping{"ok": false, "code": code, "message": err.Error()}
		exitCode, indent = 1, ""
	}
	raw, err := jsonBytes(reply, indent)
	if err == nil {
		_, err = stdout.Write(append(raw, '\n'))
	}
	if err != nil {
		fmt.Fprintln(stderr, err)
		return 2
	}
	return exitCode
}

func parseRequest(args []string) (mapping, error, bool) {
	if len(args) < 1 || len(args) > 2 {
		return nil, nil, false
	}
	selector, value, hasValue := strings.Cut(args[0], "=")
	if len(args) == 2 {
		if hasValue || strings.HasPrefix(args[1], "--") {
			return nil, nil, false
		}
		value, hasValue = args[1], true
	}
	parameters := mapping{}
	switch selector {
	case "--request":
		if !hasValue {
			return nil, nil, false
		}
		raw, err := os.ReadFile(value)
		if err != nil {
			return nil, fileError(err, value), true
		}
		parsed, err := decode(bytes.TrimPrefix(raw, []byte{0xef, 0xbb, 0xbf}))
		if err == nil && object(parsed) == nil {
			err = fmt.Errorf("Expected a JSON operation request object")
		}
		return object(parsed), err, true
	case "--help-operation":
		if value != "" {
			parameters["operation"] = value
		}
	case "--help-event":
		if !hasValue {
			return nil, nil, false
		}
		parameters["event"] = value
	default:
		return nil, nil, false
	}
	return mapping{"operation": "help", "args": parameters}, nil, true
}

func describe(args mapping) (any, error) {
	if args["operation"] != nil && args["event"] != nil {
		return nil, reject("help_selector", "Select one operation or event")
	}
	value, err := decode(helpCatalogue)
	if err != nil {
		return nil, err
	}
	catalogue := object(value)
	for _, selector := range []string{"operation", "event"} {
		if args[selector] == nil {
			continue
		}
		name := str(args[selector])
		result, exists := object(catalogue[selector+"s"])[name]
		if !exists {
			return nil, reject("help_unknown", "Unknown "+selector+": "+pythonText(args[selector]))
		}
		return result, nil
	}
	return catalogue["index"], nil
}

func dispatch(request mapping, stdout io.Writer) (any, error) {
	operation, exists := request["operation"]
	if !exists {
		return nil, missingKey("operation")
	}
	name := str(operation)
	args := mapping{}
	if raw, exists := request["args"]; exists {
		args = object(raw)
		if args == nil {
			return nil, fmt.Errorf("Operation arguments must be an object")
		}
	}
	if err := validateOperationArguments(name, args); err != nil {
		return nil, err
	}
	switch name {
	case "help":
		return describe(args)
	case "validate":
		return validate(args)
	case "initialize":
		return initialize(args)
	case "read", "audit", "read_object", "resolve_agent", "available", "event", "dashboard", "recover_lock", "serve", "stop_server":
	default:
		return nil, fmt.Errorf("Unsupported operation: %s", pythonText(operation))
	}
	directory, err := fieldString(args, "directory")
	if err != nil {
		return nil, err
	}
	switch name {
	case "event":
		return applyEventAndRender(directory, args["event"])
	case "recover_lock":
		return recoverLock(directory)
	case "serve":
		port := 0
		if raw, exists := args["port"]; exists {
			var ok bool
			port, ok = integer(raw)
			if !ok || port < 0 || port > 65535 {
				return nil, fmt.Errorf("Expected an integer port between 0 and 65535")
			}
		}
		return serve(directory, port, stdout)
	case "stop_server":
		return stopServer(directory)
	}
	view := "compact"
	if value, exists := args["view"]; exists {
		view = str(value)
	}
	if name == "read" && view != "compact" && view != "full" {
		return nil, reject("read_view", "Expected full or compact")
	}
	e, err := openExecution(directory)
	if err != nil {
		return nil, err
	}
	switch name {
	case "read":
		if view == "full" {
			return e.manifest, nil
		}
		return e.compact()
	case "audit":
		return e.audit()
	case "read_object":
		if _, err := e.compact(); err != nil {
			return nil, err
		}
		return e.readObject(args["reference"])
	case "available":
		state, err := e.schedulerState()
		if err != nil {
			return nil, err
		}
		return available(state), nil
	case "dashboard":
		return e.render()
	case "resolve_agent":
		return e.resolveAgent(args)
	}
	panic("unreachable operation")
}

type operationArguments struct {
	function           string
	required, optional string
}

var argumentsByOperation = map[string]operationArguments{
	"help":         {"describe", "", "operation event"},
	"validate":     {"validate", "project_root", "change instruction work_kind"},
	"initialize":   {"validate", "project_root", "change instruction work_kind isolation"},
	"read":         {"inspect", "directory", "view"},
	"audit":        {"audit", "directory", ""},
	"read_object":  {"read_object", "directory reference", ""},
	"event":        {"apply", "directory event", ""},
	"dashboard":    {"render", "directory", ""},
	"recover_lock": {"recover_lock", "directory", ""},
	"serve":        {"serve", "directory", "port"},
	"stop_server":  {"stop", "directory", ""},
}

func validateOperationArguments(operation string, args mapping) error {
	spec, exists := argumentsByOperation[operation]
	if !exists {
		return nil
	}
	required := strings.Fields(spec.required)
	allowed := append(strings.Fields(spec.optional), required...)
	for _, key := range sortedKeys(args) {
		if !includes(allowed, key) {
			return fmt.Errorf("%s() got an unexpected keyword argument %s", spec.function, pythonQuote(key))
		}
	}
	missing := []string{}
	for _, key := range required {
		if _, exists := args[key]; !exists {
			missing = append(missing, pythonQuote(key))
		}
	}
	switch len(missing) {
	case 1:
		return fmt.Errorf("%s() missing 1 required positional argument: %s", spec.function, missing[0])
	case 2:
		return fmt.Errorf("%s() missing 2 required positional arguments: %s and %s", spec.function, missing[0], missing[1])
	}
	return nil
}

func pythonText(value any) string {
	if text, ok := value.(string); ok {
		return text
	}
	return pythonRepr(value)
}

func pythonRepr(value any) string {
	return pythonRecord(value, "")
}

func pythonRecord(value any, field string) string {
	switch value := value.(type) {
	case string:
		return pythonQuote(value)
	case nil:
		return "None"
	case bool:
		if value {
			return "True"
		}
		return "False"
	case mapping:
		items := []string{}
		for _, key := range projectionKeys(value, field) {
			items = append(items, pythonQuote(key)+": "+pythonRecord(value[key], key))
		}
		return "{" + strings.Join(items, ", ") + "}"
	case []any:
		items := []string{}
		for _, item := range value {
			items = append(items, pythonRecord(item, field))
		}
		return "[" + strings.Join(items, ", ") + "]"
	default:
		return fmt.Sprint(value)
	}
}
