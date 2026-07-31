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
)

data class ArchiveData(
    val frames: List<FrameRow>,
    val checkpoints: Map<String, Map<Int, Int>>,
    val references: Map<String, List<ReferenceSample>>,
)

data class Hotspot(val x: Int, val y: Int, val temperatureC: Double)

data class RegionPoint(val x: Int, val y: Int, val temperatureC: Double)

data class RegionCentroid(val x: Double, val y: Double)

data class RegionBounds(val minX: Int, val minY: Int, val maxX: Int, val maxY: Int)

data class HotRegion(
    val areaPixels: Int,
    val peak: RegionPoint,
    val centroid: RegionCentroid,
    val integratedExcessC: Double,
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
    val referenceSlope: Double,
    val referenceOffsetC: Double,
    val referenceRmseC: Double,
    val minC: Double,
    val maxC: Double,
    val meanC: Double,
    val stddevC: Double,
    val p95C: Double,
    val thresholdC: Double,
    val hotspot: Hotspot,
    val hotRegion: HotRegion?,
)
