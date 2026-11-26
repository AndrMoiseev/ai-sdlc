// Command sdd exposes the native SDD workflow operations.
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"os"

	"github.com/AndrMoiseev/ai-sdlc/cli/internal/agent"
	"github.com/AndrMoiseev/ai-sdlc/cli/internal/apply"
	"github.com/AndrMoiseev/ai-sdlc/cli/internal/architect"
	"github.com/AndrMoiseev/ai-sdlc/cli/internal/check"
	"github.com/AndrMoiseev/ai-sdlc/cli/internal/checkpoint"
	"github.com/AndrMoiseev/ai-sdlc/cli/internal/setup"
	"github.com/AndrMoiseev/ai-sdlc/cli/internal/simplicity"
)

func run(args []string, stdout, stderr io.Writer) int {
	const usage = "Usage: sdd check --project-root DIR --change ID --stage documents|plan [--work-kind change|refactoring]"
	const commands = "Usage: sdd <setup|architect|check|resolve-agent|simplicity|checkpoint|apply> [options]"
	if len(args) > 0 {
		switch args[0] {
		case "architect":
			return architect.Run(args[1:], os.Stdin, stdout, stderr)
		case "apply":
			return apply.Run(args[1:], os.Stdin, stdout, stderr)
		case "setup":
			return setup.Run(args[1:], os.Stdin, stdout, stderr)
		case "checkpoint":
			return checkpoint.Run(args[1:], stdout, stderr)
		case "resolve-agent":
			return agent.Run(args[1:], stdout, stderr)
		case "simplicity":
			return simplicity.Run(args[1:], stdout, stderr)
		}
	}
	if len(args) == 1 && (args[0] == "--help" || args[0] == "-h") {
		fmt.Fprintln(stdout, commands)
		return 0
	}
	if len(args) == 0 || args[0] != "check" {
		fmt.Fprintln(stderr, commands)
		return 2
	}
	flags := flag.NewFlagSet("sdd check", flag.ContinueOnError)
	flags.SetOutput(stderr)
	flags.Usage = func() { fmt.Fprintln(flags.Output(), usage) }
	project := flags.String("project-root", "", "Project directory")
	change := flags.String("change", "", "Change ID")
	stage := flags.String("stage", "", "documents or plan")
	workKind := flags.String("work-kind", "change", "SDD work kind")
	if len(args) == 2 && (args[1] == "--help" || args[1] == "-h") {
		fmt.Fprintln(stdout, usage)
		return 0
	}
	if err := flags.Parse(args[1:]); err != nil {
		if err == flag.ErrHelp {
			return 0
		}
		return 2
	}
	if flags.NArg() != 0 || *project == "" || *change == "" || (*stage != "documents" && *stage != "plan") {
		flags.Usage()
		return 2
	}
	report, exitCode := check.Run(*project, *change, *stage, *workKind)
	encoder := json.NewEncoder(stdout)
	encoder.SetIndent("", "  ")
	encoder.SetEscapeHTML(false)
	if err := encoder.Encode(report); err != nil {
		fmt.Fprintln(stderr, err)
		return 2
	}
	return exitCode
}

func main() {
	os.Exit(run(os.Args[1:], os.Stdout, os.Stderr))
}
