package com.culvert.lib;

public final class Laplacian {
    private Laplacian() {}

    public static double[][] fromAffinity(double[][] w) {
        int n = w.length;
        double[][] l = new double[n][n];
        double[] deg = new double[n];
        for (int i = 0; i < n; i++) {
            double sum = 0.0;
            for (int j = 0; j < n; j++) {
                sum += w[i][j];
            }
            deg[i] = sum;
        }
        for (int i = 0; i < n; i++) {
            for (int j = 0; j < n; j++) {
                if (i == j) {
                    l[i][j] = deg[i];
                } else {
                    l[i][j] = -w[i][j];
                }
            }
        }
        return l;
    }

    public static double[] smallestEigenvalues(double[][] lap, int count) {
        int n = lap.length;
        double[][] a = copy(lap);
        double[] values = new double[count];
        double[][] basis = identity(n);
        for (int k = 0; k < count; k++) {
            double[] v = basis[k].clone();
            for (int iter = 0; iter < 40; iter++) {
                double[] y = matVec(a, v);
                double norm = l2(y);
                if (norm < 1e-12) {
                    break;
                }
                for (int i = 0; i < n; i++) {
                    v[i] = y[i] / norm;
                }
            }
            values[k] = rayleigh(a, v);
            for (int i = 0; i < n; i++) {
                for (int j = 0; j < n; j++) {
                    a[i][j] -= values[k] * v[i] * v[j];
                }
            }
        }
        return values;
    }

    private static double[][] copy(double[][] src) {
        int n = src.length;
        double[][] out = new double[n][n];
        for (int i = 0; i < n; i++) {
            System.arraycopy(src[i], 0, out[i], 0, n);
        }
        return out;
    }

    private static double[][] identity(int n) {
        double[][] id = new double[n][n];
        for (int i = 0; i < n; i++) {
            id[i][i] = 1.0;
        }
        return id;
    }

    private static double[] matVec(double[][] m, double[] v) {
        int n = v.length;
        double[] out = new double[n];
        for (int i = 0; i < n; i++) {
            double sum = 0.0;
            for (int j = 0; j < n; j++) {
                sum += m[i][j] * v[j];
            }
            out[i] = sum;
        }
        return out;
    }

    private static double rayleigh(double[][] m, double[] v) {
        double[] mv = matVec(m, v);
        double num = 0.0;
        double den = 0.0;
        for (int i = 0; i < v.length; i++) {
            num += v[i] * mv[i];
            den += v[i] * v[i];
        }
        return num / den;
    }

    private static double l2(double[] v) {
        double sum = 0.0;
        for (double x : v) {
            sum += x * x;
        }
        return Math.sqrt(sum);
    }
}
