package lab.thermogram

import java.nio.file.Path

data class CliOptions(val db: Path, val api: String, val output: Path)

object CliParser {
    fun parse(args: Array<String>): CliOptions {
        val values = mutableMapOf<String, String>()
        var index = 0
        while (index < args.size) {
            val key = args[index]
            require(key in setOf("--db", "--api", "--output")) { "unknown argument: $key" }
            require(index + 1 < args.size) { "missing value for $key" }
            values[key] = args[index + 1]
            index += 2
        }
        return CliOptions(
            db = Path.of(requireNotNull(values["--db"]) { "--db is required" }),
            api = requireNotNull(values["--api"]) { "--api is required" }.trimEnd('/'),
            output = Path.of(requireNotNull(values["--output"]) { "--output is required" }),
        )
    }
}
