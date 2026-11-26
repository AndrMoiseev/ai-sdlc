package setup

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"slices"
	"sort"
	"strings"
	"unicode/utf8"
)

type object = map[string]any
type fieldOrder map[string][]string

func keys[V any](values map[string]V) []string {
	names := make([]string, 0, len(values))
	for key := range values {
		names = append(names, key)
	}
	sort.Strings(names)
	return names
}

func asObject(value any) object {
	result, _ := value.(object)
	return result
}

func asString(value any) string {
	result, _ := value.(string)
	return result
}

func array(value any) []any {
	result, _ := value.([]any)
	return result
}

func stringsIn(value any) []string {
	if result, ok := value.([]string); ok {
		return result
	}
	result := []string{}
	for _, value := range array(value) {
		result = append(result, asString(value))
	}
	return result
}

func optionalText(value string) any {
	if value == "" {
		return nil
	}
	return value
}

func objectFields(value any, names ...string) bool {
	entries := asObject(value)
	if len(entries) != len(names) {
		return false
	}
	for _, name := range names {
		if _, exists := entries[name]; !exists {
			return false
		}
	}
	return true
}

func unbom(data []byte) []byte {
	return bytes.TrimPrefix(data, []byte{0xef, 0xbb, 0xbf})
}

func readJSON(path string) (any, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, fileError(err)
	}
	return decodeJSON(raw, nil)
}

func decodeJSON(raw []byte, order fieldOrder) (any, error) {
	raw = unbom(raw)
	if !utf8.Valid(raw) {
		return nil, errors.New("Invalid UTF-8 in JSON")
	}
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.UseNumber()
	result, err := decodeValue(decoder, "", order)
	if err != nil {
		return nil, err
	}
	if _, err := decoder.Token(); err != io.EOF {
		return nil, errors.New("Extra data after JSON value")
	}
	return result, nil
}

func childPath(path, key string) string {
	return path + "/" + strings.ReplaceAll(strings.ReplaceAll(key, "~", "~0"), "/", "~1")
}

func decodeValue(decoder *json.Decoder, path string, order fieldOrder) (any, error) {
	token, err := decoder.Token()
	if err != nil {
		return nil, err
	}
	switch token {
	case json.Delim('{'):
		result := object{}
		for decoder.More() {
			value, err := decoder.Token()
			if err != nil {
				return nil, err
			}
			key := value.(string)
			if _, exists := result[key]; exists {
				return nil, fmt.Errorf("Duplicate JSON key: %s", key)
			}
			if order != nil {
				order[path] = append(order[path], key)
			}
			result[key], err = decodeValue(decoder, childPath(path, key), order)
			if err != nil {
				return nil, err
			}
		}
		_, err = decoder.Token()
		return result, err
	case json.Delim('['):
		result := []any{}
		for decoder.More() {
			child, err := decodeValue(decoder, fmt.Sprintf("%s/%d", path, len(result)), order)
			if err != nil {
				return nil, err
			}
			result = append(result, child)
		}
		_, err = decoder.Token()
		return result, err
	default:
		return token, nil
	}
}

// Python's identity hashes use sorted keys, UTF-8, and spaces after both
// separators. Persisted settings retain the existing insertion order.
func jsonText(value any, pretty bool, order fieldOrder) string {
	var out strings.Builder
	var write func(any, string, int)
	write = func(value any, path string, depth int) {
		indent := func(depth int) {
			out.WriteByte('\n')
			out.WriteString(strings.Repeat("  ", depth))
		}
		next := func(index int) {
			if index > 0 {
				out.WriteByte(',')
			}
			if pretty {
				indent(depth + 1)
			} else if index > 0 {
				out.WriteByte(' ')
			}
		}
		switch entries := value.(type) {
		case object:
			out.WriteByte('{')
			names := slices.Clone(order[path])
			for _, key := range keys(entries) {
				if !slices.Contains(names, key) {
					names = append(names, key)
				}
			}
			index := 0
			for _, key := range names {
				child, exists := entries[key]
				if !exists {
					continue
				}
				next(index)
				write(key, "", 0)
				out.WriteString(": ")
				write(child, childPath(path, key), depth+1)
				index++
			}
			if pretty && index > 0 {
				indent(depth)
			}
			out.WriteByte('}')
		case []any:
			out.WriteByte('[')
			for i, child := range entries {
				next(i)
				write(child, fmt.Sprintf("%s/%d", path, i), depth+1)
			}
			if pretty && len(entries) > 0 {
				indent(depth)
			}
			out.WriteByte(']')
		case []string:
			children := make([]any, len(entries))
			for i, child := range entries {
				children[i] = child
			}
			write(children, path, depth)
		case []object:
			children := make([]any, len(entries))
			for i, child := range entries {
				children[i] = child
			}
			write(children, path, depth)
		case string:
			out.WriteByte('"')
			for _, char := range entries {
				switch char {
				case '\\', '"':
					out.WriteByte('\\')
					out.WriteRune(char)
				case '\b':
					out.WriteString(`\b`)
				case '\t':
					out.WriteString(`\t`)
				case '\n':
					out.WriteString(`\n`)
				case '\f':
					out.WriteString(`\f`)
				case '\r':
					out.WriteString(`\r`)
				default:
					if char < 32 {
						fmt.Fprintf(&out, `\u%04x`, char)
					} else {
						out.WriteRune(char)
					}
				}
			}
			out.WriteByte('"')
		default:
			raw, _ := json.Marshal(value)
			out.Write(raw)
		}
	}
	write(value, "", 0)
	return out.String()
}

func digest(value []byte) string {
	sum := sha256.Sum256(value)
	return hex.EncodeToString(sum[:])
}

func identity(value any) string  { return digest([]byte(jsonText(value, false, nil))) }
func equal(left, right any) bool { return jsonText(left, false, nil) == jsonText(right, false, nil) }

func absolute(path string) string {
	result, err := filepath.Abs(path)
	if err == nil {
		return result
	}
	return filepath.Clean(path)
}

func resolve(path string) string {
	path = absolute(path)
	current := path
	for {
		if actual, err := filepath.EvalSymlinks(current); err == nil {
			remainder, _ := filepath.Rel(current, path)
			return filepath.Join(actual, remainder)
		}
		parent := filepath.Dir(current)
		if current == parent {
			return path
		}
		current = parent
	}
}

func inside(root, path string) bool {
	rel, err := filepath.Rel(root, path)
	return err == nil && rel != ".." && !strings.HasPrefix(rel, ".."+string(os.PathSeparator))
}

func anchored(root, path string) string {
	if filepath.IsAbs(path) {
		return path
	}
	return filepath.Join(root, path)
}

func isFile(path string) bool {
	info, err := os.Stat(path)
	return err == nil && info.Mode().IsRegular()
}

func isDir(path string) bool {
	info, err := os.Stat(path)
	return err == nil && info.IsDir()
}

func projectDirectory(path, message string) (string, error) {
	root, err := filepath.EvalSymlinks(absolute(path))
	if err != nil {
		return "", fileError(err)
	}
	if !isDir(root) {
		return "", errors.New(message)
	}
	return root, nil
}

func fileError(err error) error {
	var pathErr *os.PathError
	if !errors.As(err, &pathErr) {
		return err
	}
	if errors.Is(err, os.ErrNotExist) {
		return fmt.Errorf("[Errno 2] No such file or directory: %s", pythonString(pathErr.Path))
	}
	return err
}

func safeTarget(project, relative string) (string, error) {
	if !filepath.IsLocal(relative) || slices.Contains(strings.Split(filepath.ToSlash(relative), "/"), "..") {
		return "", errors.New("Invalid project write path")
	}
	path := filepath.Join(project, relative)
	if !inside(project, resolve(path)) {
		return "", fmt.Errorf("Write escapes project: %s", path)
	}
	for cursor := path; cursor != project; cursor = filepath.Dir(cursor) {
		if info, err := os.Lstat(cursor); err == nil {
			if info.Mode()&(os.ModeSymlink|os.ModeIrregular) != 0 {
				return "", fmt.Errorf("Symlink or reparse point in write path: %s", cursor)
			}
		} else if !errors.Is(err, os.ErrNotExist) {
			return "", fileError(err)
		}
	}
	return path, nil
}

func optionalBytes(path string) ([]byte, error) {
	result, err := os.ReadFile(path)
	if errors.Is(err, os.ErrNotExist) {
		return nil, nil
	}
	return result, fileError(err)
}

func replaceFile(path string, content []byte) error {
	parent := filepath.Dir(path)
	if err := os.MkdirAll(parent, 0o755); err != nil {
		return err
	}
	staged, err := os.CreateTemp(parent, ".sdd-setup-")
	if err != nil {
		return err
	}
	defer os.Remove(staged.Name())
	if _, err = staged.Write(content); err == nil {
		err = staged.Sync()
	}
	closeErr := staged.Close()
	if err != nil || closeErr != nil {
		return errors.Join(err, closeErr)
	}
	if info, err := os.Stat(path); err == nil {
		if err := os.Chmod(staged.Name(), info.Mode().Perm()); err != nil {
			return err
		}
	}
	return os.Rename(staged.Name(), path)
}

func withLock(project, operation string, action func() error) error {
	lock, err := safeTarget(project, ".sdd/.setup.lock")
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(lock), 0o755); err != nil {
		return err
	}
	file, err := os.OpenFile(lock, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o666)
	if errors.Is(err, os.ErrExist) {
		return errors.New("Another setup owns .sdd/.setup.lock; inspect the owner before removing a stale lock")
	}
	if err != nil {
		return err
	}
	defer os.Remove(lock)
	_, writeErr := file.WriteString(jsonText(object{"pid": os.Getpid(), "operation": operation}, false, nil))
	if err := errors.Join(writeErr, file.Close()); err != nil {
		return err
	}
	return action()
}

func settingsFile(project string) (string, []byte, object, fieldOrder, error) {
	path, err := safeTarget(project, ".sdd/settings.json")
	if err != nil {
		return "", nil, nil, nil, err
	}
	raw, err := optionalBytes(path)
	if err != nil {
		return "", nil, nil, nil, err
	}
	order := fieldOrder{"": {"schema_version"}}
	if raw == nil {
		return path, nil, object{"schema_version": json.Number("1")}, order, nil
	}
	delete(order, "")
	value, err := decodeJSON(raw, order)
	return path, raw, asObject(value), order, err
}

func saveResult(result object, output, command string) (object, error) {
	summary := result
	switch command {
	case "inspect":
		agents := object{}
		for name, raw := range asObject(result["agents"]) {
			entry := mapCopy(asObject(raw))
			delete(entry, "sha256")
			agents[name] = entry
		}
		summary = object{"project_root": result["project_root"], "host": result["host"], "snapshot": result["snapshot"], "roles": result["roles"], "agents": agents}
	case "plan":
		summary = planSummary(result)
	case "detekt":
		summary = object{"project_root": result["project_root"], "version": result["version"], "explicit_matches": result["explicit_matches"],
			"pin": len(asObject(result["pin"])), "differences": len(asObject(result["differences"]))}
	}
	path := absolute(output)
	if !strings.EqualFold(filepath.Ext(path), ".json") {
		return nil, errors.New("--output must name a new .json file")
	}
	if inside(resolve(asString(summary["project_root"])), resolve(path)) {
		return nil, errors.New("--output must be outside the project")
	}
	if !isDir(filepath.Dir(path)) {
		return nil, errors.New("--output parent must be an existing workspace directory")
	}
	for cursor := path; ; cursor = filepath.Dir(cursor) {
		if strings.EqualFold(filepath.Base(cursor), "skills") || isFile(filepath.Join(cursor, "SKILL.md")) {
			return nil, errors.New("--output must be outside skill packages and collections")
		}
		if info, err := os.Lstat(cursor); err == nil && info.Mode()&(os.ModeSymlink|os.ModeIrregular) != 0 {
			return nil, fmt.Errorf("Symlink or reparse point in output path: %s", cursor)
		}
		if cursor == filepath.Dir(cursor) {
			break
		}
	}
	file, err := os.OpenFile(path, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o666)
	if errors.Is(err, os.ErrExist) {
		return nil, errors.New("--output already exists; choose a new file")
	}
	if err != nil {
		return nil, err
	}
	raw := []byte(jsonText(result, true, nil) + "\n")
	_, err = file.Write(raw)
	if err == nil {
		err = file.Sync()
	}
	if err := errors.Join(err, file.Close()); err != nil {
		return nil, err
	}
	return object{"output_file": path, "sha256": digest(raw), "summary": summary}, nil
}

func mapCopy(value object) object {
	result := object{}
	for key, child := range value {
		result[key] = child
	}
	return result
}

func pythonString(value string) string {
	quote := "'"
	if strings.Contains(value, "'") && !strings.Contains(value, "\"") {
		quote = "\""
	}
	value = strings.NewReplacer("\\", "\\\\", quote, "\\"+quote, "\r", `\r`, "\n", `\n`, "\t", `\t`).Replace(value)
	return quote + value + quote
}

func pythonList(strings []string) string {
	quoted := make([]string, len(strings))
	for i, value := range strings {
		quoted[i] = pythonString(value)
	}
	return "[" + joinComma(quoted) + "]"
}

func joinComma(parts []string) string { return strings.Join(parts, ", ") }
