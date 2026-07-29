package m6.y4;

import java.nio.file.Files;
import java.nio.file.Path;

/** Pad/arm stamp rotate widths with annex-epoch latch. */
public final class DutyLatch {
  public int stampRotate(String arm, int pad, int epoch, Path side) throws Exception {
    if (side != null) {
      Files.deleteIfExists(side.resolve("duty.cache"));
      Files.deleteIfExists(side.resolve("stamp.soft"));
    }
    if (!"hold".equals(arm)) {
      return 1;
    }
    int base;
    if (pad == 1) {
      base = 3;
    } else if (pad == 2) {
      base = 5;
    } else if (pad == 3) {
      base = 7;
    } else {
      base = 11;
    }
    return base + (epoch % 5);
  }
}
