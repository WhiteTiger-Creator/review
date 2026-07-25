package elastx

import kotlin.math.abs
import kotlin.math.exp
import kotlin.math.ln
import kotlin.math.ln1p
import kotlin.math.pow
import kotlin.math.sqrt

object Cfg {
    val SEGMENTS = listOf("grocery", "apparel", "electronics", "home")
    const val OFFSET = 8.0
    const val RECENCY = 0.97
    val LAMBDA = listOf(0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0)
    val WINSOR = mapOf(
        "log_price" to (2.5 to 97.5),
        "log_competitor_price" to (2.5 to 97.5),
        "log_traffic" to (5.0 to 100.0),
    )
    val CONT = listOf("log_price", "log_competitor_price", "log_traffic", "week_trend")
    val COVARS = listOf("log_competitor_price", "promo", "holiday", "log_traffic", "week_trend")
    const val KFOLDS = 5
    const val EMBARGO = 3
    const val HOLDOUT_START = 48
    const val N_WEEKS = 60.0
    const val ARC_STEP = 0.10
    const val MAPE_FLOOR = 5.0
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
    private fun wpercentile(x: DoubleArray, w: DoubleArray, q: Double): Double {
        val idx = x.indices.sortedBy { x[it] }
        val xs = DoubleArray(idx.size) { x[idx[it]] }
        val ws = DoubleArray(idx.size) { w[idx[it]] }
        val tot = ws.sum()
        val cum = DoubleArray(ws.size)
        var c = 0.0
        for (i in ws.indices) { cum[i] = (c + ws[i] / 2.0) / tot; c += ws[i] }
        val t = q / 100.0
        if (t <= cum.first()) return xs.first()
        if (t >= cum.last()) return xs.last()
        for (i in 1 until cum.size) {
            if (t <= cum[i]) {
                val f = if (cum[i] != cum[i - 1]) (t - cum[i - 1]) / (cum[i] - cum[i - 1]) else 0.0
                return xs[i - 1] + f * (xs[i] - xs[i - 1])
            }
        }
        return xs.last()
    }

    private fun wmeanWstd(x: DoubleArray, w: DoubleArray): Pair<Double, Double> {
        val sw = w.sum()
        var m = 0.0
        for (i in x.indices) m += w[i] * x[i]
        m /= sw
        var v = 0.0
        for (i in x.indices) v += w[i] * (x[i] - m) * (x[i] - m)
        v /= sw
        return m to if (v > 0) sqrt(v) else 1.0
    }

    class Prep(val f: Feats) {
        lateinit var w: DoubleArray
        val lim = HashMap<String, Pair<Double, Double>>()
        val mom = HashMap<String, Pair<Double, Double>>()
        val std = HashMap<String, DoubleArray>()
    }

    private fun prepare(train: List<Obs>): Prep {
        val f = Feats(train)
        val n = train.size
        val wmax = f.week.max()
        val w = DoubleArray(n) {
            val rec = Cfg.RECENCY.pow((wmax - f.week[it]).toDouble())
            val vol = ln1p(f.units[it])
            val wi = rec * vol
            if (wi > 1e-6) wi else 1e-6
        }
        val sw = w.sum()
        for (i in 0 until n) w[i] = w[i] * n / sw
        val p = Prep(f)
        p.w = w
        val cont = HashMap<String, DoubleArray>()
        for (c in listOf("log_price", "log_competitor_price", "log_traffic")) {
            val src = f.col(c)
            val lo = wpercentile(src, w, Cfg.WINSOR.getValue(c).first)
            val hi = wpercentile(src, w, Cfg.WINSOR.getValue(c).second)
            p.lim[c] = lo to hi
            cont[c] = DoubleArray(n) { minOf(maxOf(src[it], lo), hi) }
        }
        cont["week_trend"] = f.weekTrend.copyOf()
        for (c in Cfg.CONT) {
            val (m, s) = wmeanWstd(cont[c]!!, w)
            p.mom[c] = m to s
            p.std[c] = DoubleArray(n) { (cont[c]!![it] - m) / s }
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

    private fun ridgeBeta(x: Array<DoubleArray>, y: DoubleArray, w: DoubleArray, lam: Double, drop: Set<Int> = emptySet()): DoubleArray {
        val p = x[0].size
        val a = Array(p) { DoubleArray(p) }
        val b = DoubleArray(p)
        for (i in x.indices) {
            val wi = w[i]; val xi = x[i]
            for (aa in 0 until p) {
                val xa = if (aa in drop) 0.0 else xi[aa]
                b[aa] += wi * xa * y[i]
                for (cc in aa until p) {
                    val xc = if (cc in drop) 0.0 else xi[cc]
                    a[aa][cc] += wi * xa * xc
                }
            }
        }
        for (aa in 0 until p) for (cc in 0 until aa) a[aa][cc] = a[cc][aa]
        for (aa in 0 until p) {
            a[aa][aa] += lam
            if (aa in drop) {
                for (cc in 0 until p) { a[aa][cc] = 0.0; a[cc][aa] = 0.0 }
                a[aa][aa] = 1.0; b[aa] = 0.0
            }
        }
        return solve(a, b)
    }

    private fun cvCurve(x: Array<DoubleArray>, y: DoubleArray, w: DoubleArray, week: IntArray): Pair<DoubleArray, DoubleArray> {
        val n = y.size
        val uw = week.toSortedSet().toList()
        val K = Cfg.KFOLDS
        val q = uw.size / K; val rem = uw.size % K
        val blocks = ArrayList<List<Int>>()
        var start = 0
        for (k in 0 until K) { val size = q + if (k < rem) 1 else 0; blocks.add(uw.subList(start, start + size)); start += size }
        val folds = ArrayList<Pair<IntArray, IntArray>>()
        for (k in 0 until K) {
            val valW = blocks[k].toSet()
            val lo = blocks[k].min(); val hi = blocks[k].max()
            val emb = HashSet<Int>()
            for (e in 1..Cfg.EMBARGO) { emb.add(lo - e); emb.add(hi + e) }
            val tr = ArrayList<Int>(); val va = ArrayList<Int>()
            for (i in 0 until n) {
                if (week[i] in valW) va.add(i)
                else if (week[i] !in emb) tr.add(i)
            }
            folds.add(tr.toIntArray() to va.toIntArray())
        }
        val means = DoubleArray(Cfg.LAMBDA.size)
        val ses = DoubleArray(Cfg.LAMBDA.size)
        for ((li, lam) in Cfg.LAMBDA.withIndex()) {
            val errs = DoubleArray(K)
            for ((fi, fold) in folds.withIndex()) {
                val (tr, va) = fold
                val xtr = Array(tr.size) { x[tr[it]] }
                val ytr = DoubleArray(tr.size) { y[tr[it]] }
                val wtr = DoubleArray(tr.size) { w[tr[it]] }
                val beta = ridgeBeta(xtr, ytr, wtr, lam)
                var num = 0.0; var den = 0.0
                for (i in va) {
                    var pred = 0.0
                    for (j in beta.indices) pred += beta[j] * x[i][j]
                    num += w[i] * (pred - y[i]) * (pred - y[i]); den += w[i]
                }
                errs[fi] = num / den
            }
            val m = errs.sum() / K
            var v = 0.0; for (e in errs) v += (e - m) * (e - m); v /= (K - 1)
            means[li] = m; ses[li] = sqrt(v) / sqrt(K.toDouble())
        }
        return means to ses
    }

    private fun selectLambda(means: DoubleArray, ses: DoubleArray): Int {
        var j = 0
        for (i in means.indices) if (means[i] < means[j]) j = i
        val thr = means[j] + ses[j]
        var sel = 0
        for (i in means.indices) if (means[i] <= thr) sel = i
        return sel
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
        val y = DoubleArray(train.size) { ln(p.f.units[it] + Cfg.OFFSET) }
        val (means, ses) = cvCurve(x, y, p.w, p.f.week)
        val jsel = selectLambda(means, ses)
        val lam = Cfg.LAMBDA[jsel]
        var beta = ridgeBeta(x, y, p.w, lam)
        val drop = HashSet<Int>()
        for (s in Cfg.SEGMENTS) if (beta[idx.getValue("slope_$s")] > 0) drop.add(idx.getValue("slope_$s"))
        if (drop.isNotEmpty()) beta = ridgeBeta(x, y, p.w, lam, drop)
        val coef = LinkedHashMap<String, Double>()
        for (c in Cfg.COVARS) coef[c] = beta[idx.getValue(c)]
        for (s in Cfg.SEGMENTS) { coef["intercept_$s"] = beta[idx.getValue("int_$s")]; coef["price_slope_$s"] = beta[idx.getValue("slope_$s")] }
        val cvMap = LinkedHashMap<String, Double>()
        for ((i, l) in Cfg.LAMBDA.withIndex()) cvMap[Json.numKey(l)] = means[i]
        val (mlp, slp) = p.mom.getValue("log_price")
        val (loLp, hiLp) = p.lim.getValue("log_price")
        val elast = LinkedHashMap<String, Double>()
        for (s in Cfg.SEGMENTS) {
            val prices = train.filter { it.segment == s }.map { it.price }.sorted()
            val pref = median(prices)
            val sl = beta[idx.getValue("slope_$s")]
            val it0 = beta[idx.getValue("int_$s")]
            fun qAt(price: Double): Double {
                val z = (minOf(maxOf(ln(price), loLp), hiLp) - mlp) / slp
                return exp(it0 + sl * z) - Cfg.OFFSET
            }
            val p1 = pref; val p2 = pref * (1 + Cfg.ARC_STEP)
            val q1 = qAt(p1); val q2 = qAt(p2)
            elast[s] = ((q2 - q1) / ((q1 + q2) / 2)) / ((p2 - p1) / ((p1 + p2) / 2))
        }
        val mape = holdoutMape(hold, p, beta, idx)
        return Result(lam, coef, cvMap, elast, mape)
    }

    private fun holdoutMape(hold: List<Obs>, p: Prep, beta: DoubleArray, idx: Map<String, Int>): Double {
        val fh = Feats(hold)
        var num = 0.0; var den = 0.0
        for (i in hold.indices) {
            val vec = HashMap<String, Double>()
            for (c in listOf("log_price", "log_competitor_price", "log_traffic")) {
                val (lo, hi) = p.lim.getValue(c)
                val v = minOf(maxOf(fh.col(c)[i], lo), hi)
                val (m, s) = p.mom.getValue(c); vec[c] = (v - m) / s
            }
            val (mw, sw) = p.mom.getValue("week_trend"); vec["week_trend"] = (fh.weekTrend[i] - mw) / sw
            val seg = fh.segment[i]
            var pred = beta[idx.getValue("int_$seg")] + beta[idx.getValue("slope_$seg")] * vec["log_price"]!!
            for (c in Cfg.COVARS) { val xv = if (c in Cfg.CONT) vec[c]!! else fh.col(c)[i]; pred += beta[idx.getValue(c)] * xv }
            val pu = exp(pred) - Cfg.OFFSET
            val actual = fh.units[i]
            val denom = maxOf(actual, Cfg.MAPE_FLOOR)
            val ape = abs(pu - actual) / denom
            num += actual * ape; den += actual
        }
        return if (den > 0) num / den else 0.0
    }
}

class Result(
    val lambda: Double,
    val coefficients: Map<String, Double>,
    val cvMeanError: Map<String, Double>,
    val elasticities: Map<String, Double>,
    val holdoutWeightedMape: Double,
)
