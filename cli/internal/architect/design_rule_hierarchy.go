package architect

import (
	"fmt"
	"math"
	"slices"
	"sort"
)

func pathSet(paths []string) map[string]bool {
	result := map[string]bool{}
	for _, path := range paths {
		result[path] = true
	}
	return result
}

func inducedEdges(edges edgeWeights, nodes map[string]bool) edgeWeights {
	result := edgeWeights{}
	for pair, weight := range edges {
		if pair.from != pair.to && nodes[pair.from] && nodes[pair.to] {
			result[pair] = weight
		}
	}
	return result
}

func groupOwners(groups [][]string) map[string]int {
	result := map[string]int{}
	for index, group := range groups {
		for _, path := range group {
			result[path] = index
		}
	}
	return result
}

func groupLayers(groups [][]string, edges edgeWeights) ([]int, []map[int]bool, error) {
	owners := groupOwners(groups)
	suppliers := make([]map[int]bool, len(groups))
	for index := range suppliers {
		suppliers[index] = map[int]bool{}
	}
	for pair := range edges {
		left, right := owners[pair.from], owners[pair.to]
		if left != right {
			suppliers[left][right] = true
		}
	}
	positions, complete := make([]int, len(groups)), 0
	for complete < len(groups) {
		previous := complete
		for index, required := range suppliers {
			if positions[index] != 0 {
				continue
			}
			position, ready := 0, true
			for supplier := range required {
				ready = ready && positions[supplier] != 0
				position = max(position, positions[supplier])
			}
			if ready {
				positions[index] = 1 + position
				complete++
			}
		}
		if complete == previous {
			return nil, nil, fmt.Errorf("DRH groups introduce a cycle between groups")
		}
	}
	return positions, suppliers, nil
}

func terminalGroups(groups [][]string, edges edgeWeights) [][]string {
	owners := groupOwners(groups)
	incoming := map[int]bool{}
	for pair := range edges {
		if owners[pair.from] != owners[pair.to] {
			incoming[owners[pair.to]] = true
		}
	}
	var terminals [][]string
	for index, group := range groups {
		if !incoming[index] {
			terminals = append(terminals, group)
		}
	}
	return terminals
}

func baseGroups(nodes []string, edges edgeWeights) ([][]string, error) {
	forward, reverse := newAdjacency(nodes, edges, false), newAdjacency(nodes, edges, true)
	terminals := terminalGroups(components(forward, reverse), edges)
	signatures := map[string][]int{}
	for index, group := range terminals {
		for path := range reachable(forward, group[0]) {
			signatures[path] = append(signatures[path], index)
		}
	}
	pending := pathSet(nodes)
	regions := [][]string{}
	for _, start := range nodes {
		if !pending[start] {
			continue
		}
		group, stack := []string{}, []string{start}
		for len(stack) > 0 {
			node := stack[len(stack)-1]
			stack = stack[:len(stack)-1]
			if pending[node] {
				delete(pending, node)
				group = append(group, node)
				for _, connected := range []map[string]int{forward[node], reverse[node]} {
					for next := range connected {
						if pending[next] && slices.Equal(signatures[next], signatures[start]) {
							stack = append(stack, next)
						}
					}
				}
			}
		}
		sort.Strings(group)
		regions = append(regions, group)
	}
	positions, suppliers, err := groupLayers(regions, edges)
	if err != nil {
		return nil, err
	}
	conceptual := map[string][]string{}
	for index, region := range regions {
		key := fmt.Sprintf("root:%d", index)
		if len(suppliers[index]) > 0 {
			set := make([]int, 0, len(suppliers[index]))
			for supplier := range suppliers[index] {
				set = append(set, supplier)
			}
			sort.Ints(set)
			key = fmt.Sprintf("%d:%v", positions[index], set)
		}
		conceptual[key] = append(conceptual[key], region...)
	}
	groups := [][]string{}
	for _, group := range conceptual {
		sort.Strings(group)
		groups = append(groups, group)
	}
	sort.Slice(groups, func(i, j int) bool { return slices.Compare(groups[i], groups[j]) < 0 })
	return groups, nil
}

type hierarchyGroup struct {
	files []string
	layer int
}

func hierarchy(nodes []string, edges edgeWeights) ([]hierarchyGroup, error) {
	pending, err := baseGroups(nodes, edges)
	if err != nil {
		return nil, err
	}
	leaves := [][]string{}
	for len(pending) > 0 {
		group := pending[len(pending)-1]
		pending = pending[:len(pending)-1]
		internal := inducedEdges(edges, pathSet(group))
		count := len(group)
		if count < 2 || len(internal) < count || float64(len(internal)) > math.Pow(float64(count), 1.5) {
			leaves = append(leaves, group)
			continue
		}
		strong := components(newAdjacency(group, internal, false), newAdjacency(group, internal, true))
		control := terminalGroups(strong, internal)
		rest := pathSet(group)
		for _, part := range control {
			for _, node := range part {
				delete(rest, node)
			}
		}
		if len(rest) == 0 {
			leaves = append(leaves, group)
			continue
		}
		leaves = append(leaves, control...)
		remainder, err := baseGroups(keys(rest), inducedEdges(internal, rest))
		if err != nil {
			return nil, err
		}
		pending = append(pending, remainder...)
	}
	sort.Slice(leaves, func(i, j int) bool { return slices.Compare(leaves[i], leaves[j]) < 0 })
	positions, _, err := groupLayers(leaves, edges)
	if err != nil {
		return nil, err
	}
	last := 1
	for _, position := range positions {
		last = max(last, position)
	}
	connected := newAdjacency(nil, edges, false)
	result := []hierarchyGroup{}
	for index, group := range leaves {
		layer := last
		for _, node := range group {
			if connected[node] != nil {
				layer = positions[index]
				break
			}
		}
		result = append(result, hierarchyGroup{group, layer})
	}
	sort.SliceStable(result, func(i, j int) bool { return result[i].layer < result[j].layer })
	return result, nil
}

func decouplingLevel(nodes []string, edges edgeWeights, smallGroup int) (record, error) {
	if len(nodes) == 0 {
		return record{"value": nil, "status": "not_applicable", "groups": []record{}}, nil
	}
	groups, err := hierarchy(nodes, edges)
	if err != nil {
		return nil, err
	}
	reverse := newAdjacency(nodes, edges, true)
	last := groups[len(groups)-1].layer
	contributions := []record{}
	var sum preciseSum
	for _, group := range groups {
		lower, affected := map[string]bool{}, map[string]bool{}
		for _, other := range groups {
			if other.layer > group.layer {
				for _, path := range other.files {
					lower[path] = true
				}
			}
		}
		factor := 1.0
		size := len(group.files)
		if group.layer == last {
			if size > smallGroup {
				factor = math.Log(float64(smallGroup)) / math.Log(float64(size))
			}
		} else {
			for _, path := range group.files {
				for dependent := range reachable(reverse, path) {
					if lower[dependent] {
						affected[dependent] = true
					}
				}
			}
			factor = 1 - float64(len(affected))/float64(len(lower))
		}
		contribution := (100 * float64(size) / float64(len(nodes))) * factor
		sum.add(contribution)
		contributions = append(contributions, record{"files": group.files, "layer": group.layer,
			"lower_files": len(lower), "affected_lower_files": len(affected), "contribution": contribution})
	}
	return record{"value": sum.total(), "status": "known", "groups": contributions}, nil
}

func structuralMetrics(nodes []string, edges edgeWeights, smallGroup int) (record, error) {
	edges = inducedEdges(edges, pathSet(nodes))
	forward, reverse := newAdjacency(nodes, edges, false), newAdjacency(nodes, edges, true)
	cyclic, cyclicFiles, largest := [][]string{}, 0, min(len(nodes), 1)
	for _, group := range components(forward, reverse) {
		if len(group) > 1 {
			cyclic = append(cyclic, group)
			cyclicFiles += len(group)
			largest = max(largest, len(group))
		}
	}
	visibility, pairs := record{}, 0
	for _, node := range nodes {
		visibility[node] = ratioValue(len(reachable(reverse, node)), len(nodes))
		pairs += len(reachable(forward, node))
	}
	decoupling, err := decouplingLevel(nodes, edges, smallGroup)
	if err != nil {
		return nil, err
	}
	possible := len(nodes) * len(nodes)
	return record{"node_count": len(nodes), "edge_count": len(edges), "propagation_cost": ratioValue(pairs, possible),
		"reachable_pairs": pairs, "possible_pairs": possible, "cyclic_files": cyclicFiles, "cyclic_file_fraction": ratioValue(cyclicFiles, len(nodes)),
		"largest_scc_size": largest, "cyclic_components": cyclic, "visibility_in": visibility, "decoupling_level": decoupling}, nil
}

// preciseSum keeps the discarded rounding error as independent partial sums.
type preciseSum []float64

func (sum *preciseSum) add(value float64) {
	partials := *sum
	index := 0
	for _, other := range partials {
		if math.Abs(value) < math.Abs(other) {
			value, other = other, value
		}
		high := value + other
		low := other - (high - value)
		if low != 0 {
			partials[index] = low
			index++
		}
		value = high
	}
	*sum = append(partials[:index], value)
}

func (sum preciseSum) total() float64 {
	var high, low float64
	for index := len(sum) - 1; index >= 0; index-- {
		other := sum[index]
		previous := high
		high = previous + other
		low = other - (high - previous)
		if low != 0 {
			if index > 0 && math.Signbit(low) == math.Signbit(sum[index-1]) {
				correction := 2 * low
				rounded := high + correction
				if rounded-high == correction {
					high = rounded
				}
			}
			break
		}
	}
	return high
}
