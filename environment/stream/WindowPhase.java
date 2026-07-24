package com.culvert.stream;

import com.culvert.flow.Config;

public final class WindowPhase {
  public record State(double[] shift, double[] scale, int bucket) {}

  public static State phase_b(double[][] samples, Config policy) {
    int dim = samples[0].length;
    double[] shift = new double[dim];
    double[] scale = new double[dim];
    for (int d = 0; d < dim; d++) {
      shift[d] = 0.0;
      scale[d] = 1.0;
    }
    return new State(shift, scale, 0);
  }
}
