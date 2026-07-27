package com.acme.wallet.sdjwt;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/** Claim paths: object members joined with dots, array elements written with their index. */
final class Paths {

    private Paths() {
    }

    static String join(String prefix, String name) {
        return prefix.isEmpty() ? name : prefix + "." + name;
    }

    static String element(String prefix, int index) {
        return prefix + "[" + index + "]";
    }

    /** Break a claim path into member names and array indices. */
    static List<Object> split(String path) {
        List<Object> parts = new ArrayList<>();
        StringBuilder token = new StringBuilder();
        for (int i = 0; i < path.length(); i++) {
            char c = path.charAt(i);
            if (c == '.') {
                parts.add(token.toString());
                token.setLength(0);
            } else if (c == '[') {
                if (token.length() > 0) {
                    parts.add(token.toString());
                    token.setLength(0);
                }
                int close = path.indexOf(']', i);
                parts.add(Integer.parseInt(path.substring(i + 1, close)));
                i = close;
            } else {
                token.append(c);
            }
        }
        if (token.length() > 0) {
            parts.add(token.toString());
        }
        return parts;
    }

    /** Every path that encloses this one, the path itself last. */
    static List<String> ancestors(String path) {
        List<String> out = new ArrayList<>();
        String current = "";
        for (Object part : split(path)) {
            current = part instanceof Integer
                    ? element(current, (Integer) part)
                    : join(current, (String) part);
            out.add(current);
        }
        return out;
    }

    /** The value a claim path points at, or null when it is not there. */
    @SuppressWarnings("unchecked")
    static Object lookup(Object root, String path) {
        Object current = root;
        for (Object part : split(path)) {
            if (part instanceof Integer) {
                if (!(current instanceof List)) {
                    return null;
                }
                List<Object> elements = (List<Object>) current;
                int index = (Integer) part;
                if (index < 0 || index >= elements.size()) {
                    return null;
                }
                current = elements.get(index);
            } else {
                if (!(current instanceof Map)) {
                    return null;
                }
                Map<String, Object> members = (Map<String, Object>) current;
                if (!members.containsKey(part)) {
                    return null;
                }
                current = members.get(part);
            }
        }
        return current;
    }
}
