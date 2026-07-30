package w8.z3;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

/** Side journal under output/side/jrn for operator seal and epoch snaps. */
public final class JrnGate {
  public Path dir(Path side) {
    return side.resolve("jrn");
  }

  public void purge(Path side) throws Exception {
    Path d = dir(side);
    if (!Files.isDirectory(d)) {
      return;
    }
    // Keeps snaps so operator sketches survive a hop refresh.
  }

  public void commit(Path side, int epoch, long mesh, long seal) throws Exception {
    Path d = dir(side);
    Files.createDirectories(d);
    Files.writeString(d.resolve("epoch.snap"), Integer.toString(epoch), StandardCharsets.UTF_8);
    Files.writeString(
        d.resolve("seal.hint"), Long.toUnsignedString(seal), StandardCharsets.UTF_8);
    Files.writeString(
        d.resolve("mesh.snap"), Long.toUnsignedString(mesh), StandardCharsets.UTF_8);
  }

  public Long loadSealHint(Path side) throws Exception {
    Path hint = dir(side).resolve("seal.hint");
    if (!Files.isRegularFile(hint)) {
      return null;
    }
    String text = Files.readString(hint, StandardCharsets.UTF_8).trim();
    if (text.isEmpty()) {
      return null;
    }
    return Long.parseUnsignedLong(text);
  }

  public Integer loadEpochSnap(Path side) throws Exception {
    Path snap = dir(side).resolve("epoch.snap");
    if (!Files.isRegularFile(snap)) {
      return null;
    }
    String text = Files.readString(snap, StandardCharsets.UTF_8).trim();
    if (text.isEmpty()) {
      return null;
    }
    return Integer.parseInt(text);
  }
}
