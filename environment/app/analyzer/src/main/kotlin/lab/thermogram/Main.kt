package lab.thermogram

import kotlin.system.exitProcess

fun main(args: Array<String>) {
    try {
        val options = CliParser.parse(args)
        val reports = AnalysisEngine(ArchiveReader(), ApiClient(options.api)).analyze(options.db)
        ReportWriter.write(reports, options.output)
    } catch (error: Exception) {
        System.err.println("thermogram analysis failed: ${error.message}")
        exitProcess(1)
    }
}
