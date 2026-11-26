package apply

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"unicode/utf16"
	"unicode/utf8"
)

type mapping = map[string]any

type rejection struct {
	code, message string
}

func (e rejection) Error() string { return e.message }

func reject(code, message string) error { return rejection{code, message} }

func decode(raw []byte) (any, error) {
	if !utf8.Valid(raw) {
		return nil, fmt.Errorf("Invalid UTF-8 JSON")
	}
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.UseNumber()
	var value any
	if err := decoder.Decode(&value); err != nil {
		return nil, err
	}
	var extra any
	if err := decoder.Decode(&extra); !errors.Is(err, io.EOF) {
		return nil, fmt.Errorf("Extra data after JSON value")
	}
	return value, nil
}

func jsonBytes(value any, indent string) ([]byte, error) {
	var data bytes.Buffer
	encoder := json.NewEncoder(&data)
	encoder.SetEscapeHTML(false)
	encoder.SetIndent("", indent)
	if err := encoder.Encode(value); err != nil {
		return nil, err
	}
	return bytes.TrimSuffix(data.Bytes(), []byte("\n")), nil
}

// Python's canonical JSON uses escaped non-ASCII, including supplementary
// code points as surrogate pairs. Execution hashes use these exact bytes.
func ascii(raw []byte) []byte {
	var encoded bytes.Buffer
	for len(raw) != 0 {
		r, width := utf8.DecodeRune(raw)
		raw = raw[width:]
		switch {
		case r < 127:
			encoded.WriteByte(byte(r))
		case r <= 0xffff:
			fmt.Fprintf(&encoded, "\\u%04x", r)
		default:
			high, low := utf16.EncodeRune(r)
			fmt.Fprintf(&encoded, "\\u%04x\\u%04x", high, low)
		}
	}
	return encoded.Bytes()
}

func canonical(value any) ([]byte, error) {
	raw, err := jsonBytes(normalizeNumbers(value), "")
	if err != nil {
		return nil, err
	}
	return ascii(raw), nil
}

func normalizeNumbers(value any) any {
	switch value := value.(type) {
	case mapping:
		result := make(mapping, len(value))
		for key, item := range value {
			result[key] = normalizeNumbers(item)
		}
		return result
	case []any:
		result := make([]any, len(value))
		for index, item := range value {
			result[index] = normalizeNumbers(item)
		}
		return result
	case json.Number:
		raw := string(value)
		if !strings.ContainsAny(raw, ".eE") {
			if raw == "-0" {
				return json.Number("0")
			}
			return value
		}
		number, err := value.Float64()
		if err != nil {
			return value
		}
		return pythonFloat(number)
	case float64:
		return pythonFloat(value)
	default:
		return value
	}
}

func pythonFloat(number float64) json.Number {
	if math.Abs(number) >= 1e16 || number != 0 && math.Abs(number) < 1e-4 {
		return json.Number(strconv.FormatFloat(number, 'e', -1, 64))
	}
	raw := strconv.FormatFloat(number, 'f', -1, 64)
	if !strings.Contains(raw, ".") {
		raw += ".0"
	}
	return json.Number(raw)
}

func digest(value any) string {
	data, ok := value.([]byte)
	if !ok {
		data, _ = canonical(value)
	}
	sum := sha256.Sum256(data)
	return hex.EncodeToString(sum[:])
}

func readJSON(path string) (any, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, fileError(err, path)
	}
	return decode(raw)
}

func fileError(err error, path string) error {
	switch {
	case errors.Is(err, os.ErrNotExist):
		return fmt.Errorf("[Errno 2] No such file or directory: %s", pythonQuote(path))
	case errors.Is(err, os.ErrPermission):
		return fmt.Errorf("[Errno 13] Permission denied: %s", pythonQuote(path))
	default:
		return err
	}
}

func pythonQuote(text string) string {
	quote := "'"
	if strings.Contains(text, "'") && !strings.Contains(text, "\"") {
		quote = "\""
	}
	text = strings.NewReplacer("\\", "\\\\", "\n", "\\n", "\r", "\\r", "\t", "\\t", quote, "\\"+quote).Replace(text)
	return quote + text + quote
}

func atomicWrite(path string, data []byte) error {
	directory := filepath.Dir(path)
	if err := os.MkdirAll(directory, 0o755); err != nil {
		return err
	}
	file, err := os.CreateTemp(directory, ".write-")
	if err != nil {
		return err
	}
	defer os.Remove(file.Name())
	if _, err = file.Write(data); err == nil {
		err = file.Sync()
	}
	closeErr := file.Close()
	if err != nil {
		return err
	}
	if closeErr != nil {
		return closeErr
	}
	return fileError(os.Rename(file.Name(), path), path)
}

func writeJSON(path string, value any) error {
	// Preserve integral floats such as a 90.0-second timeout. Otherwise
	// re-reading the manifest changes the canonical bytes used for integrity.
	raw, err := jsonBytes(normalizeNumbers(value), "  ")
	if err != nil {
		return err
	}
	return atomicWrite(path, append(ascii(raw), '\n'))
}

func object(value any) mapping {
	result, _ := value.(mapping)
	return result
}

func array(value any) []any {
	result, _ := value.([]any)
	return result
}

func str(value any) string {
	result, _ := value.(string)
	return result
}

func integer(value any) (int, bool) {
	switch value := value.(type) {
	case int:
		return value, true
	case json.Number:
		number, err := strconv.Atoi(string(value))
		return number, err == nil
	default:
		return 0, false
	}
}

func intValue(value any) int {
	number, _ := integer(value)
	return number
}

func truth(value any) bool {
	switch value := value.(type) {
	case nil:
		return false
	case bool:
		return value
	case string:
		return value != ""
	case mapping:
		return len(value) != 0
	case []any:
		return len(value) != 0
	case []string:
		return len(value) != 0
	case int:
		return value != 0
	case json.Number:
		number, _ := value.Float64()
		return number != 0
	default:
		return true
	}
}

func selectFields(value mapping, keys ...string) mapping {
	result := make(mapping, len(keys))
	for _, key := range keys {
		result[key] = value[key]
	}
	return result
}
