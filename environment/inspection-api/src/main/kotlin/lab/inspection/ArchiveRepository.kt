package lab.inspection

import com.fasterxml.jackson.databind.JsonNode
import com.fasterxml.jackson.databind.ObjectMapper
import org.springframework.beans.factory.annotation.Value
import org.springframework.stereotype.Repository
import java.nio.charset.StandardCharsets

@Repository
class ArchiveRepository(
    private val mapper: ObjectMapper,
    @Value("\${lab.archive-path}") private val databasePath: String,
) {
    private val safeId = Regex("[A-Za-z0-9._-]+")

    fun findFrame(frameId: String): FrameMetadata? {
        require(safeId.matches(frameId)) { "invalid frame id" }
        val escaped = frameId.replace("'", "''")
        val sql = "SELECT frame_id AS frameId,camera_id AS cameraId,captured_at AS capturedAt,width,height FROM frames WHERE frame_id='$escaped';"
        val process = ProcessBuilder("sqlite3", "-readonly", "-json", databasePath, sql)
            .redirectErrorStream(true)
            .start()
        val output = process.inputStream.readAllBytes().toString(StandardCharsets.UTF_8)
        check(process.waitFor() == 0) { "sqlite lookup failed: $output" }
        val rows: JsonNode = mapper.readTree(output)
        if (!rows.isArray || rows.isEmpty) return null
        return mapper.treeToValue(rows[0], FrameMetadata::class.java)
    }
}
