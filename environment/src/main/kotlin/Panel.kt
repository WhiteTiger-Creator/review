package elastx

import java.io.File

data class Obs(
    val segment: String,
    val week: Int,
    val price: Double,
    val units: Double,
    val competitorPrice: Double,
    val promo: Double,
    val holiday: Double,
    val traffic: Double,
)

object Panel {
    fun read(path: String): List<Obs> {
        val lines = File(path).readLines().filter { it.isNotBlank() }
        val header = lines.first().split(",").map { it.trim() }
        val ix = header.withIndex().associate { (i, n) -> n to i }
        val out = ArrayList<Obs>()
        for (line in lines.drop(1)) {
            val p = line.split(",")
            out.add(
                Obs(
                    segment = p[ix.getValue("segment")].trim(),
                    week = p[ix.getValue("week")].trim().toInt(),
                    price = p[ix.getValue("price")].trim().toDouble(),
                    units = p[ix.getValue("units")].trim().toDouble(),
                    competitorPrice = p[ix.getValue("competitor_price")].trim().toDouble(),
                    promo = p[ix.getValue("promo")].trim().toDouble(),
                    holiday = p[ix.getValue("holiday")].trim().toDouble(),
                    traffic = p[ix.getValue("traffic")].trim().toDouble(),
                )
            )
        }
        return out
    }
}
