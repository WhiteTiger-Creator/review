package dev.terminus.trivia.schema;

import com.networknt.schema.JsonSchema;
import com.networknt.schema.ValidationMessage;
import dev.terminus.trivia.manifest.ArtifactKind;
import dev.terminus.trivia.manifest.LoadedArtifact;
import dev.terminus.trivia.util.PathUtil;

import java.nio.file.Path;
import java.util.ArrayList;
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
        Set<String> seenCodes = new HashSet<>();

        for (LoadedArtifact artifact : artifacts) {
            JsonSchema schema = catalog.get(artifact.kind().schemaFile());
            Set<ValidationMessage> messages = schema.validate(artifact.document());
            if (!messages.isEmpty()) {
                for (ValidationMessage msg : messages) {
                    String code = msg.getCode() != null ? msg.getCode() : "schema.validation";
                    if (seenCodes.add(code)) {
                        findings.add(new ValidationFinding(
                                PathUtil.toPosixRelative(root, artifact.absolutePath()),
                                msg.getInstanceLocation().toString(),
                                code,
                                msg.getMessage()));
                    }
                }
                return findings;
            }
        }
        return findings;
    }
}
