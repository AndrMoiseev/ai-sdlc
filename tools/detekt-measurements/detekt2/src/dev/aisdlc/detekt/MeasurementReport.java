package dev.aisdlc.detekt;

import dev.detekt.api.*;

public final class MeasurementReport implements OutputReport {
    public String getId() { return MeasurementCollection.REPORT_ID; }
    public String render(Detektion result) {
        Object report = result.getUserData().get(MeasurementCollection.RESULT_KEY);
        if (!(report instanceof String)) throw new IllegalStateException("Measurement processor did not finish");
        return (String) report;
    }
}
