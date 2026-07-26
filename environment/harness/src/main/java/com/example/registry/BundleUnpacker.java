package com.example.registry;

import org.apache.commons.compress.archivers.tar.TarArchiveEntry;
import org.apache.commons.compress.archivers.tar.TarArchiveInputStream;
import org.apache.commons.compress.compressors.gzip.GzipCompressorInputStream;

import java.io.BufferedInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;

/**
 * Unpacks the mlflow_registry_bundle.tar.gz into target/bundle. The bundle carries MLflow
 * run exports, model signature JSON, and YAML environment files captured alongside the
 * registry export; the seed database contents and pinned Hugging Face config responses
 * are not in this bundle; they're served by the sealed data service (see
 * {@link SealedDataService}) so they aren't directly readable on disk. Extraction is
 * guarded against path traversal.
 */
final class BundleUnpacker {

    void unpack(Path bundle, Path destination) throws IOException {
        if (!Files.isRegularFile(bundle)) {
            throw new IOException("registry bundle not found: " + bundle);
        }
        // Clean out any prior extraction so replays start from a pristine tree.
        if (Files.exists(destination)) {
            deleteRecursively(destination);
        }
        Files.createDirectories(destination);

        try (InputStream fileIn = Files.newInputStream(bundle);
             BufferedInputStream buffered = new BufferedInputStream(fileIn);
             GzipCompressorInputStream gzipIn = new GzipCompressorInputStream(buffered);
             TarArchiveInputStream tarIn = new TarArchiveInputStream(gzipIn)) {

            TarArchiveEntry entry;
            while ((entry = tarIn.getNextEntry()) != null) {
                Path resolved = destination.resolve(entry.getName()).normalize();
                if (!resolved.startsWith(destination)) {
                    throw new IOException("refusing to extract entry outside destination: "
                            + entry.getName());
                }
                if (entry.isDirectory()) {
                    Files.createDirectories(resolved);
                } else {
                    Files.createDirectories(resolved.getParent());
                    Files.copy(tarIn, resolved, StandardCopyOption.REPLACE_EXISTING);
                }
            }
        }
    }

    private void deleteRecursively(Path root) throws IOException {
        if (!Files.exists(root)) {
            return;
        }
        Files.walk(root)
                .sorted((a, b) -> b.getNameCount() - a.getNameCount())
                .forEach(p -> {
                    try {
                        Files.deleteIfExists(p);
                    } catch (IOException e) {
                        throw new RuntimeException("failed to clean " + p, e);
                    }
                });
    }
}
