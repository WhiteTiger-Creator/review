package com.culvert.lib;

public final class MatrixOps {
    private MatrixOps() {}

    public static double[][] affinity(double[][] points, double sigma) {
        int n = points.length;
        double[][] w = new double[n][n];
        double denom = 2.0 * sigma * sigma;
        for (int i = 0; i < n; i++) {
            w[i][i] = 0.0;
            for (int j = i + 1; j < n; j++) {
                double dist = 0.0;
                for (int d = 0; d < points[i].length; d++) {
                    double delta = points[i][d] - points[j][d];
                    dist += delta * delta;
                }
                double val = Math.exp(-dist / denom);
                w[i][j] = val;
                w[j][i] = val;
            }
        }
        return w;
    }

    public static double[][] applyWindow(double[][] points, double[] shift, double[] scale) {
        int n = points.length;
        int dim = points[0].length;
        double[][] out = new double[n][dim];
        for (int i = 0; i < n; i++) {
            for (int d = 0; d < dim; d++) {
                out[i][d] = (points[i][d] - shift[d]) / scale[d];
            }
        }
        return out;
    }
}
