package p7.u3;

import r4.n2.AdjHop;
import r4.n2.HopMap;

/** Fold scores under exact and shallow compositions. */
public final class EqFold {
  private final AdjHop table = new AdjHop();

  public long shallow(HopMap hops, VecRow row) {
    long base = ((long) row.lo) * (long) row.w;
    return base & 0xffffffffffffL;
  }

  public long exact(HopMap hops, VecRow row, int epoch) {
    long h = hops.get(row.id);
    long loW = ((long) row.lo) * (long) row.w;
    long base = (h & 0xffffffffL) ^ loW;
    base &= 0xffffffffffffL;
    if (row.arm == 0) {
      return base;
    }
    int width = table.holdRotate(row.pad) + (epoch % 3);
    long rot = Long.rotateLeft(base, width);
    long padMix =
        (((long) row.pad) * 0xA5A5L)
            ^ ((long) (epoch & 0xff))
            ^ (((long) row.pad) << 16)
            ^ (((long) (epoch % 3)) << 24)
            ^ ((((long) (epoch & 0xff)) << 8) | ((long) (row.pad & 0xff)));
    return (rot ^ (long) row.hi ^ padMix) & 0xffffffffffffL;
  }
}
