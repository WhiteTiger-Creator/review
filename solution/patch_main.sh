#!/usr/bin/env bash
set -euo pipefail

cat > /app/environment/runner/Main.java <<'EOF'
package runner;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
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
        Path journalPath = null;
        Path resumePath = null;
        for (int i = 0; i < args.length; i++) {
            if ("--case".equals(args[i]) && i + 1 < args.length) {
                caseId = Integer.parseInt(args[++i]);
            } else if ("--mode".equals(args[i]) && i + 1 < args.length) {
                mode = args[++i];
            } else if ("--wave".equals(args[i]) && i + 1 < args.length) {
                wave = args[++i];
            } else if ("--permute".equals(args[i])) {
                permute = true;
            } else if ("--journal".equals(args[i]) && i + 1 < args.length) {
                journalPath = Path.of(args[++i]);
            } else if ("--resume".equals(args[i]) && i + 1 < args.length) {
                resumePath = Path.of(args[++i]);
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

        int replayEpoch = 0;
        if (resumePath != null && Files.exists(resumePath)) {
            Types.JournalSnap snap = JournalQ4.read(resumePath);
            String waveKey = "stress".equals(mode) ? wave : "";
            if (!JournalQ4.matchesFingerprint(snap, caseId, pack.armId, mode, waveKey)) {
                System.err.println("journal fingerprint mismatch");
                System.exit(2);
            }
            replayEpoch = snap.epoch + 1;
        }

        boolean heldMode = "held".equals(mode);
        Types.AnnexCtx annex = new Types.AnnexCtx(pack, permute, heldMode);
        Map<String, byte[]> slices = SliceQ7.allSlices(pack);
        Types.LatticeView lattice = PhaseFold.op_a(annex, slices.get("c1"), pack.armId);
        Types.BarrierCert cert = MuxQ3.reconcile_b(lattice, table, draws, pack, waveScale);
        List<String> traceOrder = new ArrayList<>();
        if ("held".equals(mode) && permute && !pack.permuteOrder.isEmpty()) {
            traceOrder.addAll(pack.permuteOrder);
        }
        int carryover = "stress".equals(mode) ? stressCarryover(draws, pack.armId) : 0;
        Types.ReplayTrace trace = FrameQ7.frameTrace(cert, traceOrder, carryover);
        Types.ReportDoc doc = PhaseQ2.phase_c(cert, trace, caseId, mode);
        doc.replayEpoch = replayEpoch;

        if (!Checks.o1Feasible(cert)) {
            System.err.println("O1 feasibility failed");
        }

        writeReport(doc);

        if (journalPath != null) {
            Types.JournalSnap snap = new Types.JournalSnap();
            snap.caseId = caseId;
            snap.armId = pack.armId;
            snap.runMode = mode;
            snap.wave = "stress".equals(mode) ? wave : "";
            snap.epoch = replayEpoch;
            snap.barrierMargins = new ArrayList<>(doc.barrierMargins);
            JournalQ4.write(journalPath, snap);
        }
    }

    private static int stressCarryover(Types.DrawSet draws, int armId) {
        double sum = 0.0;
        for (Types.DrawRec draw : draws.draws) {
            if (draw.armId == armId) {
                sum += draw.weight;
            }
        }
        double excess = sum - draws.terminationWeight;
        if (excess <= 0.0) {
            return 0;
        }
        return (int) Math.floor(excess * 1000.0);
    }

    private static void writeReport(Types.ReportDoc doc) throws Exception {
        Files.createDirectories(OUT.getParent());
        StringBuilder sb = new StringBuilder();
        sb.append("{\n");
        sb.append("  \"case_id\": ").append(doc.caseId).append(",\n");
        sb.append("  \"run_mode\": \"").append(doc.runMode).append("\",\n");
        sb.append("  \"replay_epoch\": ").append(doc.replayEpoch).append(",\n");
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
EOF
