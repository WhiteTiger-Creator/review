package elastx

import java.io.File

fun main(args: Array<String>) {
    var panel: String? = null
    var out: String? = null
    var i = 0
    while (i < args.size) {
        when (args[i]) {
            "--panel" -> { panel = args[i + 1]; i += 2 }
            "--out" -> { out = args[i + 1]; i += 2 }
            else -> { System.err.println("ERROR: unknown argument ${args[i]}"); kotlin.system.exitProcess(2) }
        }
    }
    if (panel == null || out == null) {
        System.err.println("ERROR: usage: --panel <csv> --out <json>")
        kotlin.system.exitProcess(2)
    }
    if (!File(panel).isFile) {
        System.err.println("ERROR: panel not found: $panel")
        kotlin.system.exitProcess(1)
    }
    val result = Model.run(panel)
    val f = File(out)
    f.parentFile?.mkdirs()
    f.writeText(Json.write(result))
}
