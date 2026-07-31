package lab.inspection

import org.springframework.http.ResponseEntity
import org.springframework.web.bind.annotation.GetMapping
import org.springframework.web.bind.annotation.PathVariable
import org.springframework.web.bind.annotation.RestController

@RestController
class InspectionController(
    private val archive: ArchiveRepository,
    private val calibrations: CalibrationRepository,
) {
    @GetMapping("/health")
    fun health(): Map<String, String> = mapOf("status" to "ok")

    @GetMapping("/api/frames/{frameId}")
    fun frame(@PathVariable frameId: String): ResponseEntity<FrameMetadata> =
        archive.findFrame(frameId)?.let { ResponseEntity.ok(it) } ?: ResponseEntity.notFound().build()

    @GetMapping("/api/cameras/{cameraId}/calibration")
    fun calibration(@PathVariable cameraId: String): ResponseEntity<CalibrationMetadata> =
        calibrations.find(cameraId)?.let { ResponseEntity.ok(it) } ?: ResponseEntity.notFound().build()

    @GetMapping("/api/cameras/{cameraId}/geometry")
    fun geometry(@PathVariable cameraId: String): ResponseEntity<DetectorGeometryMetadata> =
        calibrations.geometry(cameraId)?.let { ResponseEntity.ok(it) } ?: ResponseEntity.notFound().build()
}
