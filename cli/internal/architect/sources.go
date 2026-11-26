package architect

import (
	"encoding/binary"
	"fmt"
	"io/fs"
	"os"
	"path"
	"path/filepath"
	"regexp"
	"strings"
)

var sourceComments = regexp.MustCompile(`"""[\s\S]*?"""|"(?:\\.|[^"\\])*"|/\*[\s\S]*?\*/|//[^\n]*`)
var sourcePackage = regexp.MustCompile(`(?m)^\s*package\s+([\pL\pN_.]+)`)
var sourceDeclaration = regexp.MustCompile(`\b(?:(abstract)\s+)?(class|interface|object)\s+[\pL\pN_]+`)

func sourceDescription(text, language string) record {
	clean := sourceComments.ReplaceAllString(text, " ")
	result := record{"package": "", "types": nil, "abstract": nil, "language": language}
	if found := sourcePackage.FindStringSubmatch(clean); len(found) > 0 {
		result["package"] = found[1]
	}
	if language == ".kt" {
		declarations := sourceDeclaration.FindAllStringSubmatch(clean, -1)
		abstract := 0
		for _, declaration := range declarations {
			if declaration[1] != "" || declaration[2] == "interface" {
				abstract++
			}
		}
		result["types"], result["abstract"] = len(declarations), abstract
	}
	return result
}

func matchesAny(name string, patterns []string) bool {
	for _, pattern := range patterns {
		// A fnmatch star includes slashes. The substitute supplies that semantic to path.Match.
		match, _ := path.Match(strings.ReplaceAll(pattern, "/", "\x00"), strings.ReplaceAll(name, "/", "\x00"))
		if match {
			return true
		}
	}
	return false
}

func readUTF8(filename string) (string, error) {
	data, err := os.ReadFile(filename)
	if err != nil {
		return "", fileError(err)
	}
	if err := validUTF8(data); err != nil {
		return "", err
	}
	return strings.TrimPrefix(string(data), "\ufeff"), nil
}

func inventory(config record, root string) (map[string]record, error) {
	sources := map[string]record{}
	patterns := stringsOf(config["exclude_paths"])
	for _, sourceRoot := range stringsOf(config["source_roots"]) {
		directory, err := resolve(joinPath(root, filepath.FromSlash(sourceRoot)))
		if err != nil {
			return nil, err
		}
		if !within(directory, root) || !isDir(directory) {
			return nil, fmt.Errorf("Source root must be an existing directory inside repository: %s", sourceRoot)
		}
		err = filepath.WalkDir(directory, func(filename string, entry fs.DirEntry, err error) error {
			if err != nil {
				return fileError(err)
			}
			language := filepath.Ext(filename)
			if (language != ".kt" && language != ".java") || !isFile(filename) {
				return nil
			}
			resolved, err := resolve(filename)
			if err != nil {
				return err
			}
			if !within(resolved, root) {
				return fmt.Errorf("Source symlink leaves repository: %s", filename)
			}
			relative, _ := filepath.Rel(root, filename)
			relative = filepath.ToSlash(relative)
			if matchesAny(relative, patterns) {
				return nil
			}
			text, err := readUTF8(filename)
			if err != nil {
				return err
			}
			sources[relative] = sourceDescription(text, language)
			return nil
		})
		if err != nil {
			return nil, err
		}
	}
	return sources, nil
}

func packageOf(name string) string {
	index := strings.LastIndexByte(name, '.')
	if index < 0 {
		return ""
	}
	return name[:index]
}

type classReader struct {
	data []byte
	err  error
}

func (reader *classReader) read(size int) []byte {
	if reader.err != nil {
		return nil
	}
	if size > len(reader.data) || size < 0 {
		reader.err = fmt.Errorf("Truncated JVM class file")
		return nil
	}
	value := reader.data[:size]
	reader.data = reader.data[size:]
	return value
}

func (reader *classReader) width(size int) int {
	data := reader.read(size)
	if data == nil {
		return 0
	}
	switch size {
	case 1:
		return int(data[0])
	case 2:
		return int(binary.BigEndian.Uint16(data))
	default:
		return int(binary.BigEndian.Uint32(data))
	}
}

func classSourceFile(data []byte) (string, string, error) {
	reader := classReader{data: data}
	magic := reader.width(4)
	if reader.err != nil {
		return "", "", reader.err
	}
	if uint32(magic) != 0xcafebabe {
		return "", "", fmt.Errorf("Invalid JVM class header")
	}
	reader.read(4)
	pool := map[int]string{}
	classes := map[int]int{}
	widths := map[int]int{3: 4, 4: 4, 5: 8, 6: 8, 8: 2, 9: 4, 10: 4, 11: 4, 12: 4, 15: 3, 16: 2, 17: 4, 18: 4, 19: 2, 20: 2}
	count := reader.width(2)
	for index := 1; index < count && reader.err == nil; index++ {
		tag := reader.width(1)
		switch tag {
		case 1:
			pool[index] = strings.ToValidUTF8(string(reader.read(reader.width(2))), "�")
		case 7:
			classes[index] = reader.width(2)
		default:
			if width, known := widths[tag]; known {
				reader.read(width)
			} else if reader.err == nil {
				return "", "", fmt.Errorf("Unsupported JVM constant tag %d", tag)
			}
		}
		if tag == 5 || tag == 6 {
			index++
		}
	}
	reader.read(2)
	classIndex := reader.width(2)
	name := strings.ReplaceAll(pool[classes[classIndex]], "/", ".")
	reader.read(2)
	reader.read(2 * reader.width(2))
	attributes := func() map[string][]byte {
		result := map[string][]byte{}
		count := reader.width(2)
		for index := 0; index < count && reader.err == nil; index++ {
			key := pool[reader.width(2)]
			result[key] = reader.read(reader.width(4))
		}
		return result
	}
	for range 2 {
		count := reader.width(2)
		for index := 0; index < count && reader.err == nil; index++ {
			reader.read(6)
			attributes()
		}
	}
	source := attributes()["SourceFile"]
	if reader.err != nil {
		return "", "", reader.err
	}
	if name == "" {
		return "", "", fmt.Errorf("%d", classIndex)
	}
	if len(source) == 0 {
		return name, "", nil
	}
	if len(source) != 2 {
		return "", "", fmt.Errorf("Invalid JVM SourceFile attribute")
	}
	return name, pool[int(binary.BigEndian.Uint16(source))], nil
}
