package apply

import (
	"bytes"
	"errors"
	"io/fs"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"sort"
	"strings"
)

type gitResult struct {
	stdout, stderr []byte
	err            error
}

func gitCommand(root string, environment []string, args ...string) gitResult {
	command := exec.Command("git", append([]string{"-C", root}, args...)...)
	if len(environment) > 0 {
		command.Env = append(os.Environ(), environment...)
	}
	var stdout, stderr bytes.Buffer
	command.Stdout, command.Stderr = &stdout, &stderr
	err := command.Run()
	return gitResult{stdout.Bytes(), stderr.Bytes(), err}
}

func (result gitResult) checked() ([]byte, error) {
	if result.err != nil {
		if len(result.stderr) > 0 {
			return nil, reject("git_failed", strings.ToValidUTF8(string(result.stderr), "\uFFFD"))
		}
		return nil, result.err
	}
	return result.stdout, nil
}

func gitBytes(root string, args ...string) ([]byte, error) {
	return gitCommand(root, nil, args...).checked()
}

func gitText(root string, args ...string) (string, error) {
	raw, err := gitBytes(root, args...)
	return strings.TrimSpace(strings.ToValidUTF8(string(raw), "\uFFFD")), err
}

func gitStatus(root string, excluded []string, includeIgnored bool) (mapping, error) {
	raw, err := gitBytes(root, "ls-files", "-v", "--stage", "-z")
	if err != nil {
		return nil, err
	}
	indexedLinks := map[string]bool{}
	for _, record := range strings.Split(string(raw), "\x00") {
		if len(record) < 3 {
			continue
		}
		tag := record[0]
		mode, _, _ := strings.Cut(record[2:], " ")
		if tag >= 'a' && tag <= 'z' || tag == 'S' || mode != "100644" && mode != "100755" && mode != "120000" {
			return nil, reject("unsupported_index", "Unsupported index mode or assume-unchanged/skip-worktree flag: "+record)
		}
		if mode == "120000" {
			_, name, _ := strings.Cut(record, "\t")
			indexedLinks[name] = true
		}
	}
	args := []string{"-c", "core.fsmonitor=false", "-c", "core.ignoreStat=false"}
	if runtime.GOOS != "windows" {
		args = append(args, "-c", "core.fileMode=true")
	}
	args = append(args, "status", "--porcelain=v2", "--branch", "--no-renames", "-z", "--untracked-files=all", "--ignore-submodules=none")
	if includeIgnored {
		args = append(args, "--ignored")
	}
	args = append(args, "--", ".")
	for _, path := range excluded {
		args = append(args, ":(top,exclude,literal)"+path)
	}
	status, err := gitBytes(root, args...)
	if err != nil {
		return nil, err
	}
	var head string
	var branch any
	dirty, untracked, ignored := []string{}, []string{}, []string{}
	for _, record := range strings.Split(string(status), "\x00") {
		if len(record) < 2 {
			continue
		}
		switch {
		case strings.HasPrefix(record, "# branch.oid "):
			head = strings.TrimPrefix(record, "# branch.oid ")
		case strings.HasPrefix(record, "# branch.head "):
			if value := strings.TrimPrefix(record, "# branch.head "); value != "(detached)" {
				branch = value
			}
		case strings.HasPrefix(record, "# "):
		case record[0] == '1', record[0] == 'u':
			count := 9
			if record[0] == 'u' {
				count = 11
			}
			fields := strings.SplitN(record, " ", count)
			if len(fields) != count {
				return nil, reject("git_status", "Unexpected status record")
			}
			dirty = append(dirty, fields[count-1])
		case record[0] == '?':
			dirty, untracked = append(dirty, record[2:]), append(untracked, record[2:])
		case record[0] == '!':
			ignored = append(ignored, record[2:])
		default:
			return nil, reject("git_status", "Unexpected status record")
		}
	}
	pathSet := make(map[string]bool)
	for _, name := range dirty {
		pathSet[name] = true
	}
	for name := range indexedLinks {
		pathSet[name] = true
	}
	for name := range pathSet {
		path := filepath.Join(root, filepath.FromSlash(name))
		info, err := os.Lstat(path)
		if err == nil && info.Mode()&os.ModeSymlink != 0 {
			if err := validateSymlink(root, path); err != nil {
				return nil, err
			}
		} else if indexedLinks[name] && !includes(dirty, name) {
			return nil, reject("invalid_symlink", "Git symlink is not materialized in this worktree: "+name)
		}
	}
	if head == "" || head == "(initial)" {
		return nil, reject("git_failed", "Repository has no HEAD commit")
	}
	sort.Strings(dirty)
	sort.Strings(untracked)
	sort.Strings(ignored)
	return mapping{"head": head, "branch": branch, "dirty_paths": dirty, "untracked_paths": untracked, "ignored_paths": ignored}, nil
}

func validateSymlink(root, path string) error {
	target, err := filepath.EvalSymlinks(path)
	if err != nil {
		return reject("invalid_symlink", "Cannot resolve symlink "+path+": "+err.Error())
	}
	relative, err := filepath.Rel(root, target)
	if err != nil || relative == ".." || strings.HasPrefix(relative, ".."+string(filepath.Separator)) {
		return reject("path_escape", "Symlink leaves worktree: "+path+" -> "+target)
	}
	for _, component := range strings.Split(filepath.ToSlash(relative), "/") {
		if strings.EqualFold(component, ".git") {
			return reject("git_path", "Symlink points into Git metadata: "+path)
		}
	}
	info, err := os.Stat(target)
	if err != nil || !info.IsDir() && !info.Mode().IsRegular() {
		return reject("invalid_symlink", "Expected file or directory: "+path)
	}
	return nil
}

func planRelative(state mapping) (string, error) {
	basis := object(state["basis"])
	return filepath.Rel(str(basis["project_root"]), str(basis["change_root"]))
}

func executionSource(state mapping) (mapping, error) {
	relative, err := planRelative(state)
	if err != nil {
		return nil, err
	}
	return gitStatus(str(object(state["basis"])["project_root"]), []string{filepath.ToSlash(filepath.Join(relative, "execution"))}, false)
}

func taskRoot(state, task mapping) string {
	if worktree := object(task["worktree"]); worktree != nil && !truth(worktree["integrated"]) {
		return str(worktree["path"])
	}
	return str(object(state["basis"])["project_root"])
}

func snapshot(state mapping, root string) (mapping, error) {
	if root == "" {
		root = str(object(state["basis"])["project_root"])
	}
	relative, err := planRelative(state)
	if err != nil {
		return nil, err
	}
	changeDir, err := contained(root, relative)
	if err != nil {
		return nil, err
	}
	files := mapping{}
	err = filepath.WalkDir(changeDir, func(path string, entry fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if path == filepath.Join(changeDir, "execution") {
			if entry.IsDir() {
				return filepath.SkipDir
			}
			return nil
		}
		if entry.IsDir() {
			return nil
		}
		rel, err := filepath.Rel(root, path)
		if err != nil {
			return err
		}
		name := filepath.ToSlash(rel)
		if entry.Type()&os.ModeSymlink != 0 {
			if err := validateSymlink(root, path); err != nil {
				return err
			}
			link, err := os.Readlink(path)
			if err != nil {
				return err
			}
			files[name] = mapping{"symlink": link}
		} else if entry.Type().IsRegular() {
			data, err := os.ReadFile(path)
			if err != nil {
				return err
			}
			files[name] = mapping{"sha256": digest(data)}
		}
		return nil
	})
	if err != nil {
		return nil, err
	}
	status, err := gitStatus(root, []string{filepath.ToSlash(filepath.Join(relative, "execution"))}, false)
	if err != nil {
		return nil, err
	}
	return mapping{"files": files, "digest": digest(files), "commit": status["head"], "branch": status["branch"], "dirty_paths": status["dirty_paths"]}, nil
}

func registeredWorktree(root, wanted string) (mapping, error) {
	raw, err := gitBytes(root, "worktree", "list", "--porcelain", "-z")
	if err != nil {
		return nil, err
	}
	for _, entry := range strings.Split(string(raw), "\x00\x00") {
		record := mapping{}
		for _, line := range strings.Split(entry, "\x00") {
			key, value, exists := strings.Cut(line, " ")
			if exists || key != "" {
				record[key] = value
			}
		}
		if samePath(filepath.FromSlash(str(record["worktree"])), wanted) {
			_, detached := record["detached"]
			result := mapping{"head": record["HEAD"], "detached": detached}
			if branch, exists := record["branch"]; exists {
				result["branch"] = strings.TrimPrefix(str(branch), "refs/heads/")
			}
			return result, nil
		}
	}
	return nil, nil
}

func changedPaths(root, base, target string) ([]string, error) {
	raw, err := gitBytes(root, "diff", "--no-renames", "--name-only", "-z", base, target)
	if err != nil {
		return nil, err
	}
	paths := []string{}
	for _, name := range strings.Split(string(raw), "\x00") {
		if name != "" {
			paths = append(paths, name)
		}
	}
	return paths, nil
}

func taskTree(root, base string, owned []string) (string, error) {
	dir, err := os.MkdirTemp("", "sdd-apply-index-")
	if err != nil {
		return "", err
	}
	defer os.RemoveAll(dir)
	environment := []string{"GIT_INDEX_FILE=" + filepath.Join(dir, "index")}
	if _, err := gitCommand(root, environment, "read-tree", base).checked(); err != nil {
		return "", err
	}
	var tracked map[string]bool
	present := []string{}
	for _, file := range owned {
		_, err := os.Lstat(filepath.Join(root, filepath.FromSlash(file)))
		if err != nil && tracked == nil {
			raw, lookupErr := gitBytes(root, "ls-tree", "-r", "--name-only", "-z", base)
			if lookupErr != nil {
				return "", lookupErr
			}
			tracked = map[string]bool{}
			for _, path := range strings.Split(string(raw), "\x00") {
				tracked[path] = true
			}
		}
		if err == nil || tracked[file] {
			present = append(present, file)
		} else if !errors.Is(err, os.ErrNotExist) {
			return "", err
		}
	}
	if len(present) == 0 {
		return gitText(root, "rev-parse", base+"^{tree}")
	}
	if _, err := gitCommand(root, environment, append([]string{"add", "--force", "--all", "--"}, present...)...).checked(); err != nil {
		return "", err
	}
	if runtime.GOOS == "windows" {
		raw, err := gitBytes(root, append([]string{"ls-files", "--stage", "-z", "--"}, present...)...)
		if err != nil {
			return "", err
		}
		pathsByMode := map[string][]string{}
		for _, entry := range strings.Split(string(raw), "\x00") {
			index, name, valid := strings.Cut(entry, "\t")
			if !valid {
				continue
			}
			parts := strings.Fields(index)
			if len(parts) != 3 || parts[2] != "0" {
				return "", reject("unmerged_index", name)
			}
			mode := parts[0]
			if (mode == "100644" || mode == "100755") && existingFile(filepath.Join(root, filepath.FromSlash(name))) {
				pathsByMode[mode] = append(pathsByMode[mode], name)
			}
		}
		for _, mode := range []struct{ index, flag string }{{"100644", "--chmod=-x"}, {"100755", "--chmod=+x"}} {
			if paths := pathsByMode[mode.index]; len(paths) != 0 {
				if _, err := gitCommand(root, environment, append([]string{"update-index", mode.flag, "--"}, paths...)...).checked(); err != nil {
					return "", err
				}
			}
		}
	}
	tree, err := gitCommand(root, environment, "write-tree").checked()
	return strings.TrimSpace(string(tree)), err
}
