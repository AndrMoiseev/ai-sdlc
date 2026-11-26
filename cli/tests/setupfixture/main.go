// setupfixture runs a fake native mise or Node process for setup's differential tests.
package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

type fixture struct {
	Tools    map[string]any
	Paths    map[string]string
	Versions map[string]string
	Reports  map[string]string
	Mode     string
}

func check(err error) {
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(90)
	}
}

func main() {
	data, err := os.ReadFile(os.Getenv("SDD_SETUP_FIXTURE"))
	check(err)
	var test fixture
	check(json.Unmarshal(data, &test))
	args := os.Args[1:]
	cwd, err := os.Getwd()
	check(err)
	output := ""
	if strings.HasPrefix(strings.ToLower(filepath.Base(os.Args[0])), "node") {
		if args[0] == "--version" {
			output = "v22.6.0\n"
		} else {
			output = "TypeSpec compiler v1.2.3\n"
		}
	} else {
		switch args[0] {
		case "--version":
			output = "mise 2026.1.1\n"
		case "ls":
			raw, err := json.Marshal(test.Tools)
			check(err)
			output = string(raw)
		case "which":
			if len(args) == 2 {
				output = test.Paths[args[1]]
			} else if args[2] == "--plugin" {
				output = args[1]
			} else {
				output = test.Versions[args[1]]
			}
		case "exec":
			output = args[2] + " " + test.Versions[args[2]]
		case "run":
			entry, err := json.Marshal(map[string]any{"argv": append([]string{"mise"}, args...), "cwd": cwd})
			check(err)
			log, err := os.OpenFile(filepath.Join(cwd, "task.log"), os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o644)
			check(err)
			_, err = log.Write(append(entry, '\n'))
			check(err)
			check(log.Close())
			if test.Mode == "fail" {
				fmt.Fprintln(os.Stderr, "fixture task failed")
				os.Exit(7)
			}
			for relative, content := range test.Reports {
				target := filepath.Join(cwd, relative)
				check(os.MkdirAll(filepath.Dir(target), 0o755))
				check(os.WriteFile(target, []byte(content), 0o644))
			}
		default:
			fmt.Fprintln(os.Stderr, "Unexpected fixture command", args)
			os.Exit(91)
		}
	}
	fmt.Print(output)
}
