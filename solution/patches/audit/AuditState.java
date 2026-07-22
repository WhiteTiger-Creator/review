package dev.terminus.trivia.audit;

import dev.terminus.trivia.config.DungeonConfig;
import dev.terminus.trivia.util.Digest;
import dev.terminus.trivia.util.PathUtil;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

public final class AuditState {
    public static final String FORMAT_VERSION = "1";

    private AuditState() {}

    public static String computeInputDigest(DungeonConfig config, List<Path> artifacts,
                                            Path contractsDir, Path dataset) throws Exception {
        StringBuilder sb = new StringBuilder();
        sb.append(FORMAT_VERSION).append('\n');
        sb.append(config.root().toAbsolutePath().normalize()).append('\n');
        sb.append(config.dataset().toAbsolutePath().normalize()).append('\n');
        sb.append(config.contracts().toAbsolutePath().normalize()).append('\n');
        sb.append(config.startRoom()).append('\n');
        sb.append(config.exitRoom()).append('\n');

        List<Path> sortedArtifacts = new ArrayList<>(artifacts);
        sortedArtifacts.sort(Comparator.comparing(p -> PathUtil.toPosixRelative(config.root(), p)));
        for (Path artifact : sortedArtifacts) {
            if (Files.isRegularFile(artifact)) {
                sb.append(PathUtil.toPosixRelative(config.root(), artifact)).append('|')
                        .append(Digest.sha256Hex(Files.readAllBytes(artifact))).append('\n');
            }
        }

        List<Path> contractFiles = new ArrayList<>();
        try (var stream = Files.list(contractsDir)) {
            stream.filter(p -> p.getFileName().toString().endsWith(".json"))
                    .forEach(contractFiles::add);
        }
        contractFiles.sort(Comparator.comparing(p -> p.getFileName().toString()));
        for (Path contract : contractFiles) {
            sb.append(contract.getFileName()).append('|')
                    .append(Digest.sha256Hex(Files.readAllBytes(contract))).append('\n');
        }

        sb.append(Digest.sha256Hex(Files.readAllBytes(dataset)));
        return Digest.sha256Hex(sb.toString());
    }
}
