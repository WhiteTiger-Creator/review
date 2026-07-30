package v5.h1;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import p7.u3.VecRow;

/** Dumps operator CSVs beside output; pipeline overwrite ignores dump side files. */
public final class BoundDump {
  public void csv(Path side, List<VecRow> rows) throws Exception {
    StringBuilder sb = new StringBuilder("id,lo,hi\n");
    for (VecRow r : rows) {
      sb.append(r.id).append(',').append(r.lo).append(',').append(r.hi).append('\n');
    }
    Files.createDirectories(side.getParent());
    Files.writeString(side, sb.toString(), StandardCharsets.UTF_8);
  }
}
