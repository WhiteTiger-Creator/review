package com.example.registry;

import java.io.IOException;
import java.io.Writer;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Dumps the migrated H2 tables to a canonical JSONL file whose bytes are stable across
 * runs, so a SHA-256 taken over it is a reliable fingerprint of the migration outcome.
 *
 * <p>Canonical rules (must match the expected digest byte-for-byte):
 * <ol>
 *   <li><b>Table order</b>: registered_models first, then model_versions. One JSON object
 *       per line; each line is prefixed with its table via a leading "table" field.</li>
 *   <li><b>Column order</b>: a fixed, explicit list per table (see TABLES). The "table"
 *       field is always emitted first, followed by that table's columns in listed
 *       order.</li>
 *   <li><b>Row order</b>: rows are read with an explicit ORDER BY on the table's primary
 *       key (name for registered_models; model_name, version for model_versions).</li>
 *   <li><b>Value normalization</b>: SQL NULL -&gt; JSON null; integers -&gt; bare integer
 *       literals; decimals/reals -&gt; fixed 6-decimal-place strings-as-numbers; strings
 *       -&gt; JSON strings with a minimal, fixed escape set; booleans -&gt; true/false.</li>
 *   <li><b>Line ending</b>: each record is followed by a single '\n'; the file ends with a
 *       trailing newline. UTF-8, no BOM.</li>
 * </ol>
 */
final class CanonicalExporter {

    /** Fixed table order and per-table column order. */
    private static final List<TableSpec> TABLES = List.of(
            new TableSpec(
                    "registered_models",
                    List.of("name", "created_time", "description", "framework",
                            "hf_repo_id", "hf_revision"),
                    "ORDER BY name"),
            new TableSpec(
                    "model_versions",
                    List.of("model_name", "version", "source_run_id", "parent_version",
                            "current_stage", "hf_architecture", "hf_model_type",
                            "hf_hidden_size", "hf_num_layers", "hf_num_heads"),
                    "ORDER BY model_name, version"));

    void export(Connection connection, Path output) throws IOException, SQLException {
        Files.createDirectories(output.getParent());
        StringBuilder buffer = new StringBuilder();
        for (TableSpec table : TABLES) {
            appendTable(connection, table, buffer);
        }
        try (Writer writer = Files.newBufferedWriter(output, StandardCharsets.UTF_8)) {
            writer.write(buffer.toString());
        }
    }

    private void appendTable(Connection connection, TableSpec table, StringBuilder buffer)
            throws SQLException {
        String columnList = String.join(", ", table.columns);
        String sql = "SELECT " + columnList + " FROM " + table.name + " " + table.orderBy;
        try (Statement statement = connection.createStatement();
             ResultSet rs = statement.executeQuery(sql)) {
            while (rs.next()) {
                Map<String, String> record = new LinkedHashMap<>();
                record.put("table", jsonString(table.name));
                for (String column : table.columns) {
                    record.put(column, normalize(rs, column));
                }
                buffer.append(toJsonObject(record)).append('\n');
            }
        }
    }

    private String normalize(ResultSet rs, String column) throws SQLException {
        Object value = rs.getObject(column);
        if (value == null || rs.wasNull()) {
            return "null";
        }
        if (value instanceof Boolean b) {
            return b ? "true" : "false";
        }
        if (value instanceof Integer || value instanceof Long
                || value instanceof Short || value instanceof Byte) {
            return value.toString();
        }
        if (value instanceof BigDecimal bd) {
            return bd.setScale(6, RoundingMode.HALF_UP).stripTrailingZeros().toPlainString();
        }
        if (value instanceof Double || value instanceof Float) {
            BigDecimal bd = new BigDecimal(value.toString()).setScale(6, RoundingMode.HALF_UP);
            return bd.stripTrailingZeros().toPlainString();
        }
        return jsonString(value.toString());
    }

    private String toJsonObject(Map<String, String> record) {
        StringBuilder sb = new StringBuilder();
        sb.append('{');
        boolean first = true;
        for (Map.Entry<String, String> entry : record.entrySet()) {
            if (!first) {
                sb.append(',');
            }
            first = false;
            sb.append(jsonString(entry.getKey())).append(':').append(entry.getValue());
        }
        sb.append('}');
        return sb.toString();
    }

    private static String jsonString(String value) {
        StringBuilder sb = new StringBuilder(value.length() + 2);
        sb.append('"');
        for (int i = 0; i < value.length(); i++) {
            char c = value.charAt(i);
            switch (c) {
                case '"': sb.append("\\\""); break;
                case '\\': sb.append("\\\\"); break;
                case '\n': sb.append("\\n"); break;
                case '\r': sb.append("\\r"); break;
                case '\t': sb.append("\\t"); break;
                default:
                    if (c < 0x20) {
                        sb.append(String.format("\\u%04x", (int) c));
                    } else {
                        sb.append(c);
                    }
            }
        }
        sb.append('"');
        return sb.toString();
    }

    private record TableSpec(String name, List<String> columns, String orderBy) {
    }
}
