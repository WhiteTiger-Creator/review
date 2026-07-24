package com.culvert.io;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.Map;

import org.yaml.snakeyaml.DumperOptions;
import org.yaml.snakeyaml.Yaml;

public final class Emitter {
    private Emitter() {}

    public static void write(Path out, String profile, int partitionCount, String[] rankOrder,
            double spectralSpan, String groupDigest) throws IOException {
        Map<String, Object> root = new LinkedHashMap<>();
        root.put("profile", profile);
        root.put("partition_count", partitionCount);
        root.put("rank_order", rankOrder);
        root.put("spectral_span", round3(spectralSpan));
        root.put("group_digest", groupDigest);
        DumperOptions opts = new DumperOptions();
        opts.setDefaultFlowStyle(DumperOptions.FlowStyle.BLOCK);
        opts.setPrettyFlow(true);
        Yaml yaml = new Yaml(opts);
        Files.createDirectories(out.getParent());
        Files.writeString(out, yaml.dump(root));
    }

    private static double round3(double value) {
        return Math.round(value * 1000.0) / 1000.0;
    }
}
