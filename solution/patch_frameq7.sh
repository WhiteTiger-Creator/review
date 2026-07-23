#!/usr/bin/env bash
set -euo pipefail

cat > /app/environment/q2s/FrameQ7.java <<'EOF'
package q2s;

import runner.Types;
import java.util.ArrayList;
import java.util.List;

public final class FrameQ7 {
    private FrameQ7() {}

    public static Types.ReplayTrace frameTrace(Types.BarrierCert cert, List<String> clusterOrder) {
        List<String> order = clusterOrder.isEmpty() ? cert.rowKeys : clusterOrder;
        List<Types.TraceStep> steps = new ArrayList<>();
        int step = 0;
        for (String cid : order) {
            int idx = cert.rowKeys.indexOf(cid);
            int margin = cert.marginVec.get(idx);
            steps.add(new Types.TraceStep(step++, cert.armId, cid, margin));
        }
        if (!order.isEmpty()) {
            String fork = order.get(order.size() - 1);
            int idx = cert.rowKeys.indexOf(fork);
            steps.add(new Types.TraceStep(step, cert.armId, fork, cert.marginVec.get(idx)));
        }
        return new Types.ReplayTrace(steps);
    }
}
EOF
