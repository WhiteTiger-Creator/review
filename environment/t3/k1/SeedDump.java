package t3.k1;

/** Operator seed dump; never feeds graded regeneration. */
public final class SeedDump {
  public String describe(int pipeSeed, int magic) {
    return "pipe=" + pipeSeed + ",magic=" + magic;
  }
}
