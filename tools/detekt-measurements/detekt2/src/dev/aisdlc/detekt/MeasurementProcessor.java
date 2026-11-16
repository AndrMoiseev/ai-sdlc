package dev.aisdlc.detekt;

import java.util.List;
import dev.detekt.api.*;
import dev.detekt.metrics.CognitiveComplexity;
import kotlin.Pair;
import org.jetbrains.kotlin.psi.KtFile;

public final class MeasurementProcessor implements FileProcessListener {
    private MeasurementCollection measurements;
    public String getId() { return "SddArchitectMeasurements"; }
    public void onStart(List<? extends KtFile> files) { measurements = new MeasurementCollection(); }
    public void onProcess(KtFile file) {
        measurements.add(file, function -> CognitiveComplexity.Companion.calculate(function));
    }
    public Detektion onFinish(List<? extends KtFile> files, Detektion result) {
        return result.plus(new Pair<>(MeasurementCollection.RESULT_KEY, measurements.finish()));
    }
}
