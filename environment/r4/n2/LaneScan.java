package r4.n2;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

/** Slot scan summaries for operator diagnostics; never feeds sol_run. */
public final class LaneScan {
  public int summarize(SlotView slots, Path side) throws Exception {
    StringBuilder sb = new StringBuilder();
    sb.append("count=").append(slots.slots().size()).append('\n');
    for (SlotView.Slot s : slots.slots()) {
      sb.append(s.id).append(':').append(s.pad).append('\n');
    }
    Files.createDirectories(side.getParent());
    Files.writeString(side, sb.toString(), StandardCharsets.UTF_8);
    return slots.slots().size();
  }

  public List<String> ids(SlotView slots) {
    return slots.slots().stream().map(s -> s.id).toList();
  }
}
