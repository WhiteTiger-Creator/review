package tools.uxr;

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
    Files.deleteIfExists(side.resolve("fold.soft"));
    EqFold fold = new EqFold();
    List<long[]> out = new ArrayList<>();
    for (VecRow row : rows) {
      long tag = fold.exact(hops, row, epoch);
      out.add(new long[] {tag, row.arm, row.lo, row.hi, row.w, row.pad});
    }
    return out;
  }

  static List<VecRow> rows(SlotView slots) {
    return new VecMat().materialize(slots);
  }
}
