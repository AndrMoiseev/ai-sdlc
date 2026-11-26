package architect

import (
	"fmt"
	"io"
	"math/big"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
)

var recommendationCriteria = []string{"modularity", "regression_risk", "change_cost_reduction"}
var recommendationStatuses = []string{"ready", "needs_check", "observe", "rejected"}
var recommendationFields = []string{"id", "status", "card", "source_evidence", "metric_evidence", "effects"}
var cardFence = regexp.MustCompile("^ {0,3}(`{3,}|~{3,})(.*)$")
var cardHeading = regexp.MustCompile(`^ {0,3}##\s+(.+?)\s*#*\s*$`)
var cardHeadingNumber = regexp.MustCompile(`^([1-6])\.\s+\S`)
var cardTitle = regexp.MustCompile(`^ {0,3}#\s+\S`)

func validateCard(text string) (string, error) {
	title, fence := "", ""
	type section struct {
		number  int
		content bool
	}
	var sections []section
	for _, line := range strings.Split(strings.ReplaceAll(text, "\r\n", "\n"), "\n") {
		marker := cardFence.FindStringSubmatch(line)
		if fence != "" {
			if marker != nil && marker[1][0] == fence[0] && len(marker[1]) >= len(fence) && strings.TrimSpace(marker[2]) == "" {
				fence = ""
			} else if len(sections) > 0 && strings.TrimSpace(line) != "" {
				sections[len(sections)-1].content = true
			}
			continue
		}
		if marker != nil {
			fence = marker[1]
			continue
		}
		if heading := cardHeading.FindStringSubmatch(line); heading != nil {
			number := cardHeadingNumber.FindStringSubmatch(heading[1])
			if number == nil {
				return "", fmt.Errorf("Card needs exactly six numbered level-two sections (1. through 6.)")
			}
			sections = append(sections, section{int(number[1][0] - '0'), false})
		} else if cardTitle.MatchString(line) {
			if title != "" || len(sections) > 0 {
				return "", fmt.Errorf("Card needs one title before its six sections")
			}
			title = strings.TrimSpace(strings.TrimSpace(line)[2:])
		} else if content := strings.TrimSpace(line); len(sections) > 0 && content != "" && !strings.HasPrefix(content, "<!--") && !strings.HasPrefix(content, "#") {
			sections[len(sections)-1].content = true
		}
	}
	if title == "" || len(sections) != 6 {
		return "", fmt.Errorf("Card needs a title and six numbered sections in order (1. through 6.)")
	}
	allContent := fence == ""
	for index, section := range sections {
		if section.number != index+1 {
			return "", fmt.Errorf("Card needs a title and six numbered sections in order (1. through 6.)")
		}
		allContent = allContent && section.content
	}
	if !allContent {
		return "", fmt.Errorf("Card has an unclosed fence or an empty section")
	}
	return title, nil
}

func rankCommand(args options, stdout io.Writer) error {
	repository := args.get("repository")
	collectionPath := filepath.Clean(args.get("collection"))
	collection, err := readObject(collectionPath)
	if err != nil {
		return err
	}
	if _, err := reportOutput(collectionPath, repository, false); err != nil {
		return err
	}
	if collection["status"] != "complete" {
		return fmt.Errorf("Collection has unfinished calculations; inspect its output outcomes")
	}
	policy, err := validatePolicy(collection["analysis_policy"], true)
	if err != nil {
		return err
	}
	root, err := resolve(repository)
	if err != nil {
		return err
	}
	sources, err := inventory(object(collection["parameters"]), root)
	if err != nil {
		return err
	}
	recommendationsPath := filepath.Clean(args.get("recommendations"))
	cardRoot, err := resolve(recommendationsPath)
	if err != nil {
		return err
	}
	document, err := readObject(recommendationsPath)
	if err != nil {
		return err
	}
	result, err := rankRecommendations(document, collection, policy, sources, filepath.Dir(cardRoot), filepath.Dir(collectionPath))
	if err != nil {
		return err
	}
	output := filepath.Clean(args.get("output"))
	destination, err := reportOutput(output, repository, false)
	if err != nil {
		return err
	}
	if exists(destination) {
		return fmt.Errorf("Output already exists")
	}
	if args.has("markdown") {
		path, err := reportOutput(args.get("markdown"), repository, false)
		if err != nil {
			return err
		}
		if exists(path) {
			return fmt.Errorf("Markdown output already exists")
		}
		if path == destination {
			return fmt.Errorf("JSON and Markdown outputs must be different files")
		}
		if err := writeText(path, []byte(rankMarkdown(result)), true, true); err != nil {
			return err
		}
	}
	if err := saveMetricJSON(output, repository, result); err != nil {
		return err
	}
	return printJSON(stdout, record{"output": output, "gaps": 0}, false)
}

func rankRecommendations(document, collection, policy record, sources map[string]record, cardRoot, audit string) (record, error) {
	scoring := object(policy["recommendations"])
	points, weights := object(scoring["effect_points"]), object(scoring["criterion_weights"])
	cards, found := document["recommendations"]
	if !found {
		return nil, fmt.Errorf("'recommendations'")
	}
	if items(cards) == nil {
		return nil, fmt.Errorf("recommendations: expected an array")
	}
	identities, paths := map[string]bool{}, map[string]bool{}
	ready, remaining := []record{}, []record{}
	scores := map[string]*big.Rat{}
	for _, value := range items(cards) {
		card := object(value)
		identity, status := str(card["id"]), str(card["status"])
		if identity == "" || identities[identity] {
			return nil, fmt.Errorf("Recommendation IDs must be unique nonempty strings")
		}
		identities[identity] = true
		if len(unknownFields(card, recommendationFields)) > 0 {
			return nil, fmt.Errorf("%s: keep narrative and design fields in the Markdown card, not ranking metadata", identity)
		}
		if !contains(recommendationStatuses, status) {
			return nil, fmt.Errorf("%s: invalid status %s", identity, display(card["status"]))
		}
		path := str(card["card"])
		if path == "" || strings.ContainsAny(path, `\:`) || strings.HasPrefix(path, "/") || contains(strings.Split(path, "/"), "..") || filepath.Ext(path) != ".md" || filepath.Base(path) == ".md" {
			return nil, fmt.Errorf("%s: card must be a relative Markdown path inside the report", identity)
		}
		if paths[path] {
			return nil, fmt.Errorf("%s: each recommendation needs its own Markdown card", identity)
		}
		paths[path] = true
		cardPath, err := resolve(filepath.Join(cardRoot, filepath.FromSlash(path)))
		if err != nil {
			return nil, err
		}
		if !within(cardPath, cardRoot) {
			return nil, fmt.Errorf("Markdown card must stay inside its report directory")
		}
		text, err := readUTF8(cardPath)
		if err != nil {
			return nil, err
		}
		title, err := validateCard(text)
		if err != nil {
			return nil, err
		}
		card["title"] = title
		sourceEvidence, metricEvidence := items(card["source_evidence"]), items(card["metric_evidence"])
		if sourceEvidence == nil || metricEvidence == nil {
			return nil, fmt.Errorf("%s: provide source_evidence and metric_evidence address lists", identity)
		}
		if status == "ready" && (len(sources) == 0 || len(sourceEvidence) == 0) {
			return nil, fmt.Errorf("%s: ready requires inspected sources", identity)
		}
		for _, value := range sourceEvidence {
			ref := object(value)
			if !sameKeys(ref, []string{"file", "declaration"}) || sources[str(ref["file"])] == nil || !truthy(ref["declaration"]) {
				return nil, fmt.Errorf("%s: source evidence must address a current file and declaration", identity)
			}
		}
		for _, value := range metricEvidence {
			ref := object(value)
			if !sameKeys(ref, []string{"path", "key"}) {
				return nil, fmt.Errorf("%s: metric evidence needs a JSONL path, object key and resolver", identity)
			}
			if _, err := resolveMeasurements([]record{ref}, collection, audit); err != nil {
				return nil, err
			}
		}
		effects := object(card["effects"])
		if status == "ready" || card["effects"] != nil {
			valid := sameKeys(effects, recommendationCriteria)
			for _, effect := range effects {
				name := str(effect)
				valid = valid && (points[name] != nil || (status != "ready" && (name == "unknown" || name == "worsening")))
			}
			if !valid {
				return nil, fmt.Errorf("%s: invalid effect profile; unknown or worsening effects cannot be ready", identity)
			}
		}
		if status != "ready" {
			remaining = append(remaining, card)
			continue
		}
		score, grounded := new(big.Rat), false
		for _, criterion := range recommendationCriteria {
			effect := str(effects[criterion])
			grounded = grounded || effect != "not_shown"
			weight, _ := new(big.Rat).SetString(display(weights[criterion]))
			count, _ := new(big.Rat).SetString(display(points[effect]))
			score.Add(score, count.Mul(count, weight))
		}
		if !grounded {
			return nil, fmt.Errorf("%s: no grounded benefit; observe or reject", identity)
		}
		if score.IsInt() {
			card["priority_score"] = score.Num()
		} else {
			card["priority_score"], _ = score.Float64()
		}
		scores[identity] = score
		ready = append(ready, card)
	}
	sort.Slice(ready, func(i, j int) bool {
		left, right := str(ready[i]["id"]), str(ready[j]["id"])
		if comparison := scores[left].Cmp(scores[right]); comparison != 0 {
			return comparison > 0
		}
		return left < right
	})
	groups := [][]string{}
	var previous *big.Rat
	for _, card := range ready {
		identity := str(card["id"])
		score := scores[identity]
		if previous == nil || score.Cmp(previous) != 0 {
			groups = append(groups, []string{})
			previous = score
		}
		groups[len(groups)-1] = append(groups[len(groups)-1], identity)
	}
	return record{"priority_groups": groups, "report_limit": scoring["report_limit"], "effect_points": points,
		"criterion_weights": weights, "recommendations": append(ready, remaining...),
		"ordering": "sum of effect_points[category] * criterion_weights[criterion]; equal scores remain tied"}, nil
}

func truthy(value any) bool {
	switch value := value.(type) {
	case nil:
		return false
	case string:
		return value != ""
	case bool:
		return value
	case []any:
		return len(value) > 0
	case map[string]any:
		return len(value) > 0
	default:
		return numeric(value) != 0
	}
}

func rankMarkdown(document record) string {
	lines := []string{"# Refactoring directions for sdd-spec", "",
		"| Priority | Score | Recommendation | Modularity | Regression risk reduction | Change cost reduction |",
		"| --- | --- | --- | --- | --- | --- |"}
	priorities := map[string]int{}
	for index, group := range document["priority_groups"].([][]string) {
		for _, identity := range group {
			priorities[identity] = index + 1
		}
	}
	link := func(card record) string {
		title := strings.NewReplacer("|", `\|`, "\n", " ", "[", `\[`, "]", `\]`).Replace(str(card["title"]))
		return "[" + title + "](<" + str(card["card"]) + ">)"
	}
	byStatus := map[string][]record{}
	for _, card := range document["recommendations"].([]record) {
		status := str(card["status"])
		byStatus[status] = append(byStatus[status], card)
	}
	ready := byStatus["ready"]
	limit := min(integer(document["report_limit"]), len(ready))
	for _, card := range ready[:limit] {
		effects := object(card["effects"])
		lines = append(lines, fmt.Sprintf("| %d | %s | %s | %s | %s | %s |", priorities[str(card["id"])], display(card["priority_score"]),
			link(card), effects["modularity"], effects["regression_risk"], effects["change_cost_reduction"]))
	}
	if len(ready) == 0 {
		lines = append(lines, "", "No evidence-backed directions are ready for sdd-spec discussion.")
	}
	for _, status := range recommendationStatuses[1:] {
		if selected := byStatus[status]; len(selected) > 0 {
			lines = append(lines, "", "## "+strings.ReplaceAll(status, "_", " "), "")
			for _, card := range selected {
				lines = append(lines, "- "+link(card))
			}
		}
	}
	if len(ready) > limit {
		lines = append(lines, "", "## Further directions", "")
		for _, card := range ready[limit:] {
			lines = append(lines, "- "+link(card))
		}
	}
	return strings.Join(lines, "\n") + "\n"
}
