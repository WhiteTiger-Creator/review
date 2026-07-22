#!/usr/bin/env python3
"""Emit fixed Java sources into solution/patches/."""

from __future__ import annotations

from pathlib import Path

TASK = Path(__file__).resolve().parents[1]
SRC = TASK / "environment" / "app" / "src" / "main" / "java" / "dev" / "terminus" / "trivia"
OUT = TASK / "solution" / "patches"

FILES = {
    "util/PathUtil.java": '''package dev.terminus.trivia.util;

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
        return rel.toString().replace('\\\\', '/');
    }
}
''',
    "manifest/YamlJsonLoader.java": '''package dev.terminus.trivia.manifest;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.snakeyaml.engine.v2.api.Load;
import org.snakeyaml.engine.v2.api.LoadSettings;
import org.snakeyaml.engine.v2.schema.JsonSchema;

import java.nio.file.Files;
import java.nio.file.Path;

public final class YamlJsonLoader {
    private static final ObjectMapper MAPPER = new ObjectMapper();
    private static final Load LOADER = new Load(
            LoadSettings.builder().setSchema(JsonSchema.getInstance()).build());

    private YamlJsonLoader() {}

    public static JsonNode load(Path path) throws Exception {
        String text = Files.readString(path);
        Object raw = LOADER.loadFromString(text);
        return MAPPER.valueToTree(raw);
    }
}
''',
    "manifest/TomlJsonLoader.java": '''package dev.terminus.trivia.manifest;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.tomlj.TomlArray;
import org.tomlj.TomlParseResult;
import org.tomlj.TomlTable;
import org.tomlj.TomlValue;

import java.nio.file.Path;
import java.util.Map;

public final class TomlJsonLoader {
    private static final ObjectMapper MAPPER = new ObjectMapper();

    private TomlJsonLoader() {}

    public static JsonNode load(Path path) throws Exception {
        TomlParseResult parsed = org.tomlj.Toml.parse(path);
        if (parsed.hasErrors()) {
            throw new IllegalArgumentException(parsed.errors().toString());
        }
        return toJson(parsed.toTomlTable());
    }

    private static JsonNode toJson(TomlTable table) {
        ObjectNode node = MAPPER.createObjectNode();
        for (Map.Entry<String, Object> entry : table.toMap().entrySet()) {
            node.set(entry.getKey(), valueToJson(table.get(entry.getKey())));
        }
        return node;
    }

    private static JsonNode valueToJson(TomlValue value) {
        if (value == null) {
            return MAPPER.nullNode();
        }
        return switch (value.type()) {
            case STRING -> MAPPER.valueToTree(value.toString());
            case BOOLEAN -> MAPPER.valueToTree(value.toBoolean());
            case LONG, INTEGER -> MAPPER.valueToTree(value.toLong());
            case DOUBLE -> MAPPER.valueToTree(value.toDouble());
            case OFFSET_DATE_TIME -> MAPPER.valueToTree(value.toOffsetDateTime().toString());
            case ARRAY -> {
                ArrayNode arr = MAPPER.createArrayNode();
                TomlArray array = value.toTomlArray();
                for (int i = 0; i < array.size(); i++) {
                    arr.add(valueToJson(array.get(i)));
                }
                yield arr;
            }
            case TABLE -> toJson(value.toTomlTable());
            default -> MAPPER.valueToTree(value.toString());
        };
    }
}
''',
    "dataset/QuestionFingerprint.java": '''package dev.terminus.trivia.dataset;

import dev.terminus.trivia.util.Digest;
import dev.terminus.trivia.util.UnicodeNormalizer;

public final class QuestionFingerprint {
    private QuestionFingerprint() {}

    public static String compute(String question) {
        return Digest.sha256Hex(UnicodeNormalizer.normalizeAnswer(question == null ? "" : question));
    }
}
''',
    "dataset/DuckDbCatalog.java": '''package dev.terminus.trivia.dataset;

import java.sql.*;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

public final class DuckDbCatalog implements AutoCloseable {
    private final Connection connection;

    public DuckDbCatalog(String parquetPath) throws SQLException {
        connection = DriverManager.getConnection("jdbc:duckdb:");
        try (Statement stmt = connection.createStatement()) {
            stmt.execute("CREATE OR REPLACE VIEW trivia AS SELECT * FROM read_parquet('"
                    + parquetPath.replace("'", "''") + "')");
        }
    }

    public Optional<QuestionRecord> lookupById(String questionId) throws SQLException {
        String sql = "SELECT question_id, question, answer_value, answer_aliases, category, difficulty, source_split "
                + "FROM trivia WHERE question_id = ?";
        try (PreparedStatement ps = connection.prepareStatement(sql)) {
            ps.setString(1, questionId);
            try (ResultSet rs = ps.executeQuery()) {
                if (rs.next()) {
                    return Optional.of(mapRow(rs));
                }
            }
        }
        return Optional.empty();
    }

    public int countById(String questionId) throws SQLException {
        try (PreparedStatement ps = connection.prepareStatement(
                "SELECT COUNT(*) FROM trivia WHERE question_id = ?")) {
            ps.setString(1, questionId);
            try (ResultSet rs = ps.executeQuery()) {
                rs.next();
                return rs.getInt(1);
            }
        }
    }

    public Optional<QuestionRecord> lookupByCanonicalRow(int oneBasedRow) throws SQLException {
        String sql = """
                SELECT question_id, question, answer_value, answer_aliases, category, difficulty, source_split
                FROM (
                  SELECT *, ROW_NUMBER() OVER (ORDER BY question_id ASC) AS canon_row
                  FROM trivia
                ) ordered WHERE canon_row = ?
                """;
        try (PreparedStatement ps = connection.prepareStatement(sql)) {
            ps.setInt(1, oneBasedRow);
            try (ResultSet rs = ps.executeQuery()) {
                if (rs.next()) {
                    return Optional.of(mapRow(rs));
                }
            }
        }
        return Optional.empty();
    }

    private QuestionRecord mapRow(ResultSet rs) throws SQLException {
        return new QuestionRecord(
                rs.getString("question_id"),
                rs.getString("question"),
                rs.getString("answer_value"),
                readAliases(rs.getArray("answer_aliases")),
                rs.getString("category"),
                rs.getInt("difficulty"),
                rs.getString("source_split"));
    }

    private List<String> readAliases(Array array) throws SQLException {
        List<String> aliases = new ArrayList<>();
        if (array == null) {
            return aliases;
        }
        Object[] values = (Object[]) array.getArray();
        if (values == null) {
            return aliases;
        }
        for (Object v : values) {
            if (v != null) {
                aliases.add(v.toString());
            }
        }
        return aliases;
    }

    @Override
    public void close() throws SQLException {
        connection.close();
    }
}
''',
    "dataset/LegacyLocatorResolver.java": '''package dev.terminus.trivia.dataset;

import dev.terminus.trivia.audit.AuditIssue;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

public final class LegacyLocatorResolver {
    private final DuckDbCatalog catalog;

    public LegacyLocatorResolver(DuckDbCatalog catalog) {
        this.catalog = catalog;
    }

    public DuckDbCatalog catalog() {
        return catalog;
    }

    public record ResolveResult(Optional<QuestionRecord> record, List<AuditIssue> issues) {}

    public ResolveResult resolve(QuestionLocator locator, String artifactPath) throws Exception {
        List<AuditIssue> issues = new ArrayList<>();
        if (locator.kind() != QuestionLocator.Kind.LEGACY_ROW) {
            throw new IllegalArgumentException("Not a legacy locator");
        }
        Optional<QuestionRecord> record = catalog.lookupByCanonicalRow(locator.row());
        if (record.isEmpty()) {
            issues.add(new AuditIssue(artifactPath, "/trivia/row", "dataset.missing-id",
                    "No record at legacy row " + locator.row()));
            return new ResolveResult(Optional.empty(), issues);
        }
        String expected = locator.fingerprint().orElse("");
        String actual = QuestionFingerprint.compute(record.get().question());
        if (!expected.equalsIgnoreCase(actual)) {
            issues.add(new AuditIssue(artifactPath, "/trivia/question_sha256", "dataset.fingerprint-mismatch",
                    "Fingerprint mismatch for row " + locator.row()));
            return new ResolveResult(Optional.empty(), issues);
        }
        return new ResolveResult(record, issues);
    }
}
''',
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for rel, content in FILES.items():
        path = OUT / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print("wrote", path)

    # Copy remaining sources from environment then overwrite patched ones already done
    import shutil

    for path in SRC.rglob("*.java"):
        rel = path.relative_to(SRC)
        dest = OUT / rel
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)

    print("Patch tree ready at", OUT)


if __name__ == "__main__":
    main()
