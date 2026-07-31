package lab.inspection

data class FrameMetadata(
    val frameId: String,
    val cameraId: String,
    val capturedAt: String,
    val width: Int,
    val height: Int,
)

data class CalibrationMetadata(
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

data class DetectorGeometryMetadata(
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

data class CalibrationDocument(
    val calibrations: List<CalibrationMetadata>,
    val geometries: List<DetectorGeometryMetadata>,
)
