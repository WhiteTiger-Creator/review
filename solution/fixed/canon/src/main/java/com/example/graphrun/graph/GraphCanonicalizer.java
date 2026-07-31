package com.example.graphrun.graph;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.databind.node.ObjectNode;

import java.math.BigDecimal;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.text.Normalizer;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.TreeSet;

public final class GraphCanonicalizer {

    private static final String DOMAIN = "GRAPHRUN.GRAPH.v1";
    private final ObjectMapper mapper;

    public GraphCanonicalizer() {
        this.mapper = new ObjectMapper();
        this.mapper.configure(SerializationFeature.ORDER_MAP_ENTRIES_BY_KEYS, true);
    }

    public String domain() {
        return DOMAIN;
    }

    public byte[] canonicalBytes(JsonNode graph) {
        String graphId = graph.path("graph_id").asText("");
        String graphType = graph.path("graph_type").asText("");
        boolean undirected = "undirected".equals(graphType);

        TreeSet<String> nodes = new TreeSet<>();
        if (graph.has("nodes") && graph.get("nodes").isArray()) {
            for (JsonNode node : graph.get("nodes")) {
                String id = nfc(node.path("id").asText(""));
                if (!id.isEmpty()) {
                    nodes.add(id);
                }
            }
        }

        TreeSet<String> edgeRecords = new TreeSet<>();
        if (graph.has("edges") && graph.get("edges").isArray()) {
            for (JsonNode edge : graph.get("edges")) {
                String source = nfc(edge.path("source").asText(""));
                String target = nfc(edge.path("target").asText(""));
                if (undirected) {
                    if (utf8Compare(source, target) > 0) {
                        String tmp = source;
                        source = target;
                        target = tmp;
                    }
                }
                String kind = edge.path("kind").asText("");
                String weight = normalizeWeight(edge.path("weight").asText("0"));
                String attrsJson = "";
                if (edge.has("attributes") && edge.get("attributes").isObject()) {
                    attrsJson = canonicalJson(edge.get("attributes"));
                }
                edgeRecords.add(source + "\0" + target + "\0" + kind + "\0" + weight + "\0" + attrsJson);
            }
        }

        List<String> fields = new ArrayList<>();
        fields.add(DOMAIN);
        fields.add(graphId);
        fields.add(graphType);
        fields.add(String.join("\n", nodes));
        fields.addAll(edgeRecords);
        return frame(fields);
    }

    public String digest(JsonNode graph) {
        return sha256Hex(canonicalBytes(graph));
    }

    public JsonNode normalize(JsonNode graph) {
        return graph;
    }

    private String canonicalJson(JsonNode node) {
        try {
            Object sorted = sortNode(node);
            return mapper.writeValueAsString(sorted);
        } catch (Exception e) {
            throw new IllegalStateException("failed to canonicalize attributes", e);
        }
    }

    private Object sortNode(JsonNode node) {
        if (node == null || node.isNull()) {
            return null;
        }
        if (node.isObject()) {
            TreeMap<String, Object> map = new TreeMap<>();
            Iterator<Map.Entry<String, JsonNode>> fields = node.fields();
            while (fields.hasNext()) {
                Map.Entry<String, JsonNode> entry = fields.next();
                map.put(entry.getKey(), sortNode(entry.getValue()));
            }
            return map;
        }
        if (node.isArray()) {
            List<Object> list = new ArrayList<>();
            for (JsonNode child : node) {
                list.add(sortNode(child));
            }
            return list;
        }
        if (node.isNumber()) {
            return node.decimalValue();
        }
        if (node.isBoolean()) {
            return node.booleanValue();
        }
        return node.asText();
    }

    static String normalizeWeight(String raw) {
        String value = raw.trim();
        if (value.isEmpty()) {
            return "0";
        }
        if (value.startsWith(".")) {
            value = "0" + value;
        }
        try {
            BigDecimal decimal = new BigDecimal(value);
            decimal = decimal.stripTrailingZeros();
            String plain = decimal.toPlainString();
            if (plain.indexOf('.') < 0) {
                return plain;
            }
            return plain;
        } catch (NumberFormatException e) {
            return value;
        }
    }

    private static String nfc(String value) {
        return Normalizer.normalize(value, Normalizer.Form.NFC);
    }

    private static int utf8Compare(String a, String b) {
        byte[] left = a.getBytes(StandardCharsets.UTF_8);
        byte[] right = b.getBytes(StandardCharsets.UTF_8);
        int len = Math.min(left.length, right.length);
        for (int i = 0; i < len; i++) {
            int diff = Byte.compare(left[i], right[i]);
            if (diff != 0) {
                return diff;
            }
        }
        return Integer.compare(left.length, right.length);
    }

    private static byte[] frame(List<String> fields) {
        int size = 0;
        for (String field : fields) {
            size += 4 + field.getBytes(StandardCharsets.UTF_8).length;
        }
        ByteBuffer buffer = ByteBuffer.allocate(size);
        for (String field : fields) {
            byte[] bytes = field.getBytes(StandardCharsets.UTF_8);
            buffer.putInt(bytes.length);
            buffer.put(bytes);
        }
        return buffer.array();
    }

    private static String sha256Hex(byte[] data) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(data);
            StringBuilder sb = new StringBuilder(hash.length * 2);
            for (byte b : hash) {
                sb.append(String.format("%02x", b));
            }
            return sb.toString();
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }
}
