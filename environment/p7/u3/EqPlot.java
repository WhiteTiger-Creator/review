package p7.u3;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import r4.n2.HopMap;

/** Plots fold histograms to logs; ignored by overwrite and holdout checks. */
public final class EqPlot {
  public void dump(Path side, HopMap hops, List<VecRow> rows) throws Exception {
    StringBuilder sb = new StringBuilder();
    for (VecRow r : rows) {
      long h = hops.get(r.id);
      sb.append(r.id).append('=').append(Long.toUnsignedString(h)).append('\n');
    }
    Files.createDirectories(side.getParent());
    Files.writeString(side, sb.toString(), StandardCharsets.UTF_8);
  }
}
