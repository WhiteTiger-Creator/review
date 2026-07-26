package runner;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import k7m.PhaseFold;
import n3p.MuxQ3;
import q2s.FrameQ7;
import q2s.PhaseQ2;
import readers.SliceQ7;
import readers.TableQ5;

public final class Main {
    private static final Path ROOT = Path.of("/app/environment");
    private static final Path OUT = Path.of("/app/output/diff_replay_dossier.json");

    public static void main(String[] args) throws Exception {
        int caseId = 352;
        String mode = "direct";
        String wave = "w0";
        boolean permute = false;
        for (int i = 0; i < args.length; i++) {
            if ("--case".equals(args[i]) && i + 1 < args.length) {
                caseId = Integer.parseInt(args[++i]);
            } else if ("--mode".equals(args[i]) && i + 1 < args.length) {
                mode = args[++i];
            } else if ("--wave".equals(args[i]) && i + 1 < args.length) {
                wave = args[++i];
            } else if ("--permute".equals(args[i])) {
                permute = true;
            }
        }

        Path packPath = switch (mode) {
            case "held" -> ROOT.resolve("app/data/pack_h0352.json");
            case "stress" -> ROOT.resolve("app/data/pack_t352.json");
            default -> ROOT.resolve("app/data/pack_t352.json");
        };
        Types.PackDoc pack = TableQ5.loadPack(packPath);
        Types.BarrierTable table = TableQ5.loadTable(ROOT.resolve("app/data/ref_q7_pack.json"));
        Types.DrawSet draws = new Types.DrawSet(wave, List.of(), 0.0);
        int waveScale = 3;
        if ("stress".equals(mode)) {
            draws = TableQ5.loadDraws(ROOT.resolve("app/data/k9_k7_pack.json"), wave);
            waveScale = TableQ5.waveScaleFor(ROOT.resolve("app/data/k9_k7_pack.json"), wave);
        }

        Types.AnnexCtx annex = new Types.AnnexCtx(pack, permute);
        Map<String, byte[]> slices = SliceQ7.allSlices(pack);
        Types.LatticeView lattice = PhaseFold.op_a(annex, slices.get("c1"), pack.armId);
        Types.BarrierCert cert = MuxQ3.reconcile_b(lattice, table, draws, pack, waveScale);
        List<String> traceOrder = new ArrayList<>();
        if ("held".equals(mode) && permute && !pack.permuteOrder.isEmpty()) {
            traceOrder.addAll(pack.permuteOrder);
        }
        Types.ReplayTrace trace = FrameQ7.frameTrace(cert, traceOrder);
        Types.ReportDoc doc = PhaseQ2.phase_c(cert, trace, caseId, mode);

        if (!Checks.o1Feasible(cert)) {
            System.err.println("O1 feasibility failed");
        }

        writeReport(doc);
    }

    private static void writeReport(Types.ReportDoc doc) throws Exception {
        Files.createDirectories(OUT.getParent());
        StringBuilder sb = new StringBuilder();
        sb.append("{\n");
        sb.append("  \"case_id\": ").append(doc.caseId).append(",\n");
        sb.append("  \"run_mode\": \"").append(doc.runMode).append("\",\n");
        sb.append("  \"barrier_margins\": [");
        for (int i = 0; i < doc.barrierMargins.size(); i++) {
            if (i > 0) {
                sb.append(", ");
            }
            sb.append(doc.barrierMargins.get(i));
        }
        sb.append("],\n");
        sb.append("  \"witness_rows\": [\n");
        for (int i = 0; i < doc.witnessRows.size(); i++) {
            Types.WitnessRow row = doc.witnessRows.get(i);
            sb.append("    {\"arm_id\": ").append(row.armId)
                    .append(", \"cluster_id\": \"").append(row.clusterId)
                    .append("\", \"margin\": ").append(row.margin)
                    .append(", \"ref\": \"").append(row.ref).append("\"}");
            if (i + 1 < doc.witnessRows.size()) {
                sb.append(",");
            }
            sb.append("\n");
        }
        sb.append("  ],\n");
        sb.append("  \"replay_deltas\": [\n");
        for (int i = 0; i < doc.replayDeltas.size(); i++) {
            Types.DeltaRow d = doc.replayDeltas.get(i);
            sb.append("    {\"step\": ").append(d.step)
                    .append(", \"arm_id\": ").append(d.armId)
                    .append(", \"cluster_id\": \"").append(d.clusterId)
                    .append("\", \"delta\": ").append(d.delta).append("}");
            if (i + 1 < doc.replayDeltas.size()) {
                sb.append(",");
            }
            sb.append("\n");
        }
        sb.append("  ],\n");
        sb.append("  \"merge_token\": \"").append(doc.mergeToken).append("\"\n");
        sb.append("}\n");
        Files.writeString(OUT, sb.toString(), StandardCharsets.UTF_8);
    }
}
