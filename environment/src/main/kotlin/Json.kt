package elastx

object Json {
    fun numKey(x: Double): String = if (x == x.toLong().toDouble()) "${x.toLong()}.0" else x.toString()

    private fun num(x: Double): String = x.toString()

    fun write(r: Result): String {
        val sb = StringBuilder()
        sb.append("{\n")
        sb.append("  \"lambda\": ").append(num(r.lambda)).append(",\n")
        sb.append("  \"coefficients\": {\n")
        obj(sb, r.coefficients, 4)
        sb.append("  },\n")
        sb.append("  \"cv_mean_error\": {\n")
        obj(sb, r.cvMeanError, 4)
        sb.append("  },\n")
        sb.append("  \"elasticities\": {\n")
        obj(sb, r.elasticities, 4)
        sb.append("  },\n")
        sb.append("  \"holdout_weighted_mape\": ").append(num(r.holdoutWeightedMape)).append("\n")
        sb.append("}\n")
        return sb.toString()
    }

    private fun obj(sb: StringBuilder, m: Map<String, Double>, indent: Int) {
        val pad = " ".repeat(indent)
        val entries = m.entries.toList()
        for ((i, e) in entries.withIndex()) {
            sb.append(pad).append("\"").append(e.key).append("\": ").append(num(e.value))
            if (i < entries.size - 1) sb.append(",")
            sb.append("\n")
        }
    }
}
