package w8.z3;

import java.nio.file.Path;

/** Resolves the annex epoch used for stamp latch and seal binding. */
public final class EpochTap {
  private final JrnGate gate = new JrnGate();

  public int effective(int manifestEpoch, Path side) throws Exception {
    Integer snap = gate.loadEpochSnap(side);
    if (snap != null) {
      return snap;
    }
    return manifestEpoch;
  }
}
