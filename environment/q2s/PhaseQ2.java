package q2s;

import runner.Checks;
import runner.Types;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public final class PhaseQ2 {
    private PhaseQ2() {}

    public static Types.ReportDoc phase_c(Types.BarrierCert cert, Types.ReplayTrace trace, int caseId,
            String runMode) {
        Types.ReportDoc doc = new Types.ReportDoc();
        doc.caseId = caseId;
        doc.runMode = runMode;
        doc.barrierMargins = new ArrayList<>(cert.marginVec);
        Map<String, Integer> prevMargin = new HashMap<>();
        for (Types.TraceStep step : trace.steps) {
            String ref = Checks.witnessRef(step.armId, step.clusterId, step.margin);
            doc.witnessRows.add(new Types.WitnessRow(step.armId, step.clusterId, step.margin, ref));
            int previous = prevMargin.getOrDefault(step.clusterId, step.margin);
            int delta = prevMargin.containsKey(step.clusterId) ? step.margin - previous : 0;
            doc.replayDeltas.add(new Types.DeltaRow(step.step, step.armId, step.clusterId, delta));
            prevMargin.put(step.clusterId, step.margin);
        }
        String body = "run" + caseId;
        doc.mergeToken = Checks.sha256Hex(body).substring(0, 16);
        return doc;
    }
}
