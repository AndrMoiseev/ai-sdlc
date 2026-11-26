package architect

import (
	"fmt"
	"io"
	"runtime"
	"strings"
)

type option struct {
	name     string
	count    int // zero is a switch, negative means one or more values
	required bool
}

var metricsOptions = map[string][]option{
	"policy":              {{"repository", 1, false}, {"defaults", 0, false}, {"collection", 1, false}, {"get", 1, false}, {"output", 1, false}},
	"collection-settings": {{"repository", 1, true}},
	"configure":           {{"repository", 1, true}, {"input", 1, false}, {"output", 1, true}},
	"collect":             {{"repository", 1, true}, {"config", 1, true}, {"output", 1, true}, {"fresh", 0, false}, {"focused", 0, false}},
	"evidence":            {{"repository", 1, true}, {"collection", 1, true}, {"output", 1, true}, {"group", 1, false}, {"files", -1, false}, {"co-change", 2, false}, {"dependencies", -1, false}},
	"status":              {{"repository", 1, true}, {"collection", 1, true}},
	"rank":                {{"repository", 1, true}, {"collection", 1, true}, {"recommendations", 1, true}, {"output", 1, true}, {"markdown", 1, false}},
}

type options map[string][]string

func (o options) get(name string) string {
	if len(o[name]) > 0 {
		return o[name][0]
	}
	return ""
}

func (o options) has(name string) bool {
	_, ok := o[name]
	return ok
}

func parseOptions(args []string, schema []option) (options, error) {
	parsed := options{}
	for len(args) > 0 {
		argument, rest := args[0], args[1:]
		flag, explicitValue, inline := strings.Cut(argument, "=")
		if !strings.HasPrefix(flag, "--") {
			return nil, fmt.Errorf("unrecognized arguments: %s", argument)
		}
		found := false
		for _, spec := range schema {
			if flag != "--"+spec.name {
				continue
			}
			found = true
			values := []string{}
			if inline {
				if spec.count == 0 {
					return nil, fmt.Errorf("argument %s: ignored explicit argument %q", flag, explicitValue)
				}
				values = append(values, explicitValue)
			} else {
				for len(rest) > 0 && !strings.HasPrefix(rest[0], "--") && (spec.count < 0 || len(values) < spec.count) {
					values, rest = append(values, rest[0]), rest[1:]
				}
			}
			if spec.count < 0 && len(values) == 0 {
				return nil, fmt.Errorf("argument %s: expected at least one argument", flag)
			}
			if spec.count >= 0 && len(values) != spec.count {
				if spec.count == 1 {
					return nil, fmt.Errorf("argument %s: expected one argument", flag)
				}
				return nil, fmt.Errorf("argument %s: expected %d arguments", flag, spec.count)
			}
			parsed[spec.name] = values
			break
		}
		if !found {
			return nil, fmt.Errorf("unrecognized arguments: %s", argument)
		}
		args = rest
	}
	var missing []string
	for _, spec := range schema {
		if spec.required && !parsed.has(spec.name) {
			missing = append(missing, "--"+spec.name)
		}
	}
	if len(missing) > 0 {
		return nil, fmt.Errorf("the following arguments are required: %s", strings.Join(missing, ", "))
	}
	return parsed, nil
}

// Run dispatches the two script families under sdd architect.
func Run(args []string, stdin io.Reader, stdout, stderr io.Writer) int {
	family, command := "", ""
	if len(args) > 0 {
		family = args[0]
	}
	if len(args) > 1 {
		command = args[1]
	}
	if family != "metrics" && family != "audit-state" {
		printDiagnostic(stderr, "usage: sdd architect {metrics,audit-state} ...")
		return 2
	}
	schema := metricsOptions[command]
	commands := "{policy,collection-settings,configure,collect,evidence,status,rank}"
	if family == "audit-state" {
		commands = "{read,check,write}"
		schema = nil
		if command == "read" || command == "check" || command == "write" {
			schema = []option{{"report-dir", 1, true}, {"input", 1, false}}
		}
	}
	usage := "usage: sdd architect " + family + " " + commands + " ..."
	if schema != nil {
		usage = "usage: sdd architect " + family + " " + command + " [-h]"
		for _, spec := range schema {
			flag := "--" + spec.name
			if spec.count != 0 {
				flag += " " + strings.ToUpper(strings.ReplaceAll(spec.name, "-", "_"))
			}
			if !spec.required {
				flag = "[" + flag + "]"
			}
			usage += " " + flag
		}
	}
	if command == "-h" || command == "--help" || (len(args) > 2 && (args[2] == "-h" || args[2] == "--help")) {
		fmt.Fprintln(stdout, usage)
		return 0
	}
	var err error
	var parsed options
	if schema == nil {
		if command == "" {
			err = fmt.Errorf("the following arguments are required: command")
		} else {
			err = fmt.Errorf("argument command: invalid choice: %s", quoted(command))
		}
	} else {
		parsed, err = parseOptions(args[2:], schema)
	}
	if err == nil && family == "metrics" {
		if command == "policy" && parsed.has("defaults") && parsed.has("collection") {
			err = fmt.Errorf("argument --collection: not allowed with argument --defaults")
		}
		if command == "evidence" {
			var selected string
			for _, query := range []string{"group", "files", "co-change", "dependencies"} {
				if parsed.has(query) {
					if selected != "" {
						err = fmt.Errorf("argument --%s: not allowed with argument --%s", query, selected)
						break
					}
					selected = query
				}
			}
			if selected == "" {
				err = fmt.Errorf("one of the arguments --group --files --co-change --dependencies is required")
			}
		}
	}
	if err != nil {
		printDiagnostic(stderr, usage)
		printDiagnostic(stderr, fmt.Sprintf("sdd architect %s: error: %s", family, err))
		return 2
	}
	if family == "audit-state" {
		var code int
		code, err = runAuditState(command, parsed, stdin, stdout)
		if err != nil {
			printDiagnostic(stderr, "Audit state error: "+err.Error())
			return 1
		}
		return code
	}
	if err := runMetrics(command, parsed, stdin, stdout); err != nil {
		printDiagnostic(stderr, "sdd-architect: "+err.Error())
		return 2
	}
	return 0
}

func printDiagnostic(writer io.Writer, diagnostic string) {
	text := diagnostic + "\n"
	if runtime.GOOS == "windows" {
		text = strings.ReplaceAll(text, "\n", "\r\n")
	}
	fmt.Fprint(writer, text)
}
