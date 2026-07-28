#!/usr/bin/env bash
set -euo pipefail

cat > /app/environment/n3p/MuxQ3.java <<'EOF'
package n3p;

import runner.Checks;
import runner.Types;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public final class MuxQ3 {
    private MuxQ3() {}

    public static Types.BarrierCert reconcile_b(Types.LatticeView view, Types.BarrierTable table,
            Types.DrawSet k7set, Types.PackDoc pack, int waveScale) {
        List<Integer> margins = new ArrayList<>();
        Map<String, Integer> boost = new HashMap<>();
        double weightSum = 0.0;
        for (Types.DrawRec draw : k7set.draws) {
            if (draw.armId == view.armId) {
                weightSum += draw.weight;
                int add = (int) Math.floor(draw.weight * waveScale);
                boost.merge(draw.clusterId, add, Integer::sum);
            }
        }
        if (!k7set.draws.isEmpty() && weightSum < k7set.terminationWeight) {
            throw new IllegalStateException("draw weight below termination threshold");
        }
        int salt = Checks.armSalt(view.armId);
        for (int i = 0; i < table.rowKeys.size(); i++) {
            String cid = table.rowKeys.get(i);
            int base = pack.marginBases.size() > i ? pack.marginBases.get(i) : table.bases.get(i);
            int h = table.cueHashes.get(i);
            int rank = Checks.labelRank(view.narrowed.getOrDefault(cid, "L0"));
            int margin = h + salt + rank - base + boost.getOrDefault(cid, 0);
            margins.add(margin);
        }
        return new Types.BarrierCert(margins, table.rowKeys, view.armId);
    }
}
EOF
