package com.acme.wallet.sdjwt;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** A small JSON reader and a writer that emits the canonical form the profile asks for. */
final class Json {

    /** Signals input that is not JSON at all. */
    static final class Malformed extends RuntimeException {
        Malformed(String message) {
            super(message);
        }
    }

    private final String text;
    private int at;

    private Json(String text) {
        this.text = text;
    }

    static Object parse(String text) {
        Json reader = new Json(text);
        reader.skip();
        Object value = reader.value();
        reader.skip();
        if (reader.at != text.length()) {
            throw new Malformed("trailing content");
        }
        return value;
    }

    /** Parse a document that has to be a JSON object. */
    @SuppressWarnings("unchecked")
    static Map<String, Object> object(String text) {
        Object value = parse(text);
        if (!(value instanceof Map)) {
            throw new Malformed("not an object");
        }
        return (Map<String, Object>) value;
    }

    private void skip() {
        while (at < text.length()) {
            char c = text.charAt(at);
            if (c == ' ' || c == '\t' || c == '\n' || c == '\r') {
                at++;
            } else {
                break;
            }
        }
    }

    private char peek() {
        if (at >= text.length()) {
            throw new Malformed("unexpected end");
        }
        return text.charAt(at);
    }

    private Object value() {
        char c = peek();
        switch (c) {
            case '{':
                return objectValue();
            case '[':
                return arrayValue();
            case '"':
                return stringValue();
            case 't':
                return literal("true", Boolean.TRUE);
            case 'f':
                return literal("false", Boolean.FALSE);
            case 'n':
                return literal("null", null);
            default:
                return numberValue();
        }
    }

    private Object literal(String word, Object result) {
        if (!text.startsWith(word, at)) {
            throw new Malformed("bad literal");
        }
        at += word.length();
        return result;
    }

    private Map<String, Object> objectValue() {
        Map<String, Object> members = new LinkedHashMap<>();
        at++;
        skip();
        if (peek() == '}') {
            at++;
            return members;
        }
        while (true) {
            skip();
            String name = stringValue();
            skip();
            if (peek() != ':') {
                throw new Malformed("expected colon");
            }
            at++;
            skip();
            members.put(name, value());
            skip();
            char c = peek();
            at++;
            if (c == '}') {
                return members;
            }
            if (c != ',') {
                throw new Malformed("expected comma");
            }
        }
    }

    private List<Object> arrayValue() {
        List<Object> elements = new ArrayList<>();
        at++;
        skip();
        if (peek() == ']') {
            at++;
            return elements;
        }
        while (true) {
            skip();
            elements.add(value());
            skip();
            char c = peek();
            at++;
            if (c == ']') {
                return elements;
            }
            if (c != ',') {
                throw new Malformed("expected comma");
            }
        }
    }

    private String stringValue() {
        if (peek() != '"') {
            throw new Malformed("expected string");
        }
        at++;
        StringBuilder out = new StringBuilder();
        while (true) {
            char c = peek();
            at++;
            if (c == '"') {
                return out.toString();
            }
            if (c != '\\') {
                if (c < 0x20) {
                    throw new Malformed("raw control character");
                }
                out.append(c);
                continue;
            }
            char escape = peek();
            at++;
            switch (escape) {
                case '"': out.append('"'); break;
                case '\\': out.append('\\'); break;
                case '/': out.append('/'); break;
                case 'b': out.append('\b'); break;
                case 'f': out.append('\f'); break;
                case 'n': out.append('\n'); break;
                case 'r': out.append('\r'); break;
                case 't': out.append('\t'); break;
                case 'u':
                    if (at + 4 > text.length()) {
                        throw new Malformed("short escape");
                    }
                    out.append((char) Integer.parseInt(text.substring(at, at + 4), 16));
                    at += 4;
                    break;
                default:
                    throw new Malformed("bad escape");
            }
        }
    }

    private Object numberValue() {
        int start = at;
        if (peek() == '-') {
            at++;
        }
        boolean fractional = false;
        while (at < text.length()) {
            char c = text.charAt(at);
            if (c >= '0' && c <= '9') {
                at++;
            } else if (c == '.' || c == 'e' || c == 'E' || c == '+' || c == '-') {
                fractional = true;
                at++;
            } else {
                break;
            }
        }
        String token = text.substring(start, at);
        if (token.isEmpty() || token.equals("-")) {
            throw new Malformed("bad number");
        }
        if (fractional) {
            return Double.parseDouble(token);
        }
        try {
            return Long.parseLong(token);
        } catch (NumberFormatException overflow) {
            return Double.parseDouble(token);
        }
    }

    /** Compare strings by the bytes of their UTF-8 encoding. */
    static final Comparator<String> BY_UTF8 = (left, right) -> {
        byte[] a = left.getBytes(StandardCharsets.UTF_8);
        byte[] b = right.getBytes(StandardCharsets.UTF_8);
        for (int i = 0; i < Math.min(a.length, b.length); i++) {
            int diff = (a[i] & 0xFF) - (b[i] & 0xFF);
            if (diff != 0) {
                return diff;
            }
        }
        return a.length - b.length;
    };

    /** Serialise a value in the canonical form: sorted members, no whitespace. */
    static String write(Object value) {
        StringBuilder out = new StringBuilder();
        writeValue(value, out);
        return out.toString();
    }

    @SuppressWarnings("unchecked")
    private static void writeValue(Object value, StringBuilder out) {
        if (value == null) {
            out.append("null");
        } else if (value instanceof String) {
            writeString((String) value, out);
        } else if (value instanceof Boolean) {
            out.append(value.toString());
        } else if (value instanceof Long || value instanceof Integer) {
            out.append(value.toString());
        } else if (value instanceof Double) {
            out.append(value.toString());
        } else if (value instanceof List) {
            out.append('[');
            boolean first = true;
            for (Object element : (List<Object>) value) {
                if (!first) {
                    out.append(',');
                }
                first = false;
                writeValue(element, out);
            }
            out.append(']');
        } else if (value instanceof Map) {
            Map<String, Object> members = (Map<String, Object>) value;
            List<String> names = new ArrayList<>(members.keySet());
            names.sort(BY_UTF8);
            out.append('{');
            boolean first = true;
            for (String name : names) {
                if (!first) {
                    out.append(',');
                }
                first = false;
                writeString(name, out);
                out.append(':');
                writeValue(members.get(name), out);
            }
            out.append('}');
        } else {
            throw new IllegalArgumentException("cannot serialise " + value.getClass());
        }
    }

    private static void writeString(String value, StringBuilder out) {
        out.append('"');
        for (int i = 0; i < value.length(); i++) {
            char c = value.charAt(i);
            switch (c) {
                case '"': out.append("\\\""); break;
                case '\\': out.append("\\\\"); break;
                case '\b': out.append("\\b"); break;
                case '\f': out.append("\\f"); break;
                case '\n': out.append("\\n"); break;
                case '\r': out.append("\\r"); break;
                case '\t': out.append("\\t"); break;
                default:
                    if (c < 0x20) {
                        out.append(String.format("\\u%04x", (int) c));
                    } else {
                        out.append(c);
                    }
            }
        }
        out.append('"');
    }
}
