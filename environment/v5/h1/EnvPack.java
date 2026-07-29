package v5.h1;

/** Published bound pack for span checks. */
public final class EnvPack {
  public final long lo;
  public final long hi;

  public EnvPack(long lo, long hi) {
    this.lo = lo;
    this.hi = hi;
  }
}
