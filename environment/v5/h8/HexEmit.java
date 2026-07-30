package v5.h8;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import m6.y4.DutyLatch;
import w8.z3.JrnGate;

/** Serializes rows to the public sol_run path. */
public final class HexEmit {
  private static final long DUTY_MIX = 0x631A31C0L;
  private final DutyLatch latch = new DutyLatch();
  private final JrnGate jrn = new JrnGate();

  public void write(Path out, List<RowDto> rows, long replaySeal, int epoch, Path side)
      throws Exception {
    List<RowDto> sorted = new ArrayList<>(rows);
    sorted.sort(Comparator.comparing(r -> r.rowId));
    long trainMesh = 0L;
    long holdMesh = 0L;
    long stamp = 0L;
    for (RowDto r : sorted) {
      long hk = Long.parseUnsignedLong(r.hopKey, 16);
      if ("hold".equals(r.arm)) {
        holdMesh ^= hk;
      } else {
        trainMesh ^= hk;
      }
      int rot = latch.stampRotate(r.arm, r.pad, epoch, side);
      stamp ^= Long.rotateLeft(hk, rot) ^ r.foldTag ^ r.spanU64;
    }
    stamp ^= DUTY_MIX;
    long mesh = Long.rotateLeft(trainMesh, epoch % 3) ^ holdMesh;
    StringBuilder sb = new StringBuilder();
    sb.append("{\n");
    sb.append("  \"schema_version\": 1,\n");
    sb.append("  \"rows\": [\n");
    for (int i = 0; i < sorted.size(); i++) {
      RowDto r = sorted.get(i);
      sb.append("    {\n");
      sb.append("      \"row_id\": \"").append(esc(r.rowId)).append("\",\n");
      sb.append("      \"hop_key\": \"").append(esc(r.hopKey)).append("\",\n");
      sb.append("      \"fold_tag\": ").append(Long.toUnsignedString(r.foldTag)).append(",\n");
      sb.append("      \"span_u64\": ").append(Long.toUnsignedString(r.spanU64)).append(",\n");
      sb.append("      \"join_hex\": \"").append(esc(r.joinHex)).append("\",\n");
      sb.append("      \"arm\": \"").append(esc(r.arm)).append("\"\n");
      sb.append("    }");
      if (i + 1 < sorted.size()) {
        sb.append(',');
      }
      sb.append('\n');
    }
    sb.append("  ],\n");
    sb.append("  \"mesh_digest\": \"").append(hex16(mesh)).append("\",\n");
    sb.append("  \"auth_stamp\": \"").append(hex16(stamp)).append("\",\n");
    sb.append("  \"replay_seal\": \"").append(hex16(replaySeal)).append("\"\n");
    sb.append("}\n");
    Files.createDirectories(out.getParent());
    Files.writeString(out, sb.toString(), StandardCharsets.UTF_8);
    if (side != null) {
      jrn.commit(side, epoch, mesh, replaySeal);
    }
  }

  private static String esc(String s) {
    return s.replace("\\", "\\\\").replace("\"", "\\\"");
  }

  private static String hex16(long v) {
    String h = Long.toUnsignedString(v, 16);
    if (h.length() > 16) {
      h = h.substring(h.length() - 16);
    }
    return "0".repeat(16 - h.length()) + h;
  }
}
