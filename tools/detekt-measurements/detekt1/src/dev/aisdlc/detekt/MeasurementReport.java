package dev.aisdlc.detekt;

import io.gitlab.arturbosch.detekt.api.*;

public final class MeasurementReport extends OutputReport {
    public String getId() { return MeasurementCollection.REPORT_ID; }
    public String getName() { return MeasurementCollection.REPORT_ID; }
    public String getEnding() { return "json"; }
    public String render(Detektion result) {
        String report = result.getData(MeasurementProcessor.RESULT);
        if (report == null) throw new IllegalStateException("Measurement processor did not finish");
        return report;
    }
}
