package com.culvert.cluster;

public final class Reducer {
    private Reducer() {}

    public static double[][] project(double[][] points, int dims) {
        int n = points.length;
        int d = Math.min(dims, points[0].length);
        double[][] out = new double[n][d];
        for (int i = 0; i < n; i++) {
            System.arraycopy(points[i], 0, out[i], 0, d);
        }
        return out;
    }
}
