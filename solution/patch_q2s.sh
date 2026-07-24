#!/usr/bin/env bash
set -euo pipefail

cat > /app/environment/q2s/PhaseQ2.java <<'EOF'
package q2s;

import runner.Checks;
import runner.Types;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

public final class PhaseQ2 {
    private PhaseQ2() {}

    public static Types.ReportDoc phase_c(Types.BarrierCert cert, Types.ReplayTrace trace, int caseId,
            String runMode) {
        Types.ReportDoc doc = new Types.ReportDoc();
        doc.caseId = caseId;
        doc.runMode = runMode;
        doc.barrierMargins = new ArrayList<>(cert.marginVec);
        Map<String, Integer> prevMargin = new HashMap<>();
        Map<String, Types.WitnessRow> witnessByCluster = new LinkedHashMap<>();
        for (Types.TraceStep step : trace.steps) {
            int idx = cert.rowKeys.indexOf(step.clusterId);
            int barrierMargin = cert.marginVec.get(idx);
            witnessByCluster.putIfAbsent(
                    step.clusterId,
                    new Types.WitnessRow(step.armId, step.clusterId, barrierMargin,
                            Checks.witnessRef(step.armId, step.clusterId, barrierMargin)));
            int previous = prevMargin.getOrDefault(step.clusterId, barrierMargin);
            int delta = prevMargin.containsKey(step.clusterId) ? barrierMargin - previous : 0;
            doc.replayDeltas.add(new Types.DeltaRow(step.step, step.armId, step.clusterId, delta));
            prevMargin.put(step.clusterId, barrierMargin);
        }
        doc.witnessRows.addAll(witnessByCluster.values());
        List<String> refs = doc.witnessRows.stream().map(r -> r.ref).sorted().collect(Collectors.toList());
        String body = String.join("|", refs) + "|" + caseId + "|" + runMode;
        doc.mergeToken = Checks.sha256Hex(body).substring(0, 16);
        return doc;
    }
}
EOF
