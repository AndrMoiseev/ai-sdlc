package setup

import (
	"archive/zip"
	"embed"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"slices"
	"strconv"
	"strings"

	"go.yaml.in/yaml/v3"
)

//go:embed assets/detekt*.yml assets/detekt-project-rules.txt
var detektAssets embed.FS

const variableNameLimit = "naming.VariableMaxLength.maximumVariableNameLength"

func detekt(args arguments) (object, error) {
	root, err := filepath.EvalSymlinks(absolute(args.value("project-root")))
	if err != nil {
		return nil, fileError(err)
	}
	version := args.value("version")
	major, _, _ := strings.Cut(version, ".")
	reference := map[string]string{"1": "1.23.8", "2": "2.0.0-alpha.6"}[major]
	if reference == "" {
		return nil, fmt.Errorf("Unsupported detekt version: %s", version)
	}
	paths, standalone := repeated(args, "config"), args.has("standalone")
	if standalone && len(paths) == 0 {
		return nil, errors.New("Standalone mode requires a project configuration file")
	}
	common, err := detektTemplate("detekt.yml")
	if err != nil {
		return nil, err
	}
	groups := keys(common)
	defaults, err := detektConfig(args.value("defaults"))
	if err != nil {
		return nil, err
	}
	native, err := ruleSettings(defaults, groups)
	if err != nil {
		return nil, err
	}
	if len(native) == 0 {
		return nil, errors.New("No built-in rule settings found in the supplied detekt defaults")
	}
	template, err := ruleSettings(common, groups)
	if err != nil {
		return nil, err
	}
	overlay, err := detektTemplate("detekt-" + major + ".yml")
	if err != nil {
		return nil, err
	}
	additions, err := ruleSettings(overlay, groups)
	if err != nil {
		return nil, err
	}
	for key, value := range additions {
		template[key] = value
	}
	recommended := mapCopy(native)
	if version == reference {
		if !slices.Equal(keys(template), keys(native)) {
			return nil, fmt.Errorf("Rule list in the supplied defaults differs from detekt %s", version)
		}
		recommended = template
	} else {
		projectRules, _ := detektAssets.ReadFile("assets/detekt-project-rules.txt")
		for _, key := range strings.Fields(string(projectRules)) {
			value, ok := template[key]
			if _, present := native[key]; present && ok {
				recommended[key] = value
			}
		}
		for key := range native {
			parts := strings.Split(key, ".")
			if parts[0] == "coroutines" || strings.HasPrefix(parts[1], "Forbidden") {
				recommended[key] = false
			}
		}
	}
	if args.has("ktlint") {
		group := "ktlint"
		if major == "1" {
			group = "formatting"
		}
		groups = append(groups, group)
		native[group+".active"], recommended[group+".active"] = true, false
	}
	type projectSetting struct {
		value any
		path  string
	}
	explicit := map[string]projectSetting{}
	for _, path := range paths {
		path, err := filepath.EvalSymlinks(anchored(root, path))
		if err != nil {
			return nil, fileError(err)
		}
		config, err := detektConfig(path)
		if err != nil {
			return nil, err
		}
		settings, err := ruleSettings(config, groups)
		if err != nil {
			return nil, err
		}
		for key, value := range settings {
			explicit[key] = projectSetting{value, path}
		}
	}
	pin, differences := object{}, object{}
	matches := 0
	for key, wanted := range recommended {
		entry, found := explicit[key]
		if !found {
			entry.value = native[key]
			if standalone && strings.HasSuffix(key, ".active") {
				entry.value = strings.Count(key, ".") == 1
			}
		}
		switch {
		case entry.value != wanted:
			differences[key] = object{"current": entry.value, "recommended": wanted, "source": optionalText(entry.path)}
		case !found || !inside(root, entry.path):
			pin[key] = wanted
		default:
			matches++
		}
	}
	selected := sortedUnique(repeated(args, "accept"))
	if slices.Equal(selected, []string{"all"}) {
		selected = append(keys(pin), keys(differences)...)
	}
	unknown, edits := []string{}, object{}
	for _, key := range selected {
		value, found := recommended[key]
		if !found {
			unknown = append(unknown, key)
		} else if pin[key] != nil || differences[key] != nil {
			parts := strings.Split(key, ".")
			node := edits
			for _, part := range parts[:len(parts)-1] {
				if node[part] == nil {
					node[part] = object{}
				}
				node = asObject(node[part])
			}
			node[parts[len(parts)-1]] = value
		}
	}
	if len(unknown) > 0 {
		return nil, fmt.Errorf("Unknown detekt setting or invalid selection: %s", strings.Join(unknown, ", "))
	}
	return object{"project_root": root, "version": version, "explicit_matches": matches,
		"pin": pin, "differences": differences, "yaml_edits": edits}, nil
}

func detektTemplate(name string) (object, error) {
	raw, err := detektAssets.ReadFile("assets/" + name)
	if err != nil {
		return nil, err
	}
	return parseDetektConfig(raw, name)
}

func detektConfig(path string) (object, error) {
	var raw []byte
	var err error
	if strings.EqualFold(filepath.Ext(path), ".jar") {
		archive, err := zip.OpenReader(path)
		if err != nil {
			return nil, err
		}
		defer archive.Close()
		report, err := archive.Open("default-detekt-config.yml")
		if err != nil {
			return nil, errors.New("\"There is no item named 'default-detekt-config.yml' in the archive\"")
		}
		defer report.Close()
		raw, err = io.ReadAll(report)
		if err != nil {
			return nil, err
		}
	} else {
		raw, err = os.ReadFile(path)
		if err != nil {
			return nil, fileError(err)
		}
	}
	return parseDetektConfig(raw, path)
}

func parseDetektConfig(raw []byte, path string) (object, error) {
	var decoded any
	if err := yaml.Unmarshal(raw, &decoded); err != nil {
		return nil, err
	}
	if decoded == nil {
		return object{}, nil
	}
	config := asObject(decoded)
	if config == nil {
		return nil, fmt.Errorf("Expected a YAML mapping in %s", path)
	}
	return config, nil
}

func ruleSettings(config object, groups []string) (object, error) {
	result := object{}
	for _, group := range groups {
		if config[group] == nil {
			continue
		}
		section := asObject(config[group])
		if section == nil {
			return nil, fmt.Errorf("Expected a mapping at %s", group)
		}
		entries := map[string]object{group: section}
		for name, value := range section {
			if entry := asObject(value); entry != nil {
				entries[group+"."+name] = entry
			}
		}
		for _, name := range keys(entries) {
			entry := entries[name]
			if value, exists := entry["maximumVariableNameLength"]; name == "naming.VariableMaxLength" && exists {
				raw := fmt.Sprint(value)
				number, err := strconv.Atoi(raw)
				if err != nil {
					return nil, fmt.Errorf("invalid literal for int() with base 10: %s", pythonString(raw))
				}
				result[variableNameLimit] = number
			}
			if active := entry["active"]; active != nil {
				switch active {
				case true, "true":
					result[name+".active"] = true
				case false, "false":
					result[name+".active"] = false
				default:
					return nil, fmt.Errorf("Expected a boolean at %s.active", name)
				}
			}
		}
	}
	return result, nil
}
