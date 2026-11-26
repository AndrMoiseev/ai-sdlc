package architect

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"runtime"
	"sort"
	"strings"
	"time"
	"unicode/utf8"
)

type record = map[string]any

func object(value any) record { result, _ := value.(map[string]any); return result }
func items(value any) []any   { result, _ := value.([]any); return result }
func str(value any) string    { result, _ := value.(string); return result }

func stringsOf(value any) []string {
	if result, ok := value.([]string); ok {
		return result
	}
	result := []string{}
	for _, item := range items(value) {
		result = append(result, str(item))
	}
	return result
}

func keys[V any](value map[string]V) []string {
	result := make([]string, 0, len(value))
	for key := range value {
		result = append(result, key)
	}
	sort.Strings(result)
	return result
}

func keyDiff[V, W any](source map[string]V, other map[string]W) []string {
	result := []string{}
	for _, key := range keys(source) {
		if _, found := other[key]; !found {
			result = append(result, key)
		}
	}
	return result
}

func contains(values []string, value string) bool {
	for _, item := range values {
		if item == value {
			return true
		}
	}
	return false
}

func quoted(value string) string {
	delimiter := "'"
	if strings.Contains(value, "'") && !strings.Contains(value, `"`) {
		delimiter = `"`
	}
	value = strings.NewReplacer(`\`, `\\`, "\n", `\n`, "\r", `\r`, "\t", `\t`, delimiter, `\`+delimiter).Replace(value)
	return delimiter + value + delimiter
}

func pythonList(values []string) string {
	list := make([]string, 0, len(values))
	for _, value := range values {
		list = append(list, quoted(value))
	}
	return "[" + strings.Join(list, ", ") + "]"
}

func display(value any) string {
	switch value := value.(type) {
	case nil:
		return "None"
	case bool:
		if value {
			return "True"
		}
		return "False"
	default:
		return fmt.Sprint(value)
	}
}

func fileError(err error) error {
	var failure *os.PathError
	if !errors.As(err, &failure) {
		return err
	}
	switch {
	case errors.Is(err, os.ErrNotExist):
		return fmt.Errorf("[Errno 2] No such file or directory: %s", quoted(failure.Path))
	case errors.Is(err, os.ErrPermission):
		return fmt.Errorf("[Errno 13] Permission denied: %s", quoted(failure.Path))
	default:
		return err
	}
}

func encodeJSON(value any, pretty bool) ([]byte, error) {
	var output bytes.Buffer
	encoder := json.NewEncoder(&output)
	encoder.SetEscapeHTML(false)
	if pretty {
		encoder.SetIndent("", "  ")
	}
	err := encoder.Encode(value)
	return output.Bytes(), err
}

func printJSON(writer io.Writer, value any, pretty bool) error {
	data, err := encodeJSON(value, pretty)
	if err != nil {
		return err
	}
	_, err = writer.Write(data)
	return err
}

type jsonDocument struct {
	value any
	text  []byte
}

var utf8BOM = []byte{0xef, 0xbb, 0xbf}

func validUTF8(data []byte) error {
	for offset := 0; offset < len(data); {
		character, size := utf8.DecodeRune(data[offset:])
		if character != utf8.RuneError || size != 1 {
			offset += size
			continue
		}
		lead := data[offset]
		width := 0
		switch {
		case 0xc2 <= lead && lead <= 0xdf:
			width = 2
		case 0xe0 <= lead && lead <= 0xef:
			width = 3
		case 0xf0 <= lead && lead <= 0xf4:
			width = 4
		}
		reason, end := "invalid start byte", offset+1
		if width > 0 {
			reason = "unexpected end of data"
			for end < min(offset+width, len(data)) {
				continuation := data[end]
				if continuation < 0x80 || continuation > 0xbf || end == offset+1 &&
					((lead == 0xe0 && continuation < 0xa0) || (lead == 0xed && continuation >= 0xa0) ||
						(lead == 0xf0 && continuation < 0x90) || (lead == 0xf4 && continuation >= 0x90)) {
					reason = "invalid continuation byte"
					break
				}
				end++
			}
		}
		if end == offset+1 {
			return fmt.Errorf("'utf-8' codec can't decode byte 0x%02x in position %d: %s", lead, offset, reason)
		}
		return fmt.Errorf("'utf-8' codec can't decode bytes in position %d-%d: %s", offset, end-1, reason)
	}
	return nil
}

func parseJSONValue(data []byte) (any, error) {
	data = bytes.TrimPrefix(data, utf8BOM)
	if !utf8.Valid(data) {
		return nil, validUTF8(data)
	}
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.UseNumber()
	var value, trailing any
	if decoder.Decode(&value) == nil && decoder.Decode(&trailing) == io.EOF {
		return value, nil
	}
	// Translate syntax errors at the command boundary using the original bytes.
	doc, err := parseDocument(data, "")
	return doc.value, err
}

func readDocument(filename, duplicateMessage string) (jsonDocument, error) {
	data, err := os.ReadFile(filename)
	if err != nil {
		return jsonDocument{}, fileError(err)
	}
	return parseDocument(data, duplicateMessage)
}

func parseDocument(data []byte, duplicateMessage string) (jsonDocument, error) {
	data = bytes.TrimPrefix(data, utf8BOM)
	if !utf8.Valid(data) {
		return jsonDocument{}, validUTF8(data)
	}
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.UseNumber()
	var formatted bytes.Buffer
	duplicate := false
	var consume func(int, bool) (any, error)
	consume = func(level int, property bool) (any, error) {
		token, err := decoder.Token()
		if err != nil {
			return nil, jsonSyntaxError(data, decoder.InputOffset(), property, err)
		}
		switch token {
		case json.Delim('{'), json.Delim('['):
			isObject := token == json.Delim('{')
			formatted.WriteRune(rune(token.(json.Delim)))
			objectValue, array := record{}, []any{}
			count := 0
			for decoder.More() {
				if count > 0 {
					formatted.WriteByte(',')
				}
				count++
				formatted.WriteString("\n" + strings.Repeat("  ", level+1))
				if isObject {
					key, err := decoder.Token()
					if err != nil {
						return nil, jsonSyntaxError(data, decoder.InputOffset(), true, err)
					}
					name, ok := key.(string)
					if !ok {
						return nil, jsonSyntaxError(data, decoder.InputOffset(), true, nil)
					}
					writeJSONString(&formatted, name)
					formatted.WriteString(": ")
					value, err := consume(level+1, false)
					if err != nil {
						return nil, err
					}
					if _, found := objectValue[name]; found {
						if duplicateMessage != "" {
							return nil, fmt.Errorf("%s: %s", duplicateMessage, name)
						}
						duplicate = true
					}
					objectValue[name] = value
				} else {
					value, err := consume(level+1, false)
					if err != nil {
						return nil, err
					}
					array = append(array, value)
				}
			}
			closing, err := decoder.Token()
			if err != nil {
				return nil, jsonSyntaxError(data, decoder.InputOffset(), isObject && count == 0, err)
			}
			if count > 0 {
				formatted.WriteString("\n" + strings.Repeat("  ", level))
			}
			formatted.WriteRune(rune(closing.(json.Delim)))
			if isObject {
				return objectValue, nil
			}
			return array, nil
		case nil:
			formatted.WriteString("null")
			return token, nil
		default:
			if value, okay := token.(string); okay {
				writeJSONString(&formatted, value)
			} else {
				fmt.Fprint(&formatted, token)
			}
			return token, nil
		}
	}
	value, err := consume(0, false)
	if err != nil {
		return jsonDocument{}, err
	}
	if offset := skipWhitespace(data, decoder.InputOffset()); offset < int64(len(data)) {
		return jsonDocument{}, jsonPosition(data, offset, "Extra data")
	}
	if duplicate {
		encoded, err := encodeJSON(value, true)
		return jsonDocument{value, encoded}, err
	}
	formatted.WriteByte('\n')
	return jsonDocument{value, formatted.Bytes()}, nil
}

func writeJSONString(output *bytes.Buffer, value string) {
	output.WriteByte('"')
	for _, character := range value {
		switch character {
		case '"', '\\':
			output.WriteByte('\\')
			output.WriteRune(character)
		case '\b':
			output.WriteString(`\b`)
		case '\f':
			output.WriteString(`\f`)
		case '\n':
			output.WriteString(`\n`)
		case '\r':
			output.WriteString(`\r`)
		case '\t':
			output.WriteString(`\t`)
		default:
			if character < 32 {
				fmt.Fprintf(output, `\u%04x`, character)
			} else {
				output.WriteRune(character)
			}
		}
	}
	output.WriteByte('"')
}

func skipWhitespace(data []byte, offset int64) int64 {
	for offset < int64(len(data)) && strings.ContainsRune(" \t\n\r", rune(data[offset])) {
		offset++
	}
	return offset
}

func jsonSyntaxError(data []byte, offset int64, property bool, cause error) error {
	if cause != nil {
		switch diagnostic := cause.Error(); {
		case strings.Contains(diagnostic, "after object key:value pair"), strings.Contains(diagnostic, "after array element"):
			return jsonPosition(data, skipWhitespace(data, offset), "Expecting ',' delimiter")
		case strings.Contains(diagnostic, "after object key"):
			return jsonPosition(data, skipWhitespace(data, offset), "Expecting ':' delimiter")
		case strings.Contains(diagnostic, "looking for beginning of object key string"):
			property = true
		}
	}
	for offset < int64(len(data)) && strings.ContainsRune(" \t\n\r,:", rune(data[offset])) {
		offset++
	}
	remaining := string(data[offset:])
	for _, constant := range []string{"NaN", "Infinity", "-Infinity"} {
		if strings.HasPrefix(remaining, constant) {
			return fmt.Errorf("Non-finite JSON value: %s", constant)
		}
	}
	message := "Expecting value"
	if property {
		message = "Expecting property name enclosed in double quotes"
	}
	return jsonPosition(data, offset, message)
}

func jsonPosition(data []byte, offset int64, message string) error {
	prefix := data[:offset]
	line := bytes.Count(prefix, []byte{'\n'}) + 1
	column := 1 + utf8.RuneCount(prefix[bytes.LastIndexByte(prefix, '\n')+1:])
	return fmt.Errorf("%s: line %d column %d (char %d)", message, line, column, utf8.RuneCount(prefix))
}

func readObject(path string) (record, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fileError(err)
	}
	parsed, err := parseJSONValue(data)
	if err != nil {
		return nil, err
	}
	value := object(parsed)
	if value == nil {
		return nil, fmt.Errorf("expected a JSON object")
	}
	return value, nil
}

// resolve follows existing ancestors, including links in paths to future outputs.
func resolve(path string) (string, error) {
	absolute, err := filepath.Abs(path)
	if err != nil {
		return "", err
	}
	return resolveAbsolute(absolute, 0)
}

func resolveAbsolute(path string, depth int) (string, error) {
	if depth > 255 {
		return "", fmt.Errorf("Symbolic link loop: %s", path)
	}
	full, err := filepath.EvalSymlinks(path)
	if err == nil {
		return full, nil
	}
	if !errors.Is(err, os.ErrNotExist) {
		return "", fileError(err)
	}
	if target, err := os.Readlink(path); err == nil {
		return resolveAbsolute(joinPath(filepath.Dir(path), target), depth+1)
	}
	parent := filepath.Dir(path)
	if parent == path {
		return path, nil
	}
	resolved, err := resolveAbsolute(parent, depth+1)
	return filepath.Join(resolved, filepath.Base(path)), err
}

func joinPath(root, path string) string {
	if filepath.IsAbs(path) {
		return path
	}
	return filepath.Join(root, path)
}

func within(path, parent string) bool {
	relative, err := filepath.Rel(parent, path)
	return err == nil && relative != ".." && !strings.HasPrefix(relative, ".."+string(filepath.Separator))
}

func exists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}

func isDir(path string) bool {
	stat, err := os.Stat(path)
	return err == nil && stat.IsDir()
}

func isFile(path string) bool {
	stat, err := os.Stat(path)
	return err == nil && stat.Mode().IsRegular()
}

var auditDate = regexp.MustCompile(`^\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}(?:\.\d{1,6})?Z$`)

func reportOutput(path, repository string, directory bool) (string, error) {
	path, err := resolve(path)
	if err != nil {
		return "", err
	}
	for _, part := range strings.Split(filepath.ToSlash(path), "/") {
		if contains([]string{".agents", ".claude", ".codex", "skills"}, part) {
			return "", fmt.Errorf("Write reports outside skill collections")
		}
	}
	if repository == "" {
		return "", fmt.Errorf("A project repository is required for report output")
	}
	root, err := resolve(repository)
	if err != nil {
		return "", err
	}
	audits := filepath.Join(root, "memory", "tech-debt", "audits")
	if !within(path, audits) || path == audits || (!directory && filepath.Dir(path) == audits) {
		return "", fmt.Errorf("Write outputs inside <project-root>/memory/tech-debt/audits/<date-time>/")
	}
	relative, err := filepath.Rel(audits, path)
	if err != nil {
		return "", err
	}
	audit := strings.Split(filepath.ToSlash(relative), "/")[0]
	if !auditDate.MatchString(audit) {
		return "", fmt.Errorf("Audit directory needs a UTC date-time: YYYY-MM-DDTHH-mm-ss[.ffffff]Z")
	}
	if _, err := time.Parse("2006-01-02T15-04-05.999999Z", audit); err != nil || strings.HasPrefix(audit, "0000-") {
		return "", fmt.Errorf("Invalid audit date-time: %s", audit)
	}
	return path, nil
}

func writeText(path string, data []byte, exclusive bool, nativeNewlines bool) error {
	if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
		return fileError(err)
	}
	flags := os.O_WRONLY | os.O_CREATE | os.O_TRUNC
	if exclusive {
		flags = os.O_WRONLY | os.O_CREATE | os.O_EXCL
	}
	file, err := os.OpenFile(path, flags, 0666)
	if err != nil {
		return fileError(err)
	}
	if nativeNewlines && runtime.GOOS == "windows" {
		data = bytes.ReplaceAll(data, []byte{'\n'}, []byte{'\r', '\n'})
	}
	_, err = file.Write(data)
	return errors.Join(fileError(err), fileError(file.Close()))
}
