package dev.aisdlc.detekt;

import java.util.List;
import java.util.Map;
import io.gitlab.arturbosch.detekt.api.*;
import io.github.detekt.metrics.CognitiveComplexity;
import org.jetbrains.kotlin.com.intellij.openapi.util.Key;
import org.jetbrains.kotlin.psi.KtFile;
import org.jetbrains.kotlin.resolve.BindingContext;

public final class MeasurementProcessor implements FileProcessListener {
    static final Key<String> RESULT = new Key<>(MeasurementCollection.RESULT_KEY);
    private MeasurementCollection measurements;
    public String getId() { return "SddArchitectMeasurements"; }
    public int getPriority() { return 0; }
    public void init(Config config) {}
    public void init(SetupContext context) {}
    public void onStart(List<? extends KtFile> files) { measurements = new MeasurementCollection(); }
    public void onStart(List<? extends KtFile> files, BindingContext context) { onStart(files); }
    public void onProcess(KtFile file) {
        measurements.add(file, function -> CognitiveComplexity.Companion.calculate(function));
    }
    public void onProcess(KtFile file, BindingContext context) { onProcess(file); }
    public void onProcessComplete(KtFile file, Map<String, ? extends List<? extends Finding>> findings) {}
    public void onProcessComplete(KtFile file, Map<String, ? extends List<? extends Finding>> findings, BindingContext context) {}
    public void onFinish(List<? extends KtFile> files, Detektion result) { result.addData(RESULT, measurements.finish()); }
    public void onFinish(List<? extends KtFile> files, Detektion result, BindingContext context) { onFinish(files, result); }
}
