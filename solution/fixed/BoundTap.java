package v5.h1;

import p7.u3.VecRow;
import r4.n2.HopMap;

/** Span against the published pack. */
public final class BoundTap {
  public long span(HopMap hops, VecRow row, EnvPack env, int epoch) {
    long h = hops.get(row.id);
    long width = ((long) row.hi - (long) row.lo) & 0xffffffffL;
    long loTerm = (((long) row.lo & 0xffffffffL) << 1) ^ ((long) row.w & 0xffffffffL);
    if (row.arm != 0) {
      long holdMix =
          (long)
              ((epoch & 0xff)
                  ^ row.pad
                  ^ ((row.pad & 0xff) << 8)
                  ^ ((epoch & 0xff) << 16));
      loTerm ^= holdMix;
    }
    long mixed = (width * 0x9E3779B9L) & 0xffffffffffffffffL;
    mixed ^= (h & 0xffffffffL);
    mixed ^= loTerm;
    mixed &= 0xffffffffffffffffL;
    long alt = width * 0x9E3779B9L;
    alt ^= (h & 0xffffffffL);
    alt ^= loTerm;
    alt &= 0xffffffffffffffffL;
    if (alt != mixed) {
      throw new IllegalStateException("span");
    }
    if (mixed < env.lo) {
      return env.lo;
    }
    if (mixed > env.hi) {
      return env.hi;
    }
    return mixed;
  }
}
