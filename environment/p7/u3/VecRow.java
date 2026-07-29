package p7.u3;

/** One packed row for fold scoring. */
public final class VecRow {
  public final String id;
  public final int pad;
  public final int arm;
  public final int lo;
  public final int hi;
  public final int w;

  public VecRow(String id, int pad, int arm, int lo, int hi, int w) {
    this.id = id;
    this.pad = pad;
    this.arm = arm;
    this.lo = lo;
    this.hi = hi;
    this.w = w;
  }
}
