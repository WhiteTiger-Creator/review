#!/bin/bash
set -euo pipefail
cat > /app/analyzer/src/main/kotlin/lab/thermogram/QirDecoder.kt <<'KOTLIN'
package lab.thermogram

import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.zip.CRC32

object QirDecoder {
    private data class RowDescriptor(val offset: Int, val length: Int, val crc: Long)

    fun decode(blob: ByteArray, expectedWidth: Int, expectedHeight: Int): IntArray {
        require(blob.size >= 25 && blob.copyOfRange(0, 4).decodeToString() == "QIR2") { "invalid QIR payload" }
        val header = ByteBuffer.wrap(blob).order(ByteOrder.LITTLE_ENDIAN)
        require(header.get(4).toInt() and 0xff == 2) { "unsupported QIR version" }
        val flags = header.get(5).toInt() and 0xff
        require(flags and 0x03 == 0x03 && flags and 0xf8 == 0) { "unsupported QIR flags" }
        val indexed = flags and 0x04 != 0
        val headerLength = header.getShort(6).toInt() and 0xffff
        val width = header.getShort(8).toInt() and 0xffff
        val height = header.getShort(10).toInt() and 0xffff
        val base = header.getInt(12)
        val streamLengthLong = header.getInt(16).toLong() and 0xffffffffL
        val expectedCrc = header.getInt(20).toLong() and 0xffffffffL
        require(width == expectedWidth && height == expectedHeight && width > 0 && height > 0) {
            "QIR dimensions disagree with database"
        }
        require(streamLengthLong in 1..Int.MAX_VALUE.toLong()) { "invalid QIR stream length" }
        val streamLength = streamLengthLong.toInt()
        require(headerLength >= 24 && headerLength <= blob.size && headerLength + streamLength == blob.size) {
            "invalid QIR lengths"
        }
        val stream = blob.copyOfRange(headerLength, blob.size)
        require(stream.last().toInt() and 0xff == 0xff) { "invalid QIR packet terminator" }
        val pixels = IntArray(width * height)

        if (indexed) {
            require(headerLength == 24 + 12 * height) { "invalid indexed QIR header length" }
            val descriptors = ArrayList<RowDescriptor>(height)
            var expectedOffset = 0
            for (row in 0 until height) {
                val position = 24 + 12 * row
                val offsetLong = header.getInt(position).toLong() and 0xffffffffL
                val lengthLong = header.getInt(position + 4).toLong() and 0xffffffffL
                val rowCrc = header.getInt(position + 8).toLong() and 0xffffffffL
                require(offsetLong <= Int.MAX_VALUE && lengthLong in 1..Int.MAX_VALUE.toLong()) {
                    "invalid indexed QIR row descriptor"
                }
                val offset = offsetLong.toInt()
                val length = lengthLong.toInt()
                require(offset == expectedOffset && offset + length <= streamLength - 1) {
                    "indexed QIR rows do not partition the stream"
                }
                descriptors += RowDescriptor(offset, length, rowCrc)
                expectedOffset += length
            }
            require(expectedOffset == streamLength - 1) { "indexed QIR rows do not cover the stream" }
            var previousCrc = 0L
            for (row in 0 until height) {
                val descriptor = descriptors[row]
                val rowBuffer = ByteBuffer.wrap(stream, descriptor.offset, descriptor.length).slice().order(ByteOrder.LITTLE_ENDIAN)
                decodeRow(rowBuffer, pixels, row * width, width, base, indexed = true)
                val actual = rowCrc(previousCrc, row, pixels, row * width, width)
                require(actual == descriptor.crc) { "QIR row checksum mismatch" }
                previousCrc = actual
            }
        } else {
            for (index in 24 until headerLength) require(blob[index].toInt() == 0) { "nonzero reserved QIR header byte" }
            val buffer = ByteBuffer.wrap(stream).order(ByteOrder.LITTLE_ENDIAN)
            for (row in 0 until height) decodeRow(buffer, pixels, row * width, width, base, indexed = false)
            require(buffer.hasRemaining() && (buffer.get().toInt() and 0xff) == 0xff && !buffer.hasRemaining()) {
                "invalid QIR terminator"
            }
        }

        val crc = CRC32()
        val scratch = ByteBuffer.allocate(4).order(ByteOrder.LITTLE_ENDIAN)
        for (pixel in pixels) {
            scratch.clear()
            scratch.putInt(pixel)
            crc.update(scratch.array())
        }
        require(crc.value == expectedCrc) { "QIR checksum mismatch" }
        return pixels
    }

    private fun decodeRow(
        buffer: ByteBuffer,
        pixels: IntArray,
        rowStart: Int,
        width: Int,
        base: Int,
        indexed: Boolean,
    ) {
        var out = rowStart
        val rowEnd = rowStart + width
        var predictor = base.toLong()
        fun emit(value: Long) {
            require(value in Int.MIN_VALUE.toLong()..Int.MAX_VALUE.toLong() && out < rowEnd) {
                "QIR detector count overflow"
            }
            pixels[out++] = value.toInt()
        }
        while (out < rowEnd) {
            require(buffer.hasRemaining()) { "truncated QIR row" }
            when (val opcode = buffer.get().toInt() and 0xff) {
                in 0x00..0x3f -> {
                    val delta = (opcode ushr 1) xor -(opcode and 1)
                    predictor += delta.toLong()
                    emit(predictor)
                }
                in 0x40..0x7f -> {
                    val count = (opcode and 0x3f) + 1
                    require(out + count <= rowEnd) { "invalid QIR run" }
                    repeat(count) { emit(predictor) }
                }
                0x80 -> {
                    require(buffer.remaining() >= 2) { "truncated QIR delta" }
                    predictor += buffer.short.toLong()
                    emit(predictor)
                }
                0x81 -> {
                    require(buffer.remaining() >= 4) { "truncated QIR absolute" }
                    predictor = buffer.int.toLong()
                    emit(predictor)
                }
                0x82 -> {
                    require(buffer.remaining() >= 3) { "truncated QIR ramp" }
                    val count = buffer.get().toInt() and 0xff
                    val delta = buffer.short.toLong()
                    require(count > 0 && out + count <= rowEnd) { "invalid QIR ramp" }
                    repeat(count) {
                        predictor += delta
                        emit(predictor)
                    }
                }
                0x83 -> {
                    require(buffer.hasRemaining()) { "truncated QIR delta block" }
                    val count = buffer.get().toInt() and 0xff
                    require(count > 0 && buffer.remaining() >= 2 * count && out + count <= rowEnd) {
                        "invalid QIR delta block"
                    }
                    repeat(count) {
                        predictor += buffer.short.toLong()
                        emit(predictor)
                    }
                }
                0x84 -> {
                    require(buffer.remaining() >= 5) { "truncated QIR accelerated ramp" }
                    val count = buffer.get().toInt() and 0xff
                    var delta = buffer.short.toLong()
                    val deltaStep = buffer.short.toLong()
                    require(count > 0 && out + count <= rowEnd) { "invalid QIR accelerated ramp" }
                    repeat(count) {
                        predictor += delta
                        emit(predictor)
                        delta += deltaStep
                        require(delta in Int.MIN_VALUE.toLong()..Int.MAX_VALUE.toLong()) { "QIR ramp delta overflow" }
                    }
                }
                0xfe -> error("early QIR row terminator")
                0xff -> error("early QIR packet terminator")
                else -> error("unknown QIR opcode")
            }
        }
        if (indexed) {
            require(buffer.hasRemaining() && (buffer.get().toInt() and 0xff) == 0xfe && !buffer.hasRemaining()) {
                "invalid indexed QIR row terminator"
            }
        }
    }

    private fun rowCrc(
        previousCrc: Long,
        row: Int,
        pixels: IntArray,
        start: Int,
        width: Int,
    ): Long {
        val crc = CRC32()
        val scratch = ByteBuffer.allocate(4).order(ByteOrder.LITTLE_ENDIAN)
        fun update(value: Int) {
            scratch.clear()
            scratch.putInt(value)
            crc.update(scratch.array())
        }
        update(previousCrc.toInt())
        update(row)
        for (index in start until start + width) update(pixels[index])
        return crc.value
    }
}
KOTLIN
cat > /app/analyzer/src/main/kotlin/lab/thermogram/CalibrationMath.kt <<'KOTLIN'
package lab.thermogram

object CalibrationMath {
    fun temperature(rawCount: Double, calibration: Calibration): Double {
        require(calibration.model == "quadratic-ambient-v2") { "unsupported calibration model" }
        require(calibration.emissivity > 0.0) { "invalid emissivity" }
        val values = listOf(
            rawCount,
            calibration.gain,
            calibration.offsetC,
            calibration.quadratic,
            calibration.ambientC,
            calibration.ambientCoupling,
            calibration.emissivity,
        )
        require(values.all(Double::isFinite)) { "non-finite calibration input" }
        val sensor = calibration.offsetC +
            calibration.gain * rawCount +
            calibration.quadratic * rawCount * rawCount
        val difference = sensor - calibration.ambientC
        val temperature = calibration.ambientC +
            difference / calibration.emissivity +
            calibration.ambientCoupling * difference
        require(temperature.isFinite()) { "non-finite temperature" }
        return temperature
    }
}
KOTLIN
cat > /app/analyzer/src/main/kotlin/lab/thermogram/Models.kt <<'KOTLIN'
package lab.thermogram

data class FrameRow(
    val frameId: String,
    val cameraId: String,
    val capturedAt: String,
    val width: Int,
    val height: Int,
    val blob: ByteArray,
)

data class FrameMetadata(
    val frameId: String,
    val cameraId: String,
    val capturedAt: String,
    val width: Int,
    val height: Int,
)

data class Calibration(
    val cameraId: String,
    val revision: String,
    val model: String,
    val gain: Double,
    val offsetC: Double,
    val quadratic: Double,
    val ambientC: Double,
    val ambientCoupling: Double,
    val emissivity: Double,
)

data class DetectorGeometry(
    val cameraId: String,
    val revision: String,
    val rotation: Int,
    val mirrorX: Boolean,
    val badPixels: List<Int>,
    val hotSigma: Double,
    val minHotArea: Int,
    val homography: List<Double>,
    val arrheniusA: Double,
    val activationEnergyJMol: Double,
    val detectorNoiseC: Double,
    val confidenceK: Double,
    val correlationMajorMm: Double,
    val correlationMinorMm: Double,
    val correlationAngleDeg: Double,
    val temporalCorrelationSeconds: Double,
)

data class ReferenceSample(
    val referenceId: String,
    val pixelIndex: Int,
    val expectedC: Double,
    val sigmaC: Double,
)

data class ArchiveData(
    val frames: List<FrameRow>,
    val checkpoints: Map<String, Map<Int, Int>>,
    val references: Map<String, List<ReferenceSample>>,
)

data class Hotspot(val x: Int, val y: Int, val temperatureC: Double, val uncertaintyC: Double)

data class RegionPoint(val x: Int, val y: Int, val temperatureC: Double, val uncertaintyC: Double)

data class PhysicalCentroid(val x: Double, val y: Double)

data class RegionBounds(val minX: Int, val minY: Int, val maxX: Int, val maxY: Int)

data class HotRegion(
    val areaPixels: Int,
    val areaMm2: Double,
    val peak: RegionPoint,
    val centroidMm: PhysicalCentroid,
    val integratedExcessCmm2: Double,
    val loadSigmaCmm2: Double,
    val lower95IntegratedExcessCmm2: Double,
    val bounds: RegionBounds,
)

data class FrameReport(
    val frameId: String,
    val cameraId: String,
    val calibrationRevision: String,
    val geometryRevision: String,
    val capturedAt: String,
    val sensorWidth: Int,
    val sensorHeight: Int,
    val width: Int,
    val height: Int,
    val repairedPixels: Int,
    val referenceQuadratic: Double,
    val referenceLinear: Double,
    val referenceOffsetC: Double,
    val referenceWeightedRmseC: Double,
    val referenceReducedChiSquare: Double,
    val projectedAreaMm2: Double,
    val arrheniusRateMm2PerSecond: Double,
    val arrheniusRateSigmaMm2PerSecond: Double,
    val temporalCorrelationSeconds: Double,
    val meanUncertaintyC: Double,
    val maxUncertaintyC: Double,
    val minC: Double,
    val maxC: Double,
    val meanC: Double,
    val stddevC: Double,
    val p95C: Double,
    val thresholdC: Double,
    val hotspot: Hotspot,
    val hotRegion: HotRegion?,
    val temperatures: List<Double>,
    val uncertainties: List<Double>,
)
KOTLIN
cat > /app/analyzer/src/main/kotlin/lab/thermogram/SimpleJson.kt <<'KOTLIN'
package lab.thermogram

object SimpleJson {
    fun string(body: String, key: String): String =
        Regex("\"${Regex.escape(key)}\"\\s*:\\s*\"([^\"]*)\"").find(body)?.groupValues?.get(1)
            ?: error("missing string field $key")

    fun int(body: String, key: String): Int = number(body, key).toInt()

    fun number(body: String, key: String): Double =
        Regex("\"${Regex.escape(key)}\"\\s*:\\s*(-?[0-9]+(?:\\.[0-9]+)?(?:[eE][+-]?[0-9]+)?)")
            .find(body)?.groupValues?.get(1)?.toDouble() ?: error("missing number field $key")

    fun boolean(body: String, key: String): Boolean =
        when (Regex("\"${Regex.escape(key)}\"\\s*:\\s*(true|false)").find(body)?.groupValues?.get(1)) {
            "true" -> true
            "false" -> false
            else -> error("missing boolean field $key")
        }

    fun intArray(body: String, key: String): List<Int> =
        arrayContent(body, key).let { content ->
            if (content.isBlank()) emptyList() else content.split(',').map { it.trim().toInt() }
        }

    fun numberArray(body: String, key: String): List<Double> =
        arrayContent(body, key).let { content ->
            if (content.isBlank()) emptyList() else content.split(',').map { it.trim().toDouble() }
        }

    private fun arrayContent(body: String, key: String): String =
        Regex("\"${Regex.escape(key)}\"\\s*:\\s*\\[([^]]*)]")
            .find(body)?.groupValues?.get(1) ?: error("missing array field $key")
}
KOTLIN
cat > /app/analyzer/src/main/kotlin/lab/thermogram/ApiClient.kt <<'KOTLIN'
package lab.thermogram

import java.net.URI
import java.net.http.HttpClient
import java.net.http.HttpRequest
import java.net.http.HttpResponse
import java.time.Duration

class ApiClient(private val baseUrl: String) {
    private val client = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5)).build()

    fun frame(frameId: String): FrameMetadata {
        val body = get("/api/frames/$frameId")
        return FrameMetadata(
            frameId = SimpleJson.string(body, "frameId"),
            cameraId = SimpleJson.string(body, "cameraId"),
            capturedAt = SimpleJson.string(body, "capturedAt"),
            width = SimpleJson.int(body, "width"),
            height = SimpleJson.int(body, "height"),
        )
    }

    fun calibration(cameraId: String): Calibration {
        val body = get("/api/cameras/$cameraId/calibration")
        return Calibration(
            cameraId = SimpleJson.string(body, "cameraId"),
            revision = SimpleJson.string(body, "revision"),
            model = SimpleJson.string(body, "model"),
            gain = SimpleJson.number(body, "gain"),
            offsetC = SimpleJson.number(body, "offsetC"),
            quadratic = SimpleJson.number(body, "quadratic"),
            ambientC = SimpleJson.number(body, "ambientC"),
            ambientCoupling = SimpleJson.number(body, "ambientCoupling"),
            emissivity = SimpleJson.number(body, "emissivity"),
        )
    }

    fun geometry(cameraId: String): DetectorGeometry {
        val body = get("/api/cameras/$cameraId/geometry")
        return DetectorGeometry(
            cameraId = SimpleJson.string(body, "cameraId"),
            revision = SimpleJson.string(body, "revision"),
            rotation = SimpleJson.int(body, "rotation"),
            mirrorX = SimpleJson.boolean(body, "mirrorX"),
            badPixels = SimpleJson.intArray(body, "badPixels"),
            hotSigma = SimpleJson.number(body, "hotSigma"),
            minHotArea = SimpleJson.int(body, "minHotArea"),
            homography = SimpleJson.numberArray(body, "homography"),
            arrheniusA = SimpleJson.number(body, "arrheniusA"),
            activationEnergyJMol = SimpleJson.number(body, "activationEnergyJMol"),
            detectorNoiseC = SimpleJson.number(body, "detectorNoiseC"),
            confidenceK = SimpleJson.number(body, "confidenceK"),
            correlationMajorMm = SimpleJson.number(body, "correlationMajorMm"),
            correlationMinorMm = SimpleJson.number(body, "correlationMinorMm"),
            correlationAngleDeg = SimpleJson.number(body, "correlationAngleDeg"),
            temporalCorrelationSeconds = SimpleJson.number(body, "temporalCorrelationSeconds"),
        )
    }

    private fun get(path: String): String {
        val request = HttpRequest.newBuilder(URI.create(baseUrl + path))
            .timeout(Duration.ofSeconds(10))
            .GET()
            .build()
        val response = client.send(request, HttpResponse.BodyHandlers.ofString())
        check(response.statusCode() == 200) { "API returned ${response.statusCode()} for $path" }
        return response.body()
    }
}
KOTLIN
cat > /app/analyzer/src/main/kotlin/lab/thermogram/ArchiveReader.kt <<'KOTLIN'
package lab.thermogram

import java.nio.file.Path

class ArchiveReader {
    fun read(database: Path): ArchiveData {
        val frameSql =
            "SELECT frame_id,camera_id,captured_at,width,height,hex(qir_blob) FROM frames ORDER BY captured_at,frame_id;"
        val frames = ProcessRunner.run(
            listOf("sqlite3", "-readonly", "-separator", "\t", database.toString(), frameSql),
        ).lineSequence().filter { it.isNotBlank() }.map { line ->
            val fields = line.split('\t')
            require(fields.size == 6) { "unexpected database row" }
            FrameRow(fields[0], fields[1], fields[2], fields[3].toInt(), fields[4].toInt(), hexToBytes(fields[5]))
        }.toList()

        val checkpointSql =
            "SELECT frame_id,pixel_index,raw_count FROM frame_checkpoints ORDER BY frame_id,pixel_index;"
        val checkpoints = mutableMapOf<String, MutableMap<Int, Int>>()
        ProcessRunner.run(
            listOf("sqlite3", "-readonly", "-separator", "\t", database.toString(), checkpointSql),
        ).lineSequence().filter { it.isNotBlank() }.forEach { line ->
            val fields = line.split('\t')
            require(fields.size == 3) { "unexpected checkpoint row" }
            checkpoints.getOrPut(fields[0]) { mutableMapOf() }[fields[1].toInt()] = fields[2].toInt()
        }

        val referenceSql =
            "SELECT frame_id,reference_id,pixel_index,expected_c,sigma_c FROM reference_samples " +
                "ORDER BY frame_id,reference_id,pixel_index;"
        val references = mutableMapOf<String, MutableList<ReferenceSample>>()
        ProcessRunner.run(
            listOf("sqlite3", "-readonly", "-separator", "\t", database.toString(), referenceSql),
        ).lineSequence().filter { it.isNotBlank() }.forEach { line ->
            val fields = line.split('\t')
            require(fields.size == 5) { "unexpected reference row" }
            references.getOrPut(fields[0]) { mutableListOf() } += ReferenceSample(
                referenceId = fields[1],
                pixelIndex = fields[2].toInt(),
                expectedC = fields[3].toDouble(),
                sigmaC = fields[4].toDouble(),
            )
        }
        return ArchiveData(frames, checkpoints, references)
    }

    private fun hexToBytes(value: String): ByteArray {
        require(value.length % 2 == 0) { "invalid blob hex" }
        return ByteArray(value.length / 2) { index ->
            value.substring(index * 2, index * 2 + 2).toInt(16).toByte()
        }
    }
}
KOTLIN
cat > /app/analyzer/src/main/kotlin/lab/thermogram/AnalysisEngine.kt <<'KOTLIN'
package lab.thermogram

import kotlin.math.abs
import kotlin.math.ceil
import kotlin.math.cos
import kotlin.math.exp
import kotlin.math.floor
import kotlin.math.max
import kotlin.math.sin
import kotlin.math.sqrt

class AnalysisEngine(private val archive: ArchiveReader, private val api: ApiClient) {
    fun analyze(database: java.nio.file.Path): List<FrameReport> {
        val data = archive.read(database)
        val knownFrames = data.frames.map { it.frameId }.toSet()
        require(data.checkpoints.keys.all { it in knownFrames }) { "checkpoint references unknown frame" }
        require(data.references.keys.all { it in knownFrames }) { "reference references unknown frame" }

        return data.frames.map { row ->
            val metadata = api.frame(row.frameId)
            require(metadata == FrameMetadata(row.frameId, row.cameraId, row.capturedAt, row.width, row.height)) {
                "API metadata disagrees for ${row.frameId}"
            }
            val calibration = api.calibration(row.cameraId)
            val geometry = api.geometry(row.cameraId)
            require(calibration.cameraId == row.cameraId && geometry.cameraId == row.cameraId) {
                "camera profile mismatch"
            }
            validateGeometry(geometry, row.width * row.height)

            val decoded = QirDecoder.decode(row.blob, row.width, row.height)
            data.checkpoints[row.frameId].orEmpty().forEach { (index, expected) ->
                require(index in decoded.indices) { "checkpoint outside detector" }
                require(decoded[index] == expected) { "checkpoint mismatch for ${row.frameId}" }
            }

            val repaired = repair(decoded, row.width, row.height, geometry.badPixels)
            val preliminary = repaired.map { CalibrationMath.temperature(it, calibration) }
            val fit = fitReferences(data.references[row.frameId].orEmpty(), preliminary, geometry.badPixels.toSet())
            val corrected = preliminary.map { value -> fit.quadratic * value * value + fit.linear * value + fit.offset }
            val uncertainty = preliminary.map { value -> propagatedUncertainty(value, fit.covariance, geometry.detectorNoiseC) }
            require(corrected.all(Double::isFinite) && uncertainty.all { it.isFinite() && it > 0.0 }) {
                "invalid corrected field uncertainty"
            }

            val oriented = orient(corrected, row.width, row.height, geometry)
            val orientedUncertainty = orient(uncertainty, row.width, row.height, geometry)
            val lowerConfidence = oriented.values.indices.map { index ->
                oriented.values[index] - geometry.confidenceK * orientedUncertainty.values[index]
            }
            require(lowerConfidence.all(Double::isFinite)) { "non-finite lower confidence field" }
            val physical = physicalGrid(oriented.width, oriented.height, geometry.homography)
            val mean = oriented.values.average()
            val variance = oriented.values.sumOf { value -> (value - mean) * (value - mean) } / oriented.values.size
            val maximum = oriented.values.maxOrNull() ?: error("empty frame")
            val hotIndex = oriented.values.indexOfFirst { it == maximum }
            val threshold = robustThreshold(lowerConfidence, geometry.hotSigma)
            val region = dominantRegion(
                oriented.values,
                orientedUncertainty.values,
                lowerConfidence,
                physical.areas,
                physical.centres,
                oriented.width,
                oriented.height,
                threshold,
                geometry.minHotArea,
                geometry,
            )
            var arrheniusRate = 0.0
            val arrheniusContributions = MutableList(oriented.values.size) { 0.0 }
            for (index in oriented.values.indices) {
                val (rate, derivative) = arrheniusRateAndDerivative(oriented.values[index], geometry)
                arrheniusRate += rate * physical.areas[index]
                arrheniusContributions[index] = derivative * orientedUncertainty.values[index] * physical.areas[index]
            }
            val arrheniusSigma = spatialSigma(
                oriented.values.indices.toList(),
                arrheniusContributions,
                physical.centres,
                geometry,
            )
            require(arrheniusRate.isFinite() && arrheniusRate > 0.0 && arrheniusSigma.isFinite() && arrheniusSigma > 0.0) {
                "invalid Arrhenius rate uncertainty"
            }

            FrameReport(
                frameId = row.frameId,
                cameraId = row.cameraId,
                calibrationRevision = calibration.revision,
                geometryRevision = geometry.revision,
                capturedAt = row.capturedAt,
                sensorWidth = row.width,
                sensorHeight = row.height,
                width = oriented.width,
                height = oriented.height,
                repairedPixels = geometry.badPixels.size,
                referenceQuadratic = fit.quadratic,
                referenceLinear = fit.linear,
                referenceOffsetC = fit.offset,
                referenceWeightedRmseC = fit.weightedRmse,
                referenceReducedChiSquare = fit.reducedChiSquare,
                projectedAreaMm2 = physical.areas.sum(),
                arrheniusRateMm2PerSecond = arrheniusRate,
                arrheniusRateSigmaMm2PerSecond = arrheniusSigma,
                temporalCorrelationSeconds = geometry.temporalCorrelationSeconds,
                meanUncertaintyC = orientedUncertainty.values.average(),
                maxUncertaintyC = orientedUncertainty.values.maxOrNull()!!,
                minC = oriented.values.minOrNull()!!,
                maxC = maximum,
                meanC = mean,
                stddevC = sqrt(variance),
                p95C = percentile95(oriented.values),
                thresholdC = threshold,
                hotspot = Hotspot(
                    hotIndex % oriented.width,
                    hotIndex / oriented.width,
                    maximum,
                    orientedUncertainty.values[hotIndex],
                ),
                hotRegion = region,
                temperatures = oriented.values,
                uncertainties = orientedUncertainty.values,
            )
        }
    }

    private data class ReferenceFit(
        val quadratic: Double,
        val linear: Double,
        val offset: Double,
        val weightedRmse: Double,
        val reducedChiSquare: Double,
        val covariance: Array<DoubleArray>,
    )
    private data class PairRow(val x: Double, val y: Double, val sigma: Double)
    private data class OrientedField(val width: Int, val height: Int, val values: List<Double>)
    private data class PhysicalPoint(val x: Double, val y: Double)
    private data class PhysicalGrid(val centres: List<PhysicalPoint>, val areas: List<Double>)
    private data class Component(
        val indices: List<Int>,
        val areaMm2: Double,
        val integratedExcess: Double,
        val loadSigma: Double,
        val lower95: Double,
        val peakIndex: Int,
        val minX: Int,
        val minY: Int,
        val maxX: Int,
        val maxY: Int,
    )

    private fun validateGeometry(geometry: DetectorGeometry, pixelCount: Int) {
        require(geometry.rotation in setOf(0, 90, 180, 270)) { "invalid detector rotation" }
        require(geometry.badPixels.distinct().size == geometry.badPixels.size) { "duplicate bad pixel" }
        require(geometry.badPixels.all { it in 0 until pixelCount }) { "bad pixel outside detector" }
        require(geometry.hotSigma.isFinite() && geometry.hotSigma > 0.0) { "invalid hot sigma" }
        require(geometry.minHotArea > 0) { "invalid minimum hot area" }
        require(geometry.homography.size == 9 && geometry.homography.all(Double::isFinite)) { "invalid homography" }
        require(geometry.arrheniusA.isFinite() && geometry.arrheniusA > 0.0) { "invalid Arrhenius A" }
        require(geometry.activationEnergyJMol.isFinite() && geometry.activationEnergyJMol > 0.0) {
            "invalid activation energy"
        }
        require(geometry.detectorNoiseC.isFinite() && geometry.detectorNoiseC > 0.0) { "invalid detector noise" }
        require(geometry.confidenceK.isFinite() && geometry.confidenceK > 0.0) { "invalid confidence factor" }
        require(geometry.correlationMajorMm.isFinite() && geometry.correlationMajorMm > 0.0) {
            "invalid major correlation length"
        }
        require(geometry.correlationMinorMm.isFinite() && geometry.correlationMinorMm > 0.0) {
            "invalid minor correlation length"
        }
        require(geometry.correlationAngleDeg.isFinite()) { "invalid correlation angle" }
        require(geometry.temporalCorrelationSeconds.isFinite() && geometry.temporalCorrelationSeconds > 0.0) {
            "invalid temporal correlation length"
        }
    }

    private fun repair(raw: IntArray, width: Int, height: Int, badPixels: List<Int>): List<Double> {
        val bad = badPixels.toSet()
        val result = raw.map(Int::toDouble).toMutableList()
        for (index in badPixels) {
            val x = index % width
            val y = index / width
            val neighbours = mutableListOf<Double>()
            for (dy in -1..1) for (dx in -1..1) {
                if (dx == 0 && dy == 0) continue
                val nx = x + dx
                val ny = y + dy
                if (nx in 0 until width && ny in 0 until height) {
                    val candidate = ny * width + nx
                    if (candidate !in bad) neighbours += raw[candidate].toDouble()
                }
            }
            require(neighbours.size >= 3) { "insufficient neighbours for detector repair" }
            result[index] = median(neighbours)
        }
        return result
    }

    private fun fitReferences(rows: List<ReferenceSample>, preliminary: List<Double>, badPixels: Set<Int>): ReferenceFit {
        val grouped = rows.groupBy { it.referenceId }
        require(grouped.size >= 5) { "insufficient blackbody references" }
        val pairs = grouped.toSortedMap().map { (_, samples) ->
            val indices = samples.map { it.pixelIndex }
            require(samples.size >= 2 && indices.distinct().size == indices.size) { "invalid reference samples" }
            require(indices.all { it in preliminary.indices } && indices.none { it in badPixels }) { "invalid reference pixel" }
            val targets = samples.map { it.expectedC }
            val sigmas = samples.map { it.sigmaC }
            require(targets.distinct().size == 1 && sigmas.distinct().size == 1) { "inconsistent reference definition" }
            val y = targets.first()
            val sigma = sigmas.first()
            require(y.isFinite() && sigma.isFinite() && sigma > 0.0) { "invalid reference value" }
            PairRow(median(indices.map { preliminary[it] }), y, sigma)
        }
        val baseWeights = pairs.map { 1.0 / (it.sigma * it.sigma) }
        val sumWeight = baseWeights.sum()
        val center = pairs.indices.sumOf { pairs[it].x * baseWeights[it] } / sumWeight
        val span = pairs.maxOf { abs(it.x - center) }
        require(span.isFinite() && span > 0.0) { "degenerate reference fit" }
        val robust = MutableList(pairs.size) { 1.0 }
        var normalized = DoubleArray(3)
        var finalMatrix = Array(3) { DoubleArray(3) }
        var finalWeights = DoubleArray(pairs.size)
        repeat(8) { iteration ->
            val matrix = Array(3) { DoubleArray(3) }
            val rhs = DoubleArray(3)
            for (index in pairs.indices) {
                val pair = pairs[index]
                val z = (pair.x - center) / span
                val basis = doubleArrayOf(z * z, z, 1.0)
                val weight = baseWeights[index] * robust[index]
                finalWeights[index] = weight
                for (i in 0..2) {
                    rhs[i] += weight * basis[i] * pair.y
                    for (j in 0..2) matrix[i][j] += weight * basis[i] * basis[j]
                }
            }
            normalized = solve3x3(matrix, rhs)
            finalMatrix = matrix
            if (iteration < 7) {
                for (index in pairs.indices) {
                    val pair = pairs[index]
                    val z = (pair.x - center) / span
                    val prediction = normalized[0] * z * z + normalized[1] * z + normalized[2]
                    val standardized = abs(prediction - pair.y) / pair.sigma
                    robust[index] = if (standardized <= 1.5) 1.0 else 1.5 / standardized
                    require(robust[index].isFinite() && robust[index] > 0.0) { "invalid robust reference weight" }
                }
            }
        }
        val q = normalized[0] / (span * span)
        val l = normalized[1] / span - 2.0 * normalized[0] * center / (span * span)
        val c = normalized[2] - normalized[1] * center / span + normalized[0] * center * center / (span * span)
        val minX = pairs.minOf { it.x }
        val maxX = pairs.maxOf { it.x }
        require(2.0 * q * minX + l > 0.0 && 2.0 * q * maxX + l > 0.0) { "non-monotonic reference correction" }
        val residuals = pairs.map { pair -> q * pair.x * pair.x + l * pair.x + c - pair.y }
        val weightedSse = pairs.indices.sumOf { finalWeights[it] * residuals[it] * residuals[it] }
        val effectiveWeight = finalWeights.sum()
        val weightedRmse = sqrt(weightedSse / effectiveWeight)
        val reducedChiSquare = weightedSse / (pairs.size - 3).toDouble()
        require(reducedChiSquare.isFinite() && reducedChiSquare > 0.0) { "invalid reduced chi square" }
        val inverseNormalized = inverse3x3(finalMatrix)
        val covarianceNormalized = Array(3) { i -> DoubleArray(3) { j -> inverseNormalized[i][j] * reducedChiSquare } }
        val transform = arrayOf(
            doubleArrayOf(1.0 / (span * span), 0.0, 0.0),
            doubleArrayOf(-2.0 * center / (span * span), 1.0 / span, 0.0),
            doubleArrayOf(center * center / (span * span), -center / span, 1.0),
        )
        val covariance = multiply(multiply(transform, covarianceNormalized), transpose(transform))
        require(listOf(q, l, c, weightedRmse).all(Double::isFinite) && covariance.flatMap { it.asList() }.all(Double::isFinite)) {
            "non-finite robust reference fit"
        }
        return ReferenceFit(q, l, c, weightedRmse, reducedChiSquare, covariance)
    }

    private fun solve3x3(matrix: Array<DoubleArray>, rhs: DoubleArray): DoubleArray {
        val augmented = Array(3) { row -> DoubleArray(4) { col -> if (col < 3) matrix[row][col] else rhs[row] } }
        val scale = matrix.flatMap { it.asList() }.maxOf { abs(it) }
        require(scale.isFinite() && scale > 0.0) { "degenerate reference fit" }
        for (column in 0..2) {
            val pivotRow = (column..2).maxBy { row -> abs(augmented[row][column]) }
            require(abs(augmented[pivotRow][column]) > 1e-12 * scale) { "degenerate reference fit" }
            if (pivotRow != column) {
                val swap = augmented[pivotRow]; augmented[pivotRow] = augmented[column]; augmented[column] = swap
            }
            val pivot = augmented[column][column]
            for (col in column..3) augmented[column][col] /= pivot
            for (row in 0..2) if (row != column) {
                val factor = augmented[row][column]
                for (col in column..3) augmented[row][col] -= factor * augmented[column][col]
            }
        }
        return doubleArrayOf(augmented[0][3], augmented[1][3], augmented[2][3])
    }

    private fun inverse3x3(matrix: Array<DoubleArray>): Array<DoubleArray> {
        val inverse = Array(3) { DoubleArray(3) }
        for (column in 0..2) {
            val rhs = DoubleArray(3); rhs[column] = 1.0
            val solution = solve3x3(Array(3) { matrix[it].clone() }, rhs)
            for (row in 0..2) inverse[row][column] = solution[row]
        }
        return inverse
    }

    private fun multiply(left: Array<DoubleArray>, right: Array<DoubleArray>): Array<DoubleArray> =
        Array(3) { i -> DoubleArray(3) { j -> (0..2).sumOf { k -> left[i][k] * right[k][j] } } }

    private fun transpose(matrix: Array<DoubleArray>): Array<DoubleArray> =
        Array(3) { i -> DoubleArray(3) { j -> matrix[j][i] } }

    private fun propagatedUncertainty(value: Double, covariance: Array<DoubleArray>, detectorNoise: Double): Double {
        val gradient = doubleArrayOf(value * value, value, 1.0)
        val fitVariance = (0..2).sumOf { i -> (0..2).sumOf { j -> gradient[i] * covariance[i][j] * gradient[j] } }
        require(fitVariance.isFinite() && fitVariance >= -1e-9) { "invalid propagated fit variance" }
        val sigma = sqrt(max(0.0, fitVariance) + detectorNoise * detectorNoise)
        require(sigma.isFinite() && sigma > 0.0) { "invalid propagated uncertainty" }
        return sigma
    }

    private fun orient(values: List<Double>, width: Int, height: Int, geometry: DetectorGeometry): OrientedField {
        val outputWidth = if (geometry.rotation in setOf(90, 270)) height else width
        val outputHeight = if (geometry.rotation in setOf(90, 270)) width else height
        val output = MutableList(outputWidth * outputHeight) { Double.NaN }
        for (y in 0 until height) for (x in 0 until width) {
            val xm = if (geometry.mirrorX) width - 1 - x else x
            val (ox, oy) = when (geometry.rotation) {
                0 -> xm to y
                90 -> height - 1 - y to xm
                180 -> width - 1 - xm to height - 1 - y
                else -> y to width - 1 - xm
            }
            output[oy * outputWidth + ox] = values[y * width + x]
        }
        require(output.all(Double::isFinite)) { "incomplete furnace mapping" }
        return OrientedField(outputWidth, outputHeight, output)
    }

    private fun physicalGrid(width: Int, height: Int, homography: List<Double>): PhysicalGrid {
        val centres = mutableListOf<PhysicalPoint>(); val areas = mutableListOf<Double>()
        for (y in 0 until height) for (x in 0 until width) {
            centres += project(x.toDouble(), y.toDouble(), homography)
            val corners = listOf(
                project(x - 0.5, y - 0.5, homography), project(x + 0.5, y - 0.5, homography),
                project(x + 0.5, y + 0.5, homography), project(x - 0.5, y + 0.5, homography),
            )
            var twiceArea = 0.0
            for (i in corners.indices) {
                val next = corners[(i + 1) % corners.size]
                twiceArea += corners[i].x * next.y - next.x * corners[i].y
            }
            val area = abs(twiceArea) / 2.0
            require(area.isFinite() && area > 0.0) { "invalid projected pixel area" }
            areas += area
        }
        return PhysicalGrid(centres, areas)
    }

    private fun project(x: Double, y: Double, h: List<Double>): PhysicalPoint {
        val denominator = h[6] * x + h[7] * y + h[8]
        require(denominator.isFinite() && abs(denominator) > 1e-12) { "invalid projective denominator" }
        val px = (h[0] * x + h[1] * y + h[2]) / denominator
        val py = (h[3] * x + h[4] * y + h[5]) / denominator
        require(px.isFinite() && py.isFinite()) { "non-finite projective coordinate" }
        return PhysicalPoint(px, py)
    }

    private fun percentile95(values: List<Double>): Double {
        val ordered = values.sorted(); val position = 0.95 * (ordered.size - 1)
        val low = floor(position).toInt(); val high = ceil(position).toInt()
        return if (low == high) ordered[low] else ordered[low] + (position - low) * (ordered[high] - ordered[low])
    }

    private fun robustThreshold(values: List<Double>, sigma: Double): Double {
        val centre = median(values); val mad = median(values.map { abs(it - centre) })
        val threshold = centre + sigma * 1.4826 * mad
        require(threshold.isFinite()) { "non-finite hot threshold" }
        return threshold
    }

    private fun dominantRegion(
        values: List<Double>,
        uncertainties: List<Double>,
        lowerConfidence: List<Double>,
        areas: List<Double>,
        centres: List<PhysicalPoint>,
        width: Int,
        height: Int,
        threshold: Double,
        minArea: Int,
        geometry: DetectorGeometry,
    ): HotRegion? {
        val hot = lowerConfidence.map { it > threshold }
        val seen = BooleanArray(values.size); val components = mutableListOf<Component>()
        for (start in values.indices) {
            if (!hot[start] || seen[start]) continue
            val queue = ArrayDeque<Int>(); val indices = mutableListOf<Int>()
            queue.add(start); seen[start] = true
            while (queue.isNotEmpty()) {
                val current = queue.removeFirst(); indices += current
                val x = current % width; val y = current / width
                for (dy in -1..1) for (dx in -1..1) {
                    if (dx == 0 && dy == 0) continue
                    val nx = x + dx; val ny = y + dy
                    if (nx in 0 until width && ny in 0 until height) {
                        val next = ny * width + nx
                        if (hot[next] && !seen[next]) { seen[next] = true; queue.add(next) }
                    }
                }
            }
            if (indices.size < minArea) continue
            val area = indices.sumOf { areas[it] }
            val integrated = indices.sumOf { (values[it] - threshold) * areas[it] }
            val loadContributions = MutableList(values.size) { 0.0 }
            indices.forEach { loadContributions[it] = uncertainties[it] * areas[it] }
            val loadSigma = spatialSigma(indices, loadContributions, centres, geometry)
            val lower95 = integrated - 1.96 * loadSigma
            if (!lower95.isFinite() || lower95 <= 0.0) continue
            val peakIndex = indices.minWith(
                compareByDescending<Int> { lowerConfidence[it] }
                    .thenByDescending { values[it] }
                    .thenBy { it },
            )
            components += Component(
                indices, area, integrated, loadSigma, lower95, peakIndex,
                indices.minOf { it % width }, indices.minOf { it / width },
                indices.maxOf { it % width }, indices.maxOf { it / width },
            )
        }
        val chosen = components.minWithOrNull(
            compareByDescending<Component> { it.lower95 }
                .thenByDescending { it.integratedExcess }
                .thenByDescending { it.areaMm2 }
                .thenByDescending { it.indices.size }
                .thenBy { it.minY }.thenBy { it.minX }.thenBy { it.peakIndex },
        ) ?: return null
        val weights = chosen.indices.map { (lowerConfidence[it] - threshold) * areas[it] }
        val totalWeight = weights.sum()
        require(totalWeight.isFinite() && totalWeight > 0.0) { "invalid confidence centroid" }
        val centroidX = chosen.indices.indices.sumOf { position -> centres[chosen.indices[position]].x * weights[position] } / totalWeight
        val centroidY = chosen.indices.indices.sumOf { position -> centres[chosen.indices[position]].y * weights[position] } / totalWeight
        return HotRegion(
            areaPixels = chosen.indices.size,
            areaMm2 = chosen.areaMm2,
            peak = RegionPoint(
                chosen.peakIndex % width,
                chosen.peakIndex / width,
                values[chosen.peakIndex],
                uncertainties[chosen.peakIndex],
            ),
            centroidMm = PhysicalCentroid(centroidX, centroidY),
            integratedExcessCmm2 = chosen.integratedExcess,
            loadSigmaCmm2 = chosen.loadSigma,
            lower95IntegratedExcessCmm2 = chosen.lower95,
            bounds = RegionBounds(chosen.minX, chosen.minY, chosen.maxX, chosen.maxY),
        )
    }

    private fun spatialSigma(
        indices: List<Int>,
        contributions: List<Double>,
        centres: List<PhysicalPoint>,
        geometry: DetectorGeometry,
    ): Double {
        val angle = Math.toRadians(geometry.correlationAngleDeg)
        val cosine = cos(angle)
        val sine = sin(angle)
        var variance = 0.0
        for (position in indices.indices) {
            val i = indices[position]
            val contributionI = contributions[i]
            require(contributionI.isFinite()) { "non-finite uncertainty contribution" }
            variance += contributionI * contributionI
            for (otherPosition in position + 1 until indices.size) {
                val j = indices[otherPosition]
                val dx = centres[j].x - centres[i].x
                val dy = centres[j].y - centres[i].y
                val major = cosine * dx + sine * dy
                val minor = -sine * dx + cosine * dy
                val scaledSquared =
                    (major / geometry.correlationMajorMm) * (major / geometry.correlationMajorMm) +
                    (minor / geometry.correlationMinorMm) * (minor / geometry.correlationMinorMm)
                val correlation = exp(-0.5 * scaledSquared)
                require(correlation.isFinite() && correlation > 0.0 && correlation <= 1.0) {
                    "invalid spatial correlation"
                }
                variance += 2.0 * contributionI * contributions[j] * correlation
            }
        }
        require(variance.isFinite() && variance > 0.0) { "invalid spatial covariance" }
        val sigma = sqrt(variance)
        require(sigma.isFinite() && sigma > 0.0) { "invalid correlated uncertainty" }
        return sigma
    }

    private fun arrheniusRateAndDerivative(temperatureC: Double, geometry: DetectorGeometry): Pair<Double, Double> {
        val kelvin = temperatureC + 273.15
        require(kelvin.isFinite() && kelvin > 0.0) { "invalid absolute temperature" }
        val gasConstant = 8.31446261815324
        val rate = geometry.arrheniusA * exp(-geometry.activationEnergyJMol / (gasConstant * kelvin))
        val derivative = rate * geometry.activationEnergyJMol / (gasConstant * kelvin * kelvin)
        require(rate.isFinite() && rate > 0.0 && derivative.isFinite() && derivative > 0.0) { "invalid Arrhenius derivative" }
        return rate to derivative
    }

    private fun median(values: List<Double>): Double {
        require(values.isNotEmpty()) { "empty median" }
        val ordered = values.sorted(); val middle = ordered.size / 2
        return if (ordered.size % 2 == 1) ordered[middle] else (ordered[middle - 1] + ordered[middle]) / 2.0
    }
}
KOTLIN
cat > /app/analyzer/src/main/kotlin/lab/thermogram/ReportWriter.kt <<'KOTLIN'
package lab.thermogram

import java.math.BigDecimal
import java.math.RoundingMode
import java.nio.charset.StandardCharsets
import java.nio.file.AtomicMoveNotSupportedException
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.StandardCopyOption
import java.time.Duration
import java.time.Instant
import kotlin.math.abs
import kotlin.math.exp
import kotlin.math.max
import kotlin.math.sqrt

object ReportWriter {
    private data class TimedFrame(val report: FrameReport, val instant: Instant)
    private data class LoadRise(
        val cameraId: String,
        val fromFrameId: String,
        val toFrameId: String,
        val rate: Double,
        val sigma: Double,
        val lower95: Double,
    )
    private data class ArrheniusAcceleration(
        val cameraId: String,
        val fromFrameId: String,
        val toFrameId: String,
        val observationCount: Int,
        val acceleration: Double,
        val sigma: Double,
        val lower95: Double,
    )
    private data class Dose(val cameraId: String, val dose: Double, val sigma: Double, val lower95: Double)

    private fun rounded(value: Double): String =
        BigDecimal.valueOf(value).setScale(3, RoundingMode.HALF_UP).toPlainString()
    private fun quote(value: String): String = "\"" + value.replace("\\", "\\\\").replace("\"", "\\\"") + "\""

    fun write(frames: List<FrameReport>, output: Path) {
        require(frames.isNotEmpty()) { "archive has no frames" }
        val timed = frames.map { TimedFrame(it, Instant.parse(it.capturedAt)) }
            .sortedWith(compareBy<TimedFrame> { it.instant }.thenBy { it.report.frameId })
        val hottest = timed.minWith(compareByDescending<TimedFrame> { it.report.maxC }.thenBy { it.report.frameId })
        val regionWinner = timed.filter { it.report.hotRegion != null }.minWithOrNull(
            compareByDescending<TimedFrame> { it.report.hotRegion!!.lower95IntegratedExcessCmm2 }
                .thenByDescending { it.report.hotRegion!!.integratedExcessCmm2 }
                .thenBy { it.report.frameId },
        )
        val fastest = fastestSignificantRise(timed)
        val acceleration = steepestSignificantArrheniusAcceleration(timed)
        val dose = largestConservativeDose(timed)
        val frameJson = timed.joinToString(",") { frameJson(it.report) }
        val auditJson = timed.joinToString(",") { auditJson(it.report) }
        val fastestJson = fastest?.let {
            "{\"cameraId\":${quote(it.cameraId)}," +
                "\"fromFrameId\":${quote(it.fromFrameId)}," +
                "\"toFrameId\":${quote(it.toFrameId)}," +
                "\"rateCmm2PerMinute\":${rounded(it.rate)}," +
                "\"sigmaCmm2PerMinute\":${rounded(it.sigma)}," +
                "\"lower95Cmm2PerMinute\":${rounded(it.lower95)}}"
        } ?: "null"
        val accelerationJson = acceleration?.let {
            "{\"cameraId\":${quote(it.cameraId)}," +
                "\"fromFrameId\":${quote(it.fromFrameId)}," +
                "\"toFrameId\":${quote(it.toFrameId)}," +
                "\"observationCount\":${it.observationCount}," +
                "\"accelerationMm2PerSecondPerMinute\":${rounded(it.acceleration)}," +
                "\"sigmaMm2PerSecondPerMinute\":${rounded(it.sigma)}," +
                "\"lower95Mm2PerSecondPerMinute\":${rounded(it.lower95)}}"
        } ?: "null"
        val doseJson = dose?.let {
            "{\"cameraId\":${quote(it.cameraId)}," +
                "\"doseMm2\":${rounded(it.dose)}," +
                "\"sigmaMm2\":${rounded(it.sigma)}," +
                "\"lower95Mm2\":${rounded(it.lower95)}}"
        } ?: "null"
        val regionFrame = regionWinner?.let { quote(it.report.frameId) } ?: "null"
        val regionLoad = regionWinner?.let { rounded(it.report.hotRegion!!.lower95IntegratedExcessCmm2) } ?: "null"
        val meanFrameMean = timed.map { it.report.meanC }.average()
        val json = "{\"frames\":[$frameJson],\"summary\":{" +
            "\"frameCount\":${timed.size}," +
            "\"hottestFrameId\":${quote(hottest.report.frameId)}," +
            "\"globalMaxC\":${rounded(hottest.report.maxC)}," +
            "\"meanFrameMeanC\":${rounded(meanFrameMean)}," +
            "\"largestConservativeRegionFrameId\":$regionFrame," +
            "\"largestLower95IntegratedExcessCmm2\":$regionLoad," +
            "\"fastestSignificantThermalLoadRise\":$fastestJson," +
            "\"steepestSignificantArrheniusAcceleration\":$accelerationJson," +
            "\"largestConservativeArrheniusDose\":$doseJson}," +
            "\"_audit\":[$auditJson]}\n"
        publish(output, json)
    }

    private fun auditJson(frame: FrameReport): String {
        val load = frame.hotRegion?.integratedExcessCmm2 ?: 0.0
        val loadSigma = frame.hotRegion?.loadSigmaCmm2 ?: 0.0
        return "{" + listOf(
            "\"frameId\":" + quote(frame.frameId),
            "\"cameraId\":" + quote(frame.cameraId),
            "\"capturedAt\":" + quote(frame.capturedAt),
            "\"temporalCorrelationSeconds\":${frame.temporalCorrelationSeconds}",
            "\"arrheniusRateMm2PerSecond\":${frame.arrheniusRateMm2PerSecond}",
            "\"arrheniusRateSigmaMm2PerSecond\":${frame.arrheniusRateSigmaMm2PerSecond}",
            "\"integratedExcessCmm2\":$load",
            "\"loadSigmaCmm2\":$loadSigma",
        ).joinToString(",") + "}"
    }

    private fun cameraRows(ordered: List<TimedFrame>): Map<String, List<TimedFrame>> =
        ordered.groupBy { it.report.cameraId }.mapValues { (_, rows) ->
            rows.sortedWith(compareBy<TimedFrame> { it.instant }.thenBy { it.report.frameId })
        }

    private fun temporalScale(rows: List<TimedFrame>): Double {
        val scale = rows.first().report.temporalCorrelationSeconds
        require(scale.isFinite() && scale > 0.0) { "invalid temporal correlation length" }
        require(rows.all { it.report.temporalCorrelationSeconds == scale }) {
            "camera temporal correlation profile changed within archive"
        }
        return scale
    }

    private fun elapsedSeconds(left: Instant, right: Instant): Double {
        val duration = Duration.between(left, right)
        return duration.seconds.toDouble() + duration.nano.toDouble() / 1_000_000_000.0
    }

    private fun temporalCorrelation(left: TimedFrame, right: TimedFrame, scaleSeconds: Double): Double {
        val elapsed = abs(elapsedSeconds(left.instant, right.instant))
        val correlation = exp(-elapsed / scaleSeconds)
        require(correlation.isFinite() && correlation > 0.0 && correlation <= 1.0) {
            "invalid temporal correlation"
        }
        return correlation
    }

    private fun fastestSignificantRise(ordered: List<TimedFrame>): LoadRise? {
        val candidates = mutableListOf<LoadRise>()
        cameraRows(ordered).forEach { (cameraId, rows) ->
            val scale = temporalScale(rows)
            rows.zipWithNext().forEach { (earlier, later) ->
                val elapsedSeconds = elapsedSeconds(earlier.instant, later.instant)
                require(elapsedSeconds > 0.0) { "non-positive frame interval" }
                val elapsedMinutes = elapsedSeconds / 60.0
                val earlierLoad = earlier.report.hotRegion?.integratedExcessCmm2 ?: 0.0
                val laterLoad = later.report.hotRegion?.integratedExcessCmm2 ?: 0.0
                val earlierSigma = earlier.report.hotRegion?.loadSigmaCmm2 ?: 0.0
                val laterSigma = later.report.hotRegion?.loadSigmaCmm2 ?: 0.0
                val covariance = earlierSigma * laterSigma * temporalCorrelation(earlier, later, scale)
                val variance = earlierSigma * earlierSigma + laterSigma * laterSigma - 2.0 * covariance
                require(variance.isFinite() && variance >= -1e-9) { "invalid correlated load-rise variance" }
                val rate = (laterLoad - earlierLoad) / elapsedMinutes
                val sigma = sqrt(max(0.0, variance)) / elapsedMinutes
                val lower95 = rate - 1.96 * sigma
                require(listOf(rate, sigma, lower95).all(Double::isFinite) && sigma >= 0.0) {
                    "invalid load-rise uncertainty"
                }
                if (lower95 > 0.0) {
                    candidates += LoadRise(cameraId, earlier.report.frameId, later.report.frameId, rate, sigma, lower95)
                }
            }
        }
        return candidates.minWithOrNull(
            compareByDescending<LoadRise> { it.lower95 }
                .thenByDescending { it.rate }
                .thenBy { it.cameraId }.thenBy { it.fromFrameId }.thenBy { it.toFrameId },
        )
    }

    private fun steepestSignificantArrheniusAcceleration(ordered: List<TimedFrame>): ArrheniusAcceleration? {
        val candidates = mutableListOf<ArrheniusAcceleration>()
        cameraRows(ordered).forEach { (cameraId, rows) ->
            if (rows.size < 2) return@forEach
            val scale = temporalScale(rows)
            val covariance = temporalCovariance(rows, scale) { it.report.arrheniusRateSigmaMm2PerSecond }
            val sigmas = rows.map { it.report.arrheniusRateSigmaMm2PerSecond }
            val correlation = Array(rows.size) { i ->
                DoubleArray(rows.size) { j -> covariance[i][j] / (sigmas[i] * sigmas[j]) }
            }
            val inverseCorrelation = invert(correlation)
            val inverse = Array(rows.size) { i ->
                DoubleArray(rows.size) { j -> inverseCorrelation[i][j] / (sigmas[i] * sigmas[j]) }
            }
            val origin = rows.first().instant
            val times = rows.map { elapsedSeconds(origin, it.instant) / 60.0 }
            require(times.zipWithNext().all { (left, right) -> right > left }) { "non-positive frame interval" }
            val values = rows.map { it.report.arrheniusRateMm2PerSecond }
            var n00 = 0.0
            var n01 = 0.0
            var n11 = 0.0
            var rhs0 = 0.0
            var rhs1 = 0.0
            for (i in rows.indices) for (j in rows.indices) {
                val weight = inverse[i][j]
                n00 += weight
                n01 += weight * times[j]
                n11 += times[i] * weight * times[j]
                rhs0 += weight * values[j]
                rhs1 += times[i] * weight * values[j]
            }
            val determinant = n00 * n11 - n01 * n01
            val scaleNormal = max(max(abs(n00), abs(n01)), abs(n11))
            require(scaleNormal.isFinite() && scaleNormal > 0.0 && determinant > 1e-12 * scaleNormal * scaleNormal) {
                "degenerate temporal GLS fit"
            }
            val slope = (-n01 * rhs0 + n00 * rhs1) / determinant
            val slopeVariance = n00 / determinant
            require(slopeVariance.isFinite() && slopeVariance > 0.0) { "invalid temporal GLS covariance" }
            val sigma = sqrt(slopeVariance)
            val lower95 = slope - 1.96 * sigma
            require(listOf(slope, sigma, lower95).all(Double::isFinite)) { "invalid Arrhenius acceleration" }
            if (lower95 > 0.0) {
                candidates += ArrheniusAcceleration(
                    cameraId,
                    rows.first().report.frameId,
                    rows.last().report.frameId,
                    rows.size,
                    slope,
                    sigma,
                    lower95,
                )
            }
        }
        return candidates.minWithOrNull(
            compareByDescending<ArrheniusAcceleration> { it.lower95 }
                .thenByDescending { it.acceleration }
                .thenBy { it.cameraId }
                .thenBy { it.fromFrameId }
                .thenBy { it.toFrameId },
        )
    }

    private fun largestConservativeDose(ordered: List<TimedFrame>): Dose? {
        val doses = mutableListOf<Dose>()
        cameraRows(ordered).forEach { (cameraId, frames) ->
            if (frames.size < 2) return@forEach
            val scale = temporalScale(frames)
            val coefficients = DoubleArray(frames.size)
            var dose = 0.0
            frames.zipWithNext().forEachIndexed { index, (earlier, later) ->
                val elapsed = elapsedSeconds(earlier.instant, later.instant)
                require(elapsed > 0.0) { "non-positive frame interval" }
                dose += 0.5 * (earlier.report.arrheniusRateMm2PerSecond + later.report.arrheniusRateMm2PerSecond) * elapsed
                coefficients[index] += 0.5 * elapsed
                coefficients[index + 1] += 0.5 * elapsed
            }
            val covariance = temporalCovariance(frames, scale) { it.report.arrheniusRateSigmaMm2PerSecond }
            var variance = 0.0
            for (i in frames.indices) for (j in frames.indices) {
                variance += coefficients[i] * covariance[i][j] * coefficients[j]
            }
            require(variance.isFinite() && variance > 0.0) { "invalid correlated Arrhenius dose variance" }
            val sigma = sqrt(variance)
            val lower95 = dose - 1.96 * sigma
            require(listOf(dose, sigma, lower95).all(Double::isFinite) && dose > 0.0 && sigma > 0.0) {
                "invalid conservative Arrhenius dose"
            }
            doses += Dose(cameraId, dose, sigma, lower95)
        }
        return doses.minWithOrNull(
            compareByDescending<Dose> { it.lower95 }.thenByDescending { it.dose }.thenBy { it.cameraId },
        )
    }

    private fun temporalCovariance(
        rows: List<TimedFrame>,
        scaleSeconds: Double,
        sigma: (TimedFrame) -> Double,
    ): Array<DoubleArray> {
        return Array(rows.size) { i ->
            DoubleArray(rows.size) { j ->
                val left = sigma(rows[i])
                val right = sigma(rows[j])
                require(left.isFinite() && left > 0.0 && right.isFinite() && right > 0.0) {
                    "invalid temporal uncertainty input"
                }
                left * right * temporalCorrelation(rows[i], rows[j], scaleSeconds)
            }
        }
    }

    private fun invert(matrix: Array<DoubleArray>): Array<DoubleArray> {
        val size = matrix.size
        require(size > 0 && matrix.all { it.size == size }) { "invalid covariance matrix" }
        val augmented = Array(size) { row -> DoubleArray(2 * size) { column ->
            when {
                column < size -> matrix[row][column]
                column - size == row -> 1.0
                else -> 0.0
            }
        } }
        val matrixScale = matrix.maxOf { row -> row.maxOf { abs(it) } }
        require(matrixScale.isFinite() && matrixScale > 0.0) { "degenerate temporal covariance" }
        for (column in 0 until size) {
            val pivot = (column until size).maxBy { row -> abs(augmented[row][column]) }
            require(abs(augmented[pivot][column]) > 1e-12 * matrixScale) { "singular temporal covariance" }
            val swap = augmented[column]
            augmented[column] = augmented[pivot]
            augmented[pivot] = swap
            val divisor = augmented[column][column]
            for (j in 0 until 2 * size) augmented[column][j] /= divisor
            for (row in 0 until size) {
                if (row == column) continue
                val factor = augmented[row][column]
                for (j in 0 until 2 * size) augmented[row][j] -= factor * augmented[column][j]
            }
        }
        val inverse = Array(size) { row -> DoubleArray(size) { column -> augmented[row][column + size] } }
        require(inverse.all { row -> row.all(Double::isFinite) }) { "non-finite temporal covariance inverse" }
        return inverse
    }

    private fun frameJson(frame: FrameReport): String {
        val region = frame.hotRegion?.let { hot ->
            "{\"areaPixels\":${hot.areaPixels}," +
                "\"areaMm2\":${rounded(hot.areaMm2)}," +
                "\"peak\":{\"x\":${hot.peak.x},\"y\":${hot.peak.y}," +
                "\"temperatureC\":${rounded(hot.peak.temperatureC)},\"uncertaintyC\":${rounded(hot.peak.uncertaintyC)}}," +
                "\"centroidMm\":{\"x\":${rounded(hot.centroidMm.x)},\"y\":${rounded(hot.centroidMm.y)}}," +
                "\"integratedExcessCmm2\":${rounded(hot.integratedExcessCmm2)}," +
                "\"loadSigmaCmm2\":${rounded(hot.loadSigmaCmm2)}," +
                "\"lower95IntegratedExcessCmm2\":${rounded(hot.lower95IntegratedExcessCmm2)}," +
                "\"bounds\":{\"minX\":${hot.bounds.minX},\"minY\":${hot.bounds.minY}," +
                "\"maxX\":${hot.bounds.maxX},\"maxY\":${hot.bounds.maxY}}}"
        } ?: "null"
        return "{" + listOf(
            "\"frameId\":" + quote(frame.frameId),
            "\"cameraId\":" + quote(frame.cameraId),
            "\"calibrationRevision\":" + quote(frame.calibrationRevision),
            "\"geometryRevision\":" + quote(frame.geometryRevision),
            "\"capturedAt\":" + quote(frame.capturedAt),
            "\"sensorWidth\":${frame.sensorWidth}", "\"sensorHeight\":${frame.sensorHeight}",
            "\"width\":${frame.width}", "\"height\":${frame.height}",
            "\"repairedPixels\":${frame.repairedPixels}",
            "\"referenceQuadratic\":${rounded(frame.referenceQuadratic)}",
            "\"referenceLinear\":${rounded(frame.referenceLinear)}",
            "\"referenceOffsetC\":${rounded(frame.referenceOffsetC)}",
            "\"referenceWeightedRmseC\":${rounded(frame.referenceWeightedRmseC)}",
            "\"referenceReducedChiSquare\":${rounded(frame.referenceReducedChiSquare)}",
            "\"projectedAreaMm2\":${rounded(frame.projectedAreaMm2)}",
            "\"arrheniusRateMm2PerSecond\":${rounded(frame.arrheniusRateMm2PerSecond)}",
            "\"arrheniusRateSigmaMm2PerSecond\":${rounded(frame.arrheniusRateSigmaMm2PerSecond)}",
            "\"meanUncertaintyC\":${rounded(frame.meanUncertaintyC)}",
            "\"maxUncertaintyC\":${rounded(frame.maxUncertaintyC)}",
            "\"minC\":${rounded(frame.minC)}", "\"maxC\":${rounded(frame.maxC)}",
            "\"meanC\":${rounded(frame.meanC)}", "\"stddevC\":${rounded(frame.stddevC)}",
            "\"p95C\":${rounded(frame.p95C)}", "\"thresholdC\":${rounded(frame.thresholdC)}",
            "\"hotspot\":{\"x\":${frame.hotspot.x},\"y\":${frame.hotspot.y}," +
                "\"temperatureC\":${rounded(frame.hotspot.temperatureC)},\"uncertaintyC\":${rounded(frame.hotspot.uncertaintyC)}}",
            "\"hotRegion\":$region",
        ).joinToString(",") + "}"
    }

    private fun publish(output: Path, json: String) {
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
KOTLIN
cat > /app/auditor/main.go <<'GO'
package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"math"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"time"
	"unicode/utf8"
)

type auditRecord struct {
	FrameID                        string  `json:"frameId"`
	CameraID                       string  `json:"cameraId"`
	CapturedAt                     string  `json:"capturedAt"`
	TemporalCorrelationSeconds     float64 `json:"temporalCorrelationSeconds"`
	ArrheniusRateMm2PerSecond      float64 `json:"arrheniusRateMm2PerSecond"`
	ArrheniusRateSigmaMm2PerSecond float64 `json:"arrheniusRateSigmaMm2PerSecond"`
	IntegratedExcessCmm2           float64 `json:"integratedExcessCmm2"`
	LoadSigmaCmm2                  float64 `json:"loadSigmaCmm2"`
	instant                        time.Time
}

type publicRegion struct {
	IntegratedExcessCmm2 float64 `json:"integratedExcessCmm2"`
	LoadSigmaCmm2        float64 `json:"loadSigmaCmm2"`
}

type publicFrame struct {
	FrameID                        string        `json:"frameId"`
	CameraID                       string        `json:"cameraId"`
	CapturedAt                     string        `json:"capturedAt"`
	ArrheniusRateMm2PerSecond      float64       `json:"arrheniusRateMm2PerSecond"`
	ArrheniusRateSigmaMm2PerSecond float64       `json:"arrheniusRateSigmaMm2PerSecond"`
	HotRegion                      *publicRegion `json:"hotRegion"`
}

type profile struct {
	CameraID               string
	MinFrames              int
	MaxGapSeconds          float64
	CrossMetricCorrelation float64
	LoadSigmaFloor         float64
	MinGLR                 float64
}

type episode struct {
	CameraID                        string  `json:"cameraId"`
	FromFrameID                     string  `json:"fromFrameId"`
	ToFrameID                       string  `json:"toFrameId"`
	ObservationCount                int     `json:"observationCount"`
	ArrheniusShiftMm2PerSecond      float64 `json:"arrheniusShiftMm2PerSecond"`
	ArrheniusShiftSigmaMm2PerSecond float64 `json:"arrheniusShiftSigmaMm2PerSecond"`
	ArrheniusLower95Mm2PerSecond    float64 `json:"arrheniusLower95Mm2PerSecond"`
	LoadShiftCmm2                   float64 `json:"loadShiftCmm2"`
	LoadShiftSigmaCmm2              float64 `json:"loadShiftSigmaCmm2"`
	LoadLower95Cmm2                 float64 `json:"loadLower95Cmm2"`
	GeneralizedLikelihoodRatio      float64 `json:"generalizedLikelihoodRatio"`
	rawArrheniusLower95             float64
	rawLoadLower95                  float64
	rawGLR                          float64
}

func main() {
	if err := run(os.Args[1:]); err != nil {
		fmt.Fprintln(os.Stderr, "thermal evidence finalizer failed:", err)
		os.Exit(1)
	}
}

func parseArgs(args []string) (map[string]string, error) {
	if len(args)%2 != 0 {
		return nil, errors.New("missing argument value")
	}
	values := map[string]string{}
	allowed := map[string]bool{"--db": true, "--report": true, "--output": true}
	for i := 0; i < len(args); i += 2 {
		if !allowed[args[i]] {
			return nil, fmt.Errorf("unknown argument: %s", args[i])
		}
		if values[args[i]] != "" {
			return nil, fmt.Errorf("duplicate argument: %s", args[i])
		}
		values[args[i]] = args[i+1]
	}
	for _, key := range []string{"--db", "--report", "--output"} {
		if values[key] == "" {
			return nil, fmt.Errorf("%s is required", key)
		}
	}
	return values, nil
}

func run(args []string) error {
	values, err := parseArgs(args)
	if err != nil {
		return err
	}
	data, err := os.ReadFile(values["--report"])
	if err != nil {
		return err
	}
	var top map[string]json.RawMessage
	if err := json.Unmarshal(data, &top); err != nil {
		return fmt.Errorf("candidate JSON: %w", err)
	}
	framesRaw, okFrames := top["frames"]
	summaryRaw, okSummary := top["summary"]
	auditRaw, okAudit := top["_audit"]
	if !okFrames || !okSummary || !okAudit || len(top) != 3 {
		return errors.New("candidate must have exact frames, summary, and _audit keys")
	}
	var frames []publicFrame
	var audits []auditRecord
	var summary map[string]json.RawMessage
	if err := json.Unmarshal(framesRaw, &frames); err != nil {
		return fmt.Errorf("frames: %w", err)
	}
	if err := json.Unmarshal(auditRaw, &audits); err != nil {
		return fmt.Errorf("audit: %w", err)
	}
	if err := json.Unmarshal(summaryRaw, &summary); err != nil {
		return fmt.Errorf("summary: %w", err)
	}
	if err := validateHandoff(frames, audits, summary); err != nil {
		return err
	}
	profiles, err := readProfiles(values["--db"])
	if err != nil {
		return err
	}
	digest, err := evidenceDigest(audits)
	if err != nil {
		return err
	}
	winner, err := dominantEpisode(audits, profiles)
	if err != nil {
		return err
	}
	digestJSON, _ := json.Marshal(digest)
	summary["evidenceSha256"] = digestJSON
	if winner == nil {
		summary["dominantBivariateThermalEpisode"] = json.RawMessage("null")
	} else {
		public := *winner
		public.ArrheniusShiftMm2PerSecond = round3(public.ArrheniusShiftMm2PerSecond)
		public.ArrheniusShiftSigmaMm2PerSecond = round3(public.ArrheniusShiftSigmaMm2PerSecond)
		public.ArrheniusLower95Mm2PerSecond = round3(public.ArrheniusLower95Mm2PerSecond)
		public.LoadShiftCmm2 = round3(public.LoadShiftCmm2)
		public.LoadShiftSigmaCmm2 = round3(public.LoadShiftSigmaCmm2)
		public.LoadLower95Cmm2 = round3(public.LoadLower95Cmm2)
		public.GeneralizedLikelihoodRatio = round3(public.GeneralizedLikelihoodRatio)
		encoded, err := json.Marshal(public)
		if err != nil {
			return err
		}
		summary["dominantBivariateThermalEpisode"] = encoded
	}
	encodedSummary, err := json.Marshal(summary)
	if err != nil {
		return err
	}
	final := map[string]json.RawMessage{
		"frames":  framesRaw,
		"summary": encodedSummary,
	}
	encoded, err := json.Marshal(final)
	if err != nil {
		return err
	}
	encoded = append(encoded, '\n')
	return atomicWrite(values["--output"], encoded)
}

func validateHandoff(frames []publicFrame, audits []auditRecord, summary map[string]json.RawMessage) error {
	if len(frames) == 0 || len(frames) != len(audits) {
		return errors.New("frame/audit count disagreement")
	}
	var frameCount int
	if raw, ok := summary["frameCount"]; !ok || json.Unmarshal(raw, &frameCount) != nil || frameCount != len(frames) {
		return errors.New("summary frameCount disagreement")
	}
	seen := map[string]bool{}
	for i := range frames {
		f := frames[i]
		a := &audits[i]
		if f.FrameID == "" || f.CameraID == "" || f.CapturedAt == "" ||
			f.FrameID != a.FrameID || f.CameraID != a.CameraID || f.CapturedAt != a.CapturedAt {
			return errors.New("frame/audit identity disagreement")
		}
		if seen[f.FrameID] {
			return errors.New("duplicate frame ID")
		}
		seen[f.FrameID] = true
		instant, err := time.Parse(time.RFC3339Nano, a.CapturedAt)
		if err != nil {
			return fmt.Errorf("invalid audit timestamp: %w", err)
		}
		a.instant = instant
		values := []float64{
			a.TemporalCorrelationSeconds, a.ArrheniusRateMm2PerSecond,
			a.ArrheniusRateSigmaMm2PerSecond, a.IntegratedExcessCmm2, a.LoadSigmaCmm2,
		}
		for _, value := range values {
			if math.IsNaN(value) || math.IsInf(value, 0) {
				return errors.New("non-finite audit value")
			}
		}
		if a.TemporalCorrelationSeconds <= 0 || a.ArrheniusRateMm2PerSecond <= 0 ||
			a.ArrheniusRateSigmaMm2PerSecond <= 0 || a.LoadSigmaCmm2 < 0 {
			return errors.New("nonphysical audit value")
		}
		if !sameRounded(f.ArrheniusRateMm2PerSecond, a.ArrheniusRateMm2PerSecond) ||
			!sameRounded(f.ArrheniusRateSigmaMm2PerSecond, a.ArrheniusRateSigmaMm2PerSecond) {
			return errors.New("public Arrhenius values disagree with audit")
		}
		load := 0.0
		loadSigma := 0.0
		if f.HotRegion != nil {
			load = f.HotRegion.IntegratedExcessCmm2
			loadSigma = f.HotRegion.LoadSigmaCmm2
		}
		if !sameRounded(load, a.IntegratedExcessCmm2) || !sameRounded(loadSigma, a.LoadSigmaCmm2) {
			return errors.New("public load values disagree with audit")
		}
	}
	return nil
}

func round3(value float64) float64 {
	return math.Round(value*1000.0) / 1000.0
}

func selection9(value float64) float64 {
	return math.Round(value*1_000_000_000.0) / 1_000_000_000.0
}

func sameRounded(public, audit float64) bool {
	return math.Abs(public-round3(audit)) <= 5e-10
}

func readProfiles(database string) (map[string]profile, error) {
	query := "SELECT camera_id,min_frames,max_gap_seconds,cross_metric_correlation,load_sigma_floor_cmm2,min_glr FROM episode_profiles ORDER BY camera_id;"
	command := exec.Command("sqlite3", "-readonly", "-separator", "\t", database, query)
	output, err := command.Output()
	if err != nil {
		return nil, fmt.Errorf("episode profile query: %w", err)
	}
	result := map[string]profile{}
	for _, line := range strings.Split(strings.TrimSpace(string(output)), "\n") {
		if strings.TrimSpace(line) == "" {
			continue
		}
		fields := strings.Split(line, "\t")
		if len(fields) != 6 {
			return nil, errors.New("invalid episode profile row")
		}
		minFrames, err1 := strconv.Atoi(fields[1])
		maxGap, err2 := strconv.ParseFloat(fields[2], 64)
		cross, err3 := strconv.ParseFloat(fields[3], 64)
		floor, err4 := strconv.ParseFloat(fields[4], 64)
		minGLR, err5 := strconv.ParseFloat(fields[5], 64)
		if err1 != nil || err2 != nil || err3 != nil || err4 != nil || err5 != nil {
			return nil, errors.New("invalid episode profile value")
		}
		p := profile{fields[0], minFrames, maxGap, cross, floor, minGLR}
		if p.CameraID == "" || p.MinFrames < 2 || !finitePositive(p.MaxGapSeconds) ||
			!finitePositive(p.LoadSigmaFloor) || !finiteNonnegative(p.MinGLR) ||
			!math.IsNaN(p.CrossMetricCorrelation) && (p.CrossMetricCorrelation <= -0.95 || p.CrossMetricCorrelation >= 0.95) ||
			math.IsNaN(p.CrossMetricCorrelation) || math.IsInf(p.CrossMetricCorrelation, 0) {
			return nil, errors.New("nonphysical episode profile")
		}
		if _, exists := result[p.CameraID]; exists {
			return nil, errors.New("duplicate episode profile")
		}
		result[p.CameraID] = p
	}
	return result, nil
}

func finitePositive(value float64) bool {
	return !math.IsNaN(value) && !math.IsInf(value, 0) && value > 0
}
func finiteNonnegative(value float64) bool {
	return !math.IsNaN(value) && !math.IsInf(value, 0) && value >= 0
}

func evidenceDigest(audits []auditRecord) (string, error) {
	var buffer bytes.Buffer
	buffer.WriteString("TGA1")
	if err := binary.Write(&buffer, binary.LittleEndian, uint32(len(audits))); err != nil {
		return "", err
	}
	for _, row := range audits {
		for _, value := range []string{row.FrameID, row.CameraID, row.CapturedAt} {
			if value == "" || !utf8.ValidString(value) || len([]byte(value)) > 65535 {
				return "", errors.New("invalid evidence string")
			}
			if err := binary.Write(&buffer, binary.LittleEndian, uint16(len([]byte(value)))); err != nil {
				return "", err
			}
			buffer.WriteString(value)
		}
		if err := binary.Write(&buffer, binary.LittleEndian, row.instant.UnixMilli()); err != nil {
			return "", err
		}
		for _, value := range []float64{
			row.TemporalCorrelationSeconds, row.ArrheniusRateMm2PerSecond,
			row.ArrheniusRateSigmaMm2PerSecond, row.IntegratedExcessCmm2, row.LoadSigmaCmm2,
		} {
			scaled := math.Round(value * 1_000.0)
			if math.IsNaN(scaled) || math.IsInf(scaled, 0) ||
				scaled < math.MinInt64 || scaled > math.MaxInt64 {
				return "", errors.New("evidence value cannot be quantized")
			}
			if err := binary.Write(&buffer, binary.LittleEndian, int64(scaled)); err != nil {
				return "", err
			}
		}
	}
	sum := sha256.Sum256(buffer.Bytes())
	return hex.EncodeToString(sum[:]), nil
}

func dominantEpisode(audits []auditRecord, profiles map[string]profile) (*episode, error) {
	byCamera := map[string][]auditRecord{}
	for _, row := range audits {
		byCamera[row.CameraID] = append(byCamera[row.CameraID], row)
	}
	var candidates []episode
	for camera, rows := range byCamera {
		p, ok := profiles[camera]
		if !ok {
			return nil, fmt.Errorf("missing episode profile for %s", camera)
		}
		sort.Slice(rows, func(i, j int) bool {
			if rows[i].instant.Equal(rows[j].instant) {
				return rows[i].FrameID < rows[j].FrameID
			}
			return rows[i].instant.Before(rows[j].instant)
		})
		for i := 1; i < len(rows); i++ {
			if !rows[i].instant.After(rows[i-1].instant) {
				return nil, errors.New("non-increasing episode timestamps")
			}
		}
		tau := rows[0].TemporalCorrelationSeconds
		for _, row := range rows {
			if row.TemporalCorrelationSeconds != tau {
				return nil, errors.New("camera temporal profile changed within archive")
			}
		}
		if len(rows) <= p.MinFrames {
			continue
		}
		inverseCorrelation, scales, times, y, err := episodeSystem(rows, p)
		if err != nil {
			return nil, err
		}
		for start := 0; start < len(rows); start++ {
			for end := start + p.MinFrames - 1; end < len(rows); end++ {
				length := end - start + 1
				if length >= len(rows) {
					continue
				}
				validGap := true
				for i := start + 1; i <= end; i++ {
					if rows[i].instant.Sub(rows[i-1].instant).Seconds() > p.MaxGapSeconds {
						validGap = false
					}
				}
				if !validGap {
					continue
				}
				candidate, err := solveWindow(rows, p, inverseCorrelation, scales, times, y, start, end)
				if err != nil {
					return nil, err
				}
				if candidate != nil {
					candidates = append(candidates, *candidate)
				}
			}
		}
	}
	if len(candidates) == 0 {
		return nil, nil
	}
	sort.Slice(candidates, func(i, j int) bool {
		a, b := candidates[i], candidates[j]
		aGLR, bGLR := selection9(a.rawGLR), selection9(b.rawGLR)
		if aGLR != bGLR {
			return aGLR > bGLR
		}
		aRate, bRate := selection9(a.rawArrheniusLower95), selection9(b.rawArrheniusLower95)
		if aRate != bRate {
			return aRate > bRate
		}
		aLoad, bLoad := selection9(a.rawLoadLower95), selection9(b.rawLoadLower95)
		if aLoad != bLoad {
			return aLoad > bLoad
		}
		if a.CameraID != b.CameraID {
			return a.CameraID < b.CameraID
		}
		if a.FromFrameID != b.FromFrameID {
			return a.FromFrameID < b.FromFrameID
		}
		return a.ToFrameID < b.ToFrameID
	})
	return &candidates[0], nil
}

func episodeSystem(rows []auditRecord, p profile) ([][]float64, []float64, []float64, []float64, error) {
	n := len(rows)
	size := 2 * n
	correlation := makeMatrix(size, size)
	scales := make([]float64, size)
	y := make([]float64, size)
	times := make([]float64, n)
	origin := rows[0].instant
	for i := range rows {
		times[i] = rows[i].instant.Sub(origin).Seconds() / 60.0
		y[2*i] = rows[i].ArrheniusRateMm2PerSecond
		y[2*i+1] = rows[i].IntegratedExcessCmm2
		scales[2*i] = rows[i].ArrheniusRateSigmaMm2PerSecond
		scales[2*i+1] = math.Max(rows[i].LoadSigmaCmm2, p.LoadSigmaFloor)
	}
	for i := range rows {
		for j := range rows {
			rho := math.Exp(-math.Abs(rows[j].instant.Sub(rows[i].instant).Seconds()) / rows[i].TemporalCorrelationSeconds)
			correlation[2*i][2*j] = rho
			correlation[2*i+1][2*j+1] = rho
			correlation[2*i][2*j+1] = p.CrossMetricCorrelation * rho
			correlation[2*j+1][2*i] = p.CrossMetricCorrelation * rho
		}
	}
	inverseCorrelation, err := invert(correlation)
	if err != nil {
		return nil, nil, nil, nil, fmt.Errorf("episode correlation: %w", err)
	}
	return inverseCorrelation, scales, times, y, nil
}

func solveWindow(rows []auditRecord, p profile, inverseCorrelation [][]float64, scales, times, y []float64, start, end int) (*episode, error) {
	n := len(rows)
	rowCount := 2 * n
	design := makeMatrix(rowCount, 6)
	for i := 0; i < n; i++ {
		inside := i >= start && i <= end
		design[2*i][0] = 1
		design[2*i][1] = times[i]
		design[2*i+1][2] = 1
		design[2*i+1][3] = times[i]
		if inside {
			design[2*i][4] = 1
			design[2*i+1][5] = 1
		}
	}
	normalizedY := make([]float64, rowCount)
	normalizedDesign := makeMatrix(rowCount, 6)
	columnScales := make([]float64, 6)
	for i := 0; i < rowCount; i++ {
		normalizedY[i] = y[i] / scales[i]
		for a := 0; a < 6; a++ {
			normalizedDesign[i][a] = design[i][a] / scales[i]
			columnScales[a] = math.Max(columnScales[a], math.Abs(normalizedDesign[i][a]))
		}
	}
	for a := 0; a < 6; a++ {
		if !finitePositive(columnScales[a]) {
			return nil, errors.New("degenerate episode design column")
		}
		for i := 0; i < rowCount; i++ {
			normalizedDesign[i][a] /= columnScales[a]
		}
	}
	normal := makeMatrix(6, 6)
	rhs := make([]float64, 6)
	for a := 0; a < 6; a++ {
		for b := 0; b < 6; b++ {
			for i := 0; i < rowCount; i++ {
				for j := 0; j < rowCount; j++ {
					normal[a][b] += normalizedDesign[i][a] * inverseCorrelation[i][j] * normalizedDesign[j][b]
				}
			}
		}
		for i := 0; i < rowCount; i++ {
			for j := 0; j < rowCount; j++ {
				rhs[a] += normalizedDesign[i][a] * inverseCorrelation[i][j] * normalizedY[j]
			}
		}
	}
	gammaCovariance, err := invert(normal)
	if err != nil {
		return nil, nil
	}
	gamma := multiplyVector(gammaCovariance, rhs)
	beta := make([]float64, 6)
	coefficientCovariance := makeMatrix(6, 6)
	for a := 0; a < 6; a++ {
		beta[a] = gamma[a] / columnScales[a]
		for b := 0; b < 6; b++ {
			coefficientCovariance[a][b] = gammaCovariance[a][b] / (columnScales[a] * columnScales[b])
		}
	}
	rateShift, loadShift := beta[4], beta[5]
	rateVar, loadVar := coefficientCovariance[4][4], coefficientCovariance[5][5]
	if !finitePositive(rateVar) || !finitePositive(loadVar) {
		return nil, errors.New("invalid episode shift covariance")
	}
	rateSigma, loadSigma := math.Sqrt(rateVar), math.Sqrt(loadVar)
	rateLower, loadLower := rateShift-1.96*rateSigma, loadShift-1.96*loadSigma
	shiftCov := [][]float64{
		{coefficientCovariance[4][4], coefficientCovariance[4][5]},
		{coefficientCovariance[5][4], coefficientCovariance[5][5]},
	}
	invShift, err := invert(shiftCov)
	if err != nil {
		return nil, fmt.Errorf("episode shift covariance: %w", err)
	}
	glr := rateShift*(invShift[0][0]*rateShift+invShift[0][1]*loadShift) +
		loadShift*(invShift[1][0]*rateShift+invShift[1][1]*loadShift)
	values := []float64{rateShift, loadShift, rateSigma, loadSigma, rateLower, loadLower, glr}
	for _, value := range values {
		if math.IsNaN(value) || math.IsInf(value, 0) {
			return nil, errors.New("non-finite episode result")
		}
	}
	if rateLower <= 0 || loadLower <= 0 || glr < p.MinGLR {
		return nil, nil
	}
	return &episode{
		CameraID:                        rows[start].CameraID,
		FromFrameID:                     rows[start].FrameID,
		ToFrameID:                       rows[end].FrameID,
		ObservationCount:                end - start + 1,
		ArrheniusShiftMm2PerSecond:      rateShift,
		ArrheniusShiftSigmaMm2PerSecond: rateSigma,
		ArrheniusLower95Mm2PerSecond:    rateLower,
		LoadShiftCmm2:                   loadShift,
		LoadShiftSigmaCmm2:              loadSigma,
		LoadLower95Cmm2:                 loadLower,
		GeneralizedLikelihoodRatio:      glr,
		rawArrheniusLower95:             rateLower,
		rawLoadLower95:                  loadLower,
		rawGLR:                          glr,
	}, nil
}

func makeMatrix(rows, columns int) [][]float64 {
	result := make([][]float64, rows)
	for i := range result {
		result[i] = make([]float64, columns)
	}
	return result
}

func invert(matrix [][]float64) ([][]float64, error) {
	n := len(matrix)
	if n == 0 {
		return nil, errors.New("empty matrix")
	}
	scale := 0.0
	for _, row := range matrix {
		if len(row) != n {
			return nil, errors.New("nonsquare matrix")
		}
		for _, value := range row {
			if math.IsNaN(value) || math.IsInf(value, 0) {
				return nil, errors.New("non-finite matrix")
			}
			scale = math.Max(scale, math.Abs(value))
		}
	}
	if scale == 0 {
		return nil, errors.New("zero matrix")
	}
	aug := makeMatrix(n, 2*n)
	for i := 0; i < n; i++ {
		copy(aug[i], matrix[i])
		aug[i][n+i] = 1
	}
	for column := 0; column < n; column++ {
		pivot := column
		for row := column + 1; row < n; row++ {
			if math.Abs(aug[row][column]) > math.Abs(aug[pivot][column]) {
				pivot = row
			}
		}
		if math.Abs(aug[pivot][column]) <= 1e-12*scale {
			return nil, errors.New("singular matrix")
		}
		aug[column], aug[pivot] = aug[pivot], aug[column]
		divisor := aug[column][column]
		for j := 0; j < 2*n; j++ {
			aug[column][j] /= divisor
		}
		for row := 0; row < n; row++ {
			if row == column {
				continue
			}
			factor := aug[row][column]
			for j := 0; j < 2*n; j++ {
				aug[row][j] -= factor * aug[column][j]
			}
		}
	}
	result := makeMatrix(n, n)
	for i := 0; i < n; i++ {
		copy(result[i], aug[i][n:])
	}
	return result, nil
}

func multiplyVector(matrix [][]float64, vector []float64) []float64 {
	result := make([]float64, len(matrix))
	for i := range matrix {
		for j := range vector {
			result[i] += matrix[i][j] * vector[j]
		}
	}
	return result
}

func atomicWrite(destination string, data []byte) error {
	parent := filepath.Dir(destination)
	if err := os.MkdirAll(parent, 0o755); err != nil {
		return err
	}
	file, err := os.CreateTemp(parent, filepath.Base(destination)+".tmp-")
	if err != nil {
		return err
	}
	name := file.Name()
	defer os.Remove(name)
	if _, err := file.Write(data); err != nil {
		file.Close()
		return err
	}
	if err := file.Sync(); err != nil {
		file.Close()
		return err
	}
	if err := file.Close(); err != nil {
		return err
	}
	if err := os.Rename(name, destination); err != nil {
		return err
	}
	return nil
}
GO
/app/bin/rebuild-analyzer
