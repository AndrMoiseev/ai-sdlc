// Syntax and metric extraction only. Dependency analysis remains jdeps.
// Execute with a JDK source launcher and the detekt 1.23.8 CLI all.jar.
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import org.jetbrains.kotlin.cli.jvm.compiler.EnvironmentConfigFiles;
import org.jetbrains.kotlin.cli.jvm.compiler.KotlinCoreEnvironment;
import org.jetbrains.kotlin.config.CompilerConfiguration;
import org.jetbrains.kotlin.com.intellij.openapi.Disposable;
import org.jetbrains.kotlin.com.intellij.openapi.util.Disposer;
import org.jetbrains.kotlin.com.intellij.openapi.util.TextRange;
import org.jetbrains.kotlin.com.intellij.psi.PsiElement;
import org.jetbrains.kotlin.com.intellij.psi.PsiErrorElement;
import org.jetbrains.kotlin.lexer.KotlinLexer;
import org.jetbrains.kotlin.lexer.KtTokens;
import org.jetbrains.kotlin.psi.*;
import io.github.detekt.metrics.CognitiveComplexity;

public class KotlinMeasurements {
    static Map<String, Object> row(Object... pairs) {
        Map<String, Object> result = new LinkedHashMap<>();
        for (int index = 0; index < pairs.length; index += 2)
            result.put((String) pairs[index], pairs[index + 1]);
        return result;
    }
    static String json(Object value) {
        if (value == null) return "null";
        if (value instanceof Boolean || value instanceof Number) return value.toString();
        if (value instanceof Map) {
            List<String> parts = new ArrayList<>();
            ((Map<?, ?>) value).forEach((key, item) -> parts.add(json(key.toString()) + ":" + json(item)));
            return "{" + String.join(",", parts) + "}";
        }
        if (value instanceof Collection) {
            List<String> parts = new ArrayList<>();
            for (Object item : (Collection<?>) value) parts.add(json(item));
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
    static void inspectErrors(PsiElement element, String path) {
        if (element instanceof PsiErrorElement)
            throw new IllegalArgumentException(path + ": " + ((PsiErrorElement) element).getErrorDescription()
                    + " at UTF-16 offset " + element.getTextOffset());
        for (PsiElement child : element.getChildren()) inspectErrors(child, path);
    }
    static Map<String, Object> measure(KtFile file, String text, String path) {
        inspectErrors(file, path);
        List<TextRange> excluded = new ArrayList<>();
        if (file.getPackageDirective() != null) excluded.add(file.getPackageDirective().getTextRange());
        for (KtImportDirective item : file.getImportDirectives()) excluded.add(item.getTextRange());
        List<Map<String, Object>> tokens = new ArrayList<>();
        KotlinLexer lexer = new KotlinLexer();
        lexer.start(text);
        while (lexer.getTokenType() != null) {
            int start = lexer.getTokenStart(), end = lexer.getTokenEnd();
            boolean omitted = lexer.getTokenType() == KtTokens.WHITE_SPACE || KtTokens.COMMENTS.contains(lexer.getTokenType());
            for (TextRange range : excluded) if (start >= range.getStartOffset() && end <= range.getEndOffset()) omitted = true;
            if (!omitted) tokens.add(row("type", lexer.getTokenType().toString(), "text", text.substring(start, end), "start", start, "end", end));
            lexer.advance();
        }
        List<Map<String, Object>> functions = new ArrayList<>(), containers = new ArrayList<>();
        file.accept(new KtTreeVisitorVoid() {
            public void visitNamedFunction(KtNamedFunction function) {
                if (function.getName() != null && function.getBodyExpression() != null) {
                    TextRange body = function.getBodyExpression().getTextRange();
                    boolean nested = false;
                    List<String> owner = new ArrayList<>();
                    for (PsiElement parent = function.getParent(); parent != null; parent = parent.getParent()) {
                        if (parent instanceof KtNamedFunction && ((KtNamedFunction) parent).getName() != null) nested = true;
                        if (parent instanceof KtNamedDeclaration) owner.add(String.valueOf(((KtNamedDeclaration) parent).getName()));
                    }
                    Collections.reverse(owner);
                    List<String> types = new ArrayList<>();
                    for (KtParameter parameter : function.getValueParameters())
                        types.add(parameter.getTypeReference() == null ? "?" : parameter.getTypeReference().getText());
                    String receiver = function.getReceiverTypeReference() == null ? "" : function.getReceiverTypeReference().getText() + ".";
                    functions.add(row("start", body.getStartOffset(), "end", body.getEndOffset(), "declaration_start", function.getTextOffset(),
                        "signature", receiver + function.getName() + "(" + String.join(",", types) + ")", "owner", String.join(".", owner),
                        "nested", nested, "cognitive_complexity", CognitiveComplexity.Companion.calculate(function)));
                    containers.add(row("kind", "function", "start", body.getStartOffset(), "end", body.getEndOffset()));
                }
                super.visitNamedFunction(function);
            }
            public void visitClassOrObject(KtClassOrObject declaration) {
                TextRange range = declaration.getTextRange();
                containers.add(row("kind", "class", "start", range.getStartOffset(), "end", range.getEndOffset()));
                super.visitClassOrObject(declaration);
            }
        });
        return row("file", path, "package", file.getPackageFqName().asString(), "tokens", tokens,
                   "functions", functions, "containers", containers);
    }
    public static void main(String[] args) throws Exception {
        if (args.length != 2) throw new IllegalArgumentException("Expected repository and UTF-8 source-file manifest");
        Path root = Paths.get(args[0]);
        Disposable disposable = Disposer.newDisposable();
        try {
            KotlinCoreEnvironment environment = KotlinCoreEnvironment.createForProduction(disposable,
                new CompilerConfiguration(), EnvironmentConfigFiles.JVM_CONFIG_FILES);
            KtPsiFactory factory = new KtPsiFactory(environment.getProject(), false);
            List<Map<String, Object>> files = new ArrayList<>();
            for (String path : Files.readAllLines(Paths.get(args[1]), StandardCharsets.UTF_8)) {
                String text = Files.readString(root.resolve(path), StandardCharsets.UTF_8).replace("\r\n", "\n").replace('\r', '\n');
                if (text.startsWith("\ufeff")) text = text.substring(1);
                files.add(measure(factory.createFile(Paths.get(path).getFileName().toString(), text), text, path));
            }
            System.out.println(json(row("format", "kotlin-measurements", "version", 1, "tool", "detekt-metrics",
                "tool_version", "1.23.8", "offsets", "UTF-16 after LF normalization", "complete", true, "files", files)));
        } finally {
            Disposer.dispose(disposable);
        }
    }
}
