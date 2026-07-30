package w8.z3;

import java.nio.file.Path;

/** Resolves the annex epoch used for stamp latch and seal binding. */
public final class EpochTap {
  public int effective(int manifestEpoch, Path side) throws Exception {
    if (side == null) {
      return manifestEpoch;
    }
    return manifestEpoch;
  }
}
