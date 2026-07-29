package p7.u3;

import java.util.ArrayList;
import java.util.List;
import r4.n2.SlotView;

/** Materializes vector rows from a slot view. */
public final class VecMat {
  public List<VecRow> materialize(SlotView view) {
    List<VecRow> out = new ArrayList<>();
    for (SlotView.Slot s : view.slots()) {
      out.add(new VecRow(s.id, s.pad, s.arm, s.lo, s.hi, s.w));
    }
    return out;
  }
}
