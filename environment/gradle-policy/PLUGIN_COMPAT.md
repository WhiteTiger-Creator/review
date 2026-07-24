# Plugin compatibility table (read-only)

Requested Gradle version comes from `workspace.manifest.json` fields `gradle_major` and `gradle_minor`.

A plugin request is compatible only when `(gradle_major, gradle_minor) >= (min_major, min_minor)` using numeric comparison.

Known plugin ids and their default minimums when `min_gradle` is omitted on the request:

| Plugin id | Default min_gradle |
|-----------|--------------------|
| `com.meshgrid.wireloom` | `8.7` |
| `com.meshgrid.depknit` | `8.8` |
| `com.meshgrid.artifactseal` | `8.10` |
| `com.meshgrid.pluginbridge` | `8.5` |
| `com.meshgrid.releasemesh` | `8.9` |
| `com.meshgrid.cataloghub` | `8.10` |
| `org.gradle.publish-offline` | `8.6` |

When `min_gradle` is present on the request, use that value instead of the table default.

Emit at most one `PLUGIN_INCOMPATIBLE` finding per plugin `id`. `entity_id` is the plugin id. `module_id` for plugin findings is `meshgrid`. `event_seq` is `0` for plugin findings evaluated before module replay.
