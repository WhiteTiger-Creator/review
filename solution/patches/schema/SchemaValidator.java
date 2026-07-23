package dev.terminus.trivia.schema;

import com.networknt.schema.JsonSchema;
import com.networknt.schema.ValidationMessage;
import dev.terminus.trivia.manifest.LoadedArtifact;
import dev.terminus.trivia.util.PathUtil;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

public final class SchemaValidator {
    private final SchemaCatalog catalog;
    private final Path root;

    public SchemaValidator(SchemaCatalog catalog, Path root) {
        this.catalog = catalog;
        this.root = root;
    }

    public List<ValidationFinding> validateAll(List<LoadedArtifact> artifacts) {
        List<ValidationFinding> findings = new ArrayList<>();
        Set<String> seen = new HashSet<>();

        for (LoadedArtifact artifact : artifacts) {
            JsonSchema schema = catalog.get(artifact.kind().schemaFile());
            Set<ValidationMessage> messages = schema.validate(artifact.document());
            for (ValidationMessage msg : messages) {
                String type = msg.getType();
                String code = (type == null || type.isBlank()) ? "schema.validation" : "schema." + type;
                String rel = PathUtil.toPosixRelative(root, artifact.absolutePath());
                String pointer = formatPointer(msg);
                String key = rel + "|" + pointer + "|" + code;
                if (seen.add(key)) {
                    findings.add(new ValidationFinding(rel, pointer, code, msg.getMessage()));
                }
            }
        }
        findings.sort(Comparator.comparing(ValidationFinding::artifact)
                .thenComparing(ValidationFinding::pointer)
                .thenComparing(ValidationFinding::code));
        return findings;
    }

    private static String formatPointer(ValidationMessage msg) {
        if ("required".equals(msg.getType())) {
            String property = msg.getProperty();
            if (property != null && !property.isBlank()) {
                String base = toJsonPointer(msg.getInstanceLocation().toString());
                return base.isEmpty() ? "/" + property : base + "/" + property;
            }
        }
        return toJsonPointer(msg.getInstanceLocation().toString());
    }

    private static String toJsonPointer(String location) {
        if (location == null || location.isEmpty() || "$".equals(location)) {
            return "";
        }
        if (location.startsWith("/")) {
            return location;
        }
        String trimmed = location.startsWith("$.") ? location.substring(2)
                : location.startsWith("$") ? location.substring(1) : location;
        if (trimmed.isEmpty()) {
            return "";
        }
        StringBuilder pointer = new StringBuilder();
        int index = 0;
        while (index < trimmed.length()) {
            char ch = trimmed.charAt(index);
            if (ch == '[') {
                int end = trimmed.indexOf(']', index);
                pointer.append('/').append(trimmed, index + 1, end);
                index = end + 1;
            } else if (ch == '.') {
                index++;
            } else {
                int start = index;
                while (index < trimmed.length()) {
                    char current = trimmed.charAt(index);
                    if (current == '.' || current == '[') {
                        break;
                    }
                    index++;
                }
                pointer.append('/').append(trimmed, start, index);
            }
        }
        return pointer.toString();
    }
}
