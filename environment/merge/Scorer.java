package com.culvert.merge;

import com.culvert.io.Loader;

public final class Scorer {
    public record ScoreRow(String id, double value) {}

    public static ScoreRow[] score(Loader.Case input) {
        ScoreRow[] rows = new ScoreRow[input.nodes().length];
        for (int i = 0; i < input.nodes().length; i++) {
            double[] feat = input.nodes()[i].features();
            double sum = 0.0;
            for (double v : feat) {
                sum += v * v;
            }
            rows[i] = new ScoreRow(input.nodes()[i].id(), Math.sqrt(sum));
        }
        return rows;
    }
}
