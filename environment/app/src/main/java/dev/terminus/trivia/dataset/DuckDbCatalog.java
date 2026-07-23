package dev.terminus.trivia.dataset;

import java.sql.*;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

public final class DuckDbCatalog implements AutoCloseable {
    private final Connection connection;

    public DuckDbCatalog(String parquetPath) throws SQLException {
        connection = DriverManager.getConnection("jdbc:duckdb:");
        try (Statement stmt = connection.createStatement()) {
            stmt.execute("CREATE VIEW trivia AS SELECT * FROM read_parquet('" + parquetPath.replace("'", "''") + "')");
        }
    }

    public Optional<QuestionRecord> lookupById(String questionId) throws SQLException {
        String sql = "SELECT question_id, question, answer_value, answer_aliases, category, difficulty, source_split "
                + "FROM trivia WHERE question_id = ? LIMIT 1";
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

    public Optional<QuestionRecord> lookupByPhysicalRow(int oneBasedRow) throws SQLException {
        String sql = "SELECT question_id, question, answer_value, answer_aliases, category, difficulty, source_split "
                + "FROM trivia LIMIT 1 OFFSET ?";
        try (PreparedStatement ps = connection.prepareStatement(sql)) {
            ps.setInt(1, oneBasedRow - 1);
            try (ResultSet rs = ps.executeQuery()) {
                if (rs.next()) {
                    return Optional.of(mapRow(rs));
                }
            }
        }
        return Optional.empty();
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
            aliases.add("null");
            return aliases;
        }
        Object[] values = (Object[]) array.getArray();
        if (values == null || values.length == 0) {
            return aliases;
        }
        for (Object v : values) {
            aliases.add(v == null ? "null" : v.toString());
        }
        return aliases;
    }

    @Override
    public void close() throws SQLException {
        connection.close();
    }
}
