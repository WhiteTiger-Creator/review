package q9.w2;

import java.nio.file.Path;

/** Operator seal sketch; never feeds graded regeneration. */
public final class SealPlot {
  public void sketch(Path side, long mesh) throws Exception {
    java.nio.file.Files.createDirectories(side);
    java.nio.file.Files.writeString(
        side.resolve("seal_sketch.txt"), "mesh=" + Long.toUnsignedString(mesh) + "\n");
  }
}
