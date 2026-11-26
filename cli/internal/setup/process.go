package setup

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"github.com/AndrMoiseev/ai-sdlc/cli/internal/childprocess"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
	"strings"
	"time"
)

type processResult struct {
	stdout, stderr string
	code           int
}

func runProcess(project string, timeout time.Duration, environment []string, argv []string) (processResult, error) {
	path := argv[0]
	if !filepath.IsAbs(path) {
		path = findExecutable(project, path)
		if path == "" {
			return processResult{}, fmt.Errorf("[Errno 2] No such file or directory: %s", pythonString(argv[0]))
		}
	}
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()
	cmd := exec.CommandContext(ctx, path, argv[1:]...)
	cmd.Dir = project
	cmd.Env = environment
	childprocess.Configure(cmd)
	cmd.WaitDelay = time.Second
	var stdout, stderr bytes.Buffer
	cmd.Stdout, cmd.Stderr = &stdout, &stderr
	err := cmd.Run()
	if ctx.Err() != nil {
		return processResult{}, fmt.Errorf("Command %s timed out after %g seconds", pythonList(argv), timeout.Seconds())
	}
	result := processResult{
		stdout: strings.ToValidUTF8(stdout.String(), "\uFFFD"),
		stderr: strings.ToValidUTF8(stderr.String(), "\uFFFD"),
	}
	var exit *exec.ExitError
	if errors.As(err, &exit) {
		result.code = exit.ExitCode()
		return result, nil
	}
	return result, err
}

func findExecutable(project, name string) string {
	search := os.Getenv("PATH")
	if search == "" {
		return ""
	}
	extensions := []string{""}
	if runtime.GOOS == "windows" && filepath.Ext(name) == "" {
		value := os.Getenv("PATHEXT")
		if value == "" {
			value = ".COM;.EXE;.BAT;.CMD"
		}
		extensions = strings.Split(value, ";")
	}
	for _, directory := range strings.Split(search, string(os.PathListSeparator)) {
		for _, extension := range extensions {
			candidate := anchored(anchored(project, directory), name+extension)
			info, err := os.Stat(candidate)
			if err == nil && info.Mode().IsRegular() && (runtime.GOOS == "windows" || info.Mode().Perm()&0o111 != 0) {
				return absolute(candidate)
			}
		}
	}
	return ""
}

type miseExecute func([]string) (string, error)

var miseVersion = regexp.MustCompile(`^(?:mise )?\d+\.\d+\.\d+(?:[-+]\S+)?(?:\s|$)`)

func checkMise(project string) object {
	executable := findExecutable(project, "mise")
	evidence := object{"command": nil, "returncode": nil, "stdout": "", "stderr": "", "error": nil}
	row := object{"id": "mise", "required": true,
		"title":  "mise is available on PATH and reports its version in the project's working environment",
		"status": "not_found", "executable": optionalText(executable), "version": nil, "evidence": evidence}
	if executable == "" {
		evidence["error"] = "mise was not found on PATH; check the existing installation before installing"
		return row
	}
	argv := []string{executable, "--version"}
	evidence["command"] = argv
	row["status"] = "failed"
	if extension := strings.ToLower(filepath.Ext(executable)); extension == ".bat" || extension == ".cmd" {
		evidence["error"] = "Use the native mise executable, not a batch wrapper"
		return row
	}
	process, err := runProcess(project, 10*time.Second, nil, argv)
	if err != nil {
		evidence["error"] = err.Error()
		return row
	}
	evidence["returncode"] = process.code
	evidence["stdout"] = newlines(process.stdout)
	evidence["stderr"] = newlines(process.stderr)
	version, _, _ := strings.Cut(strings.TrimSpace(newlines(process.stdout)), "\n")
	switch {
	case process.code != 0:
		evidence["error"] = "mise --version failed; diagnose the reported error before reinstalling"
	case !miseVersion.MatchString(version):
		evidence["error"] = "mise --version did not return a recognizable version"
	default:
		row["status"], row["version"] = "satisfied", version
	}
	return row
}

func newlines(value string) string {
	return strings.ReplaceAll(strings.ReplaceAll(value, "\r\n", "\n"), "\r", "\n")
}

type commandExit struct {
	argv []string
	processResult
}

func (err commandExit) Error() string {
	return fmt.Sprintf("Command '%s' returned non-zero exit status %d.", pythonList(err.argv), err.code)
}

func commandMessage(err error) string {
	var exit commandExit
	if errors.As(err, &exit) && strings.TrimSpace(exit.stderr) != "" {
		return strings.TrimSpace(exit.stderr)
	}
	return err.Error()
}

func miseReader(project string, mise object) miseExecute {
	if mise["status"] != "satisfied" {
		return nil
	}
	return func(args []string) (string, error) {
		argv := append([]string{asString(mise["executable"])}, args[1:]...)
		process, err := runProcess(project, 10*time.Second, append(os.Environ(), "MISE_AUTO_INSTALL=false"), argv)
		if err != nil {
			return "", err
		}
		if process.code != 0 {
			return "", commandExit{argv, process}
		}
		return process.stdout, nil
	}
}

var executableName = regexp.MustCompile(`^[\p{L}\p{N}_.+][\p{L}\p{N}_.+-]*$`)

func checkTools(tools object, order []string, project string, execute miseExecute) error {
	if len(tools) == 0 {
		return errors.New("List each required mise tool and its executable names")
	}
	out, err := execute([]string{"mise", "ls", "--current", "--json"})
	if err != nil {
		return err
	}
	value, err := decodeJSON([]byte(out), nil)
	if err != nil {
		return err
	}
	records := asObject(value)
	for _, tool := range order {
		binaries := stringsIn(tools[tool])
		if len(binaries) == 0 {
			return fmt.Errorf("List the executables provided by %s", tool)
		}
		installs := []string{}
		for _, raw := range array(records[tool]) {
			record := asObject(raw)
			source := asString(asObject(record["source"])["path"])
			install := asString(record["install_path"])
			if source != "" && record["active"] == true && record["installed"] == true && install != "" &&
				inside(project, resolve(anchored(project, source))) {
				installs = append(installs, resolve(install))
			}
		}
		if len(installs) == 0 {
			return fmt.Errorf("Configure and install %s in project mise settings", tool)
		}
		for _, binary := range binaries {
			if !executableName.MatchString(binary) {
				return fmt.Errorf("Expected executable name for %s", tool)
			}
			out, err := execute([]string{"mise", "which", binary})
			if err != nil {
				return err
			}
			path := strings.TrimSpace(out)
			if filepath.IsAbs(path) && isFile(path) {
				for _, install := range installs {
					if inside(install, resolve(path)) {
						path = ""
						break
					}
				}
				if path == "" {
					continue
				}
			}
			return fmt.Errorf("%s must resolve to the project-configured mise installation of %s", binary, tool)
		}
	}
	return nil
}

func checkBinary(execute miseExecute, project, tool string, binaries ...string) error {
	return checkTools(object{tool: binaries}, []string{tool}, project, execute)
}
