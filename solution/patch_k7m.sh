#!/usr/bin/env bash
set -euo pipefail

cat > /app/environment/k7m/PhaseFold.java <<'EOF'
package k7m;

import runner.Checks;
import runner.Types;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import readers.SliceQ7;

public final class PhaseFold {
    private PhaseFold() {}

    public static Types.LatticeView op_a(Types.AnnexCtx ctx, byte[] cueSlice, int armId) {
        Map<String, String> narrowed = new HashMap<>();
        Map<String, Types.ClusterRec> byId = new HashMap<>();
        for (Types.ClusterRec rec : ctx.pack.clusters) {
            byId.put(rec.clusterId, rec);
        }
        List<String> order = ctx.pack.permuteOrder.isEmpty()
                ? ctx.pack.clusters.stream().map(c -> c.clusterId).toList()
                : (ctx.applyPermute ? ctx.pack.permuteOrder
                        : ctx.pack.clusters.stream().map(c -> c.clusterId).toList());
        Map<String, String> labels = new HashMap<>();
        for (String cid : order) {
            labels.put(cid, ctx.pack.labelMap.getOrDefault(cid, "L0"));
        }
        for (String cid : order) {
            Types.ClusterRec rec = byId.get(cid);
            byte[] slice = SliceQ7.cueSlice(rec);
            String label = labels.get(cid);
            if ((slice[4] & 0x01) != 0) {
                String neighbor = rec.neighborId;
                int rank = Math.min(Checks.labelRank(label), Checks.labelRank(labels.get(neighbor)));
                label = "L" + rank;
            }
            labels.put(cid, label);
            narrowed.put(cid, label);
        }
        return new Types.LatticeView(narrowed, armId);
    }
}
EOF
