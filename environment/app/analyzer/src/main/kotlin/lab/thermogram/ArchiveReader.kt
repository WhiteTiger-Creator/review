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
            "SELECT frame_id,reference_id,pixel_index,expected_c FROM reference_samples " +
                "ORDER BY frame_id,reference_id,pixel_index;"
        val references = mutableMapOf<String, MutableList<ReferenceSample>>()
        ProcessRunner.run(
            listOf("sqlite3", "-readonly", "-separator", "\t", database.toString(), referenceSql),
        ).lineSequence().filter { it.isNotBlank() }.forEach { line ->
            val fields = line.split('\t')
            require(fields.size == 4) { "unexpected reference row" }
            references.getOrPut(fields[0]) { mutableListOf() } += ReferenceSample(
                referenceId = fields[1],
                pixelIndex = fields[2].toInt(),
                expectedC = fields[3].toDouble(),
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
