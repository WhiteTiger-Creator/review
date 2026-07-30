package r4.n2;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/** Packed row view for hop walks. */
public final class SlotView {
  public static final class Slot {
    public final String id;
    public final int pad;
    public final int arm;
    public final int lo;
    public final int hi;
    public final int w;

    public Slot(String id, int pad, int arm, int lo, int hi, int w) {
      this.id = id;
      this.pad = pad;
      this.arm = arm;
      this.lo = lo;
      this.hi = hi;
      this.w = w;
    }
  }

  private final List<Slot> slots;

  public SlotView(List<Slot> slots) {
    this.slots = Collections.unmodifiableList(new ArrayList<>(slots));
  }

  public List<Slot> slots() {
    return slots;
  }
}
