package dev.terminus.trivia.util;

import java.nio.file.Path;
import java.nio.file.Paths;

public final class PathUtil {
    private PathUtil() {}

    public static Path resolveFromConfig(Path configFile, String raw) {
        Path p = Paths.get(raw);
        if (p.isAbsolute()) {
            return p.normalize();
        }
        Path base = configFile.toAbsolutePath().getParent();
        if (base == null) {
            base = Paths.get(".");
        }
        return base.resolve(p).normalize();
    }

    public static String toPosixRelative(Path root, Path absolute) {
        Path rel = root.toAbsolutePath().normalize().relativize(absolute.toAbsolutePath().normalize());
        return rel.toString().replace('\\', '/');
    }
}
