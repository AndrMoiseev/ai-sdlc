package dev.aisdlc.detekt;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.ConcurrentSkipListMap;
import java.util.function.ToIntFunction;
import org.jetbrains.kotlin.config.KotlinCompilerVersion;
import org.jetbrains.kotlin.psi.*;

public final class MeasurementCollection {
    public static final String REPORT_ID = "sdd-architect-measurements";
    public static final String RESULT_KEY = "dev.aisdlc.detekt.measurements";
    private final Map<String, Map<String, Object>> files = new ConcurrentSkipListMap<>();
    private final Path repository;
    private final Set<String> expected;

    public MeasurementCollection() {
        try {
            repository = Path.of(requiredProperty("sdd.architect.repository")).toRealPath();
            expected = new TreeSet<>(Files.readAllLines(
                Path.of(requiredProperty("sdd.architect.sourceManifest")), StandardCharsets.UTF_8));
        } catch (IOException exception) {
            throw new IllegalArgumentException("Cannot read the measurement source inventory", exception);
        }
    }

    private static String requiredProperty(String name) {
        String value = System.getProperty(name);
        if (value == null || value.isBlank()) throw new IllegalArgumentException("Missing JVM property: " + name);
        return value;
    }

    public void add(KtFile file, ToIntFunction<KtNamedFunction> cognitiveComplexity) {
        try {
            String virtualPath = file.getVirtualFile().getPath();
            // detekt's virtual file can expose /C:\... on Windows.
            if (java.io.File.separatorChar == '\\' && virtualPath.matches("^/[A-Za-z]:[\\\\/].*"))
                virtualPath = virtualPath.substring(1);
            Path source = Path.of(virtualPath).toRealPath();
            if (!source.startsWith(repository)) throw new IllegalArgumentException("Source leaves repository: " + source);
            String path = repository.relativize(source).toString().replace('\\', '/');
            if (!expected.contains(path)) throw new IllegalArgumentException("Unexpected Kotlin file: " + path);
            var row = KotlinMeasurements.measure(file, path, cognitiveComplexity);
            if (files.putIfAbsent(path, row) != null) throw new IllegalArgumentException("Duplicate Kotlin file: " + path);
        } catch (IOException exception) {
            throw new IllegalArgumentException("Cannot resolve Kotlin source", exception);
        }
    }

    public String finish() {
        if (!files.keySet().equals(expected)) {
            Set<String> missing = new TreeSet<>(expected);
            missing.removeAll(files.keySet());
            throw new IllegalArgumentException("Incomplete Kotlin measurements; missing: " + missing);
        }
        return KotlinMeasurements.json(KotlinMeasurements.row(
            "format", "kotlin-measurements", "version", MeasurementMetadata.SCHEMA_VERSION,
            "measurement_profile", MeasurementMetadata.PROFILE, "plugin_version", MeasurementMetadata.PLUGIN_VERSION,
            "tool", "detekt", "tool_version", requiredProperty("sdd.architect.detekt.version"),
            "parser_version", KotlinCompilerVersion.VERSION,
            "offsets", "UTF-16 after LF normalization", "complete", true, "files", files.values()));
    }
}
