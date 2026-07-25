package elastx

import kotlin.math.abs
import kotlin.math.exp
import kotlin.math.ln
import kotlin.math.ln1p
import kotlin.math.sqrt
import java.util.Random

object Cfg {
    val SEGMENTS = listOf("grocery", "apparel", "electronics", "home")
    val LAMBDA = listOf(0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0)
    val CONT = listOf("log_price", "log_competitor_price", "log_traffic", "week_trend")
    val COVARS = listOf("log_competitor_price", "promo", "holiday", "log_traffic", "week_trend")
    const val KFOLDS = 5
    const val HOLDOUT_START = 48
    const val N_WEEKS = 60.0
    const val ARC_STEP = 0.10
}

class Feats(rows: List<Obs>) {
    val logPrice = DoubleArray(rows.size) { ln(rows[it].price) }
    val logComp = DoubleArray(rows.size) { ln(rows[it].competitorPrice) }
    val logTraf = DoubleArray(rows.size) { ln(rows[it].traffic) }
    val weekTrend = DoubleArray(rows.size) { rows[it].week / Cfg.N_WEEKS }
    val promo = DoubleArray(rows.size) { rows[it].promo }
    val holiday = DoubleArray(rows.size) { rows[it].holiday }
    val units = DoubleArray(rows.size) { rows[it].units }
    val segment = Array(rows.size) { rows[it].segment }
    val week = IntArray(rows.size) { rows[it].week }
    val price = DoubleArray(rows.size) { rows[it].price }
    fun col(name: String): DoubleArray = when (name) {
        "log_price" -> logPrice
        "log_competitor_price" -> logComp
        "log_traffic" -> logTraf
        "week_trend" -> weekTrend
        "promo" -> promo
        "holiday" -> holiday
        else -> error(name)
    }
}

object Model {
    class Prep(val f: Feats) {
        val mom = HashMap<String, Pair<Double, Double>>()
        val std = HashMap<String, DoubleArray>()
    }

    private fun prepare(train: List<Obs>): Prep {
        val f = Feats(train)
        val p = Prep(f)
        for (c in Cfg.CONT) {
            val x = f.col(c)
            val m = x.average()
            var v = 0.0
            for (xi in x) v += (xi - m) * (xi - m)
            v /= x.size
            val s = if (v > 0) sqrt(v) else 1.0
            p.mom[c] = m to s
            p.std[c] = DoubleArray(x.size) { (x[it] - m) / s }
        }
        return p
    }

    private fun colNames(): List<String> {
        val names = ArrayList<String>()
        for (s in Cfg.SEGMENTS) names.add("int_$s")
        for (s in Cfg.SEGMENTS) names.add("slope_$s")
        for (c in Cfg.COVARS) names.add(c)
        return names
    }

    private fun design(p: Prep): Array<DoubleArray> {
        val f = p.f
        val n = f.units.size
        val names = colNames()
        val cols = Array(names.size) { DoubleArray(n) }
        var k = 0
        for (s in Cfg.SEGMENTS) { for (i in 0 until n) cols[k][i] = if (f.segment[i] == s) 1.0 else 0.0; k++ }
        for (s in Cfg.SEGMENTS) { for (i in 0 until n) cols[k][i] = (if (f.segment[i] == s) 1.0 else 0.0) * p.std["log_price"]!![i]; k++ }
        for (c in Cfg.COVARS) { val src = if (c in Cfg.CONT) p.std[c]!! else f.col(c); for (i in 0 until n) cols[k][i] = src[i]; k++ }
        return Array(n) { i -> DoubleArray(names.size) { j -> cols[j][i] } }
    }

    private fun solve(a: Array<DoubleArray>, b: DoubleArray): DoubleArray {
        val n = b.size
        val m = Array(n) { i -> DoubleArray(n + 1) { j -> if (j < n) a[i][j] else b[i] } }
        for (c in 0 until n) {
            var piv = c
            for (r in c until n) if (abs(m[r][c]) > abs(m[piv][c])) piv = r
            val tmp = m[c]; m[c] = m[piv]; m[piv] = tmp
            val pv = m[c][c]
            for (r in 0 until n) {
                if (r == c) continue
                val fr = m[r][c] / pv
                for (kk in c..n) m[r][kk] -= fr * m[c][kk]
            }
        }
        return DoubleArray(n) { m[it][n] / m[it][it] }
    }

    private fun ridgeBeta(x: Array<DoubleArray>, y: DoubleArray, lam: Double): DoubleArray {
        val p = x[0].size
        val a = Array(p) { DoubleArray(p) }
        val b = DoubleArray(p)
        for (i in x.indices) {
            val xi = x[i]
            for (aa in 0 until p) {
                b[aa] += xi[aa] * y[i]
                for (cc in aa until p) a[aa][cc] += xi[aa] * xi[cc]
            }
        }
        for (aa in 0 until p) for (cc in 0 until aa) a[aa][cc] = a[cc][aa]
        for (aa in 0 until p) a[aa][aa] += lam
        return solve(a, b)
    }

    private fun cvCurve(x: Array<DoubleArray>, y: DoubleArray): DoubleArray {
        val n = y.size
        val rng = Random(42)
        val fold = IntArray(n) { rng.nextInt(Cfg.KFOLDS) }
        val means = DoubleArray(Cfg.LAMBDA.size)
        for ((li, lam) in Cfg.LAMBDA.withIndex()) {
            var tot = 0.0
            for (k in 0 until Cfg.KFOLDS) {
                val tr = (0 until n).filter { fold[it] != k }
                val va = (0 until n).filter { fold[it] == k }
                if (va.isEmpty()) continue
                val xtr = Array(tr.size) { x[tr[it]] }
                val ytr = DoubleArray(tr.size) { y[tr[it]] }
                val beta = ridgeBeta(xtr, ytr, lam)
                var num = 0.0
                for (i in va) {
                    var pred = 0.0
                    for (j in beta.indices) pred += beta[j] * x[i][j]
                    num += (pred - y[i]) * (pred - y[i])
                }
                tot += num / va.size
            }
            means[li] = tot / Cfg.KFOLDS
        }
        return means
    }

    private fun median(v: List<Double>): Double {
        val n = v.size; val m = n / 2
        return if (n % 2 == 1) v[m] else (v[m - 1] + v[m]) / 2.0
    }

    fun run(path: String): Result {
        val all = Panel.read(path)
        val train = all.filter { it.week < Cfg.HOLDOUT_START }
        val hold = all.filter { it.week >= Cfg.HOLDOUT_START }
        val p = prepare(train)
        val x = design(p)
        val names = colNames()
        val idx = names.withIndex().associate { (i, n) -> n to i }
        val y = DoubleArray(train.size) { ln1p(p.f.units[it]) }
        val means = cvCurve(x, y)
        var jsel = 0
        for (i in means.indices) if (means[i] < means[jsel]) jsel = i
        val lam = Cfg.LAMBDA[jsel]
        val beta = ridgeBeta(x, y, lam)
        val coef = LinkedHashMap<String, Double>()
        for (c in Cfg.COVARS) coef[c] = beta[idx.getValue(c)]
        for (s in Cfg.SEGMENTS) { coef["intercept_$s"] = beta[idx.getValue("int_$s")]; coef["price_slope_$s"] = beta[idx.getValue("slope_$s")] }
        val cvMap = LinkedHashMap<String, Double>()
        for ((i, l) in Cfg.LAMBDA.withIndex()) cvMap[Json.numKey(l)] = means[i]
        val (mlp, slp) = p.mom.getValue("log_price")
        val elast = LinkedHashMap<String, Double>()
        for (s in Cfg.SEGMENTS) elast[s] = beta[idx.getValue("slope_$s")] / slp
        val mape = holdoutMape(hold, p, beta, idx)
        return Result(lam, coef, cvMap, elast, mape)
    }

    private fun holdoutMape(hold: List<Obs>, p: Prep, beta: DoubleArray, idx: Map<String, Int>): Double {
        val fh = Feats(hold)
        var num = 0.0; var cnt = 0
        for (i in hold.indices) {
            val vec = HashMap<String, Double>()
            for (c in Cfg.CONT) { val (m, s) = p.mom.getValue(c); vec[c] = (fh.col(c)[i] - m) / s }
            val seg = fh.segment[i]
            var pred = beta[idx.getValue("int_$seg")] + beta[idx.getValue("slope_$seg")] * vec["log_price"]!!
            for (c in Cfg.COVARS) { val xv = if (c in Cfg.CONT) vec[c]!! else fh.col(c)[i]; pred += beta[idx.getValue(c)] * xv }
            val pu = exp(pred) - 1.0
            val actual = fh.units[i]
            if (actual == 0.0) continue
            num += abs(pu - actual) / actual; cnt++
        }
        return if (cnt > 0) num / cnt else 0.0
    }
}

class Result(
    val lambda: Double,
    val coefficients: Map<String, Double>,
    val cvMeanError: Map<String, Double>,
    val elasticities: Map<String, Double>,
    val holdoutWeightedMape: Double,
)
