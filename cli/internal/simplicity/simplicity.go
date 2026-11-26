// Package simplicity renders the review instructions for a model selected by the host.
package simplicity

import (
	"embed"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"regexp"
	"slices"
	"strings"
)

//go:embed references/*.md
var instructions embed.FS
var models = []string{"gpt-6-astra", "gpt-6.1-sol", "claude-fable-5-1", "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5", "kimi-k3"}
var kimiAliases = []string{"k3", "k3-256k", "kimi-k3.1-pro", "k3.1-pro", "kimi-k3.1-pro-highspeed", "k3.1-pro-highspeed"}
var families = []struct {
	name    string
	pattern *regexp.Regexp
}{
	{"openai", regexp.MustCompile(`^(?:gpt-(?:\d|oss-)[a-z0-9.-]*|o\d+(?:-[a-z0-9.]+)*)$`)},
	{"claude", regexp.MustCompile(`^claude-[a-z0-9]+(?:[.-][a-z0-9]+)*$`)},
	{"kimi", regexp.MustCompile(`^(?:kimi-(?:k\d|for-coding)|k\d)[a-z0-9.-]*$`)},
}

func profileFor(model string) string {
	key := strings.ToLower(model)
	if slices.Contains(models, key) {
		return key
	}
	if slices.Contains(kimiAliases, key) {
		return "kimi-k3"
	}
	for _, family := range families {
		if family.pattern.MatchString(key) {
			return family.name
		}
	}
	return ""
}

func Run(args []string, stdout, stderr io.Writer) int {
	flags := flag.NewFlagSet("simplicity", flag.ContinueOnError)
	flags.SetOutput(stderr)
	var model any
	flags.Func("model", "Selected model ID", func(value string) error { model = value; return nil })
	if err := flags.Parse(args); err != nil {
		if err == flag.ErrHelp {
			return 0
		}
		return 2
	}
	if flags.NArg() != 0 {
		flags.Usage()
		return 2
	}
	name, _ := model.(string)
	encoder := json.NewEncoder(stdout)
	if model != nil && (name == "" || strings.TrimSpace(name) != name) {
		encoder.Encode(map[string]any{"ok": false, "code": "simplicity_instructions", "message": "Model must be a nonempty identifier without surrounding whitespace"})
		return 1
	}
	read := func(path string) string {
		b, err := instructions.ReadFile(path)
		if err != nil {
			panic(err)
		}
		return strings.ReplaceAll(string(b), "\r\n", "\n")
	}
	body := read("references/simplicity.md")
	var path any
	if profile := profileFor(name); profile != "" {
		p := "references/simplicity-model-" + profile + ".md"
		path = p
		body = strings.TrimRight(body, " \r\n\t") + "\n\n" + read(p)
	}
	if err := encoder.Encode(map[string]any{"ok": true, "model": model, "profile": path, "instructions": body}); err != nil {
		fmt.Fprintln(stderr, err)
		return 2
	}
	return 0
}
