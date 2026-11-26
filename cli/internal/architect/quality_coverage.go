package architect

import (
	"encoding/xml"
	"fmt"
	"math"
	"path"
	"sort"
	"strings"
)

type sourceLine struct {
	path   string
	number int
}

func coverageMethods(text string, sources map[string]record, mappings map[string]string) ([]record, map[sourceLine]bool, error) {
	var report struct {
		XMLName xml.Name
		jacocoReport
	}
	if err := xml.Unmarshal([]byte(text), &report); err != nil {
		return nil, nil, err
	}
	if report.XMLName.Space != "" || report.XMLName.Local != "report" {
		return nil, nil, fmt.Errorf("Coverage input must be a complete JaCoCo XML report")
	}
	methods, lines := []record{}, map[sourceLine]bool{}
	methodKeys, classes := map[[3]string]bool{}, map[string]bool{}
	lookup := map[[2]string][]string{}
	for _, file := range keys(sources) {
		source := sources[file]
		key := [2]string{strings.ReplaceAll(str(source["package"]), ".", "/"), path.Base(file)}
		lookup[key] = append(lookup[key], file)
	}
	for _, pack := range report.allPackages() {
		for _, source := range pack.Sources {
			paths := lookup[[2]string{pack.Name, source.Name}]
			if len(paths) > 1 {
				return nil, nil, fmt.Errorf("Ambiguous JaCoCo source file; provide a single selected source-set report")
			}
			if len(paths) == 0 {
				continue
			}
			file := paths[0]
			covered, err := addSourceLines(lines, file, source.Lines)
			if err != nil {
				return nil, nil, err
			}
			if err := checkLineCounter(file, source.Counters, covered, len(source.Lines)-covered); err != nil {
				return nil, nil, err
			}
		}
		for _, class := range pack.Classes {
			name := strings.ReplaceAll(class.Name, "/", ".")
			file := mappings[name]
			if sources[file] == nil {
				continue
			}
			if classes[name] {
				return nil, nil, fmt.Errorf("Duplicate JaCoCo class; merge execution data before XML export")
			}
			classes[name] = true
			for _, method := range class.Methods {
				row, err := measureMethod(name, file, method)
				if err != nil {
					return nil, nil, err
				}
				key := [3]string{name, method.Name, method.Desc}
				if methodKeys[key] {
					return nil, nil, fmt.Errorf("Duplicate JaCoCo method identity")
				}
				methodKeys[key] = true
				methods = append(methods, row)
			}
		}
	}
	return methods, lines, nil
}

func addSourceLines(lines map[sourceLine]bool, file string, rows []jacocoLine) (int, error) {
	covered := 0
	for _, line := range rows {
		number, err := reportInt(line.Number)
		if err != nil {
			return 0, err
		}
		key := sourceLine{file, number}
		if _, exists := lines[key]; exists {
			return 0, fmt.Errorf("Duplicate JaCoCo source line; merge execution data before XML export")
		}
		coveredInstructions, err := reportInt(line.Covered)
		if err != nil {
			return 0, err
		}
		missed, err := reportInt(line.Missed)
		if err != nil {
			return 0, err
		}
		if number < 1 || coveredInstructions < 0 || missed < 0 || coveredInstructions+missed == 0 {
			return 0, fmt.Errorf("Invalid JaCoCo executable source line")
		}
		lines[key] = coveredInstructions > 0
		if lines[key] {
			covered++
		}
	}
	return covered, nil
}

func checkLineCounter(file string, counters []jacocoCounter, covered, missed int) error {
	var matched *jacocoCounter
	for index := range counters {
		if counters[index].Type == "LINE" {
			if matched != nil {
				return fmt.Errorf("Duplicate JaCoCo sourcefile LINE counter for %s", file)
			}
			matched = &counters[index]
		}
	}
	if matched == nil {
		return nil
	}
	declaredCovered, err := reportInt(matched.Covered)
	if err != nil {
		return err
	}
	declaredMissed, err := reportInt(matched.Missed)
	if err != nil {
		return err
	}
	if declaredCovered != covered || declaredMissed != missed {
		return fmt.Errorf("JaCoCo LINE counter mismatch for %s: declared covered/missed (%d, %d), line records give (%d, %d)",
			file, declaredCovered, declaredMissed, covered, missed)
	}
	return nil
}

func measureMethod(className, file string, method jacocoMethod) (record, error) {
	counters := map[string][2]int{}
	for _, counter := range method.Counters {
		if _, found := counters[counter.Type]; found {
			return nil, fmt.Errorf("Duplicate JaCoCo method counter")
		}
		covered, err := reportInt(counter.Covered)
		if err != nil {
			return nil, err
		}
		missed, err := reportInt(counter.Missed)
		if err != nil {
			return nil, err
		}
		if covered < 0 || missed < 0 {
			return nil, fmt.Errorf("Negative JaCoCo method counter")
		}
		counters[counter.Type] = [2]int{covered, covered + missed}
	}
	instructions, instructionFound := counters["INSTRUCTION"]
	complexity, complexityFound := counters["COMPLEXITY"]
	if !instructionFound || !complexityFound {
		return nil, fmt.Errorf("Incomplete JaCoCo method counters: %s.%s", className, method.Name)
	}
	if instructions[1] == 0 || complexity[1] == 0 {
		return nil, fmt.Errorf("JaCoCo executable method has zero instructions or complexity")
	}
	branches := counters["BRANCH"]
	execution := float64(instructions[0]) / float64(instructions[1])
	if branches[1] > 0 {
		execution = min(execution, float64(branches[0])/float64(branches[1]))
	}
	excess := float64(complexity[1]*complexity[1]) * math.Pow(1-execution, 3)
	return record{"class": className, "method": method.Name, "descriptor": method.Desc, "file": file,
		"instructions": instructions[0], "total_instructions": instructions[1], "branches": branches[0], "total_branches": branches[1],
		"complexity": complexity[1], "crap_exec": float64(complexity[1]) + excess, "excess": excess}, nil
}

func coverageSummary(paths map[string]bool, methods []record, lines map[sourceLine]bool, tokens int) record {
	var excess, crap preciseSum
	selected, values := []record{}, []float64{}
	instruction, totalInstructions, branches, totalBranches, squared := 0, 0, 0, 0, 0
	for _, row := range methods {
		if !paths[str(row["file"])] {
			continue
		}
		selected = append(selected, row)
		excess.add(numeric(row["excess"]))
		value := numeric(row["crap_exec"])
		crap.add(value)
		values = append(values, value)
		complexity := integer(row["complexity"])
		squared += complexity * complexity
		instruction += integer(row["instructions"])
		totalInstructions += integer(row["total_instructions"])
		branches += integer(row["branches"])
		totalBranches += integer(row["total_branches"])
	}
	measured := map[string]bool{}
	coveredLines, totalLines := 0, 0
	for line, covered := range lines {
		if paths[line.path] {
			measured[line.path] = true
			totalLines++
			if covered {
				coveredLines++
			}
		}
	}
	lineCoverage := qualityFraction(coveredLines, totalLines)
	omitted := keyDiff(paths, measured)
	lineCoverage["omitted_files"] = omitted
	if len(omitted) > 0 {
		lineCoverage["status"] = "unknown"
		if totalLines > 0 {
			lineCoverage["status"] = "measured_subset"
		}
	}
	var density, ecrap, p95 any
	excessSum := excess.total()
	if tokens > 0 {
		density = 1000 * excessSum / float64(tokens)
	}
	if squared > 0 {
		ecrap = 100 * excessSum / float64(squared)
	}
	if len(values) > 0 {
		sort.Float64s(values)
		p95 = values[max(0, int(math.Ceil(.95*float64(len(values))))-1)]
	}
	sort.SliceStable(selected, func(i, j int) bool {
		a, b := selected[i], selected[j]
		if a["excess"] != b["excess"] {
			return numeric(a["excess"]) > numeric(b["excess"])
		}
		for _, key := range []string{"class", "method", "descriptor"} {
			if a[key] != b[key] {
				return str(a[key]) < str(b[key])
			}
		}
		return false
	})
	return record{"method_count": len(selected), "branch": qualityFraction(branches, totalBranches),
		"instruction": qualityFraction(instruction, totalInstructions), "line": lineCoverage,
		"total_crap": crap.total(), "total_excess": excessSum, "excess_density": density, "E_CRAP": ecrap,
		"p95_crap_exec": p95, "largest_excess": selected[:min(10, len(selected))]}
}
