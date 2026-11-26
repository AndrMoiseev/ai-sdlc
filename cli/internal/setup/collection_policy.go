package setup

import (
	_ "embed"
	"encoding/json"
	"errors"
	"fmt"
	"math"
	"path/filepath"
)

//go:embed assets/analysis-policy.json
var defaultPolicy []byte

//go:embed assets/analysis-policy.schema.json
var policySchema []byte

func collectionPolicy(project string) (object, error) {
	value, _ := decodeJSON(defaultPolicy, nil)
	rule, _ := decodeJSON(policySchema, nil)
	base, schema := asObject(value), asObject(rule)
	path := filepath.Join(project, ".sdd", "architect", "analysis-policy.json")
	raw, err := optionalBytes(path)
	if err != nil {
		return nil, err
	}
	if raw == nil {
		return base, nil
	}
	overrides, err := decodeJSON(raw, nil)
	if err != nil {
		return nil, fmt.Errorf("%s: %s", path, err)
	}
	if err := validatePolicy(overrides, schema, "analysis_policy"); err != nil {
		return nil, err
	}
	mergePolicy(base, asObject(overrides))
	effect := asObject(asObject(base["recommendations"])["effect_points"])
	if !((decimal(effect["not_shown"]) < decimal(effect["local"])) && decimal(effect["local"]) < decimal(effect["substantial"])) {
		return nil, errors.New("analysis_policy.recommendations.effect_points: require not_shown < local < substantial")
	}
	family := asObject(asObject(base["investigation"])["family_points"])
	if decimal(family["limited"]) > decimal(family["usable"]) {
		return nil, errors.New("analysis_policy.investigation.family_points: limited must not exceed usable")
	}
	return base, nil
}

func mergePolicy(base, overrides object) {
	for key, value := range overrides {
		if child := asObject(value); child != nil {
			mergePolicy(asObject(base[key]), child)
		} else {
			base[key] = value
		}
	}
}

func validatePolicy(value any, rule object, path string) error {
	kind := asString(rule["type"])
	if kind == "object" {
		fields := asObject(value)
		if fields == nil {
			return fmt.Errorf("%s: expected object", path)
		}
		properties := asObject(rule["properties"])
		if unknown := unknownKeys(fields, keys(properties)); len(unknown) != 0 {
			return fmt.Errorf("%s: unknown keys %s", path, pythonList(unknown))
		}
		for _, name := range keys(fields) {
			if err := validatePolicy(fields[name], asObject(properties[name]), path+"."+name); err != nil {
				return err
			}
		}
		return nil
	}
	number := decimal(value)
	if math.IsNaN(number) || math.IsInf(number, 0) || (kind == "integer" && math.Trunc(number) != number) {
		return fmt.Errorf("%s: expected finite %s", path, kind)
	}
	invalid := map[string]func(float64) bool{
		"minimum":          func(limit float64) bool { return number < limit },
		"maximum":          func(limit float64) bool { return number > limit },
		"exclusiveMinimum": func(limit float64) bool { return number <= limit },
		"const":            func(limit float64) bool { return number != limit },
	}
	for _, keyword := range []string{"minimum", "maximum", "exclusiveMinimum", "const"} {
		if limit, exists := rule[keyword]; exists && invalid[keyword](decimal(limit)) {
			return fmt.Errorf("%s: must satisfy %s %v", path, keyword, limit)
		}
	}
	return nil
}

func decimal(value any) float64 {
	if number, ok := value.(json.Number); ok {
		if parsed, err := number.Float64(); err == nil {
			return parsed
		}
	}
	return math.NaN()
}
