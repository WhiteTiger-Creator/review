package dev.terminus.trivia.util;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

public final class CanonicalJson {
    private static final ObjectMapper MAPPER = new ObjectMapper()
            .configure(SerializationFeature.ORDER_MAP_ENTRIES_BY_KEYS, true);

    private CanonicalJson() {}

    public static String write(Object value) throws Exception {
        JsonNode tree = MAPPER.valueToTree(value);
        return MAPPER.writerWithDefaultPrettyPrinter().writeValueAsString(canonicalize(tree)) + "\n";
    }

    private static JsonNode canonicalize(JsonNode node) {
        if (node.isObject()) {
            ObjectNode out = MAPPER.createObjectNode();
            List<String> keys = new ArrayList<>();
            node.fieldNames().forEachRemaining(keys::add);
            keys.sort(Comparator.naturalOrder());
            for (String key : keys) {
                out.set(key, canonicalize(node.get(key)));
            }
            return out;
        }
        if (node.isArray()) {
            ArrayNode out = MAPPER.createArrayNode();
            for (JsonNode child : node) {
                out.add(canonicalize(child));
            }
            return out;
        }
        return node;
    }

    public static Map<String, Object> sortedMap() {
        return new TreeMap<>();
    }
}
