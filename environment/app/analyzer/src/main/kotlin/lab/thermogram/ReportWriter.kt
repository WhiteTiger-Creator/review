package lab.thermogram

import java.math.BigDecimal
import java.math.RoundingMode
import java.nio.charset.StandardCharsets
import java.nio.file.AtomicMoveNotSupportedException
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.StandardCopyOption

object ReportWriter {
    private fun rounded(value: Double): String =
        BigDecimal.valueOf(value).setScale(3, RoundingMode.HALF_UP).toPlainString()

    private fun quote(value: String): String =
        "\"" + value.replace("\\", "\\\\").replace("\"", "\\\"") + "\""

    fun write(frames: List<FrameReport>, output: Path) {
        val ordered = frames.sortedWith(compareBy<FrameReport> { it.capturedAt }.thenBy { it.frameId })
        val hottest = ordered.maxWithOrNull(compareBy<FrameReport> { it.maxC }.thenByDescending { it.frameId })
            ?: error("archive has no frames")
        val frameJson = ordered.joinToString(",") { frame ->
            val region = frame.hotRegion?.let { hot ->
                "{\"areaPixels\":${hot.areaPixels}," +
                    "\"peak\":{\"x\":${hot.peak.x},\"y\":${hot.peak.y},\"temperatureC\":${rounded(hot.peak.temperatureC)}}," +
                    "\"centroid\":{\"x\":${rounded(hot.centroid.x)},\"y\":${rounded(hot.centroid.y)}}," +
                    "\"integratedExcessC\":${rounded(hot.integratedExcessC)}," +
                    "\"bounds\":{\"minX\":${hot.bounds.minX},\"minY\":${hot.bounds.minY}," +
                    "\"maxX\":${hot.bounds.maxX},\"maxY\":${hot.bounds.maxY}}}"
            } ?: "null"
            "{" + listOf(
                "\"frameId\":" + quote(frame.frameId),
                "\"cameraId\":" + quote(frame.cameraId),
                "\"calibrationRevision\":" + quote(frame.calibrationRevision),
                "\"geometryRevision\":" + quote(frame.geometryRevision),
                "\"capturedAt\":" + quote(frame.capturedAt),
                "\"sensorWidth\":${frame.sensorWidth}",
                "\"sensorHeight\":${frame.sensorHeight}",
                "\"width\":${frame.width}",
                "\"height\":${frame.height}",
                "\"repairedPixels\":${frame.repairedPixels}",
                "\"referenceSlope\":${rounded(frame.referenceSlope)}",
                "\"referenceOffsetC\":${rounded(frame.referenceOffsetC)}",
                "\"referenceRmseC\":${rounded(frame.referenceRmseC)}",
                "\"minC\":${rounded(frame.minC)}",
                "\"maxC\":${rounded(frame.maxC)}",
                "\"meanC\":${rounded(frame.meanC)}",
                "\"stddevC\":${rounded(frame.stddevC)}",
                "\"p95C\":${rounded(frame.p95C)}",
                "\"thresholdC\":${rounded(frame.thresholdC)}",
                "\"hotspot\":{\"x\":${frame.hotspot.x},\"y\":${frame.hotspot.y}," +
                    "\"temperatureC\":${rounded(frame.hotspot.temperatureC)}}",
                "\"hotRegion\":$region",
            ).joinToString(",") + "}"
        }
        val meanFrameMean = ordered.map { it.meanC }.average()
        val json = "{\"frames\":[$frameJson],\"summary\":{" +
            "\"frameCount\":${ordered.size}," +
            "\"hottestFrameId\":${quote(hottest.frameId)}," +
            "\"globalMaxC\":${rounded(hottest.maxC)}," +
            "\"meanFrameMeanC\":${rounded(meanFrameMean)}," +
            "\"largestHotRegionFrameId\":null," +
            "\"largestIntegratedExcessC\":null," +
            "\"fastestMeanRise\":null}}\n"
        val parent = output.toAbsolutePath().parent ?: Path.of(".")
        Files.createDirectories(parent)
        val temp = Files.createTempFile(parent, output.fileName.toString(), ".tmp")
        try {
            Files.writeString(temp, json, StandardCharsets.UTF_8)
            try {
                Files.move(temp, output, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING)
            } catch (_: AtomicMoveNotSupportedException) {
                Files.move(temp, output, StandardCopyOption.REPLACE_EXISTING)
            }
        } finally {
            Files.deleteIfExists(temp)
        }
    }
}
