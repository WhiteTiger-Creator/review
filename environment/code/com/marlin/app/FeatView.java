package com.marlin.app;

public final class FeatView {
    private final int[] vals;

    public FeatView(int[] vals) {
        this.vals = vals == null ? new int[0] : vals.clone();
    }

    public int len() {
        return vals.length;
    }

    public int at(int ix) {
        return vals[ix];
    }
}
