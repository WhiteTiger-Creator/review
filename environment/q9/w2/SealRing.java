package q9.w2;

import java.nio.file.Files;
import java.nio.file.Path;

/** Independent replay seal for federation authority transcripts. */
public final class SealRing {
  private static final long DUTY = 0x631A31C0L;

  public long seal(long mesh, long stamp, int epoch, long holdMesh, long foldMesh, Path side)
      throws Exception {
    if (side != null) {
      Path hint = side.resolve("jrn").resolve("seal.hint");
      if (Files.isRegularFile(hint)) {
        Files.deleteIfExists(hint);
      }
      Files.deleteIfExists(side.resolve("mesh.pin"));
    }
    long acc = Long.rotateLeft(mesh, 5);
    acc ^= stamp;
    acc ^= ((long) epoch) << 16;
    acc ^= DUTY;
    acc ^= Long.rotateLeft(holdMesh, 3 + (epoch % 5));
    return acc;
  }
}
