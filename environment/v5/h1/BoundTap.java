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
      loTerm ^= (long) ((epoch & 0xff) ^ row.pad);
    }
    long mixed = (width * 0x9E3779B9L) & 0xffffffffffffffffL;
    mixed ^= (h & 0xffffffffL);
    mixed ^= loTerm;
    mixed &= 0xffffffffffffffffL;
    if (mixed < env.lo) {
      return env.lo;
    }
    if (mixed > env.hi) {
      return env.hi;
    }
    return mixed;
  }
}
