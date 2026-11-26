package setup

import (
	"bytes"
	"encoding/binary"
	"errors"
	"fmt"
	"io"
	"io/fs"
	"os"
	"path"
	"path/filepath"
	"regexp"
	"slices"
	"strings"
	"unicode/utf8"
)

type sourceFile struct {
	packageName string
	language    string
}

var kotlinComments = regexp.MustCompile(`(?s)""".*?"""|"(?:\\.|[^"\\])*"|/\*.*?\*/|//[^\n]*`)
var packageDeclaration = regexp.MustCompile(`(?m)^\s*package\s+([\p{L}\p{N}_.]+)`)

func collectionSources(project string, scope object) (map[string]sourceFile, error) {
	sources := map[string]sourceFile{}
	excluded := stringsIn(scope["exclude_paths"])
	for _, sourceRoot := range stringsIn(scope["source_roots"]) {
		directory := resolve(filepath.Join(project, filepath.FromSlash(sourceRoot)))
		if !isDir(directory) || !inside(project, directory) {
			return nil, fmt.Errorf("Source root must be an existing directory inside repository: %s", sourceRoot)
		}
		err := filepath.WalkDir(directory, func(file string, entry fs.DirEntry, err error) error {
			if err != nil {
				return err
			}
			extension := filepath.Ext(file)
			if (extension != ".kt" && extension != ".java") || !isFile(file) {
				return nil
			}
			if !inside(project, resolve(file)) {
				return fmt.Errorf("Source symlink leaves repository: %s", file)
			}
			relative, _ := filepath.Rel(project, file)
			relative = filepath.ToSlash(relative)
			if matchesPatterns(relative, excluded) {
				return nil
			}
			raw, err := os.ReadFile(file)
			if err != nil {
				return fileError(err)
			}
			if !utf8.Valid(raw) {
				return fmt.Errorf("Invalid UTF-8 in source %s", file)
			}
			packageName := ""
			clean := kotlinComments.ReplaceAllString(string(unbom(raw)), " ")
			if match := packageDeclaration.FindStringSubmatch(clean); match != nil {
				packageName = match[1]
			}
			sources[relative] = sourceFile{packageName, extension}
			return nil
		})
		if err != nil {
			return nil, err
		}
	}
	return sources, nil
}

func matchesPatterns(value string, patterns []string) bool {
	// Python's fnmatchcase treats slash like any other character. Substitute
	// a character that path.Match does not handle as a separator.
	const separator = "\x00"
	for _, pattern := range patterns {
		pattern = strings.ReplaceAll(pattern, "/", separator)
		pattern = strings.ReplaceAll(pattern, "[!", "[^")
		if match, _ := path.Match(pattern, strings.ReplaceAll(value, "/", separator)); match {
			return true
		}
	}
	return false
}

func admittedClass(name string, prefixes, excluded []string) bool {
	return slices.ContainsFunc(prefixes, func(prefix string) bool {
		return name == prefix || strings.HasPrefix(name, prefix+".")
	}) && !matchesPatterns(name, excluded)
}

func classMappings(project string, scope object, sources map[string]sourceFile) (map[string]string, error) {
	mappings := map[string]string{}
	lookup := map[[2]string][]string{}
	for _, path := range keys(sources) {
		key := [2]string{sources[path].packageName, filepath.Base(path)}
		lookup[key] = append(lookup[key], path)
	}
	type gap struct {
		class   string
		message string
	}
	gaps := []gap{}
	prefixes, excluded := stringsIn(scope["package_prefixes"]), stringsIn(scope["exclude_classes"])
	for _, directory := range stringsIn(scope["class_directories"]) {
		directory := resolve(filepath.Join(project, filepath.FromSlash(directory)))
		if !isDir(directory) {
			gaps = append(gaps, gap{message: "{'reason': " + pythonString("Missing compiled class directory: "+directory) + "}"})
			continue
		}
		err := filepath.WalkDir(directory, func(file string, entry fs.DirEntry, err error) error {
			if err != nil || filepath.Ext(file) != ".class" || entry.IsDir() {
				return err
			}
			raw, err := os.ReadFile(file)
			name, source := "", ""
			if err == nil {
				name, source, err = classSource(raw)
			}
			if err != nil {
				gaps = append(gaps, gap{message: "{'reason': " + pythonString(err.Error()) + ", 'class_file': " + pythonString(file) + "}"})
				return nil
			}
			if !admittedClass(name, prefixes, excluded) {
				return nil
			}
			packageName := ""
			if dot := strings.LastIndex(name, "."); dot >= 0 {
				packageName = name[:dot]
			}
			candidates := lookup[[2]string{packageName, source}]
			if len(candidates) != 1 {
				sourceValue := "None"
				if source != "" {
					sourceValue = pythonString(source)
				}
				gaps = append(gaps, gap{name, "{'class': " + pythonString(name) + ", 'source_file': " + sourceValue +
					", 'candidates': " + pythonList(candidates) + "}"})
				return nil
			}
			if previous := mappings[name]; previous != "" && previous != candidates[0] {
				return fmt.Errorf("Conflicting JVM class %s", name)
			}
			mappings[name] = candidates[0]
			return nil
		})
		if err != nil {
			return nil, err
		}
	}
	for _, name := range keys(asObject(scope["class_files"])) {
		file := asString(asObject(scope["class_files"])[name])
		relative, err := reportRelative(file, project)
		if err != nil {
			return nil, err
		}
		if _, found := sources[relative]; !found {
			return nil, fmt.Errorf("Explicit mapping is outside source inventory: %s -> %s", name, relative)
		}
		mappings[name] = relative
	}
	unresolved := []string{}
	for _, gap := range gaps {
		if gap.class == "" || mappings[gap.class] == "" {
			unresolved = append(unresolved, gap.message)
		}
	}
	if len(unresolved) != 0 {
		return nil, fmt.Errorf("Incomplete JVM source mapping: [%s]", joinComma(unresolved[:min(3, len(unresolved))]))
	}
	return mappings, nil
}

type classReader struct {
	reader *bytes.Reader
	err    error
}

func (reader *classReader) read(size int) []byte {
	if reader.err != nil {
		return nil
	}
	if size < 0 || size > reader.reader.Len() {
		reader.err = errors.New("Truncated JVM class file")
		return nil
	}
	result := make([]byte, size)
	_, reader.err = io.ReadFull(reader.reader, result)
	return result
}

func (reader *classReader) number(size int) int {
	value := reader.read(size)
	if value == nil {
		return 0
	}
	switch size {
	case 1:
		return int(value[0])
	case 2:
		return int(binary.BigEndian.Uint16(value))
	default:
		return int(binary.BigEndian.Uint32(value))
	}
}

func classSource(raw []byte) (string, string, error) {
	reader := &classReader{reader: bytes.NewReader(raw)}
	if header := reader.read(4); !bytes.Equal(header, []byte{0xca, 0xfe, 0xba, 0xbe}) {
		if reader.err != nil {
			return "", "", reader.err
		}
		return "", "", errors.New("Invalid JVM class header")
	}
	reader.read(4)
	count := reader.number(2)
	text, classes := map[int]string{}, map[int]int{}
	widths := map[int]int{3: 4, 4: 4, 5: 8, 6: 8, 8: 2, 9: 4, 10: 4, 11: 4, 12: 4,
		15: 3, 16: 2, 17: 4, 18: 4, 19: 2, 20: 2}
	for index := 1; index < count && reader.err == nil; index++ {
		switch tag := reader.number(1); tag {
		case 1:
			text[index] = strings.ToValidUTF8(string(reader.read(reader.number(2))), "\uFFFD")
		case 7:
			classes[index] = reader.number(2)
		default:
			if reader.err != nil {
				break
			}
			width, valid := widths[tag]
			if !valid {
				return "", "", fmt.Errorf("Unsupported JVM constant tag %d", tag)
			}
			reader.read(width)
			if tag == 5 || tag == 6 {
				index++
			}
		}
	}
	reader.read(2)
	name := strings.ReplaceAll(text[classes[reader.number(2)]], "/", ".")
	reader.read(2)
	reader.read(reader.number(2) * 2)
	readAttributes := func() string {
		source := ""
		for count := reader.number(2); count > 0 && reader.err == nil; count-- {
			key := text[reader.number(2)]
			size := reader.number(4)
			if key == "SourceFile" && size == 2 {
				source = text[reader.number(2)]
			} else {
				reader.read(size)
			}
		}
		return source
	}
	for range []string{"fields", "methods"} {
		for count := reader.number(2); count > 0 && reader.err == nil; count-- {
			reader.read(6)
			readAttributes()
		}
	}
	source := readAttributes()
	if reader.err != nil {
		return "", "", reader.err
	}
	if name == "" {
		return "", "", errors.New("Invalid JVM class name")
	}
	return name, source, nil
}
