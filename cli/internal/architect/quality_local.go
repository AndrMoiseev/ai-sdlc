package architect

import (
	"container/heap"
	"math"
	"slices"
	"sort"
)

type containerPenalty struct {
	value float64
	end   int
}

type activePenalties []containerPenalty

func (p activePenalties) Len() int { return len(p) }
func (p activePenalties) Less(i, j int) bool {
	if p[i].value != p[j].value {
		return p[i].value > p[j].value
	}
	return p[i].end < p[j].end
}
func (p activePenalties) Swap(i, j int) { p[i], p[j] = p[j], p[i] }
func (p *activePenalties) Push(value any) {
	*p = append(*p, value.(containerPenalty))
}
func (p *activePenalties) Pop() any {
	length := len(*p)
	value := (*p)[length-1]
	*p = (*p)[:length-1]
	return value
}

func maintainability(files map[string]record, parameters record) record {
	totalTokens, cognitiveWeight, complexTokens := 0, 0, 0
	cognitiveExcess, sizeExcess := 0.0, 0.0
	functions, largest := []record{}, []record{}
	maxComplexity := 0
	for _, path := range keys(files) {
		row := files[path]
		tokens := items(row["tokens"])
		starts := make([]float64, 0, len(tokens))
		for _, token := range tokens {
			starts = append(starts, numeric(object(token)["start"]))
		}
		totalTokens += len(tokens)
		bounds := func(container record) (int, int) {
			start, _ := reportNumeric(container["start"])
			end, _ := reportNumeric(container["end"])
			return sort.SearchFloat64s(starts, start), sort.SearchFloat64s(starts, end)
		}
		for _, entry := range items(row["functions"]) {
			function := object(entry)
			if function["nested"] == true {
				continue
			}
			start, end := bounds(function)
			weight := end - start
			complexity := integer(function["cognitive_complexity"])
			threshold := numeric(parameters["cognitive_complexity"])
			excess := float64(weight) * max(0.0, float64(complexity)/threshold-1)
			cognitiveWeight += weight
			cognitiveExcess += excess
			maxComplexity = max(maxComplexity, complexity)
			if float64(complexity) > threshold {
				complexTokens += weight
			}
			functions = append(functions, mergeRecords(record{"file": path}, function, record{"tokens": weight, "excess": excess}))
		}
		events := map[int][]containerPenalty{}
		filePenalty := max(0.0, float64(len(tokens))/numeric(parameters["file_tokens"])-1)
		for _, entry := range items(row["containers"]) {
			container := object(entry)
			start, end := bounds(container)
			penalty := max(0.0, float64(end-start)/numeric(parameters[str(container["kind"])+"_tokens"])-1)
			if penalty > 0 {
				events[start] = append(events[start], containerPenalty{penalty, end})
			}
		}
		active := &activePenalties{}
		var contribution float64
		for position := range tokens {
			for _, penalty := range events[position] {
				heap.Push(active, penalty)
			}
			for active.Len() > 0 && (*active)[0].end <= position {
				heap.Pop(active)
			}
			penalty := filePenalty
			if active.Len() > 0 {
				penalty = max(penalty, (*active)[0].value)
			}
			contribution += penalty
		}
		sizeExcess += contribution
		largest = append(largest, record{"file": path, "tokens": len(tokens), "size_excess": contribution})
	}
	var cognitiveScore, sizeScore, weightedP95, maximum, value any
	if cognitiveWeight > 0 {
		cognitiveScore = qualityScore(cognitiveExcess / float64(cognitiveWeight))
	}
	if totalTokens > 0 {
		sizeScore = qualityScore(sizeExcess / float64(totalTokens))
	}
	if len(functions) > 0 {
		maximum = maxComplexity
	}
	status := "not_applicable"
	if cognitiveScore != nil && sizeScore != nil {
		value = math.Sqrt(numeric(cognitiveScore) * numeric(sizeScore))
		status = "known"
	}
	weighted := append([]record{}, functions...)
	sort.SliceStable(weighted, func(i, j int) bool {
		return numeric(weighted[i]["cognitive_complexity"]) < numeric(weighted[j]["cognitive_complexity"])
	})
	accumulated := 0
	for _, function := range weighted {
		accumulated += integer(function["tokens"])
		if cognitiveWeight > 0 && float64(accumulated) >= .95*float64(cognitiveWeight) {
			weightedP95 = function["cognitive_complexity"]
			break
		}
	}
	sort.SliceStable(functions, func(i, j int) bool {
		left, right := functions[i], functions[j]
		if left["excess"] != right["excess"] {
			return numeric(left["excess"]) > numeric(right["excess"])
		}
		if left["file"] != right["file"] {
			return str(left["file"]) < str(right["file"])
		}
		return numeric(left["start"]) < numeric(right["start"])
	})
	sort.SliceStable(largest, func(i, j int) bool { return numeric(largest[i]["size_excess"]) > numeric(largest[j]["size_excess"]) })
	return record{"value": value, "status": status, "cognitive_score": cognitiveScore, "size_score": sizeScore, "tokens": totalTokens,
		"function_count": len(functions), "function_tokens": cognitiveWeight, "outside_function_tokens": totalTokens - cognitiveWeight,
		"cognitive_excess": cognitiveExcess, "size_excess": sizeExcess, "maximum_cognitive_complexity": maximum, "weighted_p95_cognitive_complexity": weightedP95,
		"complex_tokens": complexTokens, "complex_token_fraction": qualityFraction(complexTokens, cognitiveWeight),
		"largest_cognitive_contributions": functions[:min(10, len(functions))], "largest_size_contributions": largest[:min(10, len(largest))]}
}

type interval [2]int

func summarizeIntervals(intervals []interval) record {
	sort.Slice(intervals, func(i, j int) bool {
		if intervals[i][0] != intervals[j][0] {
			return intervals[i][0] < intervals[j][0]
		}
		return intervals[i][1] < intervals[j][1]
	})
	merged := []interval{}
	for _, current := range intervals {
		if n := len(merged); n > 0 && current[0] <= merged[n-1][1] {
			merged[n-1][1] = max(merged[n-1][1], current[1])
		} else {
			merged = append(merged, current)
		}
	}
	tokens := 0
	for _, current := range merged {
		tokens += current[1] - current[0]
	}
	return record{"tokens": tokens, "intervals": merged}
}

type tokenOccurrence struct {
	path  string
	start int
}

func duplication(files map[string]record, minimum int, owners map[string]string) (map[string]record, map[string]record) {
	identifiers, sequences := map[[2]string]uint64{}, map[string][]uint64{}
	paths := keys(files)
	for _, path := range paths {
		row := files[path]
		sequence := []uint64{}
		for _, entry := range items(row["tokens"]) {
			token := object(entry)
			key := [2]string{str(token["type"]), str(token["text"])}
			identity, known := identifiers[key]
			if !known {
				identity = uint64(len(identifiers) + 1)
				identifiers[key] = identity
			}
			sequence = append(sequence, identity)
		}
		sequences[path] = sequence
	}
	const base uint64 = 1000003
	power := uint64(1)
	for i := 1; i < minimum; i++ {
		power *= base
	}
	buckets := map[uint64][][]tokenOccurrence{}
	for _, path := range paths {
		sequence := sequences[path]
		var current uint64
		for index, token := range sequence {
			if index >= minimum {
				current -= sequence[index-minimum] * power
			}
			current = current*base + token
			if index+1 < minimum {
				continue
			}
			start := index + 1 - minimum
			grouped := false
			for bucketIndex, occurrences := range buckets[current] {
				first := occurrences[0]
				other := sequences[first.path][first.start : first.start+minimum]
				if slices.Equal(other, sequence[start:index+1]) {
					buckets[current][bucketIndex] = append(occurrences, tokenOccurrence{path, start})
					grouped = true
					break
				}
			}
			if !grouped {
				buckets[current] = append(buckets[current], []tokenOccurrence{{path, start}})
			}
		}
	}
	intervals, boundary := map[string][]interval{}, map[string][]interval{}
	for _, bucket := range buckets {
		for _, occurrences := range bucket {
			if len(occurrences) < 2 {
				continue
			}
			files, modules := map[string]bool{}, map[string]bool{}
			for _, occurrence := range occurrences {
				files[occurrence.path], modules[owners[occurrence.path]] = true, true
			}
			first, last := occurrences[0].start, occurrences[len(occurrences)-1].start
			for _, occurrence := range occurrences {
				path, start := occurrence.path, occurrence.start
				if len(files) > 1 || max(start-first, last-start) >= minimum {
					span := interval{start, start + minimum}
					intervals[path] = append(intervals[path], span)
					if len(modules) > 1 {
						boundary[path] = append(boundary[path], span)
					}
				}
			}
		}
	}
	local, crossModule := map[string]record{}, map[string]record{}
	for _, path := range paths {
		local[path], crossModule[path] = summarizeIntervals(intervals[path]), summarizeIntervals(boundary[path])
	}
	return local, crossModule
}
