package com.culvert.online;

public final class Regret {
    private Regret() {}

    public static double bound(int horizon, double loss) {
        return Math.sqrt(horizon) * loss;
    }
}
