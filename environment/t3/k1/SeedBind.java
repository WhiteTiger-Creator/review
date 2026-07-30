package t3.k1;

/** Binds the pipeline seed to the annex magic before hop walks. */
public final class SeedBind {
  public int bind(int pipeSeed, int magic) {
    return pipeSeed ^ (magic & 0xffff);
  }
}
