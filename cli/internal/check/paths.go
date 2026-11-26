package check

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"slices"
	"strings"
	"unicode"
)

// Resolve the existing prefix as well as the lexical path. A missing final file
// is a valid input to this function: its reader owns the missing-file diagnostic.
func containedPath(root, relative string) (string, *checkError) {
	if relative == "" {
		return "", &checkError{Code: "invalid_path", Message: "Expected a nonempty relative path", Exit: 1}
	}
	if !filepath.IsLocal(relative) || strings.ContainsAny(relative, "\\:") || slices.Contains(strings.Split(relative, "/"), "..") {
		return "", &checkError{Code: "path_escape", Message: "Path must stay under its root: " + relative, Exit: 1}
	}
	path := root
	for _, part := range strings.Split(filepath.ToSlash(filepath.Clean(relative)), "/") {
		path = filepath.Join(path, part)
		info, err := os.Lstat(path)
		if errors.Is(err, os.ErrNotExist) {
			continue
		}
		if err != nil {
			return "", fileError(path, err)
		}
		if info.Mode()&os.ModeSymlink != 0 || info.Mode()&os.ModeIrregular != 0 {
			resolved, err := filepath.EvalSymlinks(path)
			if err != nil {
				return "", fileError(path, err)
			}
			rel, err := filepath.Rel(root, resolved)
			if err != nil || !filepath.IsLocal(rel) {
				return "", &checkError{Code: "path_escape", Message: "Path escapes its root: " + relative, Path: path, Exit: 1}
			}
			path = resolved
		}
	}
	return path, nil
}

// The Python API includes the filename's repr in its public error message.
func missingFileMessage(path string) string {
	quote := '\''
	if strings.ContainsRune(path, '\'') && !strings.ContainsRune(path, '"') {
		quote = '"'
	}
	var message strings.Builder
	message.WriteString("[Errno 2] No such file or directory: ")
	message.WriteRune(quote)
	for _, r := range path {
		switch {
		case r == '\\' || r == quote:
			message.WriteByte('\\')
			message.WriteRune(r)
		case r == '\t':
			message.WriteString("\\t")
		case r == '\n':
			message.WriteString("\\n")
		case r == '\r':
			message.WriteString("\\r")
		case unicode.IsPrint(r):
			message.WriteRune(r)
		case r < 0x100:
			fmt.Fprintf(&message, "\\x%02x", r)
		case r <= 0xffff:
			fmt.Fprintf(&message, "\\u%04x", r)
		default:
			fmt.Fprintf(&message, "\\U%08x", r)
		}
	}
	message.WriteRune(quote)
	return message.String()
}
