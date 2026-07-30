package tools.uxr;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import p7.u3.EqFold;
import p7.u3.EqPlot;
import p7.u3.VecMat;
import p7.u3.VecRow;
import r4.n2.HopMap;
import r4.n2.SlotView;

final class RunFold {
  static List<long[]> go(HopMap hops, SlotView slots, Path side, int epoch) throws Exception {
    List<VecRow> rows = new VecMat().materialize(slots);
    new EqPlot().dump(side.resolve("plot.txt"), hops, rows);
    EqFold fold = new EqFold();
    Path soft = side.resolve("fold.soft");
    boolean softHold = Files.isRegularFile(soft);
    List<long[]> out = new ArrayList<>();
    for (VecRow row : rows) {
      long tag;
      if (row.arm != 0 && softHold) {
        tag = fold.shallow(hops, row);
      } else {
        tag = fold.exact(hops, row, epoch);
      }
      out.add(new long[] {tag, row.arm, row.lo, row.hi, row.w, row.pad});
    }
    Files.writeString(soft, "1", StandardCharsets.UTF_8);
    return out;
  }

  static List<VecRow> rows(SlotView slots) {
    return new VecMat().materialize(slots);
  }
}
