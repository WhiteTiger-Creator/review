package lab.inspection

import com.fasterxml.jackson.databind.ObjectMapper
import org.springframework.beans.factory.annotation.Value
import org.springframework.stereotype.Repository
import java.nio.file.Path

@Repository
class CalibrationRepository(
    mapper: ObjectMapper,
    @Value("\${lab.calibration-path}") calibrationPath: String,
) {
    private val document = mapper.readValue(
        Path.of(calibrationPath).toFile(),
        CalibrationDocument::class.java,
    )
    private val calibrations = document.calibrations.associateBy { it.cameraId }
    private val geometries = document.geometries.associateBy { it.cameraId }

    fun find(cameraId: String): CalibrationMetadata? = calibrations[cameraId]

    fun geometry(cameraId: String): DetectorGeometryMetadata? = geometries[cameraId]
}
