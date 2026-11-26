// Package setup implements project requirements checks and verified settings changes.
package setup

import (
	"fmt"
	"io"
	"slices"
	"strconv"
	"strings"
)

const help = `usage: sdd setup [-h]
                 {progress,audit,jvm-step,typespec,detekt,collection,inspect,plan,apply}
                 ...

Audit project requirements; inspect, plan and apply SDD role settings. JSON in;
JSON out.

positional arguments:
  {progress,audit,jvm-step,typespec,detekt,collection,inspect,plan,apply}
    progress            Read, reset, or record successfully verified setup
                        steps
    audit               Read-only project requirements audit
    jvm-step            Check one JVM setup step without repeating a full
                        project audit
    typespec            Inspect local TypeSpec after mise tool setup
    detekt              Compare recommended settings for one detekt task
    collection          Verify and save the project audit command

options:
  -h, --help            show this help message and exit
`

type arguments map[string][][]string

func (args arguments) has(name string) bool { return len(args[name]) != 0 }
func (args arguments) values(name string) []string {
	if len(args[name]) > 0 {
		return args[name][len(args[name])-1]
	}
	return nil
}
func (args arguments) value(name string) string {
	if values := args.values(name); len(values) > 0 {
		return values[0]
	}
	return ""
}

// Optional and variadic flags use negative arities. Repeated flags retain the
// individual occurrences so that observations keep their original grouping.
const (
	optional = -1
	all      = -2
	onePlus  = -3
)

type command struct {
	options        map[string]int
	required       []string
	exclusive      [][]string
	requiredGroups [][]string
	run            func(arguments) (object, error)
}

var commands = map[string]command{
	"progress": {
		options:  map[string]int{"project-root": 1, "applicable": all, "reset": onePlus, "complete": 1, "failed": 1, "project-changed": 0, "check-exit-code": 1},
		required: []string{"project-root"}, exclusive: [][]string{{"reset", "complete", "failed"}}, run: progress,
	},
	"audit": {
		options:  map[string]int{"project-root": 1, "build-root": 1, "jvm": optional, "no-jvm": 0, "junit": 2, "archunit": 2, "ktlint": 3, "no-ktlint": 0, "detekt": 3, "no-detekt": 0, "jacoco-module": 1, "jacoco": 3, "output": 1},
		required: []string{"project-root"}, requiredGroups: [][]string{{"jvm", "no-jvm"}, {"ktlint", "no-ktlint"}, {"detekt", "no-detekt"}}, run: audit,
	},
	"jvm-step": {
		options:  map[string]int{"project-root": 1, "build-root": 1, "jdk": 1, "observation": 2, "jacoco-module": 1, "jacoco": 3},
		required: []string{"project-root"}, run: jvmStep,
	},
	"typespec": {
		options:  map[string]int{"project-root": 1, "package-dir": 1, "output": 1},
		required: []string{"project-root"}, run: typespec,
	},
	"detekt": {
		options:  map[string]int{"project-root": 1, "version": 1, "defaults": 1, "config": 1, "standalone": 0, "ktlint": 0, "accept": 1, "output": 1},
		required: []string{"project-root", "version", "defaults"}, run: detekt,
	},
	"collection": {
		options:  map[string]int{"project-root": 1, "request": 1},
		required: []string{"project-root", "request"}, run: collection,
	},
	"inspect": {
		options:  map[string]int{"project-root": 1, "host": 1, "sdd-spec": 1, "sdd-shared": 1, "user-agent-dir": 1, "available-agents": 1, "names": all, "output": 1},
		required: []string{"project-root", "host"}, run: inspectCommand,
	},
	"plan": {
		options:  map[string]int{"request": 1, "output": 1},
		required: []string{"request"}, run: planCommand,
	},
	"apply": {
		options:  map[string]int{"plan": 1},
		required: []string{"plan"}, run: applyCommand,
	},
}

// Run executes one setup command. Requests and plans are read from named files.
func Run(argv []string, _ io.Reader, stdout, stderr io.Writer) int {
	if len(argv) > 0 && isHelp(argv[0]) {
		fmt.Fprint(stdout, help)
		return 0
	}
	if len(argv) == 0 {
		fmt.Fprintln(stderr, "sdd setup: a subcommand is required")
		return 2
	}
	name := argv[0]
	spec, found := commands[name]
	if !found {
		fmt.Fprintf(stderr, "sdd setup: unknown subcommand %q\n", name)
		return 2
	}
	if slices.ContainsFunc(argv[1:], isHelp) {
		flags := keys(spec.options)
		for i := range flags {
			flags[i] = "--" + flags[i]
		}
		fmt.Fprintf(stdout, "usage: sdd setup %s %s\n", name, strings.Join(flags, " "))
		return 0
	}
	args, err := parseArguments(name, spec, argv[1:])
	if err != nil {
		fmt.Fprintf(stderr, "sdd setup %s: %s\n", name, err)
		return 2
	}
	result, err := spec.run(args)
	if err == nil && args.has("output") {
		result, err = saveResult(result, args.value("output"), name)
	}
	if err != nil {
		fmt.Fprintln(stdout, jsonText(object{"ok": false, "code": "sdd_setup", "message": err.Error()}, false, nil))
		return 1
	}
	fmt.Fprintln(stdout, jsonText(object{"ok": true, "result": result}, true, nil))
	return 0
}

func isHelp(arg string) bool { return arg == "-h" || arg == "--help" }

func parseArguments(name string, spec command, argv []string) (arguments, error) {
	args := arguments{}
	for len(argv) > 0 {
		flag := argv[0]
		argv = argv[1:]
		if name == "jvm-step" && !strings.HasPrefix(flag, "-") && !args.has("step") {
			if !slices.Contains([]string{"jdk", "gradle", "junit5", "jacoco", "archunit"}, flag) {
				return nil, fmt.Errorf("invalid step %q", flag)
			}
			args["step"] = [][]string{{flag}}
			continue
		}
		option, first, attached := strings.Cut(strings.TrimPrefix(flag, "--"), "=")
		arity, known := spec.options[option]
		if !known || !strings.HasPrefix(flag, "--") {
			return nil, fmt.Errorf("unrecognized argument %s", flag)
		}
		values := []string{}
		if attached {
			if arity == 0 {
				return nil, fmt.Errorf("--%s takes no value", option)
			}
			values = append(values, first)
		}
		for len(argv) > 0 && !strings.HasPrefix(argv[0], "--") &&
			((arity >= 0 && len(values) < arity) || (arity == optional && len(values) == 0) || arity <= all) {
			values = append(values, argv[0])
			argv = argv[1:]
		}
		if (arity > 0 && len(values) != arity) || (arity == onePlus && len(values) == 0) {
			return nil, fmt.Errorf("--%s needs a value", option)
		}
		args[option] = append(args[option], values)
	}
	required := spec.required
	if name == "jvm-step" {
		required = append(slices.Clone(required), "step")
	}
	for _, option := range required {
		if !args.has(option) {
			return nil, fmt.Errorf("missing required argument --%s", option)
		}
	}
	for _, group := range append(slices.Clone(spec.exclusive), spec.requiredGroups...) {
		active := []string{}
		for _, option := range group {
			if args.has(option) {
				active = append(active, option)
			}
		}
		if len(active) > 1 {
			return nil, fmt.Errorf("choose one of %s", strings.Join(group, ", "))
		}
	}
	for _, group := range spec.requiredGroups {
		if !slices.ContainsFunc(group, args.has) {
			return nil, fmt.Errorf("choose one of %s", strings.Join(group, ", "))
		}
	}
	switch name {
	case "inspect":
		if !slices.Contains([]string{"codex", "claude-code"}, args.value("host")) {
			return nil, fmt.Errorf("invalid host %q", args.value("host"))
		}
	case "progress":
		for _, option := range []string{"applicable", "reset", "complete", "failed"} {
			for _, step := range args.values(option) {
				if !slices.Contains(steps, step) && !(option == "reset" && step == "all") {
					return nil, fmt.Errorf("invalid step %q for --%s", step, option)
				}
			}
		}
		for _, code := range args["check-exit-code"] {
			if _, err := strconv.Atoi(code[0]); err != nil {
				return nil, fmt.Errorf("invalid check exit code %q", code[0])
			}
		}
	}
	return args, nil
}

func repeated(args arguments, name string) []string {
	values := []string{}
	for _, value := range args[name] {
		values = append(values, value[0])
	}
	return values
}
