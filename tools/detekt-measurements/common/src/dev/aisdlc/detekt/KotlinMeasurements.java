package dev.aisdlc.detekt;

import java.util.*;
import java.util.function.ToIntFunction;
import org.jetbrains.kotlin.lexer.KotlinLexer;
import org.jetbrains.kotlin.lexer.KtTokens;
import org.jetbrains.kotlin.psi.*;

/** Shared sources are compiled against each adapter's host PSI; no parser is created here. */
public final class KotlinMeasurements {
    private KotlinMeasurements() {}

    public static Map<String, Object> row(Object... pairs) {
        Map<String, Object> result = new LinkedHashMap<>();
        for (int index = 0; index < pairs.length; index += 2)
            result.put((String) pairs[index], pairs[index + 1]);
        return result;
    }

    public static String json(Object value) {
        if (value == null) return "null";
        if (value instanceof Boolean || value instanceof Number) return value.toString();
        if (value instanceof Map<?, ?> map) {
            List<String> parts = new ArrayList<>();
            map.forEach((key, item) -> parts.add(json(key.toString()) + ":" + json(item)));
            return "{" + String.join(",", parts) + "}";
        }
        if (value instanceof Collection<?> collection) {
            List<String> parts = new ArrayList<>();
            for (Object item : collection) parts.add(json(item));
            return "[" + String.join(",", parts) + "]";
        }
        StringBuilder result = new StringBuilder("\"");
        for (char character : value.toString().toCharArray()) {
            if (character == '\\' || character == '"') result.append('\\').append(character);
            else if (character < 32) result.append(String.format("\\u%04x", (int) character));
            else result.append(character);
        }
        return result.append('"').toString();
    }

    public static Map<String, Object> measure(KtFile file, String path,
                                               ToIntFunction<KtNamedFunction> cognitiveComplexity) {
        String original = file.getText();
        int[] offsets = new int[original.length() + 1];
        StringBuilder normalized = new StringBuilder();
        for (int index = 0; index < original.length(); index++) {
            offsets[index] = normalized.length();
            char character = original.charAt(index);
            if (index == 0 && character == '\ufeff') continue;
            if (character == '\r' && index + 1 < original.length() && original.charAt(index + 1) == '\n') continue;
            normalized.append(character == '\r' ? '\n' : character);
        }
        offsets[original.length()] = normalized.length();
        String text = normalized.toString();
        // Inferred PSI node types let these same sources compile with shaded 1.x and unshaded 2.x PSI.
        var root = file.getNode();
        var node = root.getFirstChildNode();
        while (node != null) {
            if (node.getElementType().toString().equals("ERROR_ELEMENT"))
                throw new IllegalArgumentException(path + ": invalid Kotlin syntax at UTF-16 offset " + offsets[node.getStartOffset()]);
            if (node.getFirstChildNode() != null) node = node.getFirstChildNode();
            else {
                while (node != root && node.getTreeNext() == null) node = node.getTreeParent();
                if (node == root) break;
                node = node.getTreeNext();
            }
        }
        List<int[]> excluded = new ArrayList<>();
        if (file.getPackageDirective() != null) {
            var range = file.getPackageDirective().getTextRange();
            excluded.add(new int[]{offsets[range.getStartOffset()], offsets[range.getEndOffset()]});
        }
        for (var directive : file.getImportDirectives()) {
            var range = directive.getTextRange();
            excluded.add(new int[]{offsets[range.getStartOffset()], offsets[range.getEndOffset()]});
        }
        List<Map<String, Object>> tokens = new ArrayList<>();
        KotlinLexer lexer = new KotlinLexer();
        lexer.start(text);
        while (lexer.getTokenType() != null) {
            int start = lexer.getTokenStart(), end = lexer.getTokenEnd();
            boolean omitted = lexer.getTokenType() == KtTokens.WHITE_SPACE || KtTokens.COMMENTS.contains(lexer.getTokenType());
            for (int[] range : excluded) if (start >= range[0] && end <= range[1]) omitted = true;
            if (!omitted) tokens.add(row("type", lexer.getTokenType().toString(), "text", text.substring(start, end),
                                        "start", start, "end", end));
            lexer.advance();
        }
        List<Map<String, Object>> functions = new ArrayList<>(), containers = new ArrayList<>();
        file.accept(new KtTreeVisitorVoid() {
            @Override public void visitNamedFunction(KtNamedFunction function) {
                if (function.getName() != null && function.getBodyExpression() != null) {
                    var body = function.getBodyExpression().getTextRange();
                    boolean nested = false;
                    List<String> owner = new ArrayList<>();
                    for (var parent = function.getParent(); parent != null; parent = parent.getParent()) {
                        if (parent instanceof KtNamedFunction named && named.getName() != null) nested = true;
                        if (parent instanceof KtNamedDeclaration declaration) owner.add(String.valueOf(declaration.getName()));
                    }
                    Collections.reverse(owner);
                    List<String> types = new ArrayList<>();
                    for (KtParameter parameter : function.getValueParameters())
                        types.add(parameter.getTypeReference() == null ? "?" : parameter.getTypeReference().getText());
                    String receiver = function.getReceiverTypeReference() == null ? "" : function.getReceiverTypeReference().getText() + ".";
                    functions.add(row("start", offsets[body.getStartOffset()], "end", offsets[body.getEndOffset()],
                        "declaration_start", offsets[function.getTextOffset()],
                        "signature", receiver + function.getName() + "(" + String.join(",", types) + ")",
                        "owner", String.join(".", owner), "nested", nested,
                        "cognitive_complexity", cognitiveComplexity.applyAsInt(function)));
                    containers.add(row("kind", "function", "start", offsets[body.getStartOffset()], "end", offsets[body.getEndOffset()]));
                }
                super.visitNamedFunction(function);
            }
            @Override public void visitClassOrObject(KtClassOrObject declaration) {
                var range = declaration.getTextRange();
                containers.add(row("kind", "class", "start", offsets[range.getStartOffset()], "end", offsets[range.getEndOffset()]));
                super.visitClassOrObject(declaration);
            }
        });
        return row("file", path, "package", file.getPackageFqName().asString(),
                   "tokens", tokens, "functions", functions, "containers", containers);
    }
}
