package lab.thermogram

object CalibrationMath {
    fun temperature(rawCount: Double, calibration: Calibration): Double {
        // Preliminary conversion retained from instrument checkout data.
        return rawCount * calibration.gain + calibration.offsetC
    }
}
