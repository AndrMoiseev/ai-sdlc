package check

import (
	"bytes"
	"errors"
	"fmt"
	"io"
	"os"
	"slices"
	"sort"
	"strings"
	"unicode/utf8"

	"github.com/yuin/goldmark"
	"github.com/yuin/goldmark/ast"
	"github.com/yuin/goldmark/text"
	"go.yaml.in/yaml/v3"
)

const maxDocumentCharacters = 4_000_000

type document struct {
	metadata map[string]any
	records  []map[string]any
}

type documentDiagnostic struct {
	code, message string
	elementID     any
	unreadable    bool
}

type recordSchema struct {
	documentType, prefix string
	required, optional   []string
}

var recordSchemas = map[string]recordSchema{
	"requirement": {"spec", "REQ", []string{"operation"}, []string{"source"}},
	"acceptance":  {"spec", "AC", []string{"requirement", "conditions", "expected"}, nil},
	"decision":    {"design", "DEC", []string{"requirements"}, nil},
	"task":        {"tasks", "TASK", []string{"number", "covers", "depends_on", "status", "verification"}, []string{"cannot_parallel_with"}},
}

func validDocumentSlug(value any) bool {
	slug, ok := value.(string)
	return ok && len(slug) <= 64 && changeID.MatchString(slug)
}

func validDocumentID(value, prefix string) bool {
	slug, ok := strings.CutPrefix(value, prefix+"-")
	return ok && validDocumentSlug(slug)
}

func nonemptyText(value any) bool {
	text, ok := value.(string)
	return ok && strings.TrimSpace(text) != ""
}

func hasFields(mapping map[string]any, required, optional []string) bool {
	for _, key := range required {
		if _, present := mapping[key]; !present {
			return false
		}
	}
	for key := range mapping {
		if !slices.Contains(required, key) && !slices.Contains(optional, key) {
			return false
		}
	}
	return true
}

func parseDocument(path, expectedType, workKind string) (document, *documentDiagnostic) {
	source, diagnostic := readDocumentText(path)
	if diagnostic != nil {
		return document{}, diagnostic
	}
	opening, remaining, _ := strings.Cut(source, "\n")
	if strings.TrimSpace(opening) != "---" {
		return document{}, &documentDiagnostic{code: "frontmatter", message: "Document must start with YAML frontmatter"}
	}
	var metadataText strings.Builder
	var body string
	found := false
	for remaining != "" {
		line, next, _ := strings.Cut(remaining, "\n")
		if strings.TrimSpace(line) == "---" {
			body, found = next, true
			break
		}
		metadataText.WriteString(line)
		metadataText.WriteByte('\n')
		remaining = next
	}
	if !found {
		return document{}, &documentDiagnostic{code: "frontmatter", message: "Unterminated frontmatter"}
	}
	metadata, diagnostic := parseYAMLMapping(metadataText.String())
	if diagnostic != nil {
		return document{}, diagnostic
	}
	if diagnostic = validateDocumentMetadata(metadata, expectedType, workKind); diagnostic != nil {
		return document{}, diagnostic
	}
	records, diagnostic := readDocumentRecords([]byte(body), expectedType, workKind)
	return document{metadata: metadata, records: records}, diagnostic
}

func readDocumentText(path string) (string, *documentDiagnostic) {
	info, err := os.Stat(path)
	if err != nil {
		return documentReadError(path, err)
	}
	if !info.Mode().IsRegular() {
		return "", &documentDiagnostic{code: "unreadable_input", message: "Expected a regular document file", unreadable: true}
	}
	file, err := os.Open(path)
	if err != nil {
		return documentReadError(path, err)
	}
	defer file.Close()
	// Allow the UTF-8 BOM, four bytes per character, and one character past the limit.
	source, err := io.ReadAll(io.LimitReader(file, 3+4*(maxDocumentCharacters+1)))
	if err != nil {
		return documentReadError(path, err)
	}
	source = bytes.TrimPrefix(source, []byte{0xEF, 0xBB, 0xBF})
	documentText := strings.NewReplacer("\r\n", "\n", "\r", "\n").Replace(string(source))
	if utf8.RuneCountInString(documentText) > maxDocumentCharacters {
		return "", &documentDiagnostic{code: "document_limit", message: "Document exceeds the 4,000,000 character limit"}
	}
	if !utf8.Valid(source) {
		return "", &documentDiagnostic{code: "unreadable_input", message: invalidUTF8Message(source), unreadable: true}
	}
	return documentText, nil
}

func documentReadError(path string, err error) (string, *documentDiagnostic) {
	failure := fileError(path, err)
	return "", &documentDiagnostic{code: failure.Code, message: failure.Message, unreadable: true}
}

func invalidUTF8Message(source []byte) string {
	// The process report includes the decoder's byte range and reason.
	for offset := 0; offset < len(source); {
		runeValue, width := utf8.DecodeRune(source[offset:])
		if runeValue != utf8.RuneError || width != 1 {
			offset += width
			continue
		}
		first := source[offset]
		if first < 0xc2 || first > 0xf4 {
			return fmt.Sprintf("'utf-8' codec can't decode byte 0x%02x in position %d: invalid start byte", first, offset)
		}
		width = 2
		if first >= 0xe0 {
			width = 3
		}
		if first >= 0xf0 {
			width = 4
		}
		length := 1
		for length < width && offset+length < len(source) {
			next := source[offset+length]
			if next < 0x80 || next > 0xbf || (length == 1 && !validUTF8SecondByte(first, next)) {
				break
			}
			length++
		}
		reason := "invalid continuation byte"
		if offset+length == len(source) {
			reason = "unexpected end of data"
		}
		if length == 1 {
			return fmt.Sprintf("'utf-8' codec can't decode byte 0x%02x in position %d: %s", first, offset, reason)
		}
		return fmt.Sprintf("'utf-8' codec can't decode bytes in position %d-%d: %s", offset, offset+length-1, reason)
	}
	return "Invalid UTF-8 input"
}

func validUTF8SecondByte(first, second byte) bool {
	switch first {
	case 0xe0:
		return second >= 0xa0
	case 0xed:
		return second <= 0x9f
	case 0xf0:
		return second >= 0x90
	case 0xf4:
		return second <= 0x8f
	default:
		return true
	}
}

func parseYAMLMapping(source string) (map[string]any, *documentDiagnostic) {
	if utf8.RuneCountInString(source) > 1_000_000 {
		return nil, &documentDiagnostic{code: "yaml_limit", message: "YAML exceeds the 1,000,000 character limit"}
	}
	decoder := yaml.NewDecoder(strings.NewReader(source))
	var tree yaml.Node
	err := decoder.Decode(&tree)
	if errors.Is(err, io.EOF) {
		return nil, &documentDiagnostic{code: "yaml_mapping", message: "Expected a YAML mapping"}
	}
	if err != nil {
		return nil, &documentDiagnostic{code: "invalid_yaml", message: err.Error()}
	}
	var trailing yaml.Node
	if err := decoder.Decode(&trailing); !errors.Is(err, io.EOF) {
		if err != nil {
			return nil, &documentDiagnostic{code: "invalid_yaml", message: err.Error()}
		}
		return nil, &documentDiagnostic{code: "invalid_yaml", message: "Expected one YAML document"}
	}
	count := 0
	if diagnostic := inspectYAML(&tree, 0, &count); diagnostic != nil {
		return nil, diagnostic
	}
	if len(tree.Content) != 1 || tree.Content[0].Kind != yaml.MappingNode {
		return nil, &documentDiagnostic{code: "yaml_mapping", message: "Expected a YAML mapping"}
	}
	var mapping map[string]any
	if err := tree.Decode(&mapping); err != nil {
		return nil, &documentDiagnostic{code: "invalid_yaml", message: err.Error()}
	}
	return mapping, nil
}

func inspectYAML(node *yaml.Node, depth int, count *int) *documentDiagnostic {
	(*count)++
	if *count > 100_000 {
		return &documentDiagnostic{code: "yaml_limit", message: "YAML exceeds the 100,000 token limit"}
	}
	if node.Kind == yaml.AliasNode || node.Anchor != "" || node.Style&yaml.TaggedStyle != 0 {
		return &documentDiagnostic{code: "unsafe_yaml", message: "YAML aliases, anchors and explicit tags are forbidden"}
	}
	// PyYAML resolves the plain YAML 1.1 yes/no/on/off scalars to booleans.
	if node.Kind == yaml.ScalarNode && node.Style == 0 && node.ShortTag() == "!!str" {
		switch node.Value {
		case "yes", "Yes", "YES", "on", "On", "ON":
			node.Tag, node.Value = "!!bool", "true"
		case "no", "No", "NO", "off", "Off", "OFF":
			node.Tag, node.Value = "!!bool", "false"
		}
	}
	if node.Kind == yaml.MappingNode || node.Kind == yaml.SequenceNode {
		depth++
		if depth > 64 {
			return &documentDiagnostic{code: "yaml_limit", message: "YAML nesting exceeds 64 levels"}
		}
	}
	var keys map[string]bool
	if node.Kind == yaml.MappingNode {
		keys = make(map[string]bool)
	}
	for index, child := range node.Content {
		if diagnostic := inspectYAML(child, depth, count); diagnostic != nil {
			return diagnostic
		}
		if node.Kind != yaml.MappingNode || index%2 != 0 {
			continue
		}
		if child.Kind != yaml.ScalarNode || child.ShortTag() != "!!str" {
			return &documentDiagnostic{code: "yaml_key", message: "Mapping keys must be strings; merge keys are forbidden"}
		}
		if keys[child.Value] {
			return &documentDiagnostic{code: "duplicate_key", message: "Duplicate YAML key: " + child.Value}
		}
		keys[child.Value] = true
	}
	return nil
}

func validateDocumentMetadata(metadata map[string]any, expectedType, workKind string) *documentDiagnostic {
	declared, present := metadata["work_kind"]
	if !present {
		declared = "change"
	}
	if declared != "change" && declared != "refactoring" {
		return &documentDiagnostic{code: "unsupported_work_kind", message: "Unsupported declared work kind: " + documentValue(declared) + "; install a matching SDD bundle", unreadable: true}
	}
	if declared != workKind {
		return &documentDiagnostic{code: "work_kind_mismatch", message: fmt.Sprintf("Document declares %s, selected work is %s; correct the work selection or document placement", declared, workKind)}
	}
	kind, present := metadata["document_type"]
	if !present {
		kind = ""
	}
	documentType, ok := kind.(string)
	if !ok {
		return &documentDiagnostic{code: "document_type", message: "document_type must be a string"}
	}
	version, ok := metadata["schema_version"].(int)
	expectedVersion := 1
	if documentType == "state" || documentType == "review" || documentType == "decisions" {
		expectedVersion = 2
	}
	if ok && expectedVersion == 2 && version == 1 {
		return &documentDiagnostic{code: "migration_required", message: "Legacy evidence requires migration: inspect the checkpoint, accept the current clean HEAD, then migrate state and decisions; preserve reports without a reliable commit outside the active review set", unreadable: true}
	}
	if !ok || version != expectedVersion {
		return &documentDiagnostic{code: "unsupported_version", message: "Unsupported " + workKind + " schema version: " + documentValue(metadata["schema_version"]) + "; install a matching SDD bundle", unreadable: true}
	}
	if version == 2 && (!validDocumentSlug(metadata["change_id"]) || metadata["work_kind"] != workKind) {
		return &documentDiagnostic{code: "document_identity", message: "Version 2 documents require explicit work_kind and change_id"}
	}
	if documentType == "state" && expectedType != "state" {
		return &documentDiagnostic{code: "state_format", message: "Checkpoint metadata requires state.yaml; Markdown state documents are unsupported"}
	}
	if documentType != expectedType {
		return &documentDiagnostic{code: "document_identity", message: "Document type/change_id does not match its location"}
	}
	if !slices.Contains([]string{"proposal", "tasks", "spec", "design"}, expectedType) {
		return nil
	}
	required := []string{"change_id", "document_type", "language", "schema_version"}
	if documentType == "spec" {
		required = append(required, "capability")
	}
	if _, present := metadata["work_kind"]; present {
		required = append(required, "work_kind")
	}
	if !hasFields(metadata, required, nil) {
		sort.Strings(required)
		return &documentDiagnostic{code: "document_fields", message: "Expected fields: " + documentList(required)}
	}
	if !validDocumentSlug(metadata["change_id"]) || !nonemptyText(metadata["language"]) {
		return &documentDiagnostic{code: "document_metadata", message: "Invalid change_id or language"}
	}
	if documentType == "spec" {
		capability, _ := metadata["capability"].(string)
		for _, segment := range strings.Split(capability, "/") {
			if !validDocumentSlug(segment) {
				return &documentDiagnostic{code: "capability", message: "Invalid capability path"}
			}
		}
	}
	return nil
}

func documentValue(value any) string {
	switch value := value.(type) {
	case nil:
		return "None"
	case bool:
		if value {
			return "True"
		}
		return "False"
	default:
		return fmt.Sprint(value)
	}
}

func documentList(values []string) string {
	quoted := make([]string, 0, len(values))
	for _, value := range values {
		quoted = append(quoted, "'"+value+"'")
	}
	return "[" + strings.Join(quoted, ", ") + "]"
}

func readDocumentRecords(body []byte, documentType, workKind string) ([]map[string]any, *documentDiagnostic) {
	markdown := goldmark.DefaultParser()
	root := markdown.Parse(text.NewReader(body))
	records := make([]map[string]any, 0)
	seen := make(map[string]bool)
	parentRequirement := ""
	nested := false
	var positionErrors []*documentDiagnostic
	var diagnostic *documentDiagnostic
	_ = ast.Walk(root, func(node ast.Node, entering bool) (ast.WalkStatus, error) {
		if !entering {
			return ast.WalkContinue, nil
		}
		if heading, ok := node.(*ast.Heading); ok && heading.Parent() == root && heading.Level < 3 {
			parentRequirement = ""
		}
		fence, ok := node.(*ast.FencedCodeBlock)
		if !ok || fence.Info == nil || strings.TrimSpace(string(fence.Info.Segment.Value(body))) != "yaml" {
			return ast.WalkContinue, nil
		}
		var yamlText bytes.Buffer
		for index := 0; index < fence.Lines().Len(); index++ {
			line := fence.Lines().At(index)
			yamlText.Write(line.Value(body))
		}
		record, failure := parseYAMLMapping(yamlText.String())
		if failure != nil {
			if failure.code == "yaml_mapping" {
				return ast.WalkContinue, nil
			}
			diagnostic = failure
			return ast.WalkStop, nil
		}
		kind, present := record["sdd_record"]
		if !present {
			return ast.WalkContinue, nil
		}
		specRequirement := documentType == "spec" && kind == "requirement"
		heading, ok := node.PreviousSibling().(*ast.Heading)
		expectedLevel := 3
		if specRequirement && ok && heading.Level == 2 {
			expectedLevel = 2
			nested = true
		}
		if !ok || node.Parent() != root || heading.Level != expectedLevel {
			diagnostic = &documentDiagnostic{code: "record_position", message: "A record must immediately follow a level-three heading (level two is allowed for spec requirements)"}
			return ast.WalkStop, nil
		}
		if !recordAdjacentToHeading(body, heading, fence.Info.Segment.Start) {
			diagnostic = &documentDiagnostic{code: "record_position", message: "Only a blank line may separate heading and record"}
			return ast.WalkStop, nil
		}
		id, ok := record["id"].(string)
		if !ok || seen[id] {
			diagnostic = &documentDiagnostic{code: "duplicate_id", message: "Missing or duplicate ID: " + documentValue(record["id"])}
			return ast.WalkStop, nil
		}
		seen[id] = true
		if diagnostic = validateDocumentRecord(documentType, workKind, id, record); diagnostic != nil {
			return ast.WalkStop, nil
		}
		if specRequirement && heading.Level == 2 {
			parentRequirement = id
		} else if specRequirement {
			positionErrors = append(positionErrors, &documentDiagnostic{code: "record_position", message: "Use level-two headings for all requirements in a nested spec", elementID: id})
		}
		if documentType == "spec" && kind == "acceptance" && (parentRequirement == "" || record["requirement"] != parentRequirement) {
			positionErrors = append(positionErrors, &documentDiagnostic{code: "acceptance_parent", message: "Nested acceptance must reference its enclosing requirement", elementID: id})
		}
		records = append(records, record)
		return ast.WalkContinue, nil
	})
	if diagnostic != nil {
		return nil, diagnostic
	}
	if nested && len(positionErrors) > 0 {
		return nil, positionErrors[0]
	}
	return records, nil
}

var refactoringSchemas = map[string]recordSchema{
	"criterion":    {"design", "AC", []string{"purpose", "scope", "conditions", "expected"}, []string{"parent", "source"}},
	"decision":     {"design", "DEC", []string{"criteria"}, []string{"supersedes"}},
	"task":         {"tasks", "TASK", []string{"number", "scope", "contributes_to", "preserves", "depends_on", "status", "verification"}, []string{"cannot_parallel_with", "preservation_reason", "test_changes"}},
	"acceptance":   {"tasks", "AC", []string{"task", "conditions", "expected", "lifetime"}, []string{"until_task", "replaced_by"}},
	"verification": {"tasks", "CHECK", []string{"criteria", "test_description", "location", "run"}, []string{"execution_kind", "setup_task"}},
}

func validateDocumentRecord(documentType, workKind, id string, record map[string]any) *documentDiagnostic {
	if !slices.Contains([]string{"proposal", "tasks", "spec", "design"}, documentType) {
		return nil
	}
	kind, _ := record["sdd_record"].(string)
	schema, ok := recordSchemas[kind]
	if workKind == "refactoring" {
		schema, ok = refactoringSchemas[kind]
	}
	if !ok || documentType != schema.documentType {
		return &documentDiagnostic{code: "record_type", message: fmt.Sprintf("Record %s is not allowed in %s", documentValue(record["sdd_record"]), documentType), elementID: id}
	}
	required := append([]string{"sdd_record", "id"}, schema.required...)
	if !hasFields(record, required, schema.optional) {
		return &documentDiagnostic{code: "record_fields", message: "Invalid fields for " + kind, elementID: id}
	}
	if !validDocumentID(id, schema.prefix) {
		return &documentDiagnostic{code: "invalid_id", message: fmt.Sprintf("Invalid %s ID: %s", schema.prefix, id), elementID: id}
	}
	return nil
}

func recordAdjacentToHeading(body []byte, heading *ast.Heading, fenceOffset int) bool {
	fenceStart := bytes.LastIndexByte(body[:fenceOffset], '\n') + 1
	if fenceStart == 0 {
		return false
	}
	if heading.Lines().Len() == 0 {
		// Empty ATX headings have no source segment. Look for the heading in the
		// two possible lines preceding the fence.
		prefix := body[:fenceStart-1]
		last := bytes.LastIndexByte(prefix, '\n')
		line := bytes.TrimSpace(prefix[last+1:])
		if len(line) == 0 && last >= 0 {
			prefix = prefix[:last]
			line = bytes.TrimSpace(prefix[bytes.LastIndexByte(prefix, '\n')+1:])
		}
		return bytes.HasPrefix(line, []byte(strings.Repeat("#", heading.Level)))
	}
	lastLine := heading.Lines().At(heading.Lines().Len() - 1)
	end := lastLine.Stop
	if end > 0 && body[end-1] == '\n' {
		end--
	}
	if next := bytes.IndexByte(body[end:], '\n'); next >= 0 {
		end += next + 1
	}
	if end > fenceStart {
		return false
	}
	remaining := body[end:fenceStart]
	// Goldmark's Setext heading source segments omit the underline.
	if heading.Level == 2 && len(remaining) != 0 {
		firstLine, rest, _ := bytes.Cut(remaining, []byte{'\n'})
		underline := bytes.TrimSpace(firstLine)
		if len(underline) > 0 && len(bytes.Trim(underline, "-")) == 0 {
			remaining = rest
		}
	}
	return len(bytes.TrimSpace(remaining)) == 0 && bytes.Count(remaining, []byte{'\n'}) <= 1
}
