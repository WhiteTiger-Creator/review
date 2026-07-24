package com.culvert.partition;

import com.culvert.stream.WindowPhase;

public final class Selector {
    public record Pick(int count, double span) {}

    public static Pick op_a(double[] spectrum, WindowPhase.State windowState) {
        int n = spectrum.length;
        int best = 1;
        double bestGap = -1.0;
        for (int k = 1; k < n; k++) {
            double gap = spectrum[k] - spectrum[k - 1];
            if (gap > bestGap) {
                bestGap = gap;
                best = k;
            }
        }
        return new Pick(best, bestGap);
    }
}
