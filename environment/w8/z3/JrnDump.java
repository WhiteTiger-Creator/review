package w8.z3;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

/** Operator journal sketch; never feeds graded regeneration. */
public final class JrnDump {
  public void sketch(Path side, int epoch) throws Exception {
    Path out = side.resolve("jrn_sketch.txt");
    Files.createDirectories(side);
    Files.writeString(out, "epoch=" + epoch + "\n", StandardCharsets.UTF_8);
  }
}
