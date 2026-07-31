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
        when (
            Regex("\"${Regex.escape(key)}\"\\s*:\\s*(true|false)")
                .find(body)?.groupValues?.get(1)
        ) {
            "true" -> true
            "false" -> false
            else -> error("missing boolean field $key")
        }

    fun intArray(body: String, key: String): List<Int> {
        val content = Regex("\"${Regex.escape(key)}\"\\s*:\\s*\\[([^]]*)]")
            .find(body)?.groupValues?.get(1) ?: error("missing array field $key")
        if (content.isBlank()) return emptyList()
        return content.split(',').map { token -> token.trim().toInt() }
    }

    fun numberArray(body: String, key: String): List<Double> {
        val content = Regex("\"${Regex.escape(key)}\"\\s*:\\s*\\[([^]]*)]")
            .find(body)?.groupValues?.get(1) ?: error("missing array field $key")
        if (content.isBlank()) return emptyList()
        return content.split(',').map { token -> token.trim().toDouble() }
    }
}
