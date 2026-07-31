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
        val request = HttpRequest.newBuilder(URI.create(baseUrl + path)).timeout(Duration.ofSeconds(10)).GET().build()
        val response = client.send(request, HttpResponse.BodyHandlers.ofString())
        check(response.statusCode() == 200) { "API returned ${response.statusCode()} for $path" }
        return response.body()
    }
}
