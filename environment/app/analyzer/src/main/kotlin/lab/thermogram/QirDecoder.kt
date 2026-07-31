package lab.thermogram

import java.nio.ByteBuffer
import java.nio.ByteOrder

object QirDecoder {
    fun decode(blob: ByteArray, expectedWidth: Int, expectedHeight: Int): IntArray {
        require(blob.size >= 24 && blob.copyOfRange(0, 4).decodeToString() == "QIR2") { "invalid QIR payload" }
        val buffer = ByteBuffer.wrap(blob).order(ByteOrder.LITTLE_ENDIAN)
        val width = buffer.getShort(8).toInt()
        val height = buffer.getShort(10).toInt()
        require(width == expectedWidth && height == expectedHeight) { "QIR dimensions disagree with database" }

        // Preliminary importer: QIR2 packet reconstruction is not implemented yet.
        var predictor = buffer.getInt(12)
        val pixels = IntArray(width * height)
        buffer.position(24)
        for (index in pixels.indices) {
            if (buffer.remaining() >= 2) predictor += buffer.short.toInt()
            pixels[index] = predictor
        }
        return pixels
    }
}
