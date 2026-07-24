package com.culvert.flow;

import com.culvert.partition.Selector;
import com.culvert.io.Emitter;
import com.culvert.io.Loader;
import com.culvert.lib.Laplacian;
import com.culvert.lib.MatrixOps;
import com.culvert.stream.WindowPhase;
import com.culvert.merge.Fuser;
import com.culvert.merge.Scorer;

import java.nio.file.Path;
import java.util.Arrays;

public final class Flow {
    public static void run(Path casePath, Path configPath, Path outputPath) throws Exception {
        Config cfg = Config.load(configPath);
        Loader.Case input = Loader.load(casePath);
        double[][] raw = new double[input.nodes().length][];
        for (int i = 0; i < input.nodes().length; i++) {
            raw[i] = input.nodes()[i].features();
        }
        WindowPhase.State window = WindowPhase.phase_b(raw, cfg);
        double[][] normed = MatrixOps.applyWindow(raw, window.shift(), window.scale());
        double[][] affinity = MatrixOps.affinity(normed, cfg.sigma());
        double[][] lap = Laplacian.fromAffinity(affinity);
        int eigenCount = Math.min(4, input.nodes().length);
        double[] spectrum = Laplacian.smallestEigenvalues(lap, eigenCount);
        Selector.Pick pick = Selector.op_a(spectrum, window);
        int[] labels = assign(normed, pick.count());
        boolean marked = input.marks().stream().anyMatch(m -> m.contains("0417"));
        Fuser.PartitionView part = new Fuser.PartitionView(labels, marked);
        Scorer.ScoreRow[] scored = Scorer.score(input);
        Fuser.Result fused = Fuser.reconcile_c(part, new Fuser.ScoreView(scored));
        Emitter.write(outputPath, cfg.profile(), pick.count(), fused.rankOrder(), pick.span(),
                fused.groupDigest());
    }

    private static int[] assign(double[][] points, int k) {
        int n = points.length;
        int[] labels = new int[n];
        double[] means = new double[k];
        for (int i = 0; i < n; i++) {
            double coord = points[i][0];
            int bucket = (int) Math.floor((coord + 2.0) / 4.0 * k);
            if (bucket < 0) {
                bucket = 0;
            }
            if (bucket >= k) {
                bucket = k - 1;
            }
            labels[i] = bucket;
        }
        for (int c = 0; c < k; c++) {
            double sum = 0.0;
            int count = 0;
            for (int i = 0; i < n; i++) {
                if (labels[i] == c) {
                    sum += points[i][1];
                    count++;
                }
            }
            means[c] = count == 0 ? 0.0 : sum / count;
        }
        Arrays.sort(means);
        return labels;
    }

    public static void main(String[] args) throws Exception {
        if (args.length < 1) {
            System.err.println("usage: Flow <case.json>");
            System.exit(2);
        }
        Path casePath = Path.of(args[0]);
        Path config = Path.of("/app/environment/config/pipeline.properties");
        Path out = Path.of("/app/output/culvert_rank.yaml");
        run(casePath, config, out);
    }
}
