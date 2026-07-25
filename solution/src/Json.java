package com.acme.inbox.jwe;

import jakarta.json.JsonArray;
import jakarta.json.JsonNumber;
import jakarta.json.JsonObject;
import jakarta.json.JsonReader;
import jakarta.json.JsonString;
import jakarta.json.JsonValue;

import java.io.StringReader;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

/**
 * Canonical JSON writer for the report: object keys sorted by their UTF-8 bytes, compact
 * separators, no insignificant whitespace, JSON-standard string escaping with non-ASCII escaped as
 * \\uXXXX. This is a deliberately small serializer so the audit output is byte-for-byte stable and
 * does not depend on a library's formatting choices.
 */
final class Json {

    private Json() {
    }

    /** Parses a JSON document into plain Java values (Map, List, String, Long, Double, Boolean, null). */
    static Object parse(String text) {
        try (JsonReader reader = jakarta.json.Json.createReader(new StringReader(text))) {
            return convert(reader.readValue());
        }
    }

    private static Object convert(JsonValue value) {
        switch (value.getValueType()) {
            case OBJECT:
                Map<String, Object> object = new LinkedHashMap<>();
                for (Map.Entry<String, JsonValue> entry : ((JsonObject) value).entrySet()) {
                    object.put(entry.getKey(), convert(entry.getValue()));
                }
                return object;
            case ARRAY:
                List<Object> array = new ArrayList<>();
                for (JsonValue item : (JsonArray) value) {
                    array.add(convert(item));
                }
                return array;
            case STRING:
                return ((JsonString) value).getString();
            case NUMBER:
                JsonNumber number = (JsonNumber) value;
                return number.isIntegral() ? (Object) number.longValue() : (Object) number.doubleValue();
            case TRUE:
                return Boolean.TRUE;
            case FALSE:
                return Boolean.FALSE;
            default:
                return null;
        }
    }

    static String canonical(Object value) {
        StringBuilder sb = new StringBuilder();
        write(sb, value);
        return sb.toString();
    }

    private static void write(StringBuilder sb, Object value) {
        if (value == null) {
            sb.append("null");
        } else if (value instanceof String) {
            writeString(sb, (String) value);
        } else if (value instanceof Boolean) {
            sb.append(((Boolean) value) ? "true" : "false");
        } else if (value instanceof Integer || value instanceof Long) {
            sb.append(value.toString());
        } else if (value instanceof Map) {
            writeObject(sb, (Map<?, ?>) value);
        } else if (value instanceof List) {
            writeArray(sb, (List<?>) value);
        } else {
            throw new IllegalArgumentException("cannot serialize " + value.getClass());
        }
    }

    private static void writeObject(StringBuilder sb, Map<?, ?> map) {
        // Sort keys by their UTF-8 byte sequence, which is the canonical order the report uses.
        TreeMap<String, Object> sorted = new TreeMap<>(Json::compareUtf8);
        for (Map.Entry<?, ?> entry : map.entrySet()) {
            sorted.put(String.valueOf(entry.getKey()), entry.getValue());
        }
        sb.append('{');
        boolean first = true;
        for (Map.Entry<String, Object> entry : sorted.entrySet()) {
            if (!first) {
                sb.append(',');
            }
            first = false;
            writeString(sb, entry.getKey());
            sb.append(':');
            write(sb, entry.getValue());
        }
        sb.append('}');
    }

    private static void writeArray(StringBuilder sb, List<?> list) {
        sb.append('[');
        boolean first = true;
        for (Object item : list) {
            if (!first) {
                sb.append(',');
            }
            first = false;
            write(sb, item);
        }
        sb.append(']');
    }

    private static void writeString(StringBuilder sb, String s) {
        sb.append('"');
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"':
                    sb.append("\\\"");
                    break;
                case '\\':
                    sb.append("\\\\");
                    break;
                case '\b':
                    sb.append("\\b");
                    break;
                case '\t':
                    sb.append("\\t");
                    break;
                case '\n':
                    sb.append("\\n");
                    break;
                case '\f':
                    sb.append("\\f");
                    break;
                case '\r':
                    sb.append("\\r");
                    break;
                default:
                    if (c < 0x20 || c >= 0x80) {
                        sb.append(String.format("\\u%04x", (int) c));
                    } else {
                        sb.append(c);
                    }
            }
        }
        sb.append('"');
    }

    static int compareUtf8(String a, String b) {
        byte[] ab = a.getBytes(java.nio.charset.StandardCharsets.UTF_8);
        byte[] bb = b.getBytes(java.nio.charset.StandardCharsets.UTF_8);
        int n = Math.min(ab.length, bb.length);
        for (int i = 0; i < n; i++) {
            int x = ab[i] & 0xff;
            int y = bb[i] & 0xff;
            if (x != y) {
                return x - y;
            }
        }
        return ab.length - bb.length;
    }
}
