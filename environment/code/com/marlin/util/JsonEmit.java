package com.marlin.util;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

public final class JsonEmit {
    private JsonEmit() {}

    public static void writeSheet(Path dest, Map<String, Object> root) throws IOException {
        Files.createDirectories(dest.getParent());
        Files.writeString(dest, render(root) + "\n", StandardCharsets.UTF_8);
    }

    @SuppressWarnings("unchecked")
    private static String render(Object node) {
        if (node == null) {
            return "null";
        }
        if (node instanceof String s) {
            return "\"" + escape(s) + "\"";
        }
        if (node instanceof Number || node instanceof Boolean) {
            return node.toString();
        }
        if (node instanceof Map<?, ?> map) {
            List<String> parts = new ArrayList<>();
            for (Map.Entry<?, ?> e : map.entrySet()) {
                parts.add(render(String.valueOf(e.getKey())) + ":" + render(e.getValue()));
            }
            return "{" + String.join(",", parts) + "}";
        }
        if (node instanceof List<?> list) {
            List<String> parts = new ArrayList<>();
            for (Object o : list) {
                parts.add(render(o));
            }
            return "[" + String.join(",", parts) + "]";
        }
        return "\"" + escape(String.valueOf(node)) + "\"";
    }

    private static String escape(String s) {
        return s.replace("\\", "\\\\").replace("\"", "\\\"");
    }
}
