// Package checkpoint manages the accepted Git ref for an SDD work in one worktree.
package checkpoint

import (
	"bytes"
	"crypto/sha256"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"slices"
	"strings"
)

type problem struct{ code, message string }

func (p *problem) Error() string  { return p.message }
func fail(code, msg string) error { return &problem{code, msg} }

type repository struct {
	root, dir, ref string
	oidSize        int
}
type change struct {
	Status   string `json:"status"`
	Path     string `json:"path"`
	Original string `json:"original_path,omitempty"`
}
type reviewed struct {
	Paths     []string `json:"paths"`
	Tree      string   `json:"tree"`
	IndexTree string   `json:"index_tree"`
}

// CommitExists checks that an evidence OID names a commit in this repository.
func CommitExists(project, oid string) bool {
	g := repository{root: project}
	kind, e := g.value("cat-file", "-t", oid)
	return e == nil && kind == "commit"
}

func (g repository) command(index, input string, args ...string) (string, string, int, error) {
	cmd := exec.Command("git", append([]string{"-C", g.root}, args...)...)
	env := []string{}
	for _, s := range os.Environ() {
		k, _, _ := strings.Cut(s, "=")
		switch strings.ToUpper(k) {
		case "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_OPTIONAL_LOCKS", "GIT_LITERAL_PATHSPECS":
			continue
		}
		env = append(env, s)
	}
	cmd.Env = append(env, "GIT_OPTIONAL_LOCKS=0", "GIT_LITERAL_PATHSPECS=1")
	if index != "" {
		cmd.Env = append(cmd.Env, "GIT_INDEX_FILE="+index)
	}
	var out, stderr bytes.Buffer
	cmd.Stdout = &out
	cmd.Stderr = &stderr
	cmd.Stdin = strings.NewReader(input)
	err := cmd.Run()
	var exit *exec.ExitError
	if errors.As(err, &exit) {
		return out.String(), strings.ToValidUTF8(stderr.String(), "\uFFFD"), exit.ExitCode(), nil
	}
	if errors.Is(err, exec.ErrNotFound) {
		return "", "", 0, fail("git_unavailable", "Git executable or project directory is unavailable")
	}
	return out.String(), stderr.String(), 0, err
}
func (g repository) run(index, input string, args ...string) (string, error) {
	out, msg, rc, err := g.command(index, input, args...)
	if err != nil {
		return "", err
	}
	if rc != 0 {
		code := "git_error"
		if strings.Contains(msg, "not a git repository") {
			code = "not_repository"
		}
		return "", fail(code, strings.TrimSpace(msg))
	}
	return out, nil
}
func (g repository) value(args ...string) (string, error) {
	s, e := g.run("", "", args...)
	return strings.TrimSpace(s), e
}

func open(project, kind, id string) (repository, error) {
	p, err := filepath.Abs(project)
	g := repository{root: p, oidSize: 40}
	if err != nil {
		return g, err
	}
	if g.root, err = g.value("rev-parse", "--show-toplevel"); err != nil {
		return g, err
	}
	dir, err := g.value("rev-parse", "--absolute-git-dir")
	if err != nil {
		return g, err
	}
	g.dir, err = filepath.EvalSymlinks(filepath.Clean(dir))
	if err != nil {
		return g, err
	}
	identity := g.dir
	if runtime.GOOS == "windows" {
		identity = strings.ToLower(identity)
	}
	g.ref = fmt.Sprintf("refs/sdd/checkpoints/%s/%s/%x", kind, id, sha256.Sum256([]byte(identity)))
	format, err := g.value("rev-parse", "--show-object-format")
	if format == "sha256" {
		g.oidSize = 64
	}
	return g, err
}
func (g repository) accepted() (string, error) {
	_, _, rc, e := g.command("", "", "symbolic-ref", "-q", g.ref)
	if e != nil {
		return "", e
	}
	if rc == 0 {
		return "", fail("invalid_checkpoint_ref", "Checkpoint reference must be direct, not symbolic")
	}
	_, msg, rc, e := g.command("", "", "show-ref", "--verify", "--quiet", g.ref)
	if e != nil || rc == 1 {
		return "", e
	}
	if rc != 0 {
		return "", fail("invalid_checkpoint_ref", msg)
	}
	oid, e := g.value("rev-parse", "--verify", g.ref)
	if e != nil {
		return "", e
	}
	kind, e := g.value("cat-file", "-t", oid)
	if e == nil && kind != "commit" {
		e = fail("invalid_checkpoint_ref", "Checkpoint reference does not identify a commit")
	}
	return oid, e
}
func (g repository) changes() ([]change, error) {
	records, e := g.run("", "", "ls-files", "-v", "-z")
	if e != nil {
		return nil, e
	}
	hidden := []string{}
	for _, r := range strings.Split(records, "\x00") {
		if len(r) > 2 && (r[0] == 'S' || r[0] >= 'a' && r[0] <= 'z') {
			hidden = append(hidden, "'"+strings.ReplaceAll(r[2:], "'", "\\'")+"'")
		}
	}
	if len(hidden) > 0 {
		return nil, fail("unsupported_index_flags", "Cannot verify tracked files with assume-unchanged/skip-worktree flags: ["+strings.Join(hidden, ", ")+"]. Resolve these flags explicitly before retrying; files and flags were preserved.")
	}
	raw, e := g.run("", "", "status", "--porcelain=v1", "-z", "--untracked-files=all", "--ignore-submodules=none")
	if e != nil {
		return nil, e
	}
	result := []change{}
	rows := strings.Split(raw, "\x00")
	for i := 0; i < len(rows); i++ {
		r := rows[i]
		if r == "" {
			continue
		}
		if len(r) < 4 {
			return nil, fail("git_error", "Invalid porcelain status")
		}
		c := change{Status: r[:2], Path: r[3:]}
		if strings.ContainsAny(c.Status, "RC") {
			i++
			if i >= len(rows) {
				return nil, fail("git_error", "Missing rename source")
			}
			c.Original = rows[i]
		}
		result = append(result, c)
	}
	return result, nil
}
func (g repository) stage(paths []string, index string) error {
	raw, e := g.run(index, "", "ls-files", "--cached", "-z")
	if e != nil {
		return e
	}
	tracked := map[string]bool{}
	for _, p := range strings.Split(raw, "\x00") {
		tracked[p] = true
	}
	selected := []string{}
	for _, p := range paths {
		_, err := os.Lstat(filepath.Join(g.root, p))
		if tracked[p] || err == nil {
			selected = append(selected, p)
		}
	}
	if len(selected) == 0 {
		return nil
	}
	_, e = g.run(index, strings.Join(selected, "\x00")+"\x00", "add", "--all", "--pathspec-from-file=-", "--pathspec-file-nul")
	return e
}
func (g repository) capture() (reviewed, error) {
	r := reviewed{Paths: []string{}}
	changes, e := g.changes()
	if e != nil {
		return r, e
	}
	for _, change := range changes {
		r.Paths = append(r.Paths, change.Path)
		if change.Original != "" {
			r.Paths = append(r.Paths, change.Original)
		}
	}
	slices.Sort(r.Paths)
	r.Paths = slices.Compact(r.Paths)
	tmp, e := os.MkdirTemp("", "sdd-checkpoint-")
	if e != nil {
		return r, e
	}
	defer os.RemoveAll(tmp)
	idx := filepath.Join(tmp, "index")
	if _, e = g.run(idx, "", "read-tree", "HEAD"); e != nil {
		return r, e
	}
	if len(r.Paths) > 0 {
		if e = g.stage(r.Paths, idx); e != nil {
			return r, e
		}
	}
	tree, e := g.run(idx, "", "write-tree")
	if e != nil {
		return r, e
	}
	r.Tree = strings.TrimSpace(tree)
	r.IndexTree, e = g.value("write-tree")
	return r, e
}
func (g repository) update(oid, old, msg string) error {
	if old == "" {
		old = strings.Repeat("0", g.oidSize)
	}
	input := fmt.Sprintf("start\nverify HEAD %s\nupdate %s %s %s\nprepare\ncommit\n", oid, g.ref, oid, old)
	_, e := g.run("", input, "update-ref", "--no-deref", "--create-reflog", "-m", msg, "--stdin")
	return e
}
