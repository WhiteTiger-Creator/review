package tools.uxr;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import m6.y4.DutyLatch;
import m6.y4.DutyPlot;
import p7.u3.VecRow;
import q9.w2.SealPlot;
import q9.w2.SealRing;
import r4.n2.HopMap;
import r4.n2.SlotView;
import t3.k1.SeedBind;
import t3.k1.SeedDump;
import v5.h8.RowDto;
import w8.z3.EpochTap;
import w8.z3.JrnDump;

/** Public CLI driver writing /app/output/sol_run.json. */
public final class Main {
  private static final int PIPE_SEED = 0x4D31A7;

  public static void main(String[] args) throws Exception {
    Path root = Path.of("/app/data/annex31");
    Path out = Path.of("/app/output/sol_run.json");
    Path sealOut = Path.of("/app/output/replay_seal.json");
    Path side = Path.of("/app/output/side");

    LoadA31 loader = new LoadA31();
    int magic = loader.magic(root);
    new SeedDump().describe(PIPE_SEED, magic);
    int seed = new SeedBind().bind(PIPE_SEED, magic);
    int manifestEpoch = readEpoch(root.resolve("manifest.json"));
    int epoch = new EpochTap().effective(manifestEpoch, side);
    new DutyPlot().sketch(epoch);
    new JrnDump().sketch(side, epoch);

    SlotView slots = loader.load(root);
    HopMap hops = RunHop.go(slots, seed, side, epoch);
    List<VecRow> rows = RunFold.rows(slots);
    List<long[]> tags = RunFold.go(hops, slots, side, epoch);
    List<Long> spans = RunTap.go(hops, rows, side, epoch);

    DutyLatch latch = new DutyLatch();
    List<RowDto> emit = new ArrayList<>();
    long trainMesh = 0L;
    long holdMesh = 0L;
    long foldMesh = 0L;
    long stamp = 0L;
    for (int i = 0; i < rows.size(); i++) {
      VecRow row = rows.get(i);
      long tag = tags.get(i)[0];
      long sp = spans.get(i);
      long hk = hops.get(row.id);
      String hopKey = hex16(hk);
      long armBit = row.arm == 0 ? 0L : 1L;
      long join = hk ^ tag ^ sp ^ armBit;
      if (row.arm != 0) {
        join ^= (long) (epoch & 0xff);
      }
      String arm = row.arm == 0 ? "train" : "hold";
      emit.add(new RowDto(row.id, hopKey, tag, sp, hex16(join), arm, row.pad));
      if (row.arm == 0) {
        trainMesh ^= hk;
      } else {
        holdMesh ^= hk;
        foldMesh ^= tag;
      }
      int rot = latch.stampRotate(arm, row.pad, epoch, side);
      stamp ^= Long.rotateLeft(hk, rot) ^ tag ^ sp;
    }
    stamp ^= 0x631A31C0L;
    long mesh = Long.rotateLeft(trainMesh, epoch % 3) ^ holdMesh;
    long replay = new SealRing().seal(mesh, stamp, epoch, holdMesh, foldMesh, side);
    new SealPlot().sketch(side, mesh);
    RunEmit.go(out, emit, replay, epoch, side);
    writeSeal(sealOut, replay, epoch);
  }

  private static int readEpoch(Path manifest) throws Exception {
    String text = Files.readString(manifest, StandardCharsets.UTF_8);
    int ix = text.indexOf("\"epoch\"");
    if (ix < 0) {
      throw new IllegalStateException("epoch");
    }
    int colon = text.indexOf(':', ix);
    int end = colon + 1;
    while (end < text.length() && Character.isWhitespace(text.charAt(end))) {
      end++;
    }
    int start = end;
    while (end < text.length() && Character.isDigit(text.charAt(end))) {
      end++;
    }
    return Integer.parseInt(text.substring(start, end));
  }

  private static void writeSeal(Path out, long seal, int epoch) throws Exception {
    String body =
        "{\n"
            + "  \"schema_version\": 1,\n"
            + "  \"epoch\": "
            + epoch
            + ",\n"
            + "  \"seal_hex\": \""
            + hex16(seal)
            + "\"\n"
            + "}\n";
    Files.createDirectories(out.getParent());
    Files.writeString(out, body, StandardCharsets.UTF_8);
  }

  private static String hex16(long v) {
    String h = Long.toUnsignedString(v, 16);
    if (h.length() > 16) {
      h = h.substring(h.length() - 16);
    }
    return "0".repeat(16 - h.length()) + h;
  }
}
