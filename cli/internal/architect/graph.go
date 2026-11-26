package architect

import (
	"fmt"
	"math"
	"slices"
	"sort"
	"strings"
)

func moduleFor(packageName string, modules record) (string, bool, error) {
	longest := -1
	owners := map[string]bool{}
	for name, prefixes := range modules {
		for _, prefix := range stringsOf(prefixes) {
			if packageName == prefix || strings.HasPrefix(packageName, prefix+".") {
				if size := len([]rune(prefix)); size >= longest {
					if size > longest {
						clear(owners)
						longest = size
					}
					owners[name] = true
				}
			}
		}
	}
	if len(owners) > 1 {
		return "", false, fmt.Errorf("Ambiguous module ownership for %s: %s", packageName, pythonList(keys(owners)))
	}
	for owner := range owners {
		return owner, true, nil
	}
	return "", false, nil
}

func aggregate(edges edgeWeights, resolve func(string) (string, bool)) edgeWeights {
	result := edgeWeights{}
	for pair, weight := range edges {
		left, leftMapped := resolve(pair.from)
		right, rightMapped := resolve(pair.to)
		if leftMapped && rightMapped && left != right {
			result[edge{left, right}] += weight
		}
	}
	return result
}

type adjacency map[string]map[string]int

func newAdjacency(nodes []string, edges edgeWeights, reverse bool) adjacency {
	graph := adjacency{}
	for _, node := range nodes {
		graph[node] = map[string]int{}
	}
	for pair, weight := range edges {
		from, to := pair.from, pair.to
		if from == to {
			continue
		}
		if reverse {
			from, to = to, from
		}
		if graph[from] == nil {
			graph[from] = map[string]int{}
		}
		if graph[to] == nil {
			graph[to] = map[string]int{}
		}
		graph[from][to] = weight
	}
	return graph
}

func reachable(graph adjacency, start string) map[string]bool {
	seen, pending := map[string]bool{start: true}, []string{start}
	for len(pending) > 0 {
		node := pending[len(pending)-1]
		pending = pending[:len(pending)-1]
		for candidate := range graph[node] {
			if !seen[candidate] {
				seen[candidate] = true
				pending = append(pending, candidate)
			}
		}
	}
	return seen
}

func components(forward, reverse adjacency) [][]string {
	visited := map[string]bool{}
	finish := []string{}
	type visit struct {
		node string
		done bool
	}
	for _, start := range keys(forward) {
		pending := []visit{{start, false}}
		for len(pending) > 0 {
			current := pending[len(pending)-1]
			pending = pending[:len(pending)-1]
			if current.done {
				finish = append(finish, current.node)
			} else if !visited[current.node] {
				visited[current.node] = true
				pending = append(pending, visit{current.node, true})
				for next := range forward[current.node] {
					if !visited[next] {
						pending = append(pending, visit{next, false})
					}
				}
			}
		}
	}
	clear(visited)
	result := [][]string{}
	for i := len(finish) - 1; i >= 0; i-- {
		start := finish[i]
		if visited[start] {
			continue
		}
		group, pending := []string{}, []string{start}
		for len(pending) > 0 {
			node := pending[len(pending)-1]
			pending = pending[:len(pending)-1]
			if !visited[node] {
				group = append(group, node)
				visited[node] = true
				for next := range reverse[node] {
					if !visited[next] {
						pending = append(pending, next)
					}
				}
			}
		}
		sort.Strings(group)
		result = append(result, group)
	}
	sort.Slice(result, func(i, j int) bool {
		if len(result[i]) != len(result[j]) {
			return len(result[i]) > len(result[j])
		}
		return slices.Compare(result[i], result[j]) < 0
	})
	return result
}

func dependencyLayers(edges edgeWeights) []record {
	remaining := map[string]bool{}
	for pair := range edges {
		remaining[pair.from], remaining[pair.to] = true, true
	}
	result := []record{}
	for len(remaining) > 0 {
		current := edgeWeights{}
		outgoing, incoming := map[string]bool{}, map[string]bool{}
		for pair, weight := range edges {
			if remaining[pair.from] && remaining[pair.to] {
				current[pair] = weight
				outgoing[pair.from], incoming[pair.to] = true, true
			}
		}
		selected, kind := keyDiff(remaining, outgoing), "no_suppliers"
		if len(selected) == 0 {
			selected, kind = keyDiff(remaining, incoming), "no_consumers"
		}
		if len(selected) == 0 {
			selected, kind = components(newAdjacency(nil, current, false), newAdjacency(nil, current, true))[0], "cyclic_core"
		}
		result = append(result, record{"members": selected, "kind": kind, "position": len(result) + 1})
		for _, node := range selected {
			delete(remaining, node)
		}
	}
	return result
}

func ratioValue(numerator, denominator int) any {
	if denominator == 0 {
		return nil
	}
	return float64(numerator) / float64(denominator)
}

var graphNodeMetrics = []string{"fan-in", "fan-out", "incoming-weight", "outgoing-weight", "reachable-in", "reachable-out", "visibility-in", "visibility-out"}

func emitGraph(analysis *measurementAnalysis, level string, edges edgeWeights) map[string]record {
	forward, reverse := newAdjacency(nil, edges, false), newAdjacency(nil, edges, true)
	count := len(forward)
	nodes := map[string]record{}
	var rows []record
	for pair, weight := range edges {
		rows = append(rows, record{"from": pair.from, "to": pair.to, "value": weight})
	}
	analysis.rows["dependencies/"+level] = rows
	propagation := 0
	for _, node := range keys(forward) {
		incoming, outgoing := len(reachable(reverse, node)), len(reachable(forward, node))
		incomingWeight, outgoingWeight := 0, 0
		for _, weight := range forward[node] {
			outgoingWeight += weight
		}
		for _, weight := range reverse[node] {
			incomingWeight += weight
		}
		values := []any{len(reverse[node]), len(forward[node]), incomingWeight, outgoingWeight, incoming, outgoing, ratioValue(incoming, count), ratioValue(outgoing, count)}
		nodes[node] = record{}
		for index, metric := range graphNodeMetrics {
			value := values[index]
			nodes[node][metric] = value
			row := measurementNumber(value, "")
			row["node"] = node
			if strings.HasPrefix(metric, "visibility") {
				row["numerator"], row["denominator"] = values[index-2], count
			}
			analysis.rows[metric+"/"+level] = append(analysis.rows[metric+"/"+level], row)
		}
		propagation += outgoing
	}
	for metric, value := range map[string]int{"node-count": count, "edge-count": len(edges)} {
		row := measurementNumber(value, "")
		row["graph"] = level
		analysis.rows[metric+"/"+level] = []record{row}
	}
	status := "measured"
	if count == 0 {
		status = "not_applicable"
	}
	analysis.rows["propagation-cost/"+level] = []record{{"graph": level, "status": status, "numerator": propagation,
		"denominator": count * count, "value": ratioValue(propagation, count*count)}}
	membership := map[string]int{}
	for index, group := range components(forward, reverse) {
		if len(group) > 1 {
			analysis.rows["cyclic-components/"+level] = append(analysis.rows["cyclic-components/"+level], record{"members": group})
			for _, node := range group {
				membership[node] = index + 1
			}
		}
	}
	for pair, weight := range edges {
		if membership[pair.from] != 0 && membership[pair.from] == membership[pair.to] {
			analysis.rows["cyclic-edges/"+level] = append(analysis.rows["cyclic-edges/"+level], record{"from": pair.from, "to": pair.to, "value": weight})
		}
	}
	analysis.rows["dependency-layers/"+level] = dependencyLayers(edges)
	return nodes
}

func emitMartin(analysis *measurementAnalysis, sources map[string]record, nodes map[string]record, policy record) {
	counts := map[string][3]int{}
	for _, row := range sources {
		packageName := str(row["package"])
		count := counts[packageName]
		if row["types"] == nil {
			count[2]++
		} else {
			count[0] += integer(row["types"])
			count[1] += integer(row["abstract"])
		}
		counts[packageName] = count
	}
	minimum := integer(object(object(policy["measurements"])["martin"])["minimum_types"])
	for packageName, count := range counts {
		incoming, outgoing := integer(nodes[packageName]["incoming-weight"]), integer(nodes[packageName]["outgoing-weight"])
		var metrics []any
		status := "not_applicable"
		reason := fmt.Sprintf("Requires at least %d measured types and nonzero package weight", minimum)
		switch {
		case count[0] >= minimum && incoming+outgoing > 0:
			instability := float64(outgoing) / float64(incoming+outgoing)
			abstractness := float64(count[1]) / float64(count[0])
			metrics = []any{incoming, outgoing, instability, abstractness, math.Abs(abstractness + instability - 1)}
			status = "measured"
			if count[2] > 0 {
				status = "measured_subset"
			}
		case count[2] > 0 && count[0] < minimum && incoming+outgoing > 0:
			status, reason = "unknown", "Type population is incomplete"
		}
		for index, name := range []string{"ca", "ce", "instability", "abstractness", "distance"} {
			var value any
			if metrics != nil {
				value = metrics[index]
			}
			row := measurementNumber(value, reason)
			row["package"], row["types"], row["abstract_types"], row["status"] = packageName, count[0], count[1], status
			identifier := name + "/package"
			analysis.rows[identifier] = append(analysis.rows[identifier], row)
		}
	}
}

func emitModuleViews(analysis *measurementAnalysis, edges edgeWeights, modules, policy record) {
	internal, boundary := map[string]int{}, map[string]int{}
	type ownership struct {
		name  string
		known bool
	}
	external := map[string]map[ownership]int{}
	for pair, weight := range edges {
		left, leftMapped, _ := moduleFor(pair.from, modules)
		right, rightMapped, _ := moduleFor(pair.to, modules)
		if leftMapped && rightMapped && left == right {
			internal[left] += weight
			continue
		}
		if leftMapped {
			boundary[left] += weight
		}
		if rightMapped {
			boundary[right] += weight
		}
		for _, name := range []string{pair.from, pair.to} {
			if external[name] == nil {
				external[name] = map[ownership]int{}
			}
		}
		external[pair.from][ownership{right, rightMapped}] += weight
		external[pair.to][ownership{left, leftMapped}] += weight
	}
	for name := range modules {
		total := internal[name] + boundary[name]
		status := "measured"
		if total == 0 {
			status = "not_applicable"
		}
		analysis.rows["cohesion/module"] = append(analysis.rows["cohesion/module"], record{"module": name,
			"internal": internal[name], "boundary": boundary[name], "value": ratioValue(internal[name], total), "status": status})
	}
	thresholds := object(object(policy["measurements"])["external_affinity"])
	for packageName, weights := range external {
		total, declared := 0, 0
		for owner, weight := range weights {
			total += weight
			if owner.known {
				declared += weight
			}
		}
		shares, ranked := record{}, []float64{}
		for owner, weight := range weights {
			if owner.known && declared > 0 {
				share := float64(weight) / float64(declared)
				shares[owner.name] = share
				ranked = append(ranked, share)
			}
		}
		sort.Sort(sort.Reverse(sort.Float64Slice(ranked)))
		fraction := float64(declared) / float64(total)
		category := "leading_external"
		switch {
		case declared == 0 || fraction < numeric(thresholds["minimum_declared_fraction"]):
			category = "grey"
		case ranked[0] < numeric(thresholds["minimum_leading_share"]):
			category = "orphan"
		case len(ranked) > 1 && ranked[1] >= numeric(thresholds["minimum_bridge_share"]):
			category = "bridge"
		}
		analysis.rows["external-affinity/package"] = append(analysis.rows["external-affinity/package"], record{"package": packageName,
			"external_weight": total, "declared_weight": declared, "declared_fraction": fraction, "shares": shares, "category": category})
	}
}
