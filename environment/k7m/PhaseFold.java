package k7m;

import runner.Checks;
import runner.Types;
import readers.SliceQ7;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public final class PhaseFold {
    private PhaseFold() {}

    public static Types.LatticeView op_a(Types.AnnexCtx ctx, byte[] cueSlice, int armId) {
        Map<String, String> narrowed = new HashMap<>();
        Map<String, Types.ClusterRec> byId = new HashMap<>();
        for (Types.ClusterRec rec : ctx.pack.clusters) {
            byId.put(rec.clusterId, rec);
        }
        List<String> order = ctx.pack.clusters.stream().map(c -> c.clusterId).toList();
        for (String cid : order) {
            Types.ClusterRec rec = byId.get(cid);
            byte[] slice = SliceQ7.cueSlice(rec);
            String label = ctx.pack.labelMap.getOrDefault(cid, "L0");
            if ((slice[4] & 0x01) != 0) {
                String neighbor = rec.neighborId;
                int rank = Math.min(
                        Checks.labelRank(label),
                        Checks.labelRank(ctx.pack.labelMap.getOrDefault(neighbor, "L0")));
                label = "L" + rank;
            }
            narrowed.put(cid, label);
        }
        return new Types.LatticeView(narrowed, armId);
    }
}
