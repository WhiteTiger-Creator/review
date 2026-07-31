package lab.thermogram

import kotlin.math.sqrt

class AnalysisEngine(private val archive: ArchiveReader, private val api: ApiClient) {
    fun analyze(database: java.nio.file.Path): List<FrameReport> {
        val data = archive.read(database)
        return data.frames.map { row ->
            val metadata = api.frame(row.frameId)
            require(metadata == FrameMetadata(row.frameId, row.cameraId, row.capturedAt, row.width, row.height)) {
                "API metadata disagrees for ${row.frameId}"
            }
            val calibration = api.calibration(row.cameraId)
            val geometry = api.geometry(row.cameraId)
            val raw = QirDecoder.decode(row.blob, row.width, row.height)
            val temperatures = raw.map { CalibrationMath.temperature(it.toDouble(), calibration) }
            val mean = temperatures.average()
            val maximum = temperatures.maxOrNull() ?: error("empty frame")
            val hotIndex = temperatures.indexOfFirst { it == maximum }
            FrameReport(
                frameId = row.frameId,
                cameraId = row.cameraId,
                calibrationRevision = calibration.revision,
                geometryRevision = geometry.revision,
                capturedAt = row.capturedAt,
                sensorWidth = row.width,
                sensorHeight = row.height,
                width = row.width,
                height = row.height,
                repairedPixels = 0,
                referenceSlope = 1.0,
                referenceOffsetC = 0.0,
                referenceRmseC = 0.0,
                minC = temperatures.minOrNull()!!,
                maxC = maximum,
                meanC = mean,
                stddevC = sqrt(temperatures.sumOf { (it - mean) * (it - mean) } / temperatures.size),
                p95C = maximum,
                thresholdC = mean,
                hotspot = Hotspot(hotIndex % row.width, hotIndex / row.width, maximum),
                hotRegion = null,
            )
        }
    }
}
