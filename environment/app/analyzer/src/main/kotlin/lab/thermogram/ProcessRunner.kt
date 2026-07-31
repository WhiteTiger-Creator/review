package lab.thermogram

import java.nio.charset.StandardCharsets

object ProcessRunner {
    fun run(command: List<String>): String {
        val process = ProcessBuilder(command).redirectErrorStream(true).start()
        val output = process.inputStream.readAllBytes().toString(StandardCharsets.UTF_8)
        check(process.waitFor() == 0) {
            "command failed: ${command.joinToString(" ")}\n$output"
        }
        return output
    }
}
