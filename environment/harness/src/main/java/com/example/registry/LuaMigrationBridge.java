package com.example.registry;

import org.luaj.vm2.Globals;
import org.luaj.vm2.LoadState;
import org.luaj.vm2.LuaTable;
import org.luaj.vm2.LuaValue;
import org.luaj.vm2.Varargs;
import org.luaj.vm2.compiler.LuaC;
import org.luaj.vm2.lib.Bit32Lib;
import org.luaj.vm2.lib.CoroutineLib;
import org.luaj.vm2.lib.OneArgFunction;
import org.luaj.vm2.lib.PackageLib;
import org.luaj.vm2.lib.StringLib;
import org.luaj.vm2.lib.TableLib;
import org.luaj.vm2.lib.jse.JseBaseLib;
import org.luaj.vm2.lib.jse.JseMathLib;

import java.io.IOException;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.ResultSetMetaData;
import java.sql.SQLException;
import java.sql.Types;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * Executes Lua migration scripts against the H2 metadata database through an in-JVM LuaJ
 * interpreter. Migrations reach the database and the Hugging Face Hub only through the
 * globals this bridge installs:
 *
 * <ul>
 *   <li>{@code db.query(sql)} -&gt; array of row tables keyed by lowercase column name;</li>
 *   <li>{@code db.update(sql)} -&gt; affected row count;</li>
 *   <li>{@code http.get(url)} -&gt; response body string;</li>
 *   <li>{@code json.decode(text)} -&gt; a Lua table for a JSON object/array.</li>
 * </ul>
 *
 * Migrations never open the database file, the seed SQL, or a socket directly; the bridge
 * is the only surface they are given. This is enforced at the interpreter level, not just
 * by convention: the Lua environment is built by hand rather than via
 * {@code JsePlatform.standardGlobals()}, so {@code io.*}, {@code os.*}, {@code require} /
 * {@code package.*}, {@code dofile}/{@code loadfile}, and Java interop via
 * {@code luajava.*} are never installed in the first place. {@code db.query}/
 * {@code db.update} additionally reject SQL that reaches outside the database itself
 * (H2's {@code CSVREAD}/file-I/O functions, {@code CREATE ALIAS}/{@code CREATE TRIGGER}
 * Java interop, linked datasources) — see {@link #checkSqlAllowed}.
 */
final class LuaMigrationBridge {

    private final Connection connection;
    private final HubConfigClient hubConfigClient;

    LuaMigrationBridge(Connection connection, HubConfigClient hubConfigClient) {
        this.connection = connection;
        this.hubConfigClient = hubConfigClient;
    }

    /** Load, install globals, and run a single migration file. */
    void runMigration(Path migrationFile) throws IOException {
        String source = Files.readString(migrationFile, StandardCharsets.UTF_8);
        LuaValue globals = sandboxedGlobals();

        LuaTable db = new LuaTable();
        db.set("query", new QueryFunction());
        db.set("update", new UpdateFunction());
        globals.set("db", db);

        LuaTable http = new LuaTable();
        http.set("get", new HttpGetFunction());
        globals.set("http", http);

        LuaTable json = new LuaTable();
        json.set("decode", new JsonDecodeFunction());
        globals.set("json", json);

        LuaValue chunk = globals.get("load").call(
                LuaValue.valueOf(source),
                LuaValue.valueOf(migrationFile.getFileName().toString()));
        if (chunk.isnil()) {
            throw new IOException("failed to load migration: " + migrationFile);
        }
        chunk.call();
    }

    /**
     * Builds a restricted Lua environment: the base language (control flow, tables,
     * strings, math, coroutines) plus whatever the caller layers on top (db/http/json).
     * Omits {@code JseIoLib} ({@code io.*}), {@code JseOsLib} ({@code os.*}), and
     * {@code LuajavaLib} (arbitrary Java class access) compared to
     * {@code JsePlatform.standardGlobals()}. {@code PackageLib} is loaded only because the
     * other libraries register themselves into {@code package.loaded} as part of their own
     * {@code call()} setup; once that's done, {@code require}/{@code package} (module
     * loading) and {@code dofile}/{@code loadfile} (base functions that read files
     * directly) are all nilled back out, so nothing capable of loading code or data from
     * disk survives into the migration's environment.
     */
    private static Globals sandboxedGlobals() {
        Globals globals = new Globals();
        globals.load(new JseBaseLib());
        globals.load(new PackageLib());
        globals.load(new Bit32Lib());
        globals.load(new TableLib());
        globals.load(new StringLib());
        globals.load(new CoroutineLib());
        globals.load(new JseMathLib());
        LoadState.install(globals);
        LuaC.install(globals);
        globals.set("require", LuaValue.NIL);
        globals.set("package", LuaValue.NIL);
        globals.set("dofile", LuaValue.NIL);
        globals.set("loadfile", LuaValue.NIL);
        return globals;
    }

    /**
     * H2 constructs reachable from plain SQL that reach outside the database itself: file
     * I/O ({@code CSVREAD}/{@code CSVWRITE}/{@code FILE_READ}/{@code FILE_WRITE}/
     * {@code RUNSCRIPT}/{@code SCRIPT TO}), arbitrary Java execution
     * ({@code CREATE ALIAS}/{@code CREATE TRIGGER}, which can bind to an existing Java
     * method or compile inline source), and cross-datasource access
     * ({@code CREATE LINKED TABLE}/{@code LINK SCHEMA}). None of these are legitimate in a
     * schema migration or metadata backfill, so {@code db.query}/{@code db.update} reject
     * them outright rather than letting H2 execute them.
     */
    private static final String[] FORBIDDEN_SQL_CONSTRUCTS = {
        "CSVREAD", "CSVWRITE", "FILE_READ", "FILE_WRITE", "RUNSCRIPT", "SCRIPT TO",
        "CREATE ALIAS", "CREATE TRIGGER", "CREATE FORCE TRIGGER",
        "CREATE LINKED TABLE", "LINK SCHEMA",
    };

    private static void checkSqlAllowed(String sql) {
        String upper = sql.toUpperCase(Locale.ROOT);
        for (String forbidden : FORBIDDEN_SQL_CONSTRUCTS) {
            if (upper.contains(forbidden)) {
                throw new RuntimeException("db rejected SQL using a disallowed construct ("
                        + forbidden + "): migrations may only use ordinary DDL/DML against "
                        + "this database, not H2's file I/O, Java-interop, or "
                        + "linked-datasource extensions.");
            }
        }
    }

    /** db.query(sql) -> array (1-based) of row tables. */
    private final class QueryFunction extends OneArgFunction {
        @Override
        public LuaValue call(LuaValue sqlArg) {
            String sql = sqlArg.checkjstring();
            checkSqlAllowed(sql);
            try (PreparedStatement statement = connection.prepareStatement(sql);
                 ResultSet rs = statement.executeQuery()) {
                ResultSetMetaData meta = rs.getMetaData();
                int columns = meta.getColumnCount();
                LuaTable rows = new LuaTable();
                int index = 1;
                while (rs.next()) {
                    LuaTable row = new LuaTable();
                    for (int c = 1; c <= columns; c++) {
                        String name = meta.getColumnLabel(c).toLowerCase();
                        row.set(name, sqlToLua(rs, c, meta.getColumnType(c)));
                    }
                    rows.set(index++, row);
                }
                return rows;
            } catch (SQLException e) {
                throw new RuntimeException("db.query failed: " + e.getMessage(), e);
            }
        }
    }

    /** db.update(sql) -> affected row count. */
    private final class UpdateFunction extends OneArgFunction {
        @Override
        public LuaValue call(LuaValue sqlArg) {
            String sql = sqlArg.checkjstring();
            checkSqlAllowed(sql);
            try (PreparedStatement statement = connection.prepareStatement(sql)) {
                int affected = statement.executeUpdate();
                return LuaValue.valueOf(affected);
            } catch (SQLException e) {
                throw new RuntimeException("db.update failed: " + e.getMessage(), e);
            }
        }
    }

    /** http.get(url) -> body string. */
    private final class HttpGetFunction extends OneArgFunction {
        @Override
        public LuaValue call(LuaValue urlArg) {
            String url = urlArg.checkjstring();
            try {
                return LuaValue.valueOf(hubConfigClient.get(url));
            } catch (IOException e) {
                throw new RuntimeException("http.get failed: " + e.getMessage(), e);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                throw new RuntimeException("http.get interrupted", e);
            }
        }
    }

    /** json.decode(text) -> Lua table. */
    private static final class JsonDecodeFunction extends OneArgFunction {
        @Override
        public LuaValue call(LuaValue textArg) {
            String text = textArg.checkjstring();
            return new JsonParser(text).parseValue();
        }
    }

    private static LuaValue sqlToLua(ResultSet rs, int column, int sqlType) throws SQLException {
        switch (sqlType) {
            case Types.INTEGER:
            case Types.SMALLINT:
            case Types.TINYINT:
            case Types.BIGINT: {
                long v = rs.getLong(column);
                return rs.wasNull() ? LuaValue.NIL : LuaValue.valueOf(v);
            }
            case Types.DECIMAL:
            case Types.NUMERIC:
            case Types.DOUBLE:
            case Types.FLOAT:
            case Types.REAL: {
                BigDecimal v = rs.getBigDecimal(column);
                return v == null ? LuaValue.NIL : LuaValue.valueOf(v.doubleValue());
            }
            case Types.BOOLEAN:
            case Types.BIT: {
                boolean v = rs.getBoolean(column);
                return rs.wasNull() ? LuaValue.NIL : LuaValue.valueOf(v);
            }
            default: {
                String v = rs.getString(column);
                return v == null ? LuaValue.NIL : LuaValue.valueOf(v);
            }
        }
    }

    /**
     * A minimal, dependency-free JSON reader producing LuaJ values. JSON objects become
     * LuaTables keyed by string; arrays become LuaTables keyed 1-based; numbers become Lua
     * numbers; null becomes nil.
     */
    private static final class JsonParser {
        private final String text;
        private int pos;

        JsonParser(String text) {
            this.text = text;
        }

        LuaValue parseValue() {
            skipWhitespace();
            char c = peek();
            switch (c) {
                case '{':
                    return parseObject();
                case '[':
                    return parseArray();
                case '"':
                    return LuaValue.valueOf(parseString());
                case 't':
                case 'f':
                    return parseBoolean();
                case 'n':
                    expect("null");
                    return LuaValue.NIL;
                default:
                    return parseNumber();
            }
        }

        private LuaValue parseObject() {
            LuaTable table = new LuaTable();
            expect("{");
            skipWhitespace();
            if (peek() == '}') {
                pos++;
                return table;
            }
            while (true) {
                skipWhitespace();
                String key = parseString();
                skipWhitespace();
                expect(":");
                LuaValue value = parseValue();
                table.set(key, value);
                skipWhitespace();
                char c = next();
                if (c == '}') {
                    break;
                }
                if (c != ',') {
                    throw new RuntimeException("expected ',' or '}' in object at " + pos);
                }
            }
            return table;
        }

        private LuaValue parseArray() {
            LuaTable table = new LuaTable();
            expect("[");
            skipWhitespace();
            if (peek() == ']') {
                pos++;
                return table;
            }
            int index = 1;
            while (true) {
                LuaValue value = parseValue();
                table.set(index++, value);
                skipWhitespace();
                char c = next();
                if (c == ']') {
                    break;
                }
                if (c != ',') {
                    throw new RuntimeException("expected ',' or ']' in array at " + pos);
                }
            }
            return table;
        }

        private String parseString() {
            skipWhitespace();
            if (next() != '"') {
                throw new RuntimeException("expected string at " + pos);
            }
            StringBuilder sb = new StringBuilder();
            while (true) {
                char c = next();
                if (c == '"') {
                    break;
                }
                if (c == '\\') {
                    char esc = next();
                    switch (esc) {
                        case '"': sb.append('"'); break;
                        case '\\': sb.append('\\'); break;
                        case '/': sb.append('/'); break;
                        case 'b': sb.append('\b'); break;
                        case 'f': sb.append('\f'); break;
                        case 'n': sb.append('\n'); break;
                        case 'r': sb.append('\r'); break;
                        case 't': sb.append('\t'); break;
                        case 'u':
                            String hex = text.substring(pos, pos + 4);
                            pos += 4;
                            sb.append((char) Integer.parseInt(hex, 16));
                            break;
                        default:
                            throw new RuntimeException("bad escape \\" + esc + " at " + pos);
                    }
                } else {
                    sb.append(c);
                }
            }
            return sb.toString();
        }

        private LuaValue parseNumber() {
            int start = pos;
            while (pos < text.length()) {
                char c = text.charAt(pos);
                if ((c >= '0' && c <= '9') || c == '-' || c == '+' || c == '.'
                        || c == 'e' || c == 'E') {
                    pos++;
                } else {
                    break;
                }
            }
            String token = text.substring(start, pos);
            double d = Double.parseDouble(token);
            if (d == Math.rint(d) && !token.contains(".") && !token.contains("e")
                    && !token.contains("E")) {
                return LuaValue.valueOf((long) d);
            }
            return LuaValue.valueOf(d);
        }

        private LuaValue parseBoolean() {
            if (peek() == 't') {
                expect("true");
                return LuaValue.TRUE;
            }
            expect("false");
            return LuaValue.FALSE;
        }

        private void skipWhitespace() {
            while (pos < text.length() && Character.isWhitespace(text.charAt(pos))) {
                pos++;
            }
        }

        private char peek() {
            return text.charAt(pos);
        }

        private char next() {
            return text.charAt(pos++);
        }

        private void expect(String token) {
            if (!text.startsWith(token, pos)) {
                throw new RuntimeException("expected '" + token + "' at " + pos);
            }
            pos += token.length();
        }
    }
}
