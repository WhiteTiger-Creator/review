package com.culvert.flow;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Properties;

public final class Config {
    private final double sigma;
    private final int window;
    private final int minSamples;
    private final String profile;

    private Config(double sigma, int window, int minSamples, String profile) {
        this.sigma = sigma;
        this.window = window;
        this.minSamples = minSamples;
        this.profile = profile;
    }

    public static Config load(Path path) throws IOException {
        Properties props = new Properties();
        try (InputStream in = Files.newInputStream(path)) {
            props.load(in);
        }
        return new Config(
                Double.parseDouble(props.getProperty("sigma", "1.25")),
                Integer.parseInt(props.getProperty("policy.window", "8")),
                Integer.parseInt(props.getProperty("policy.min_samples", "3")),
                props.getProperty("output.profile", "culvert-inv-1"));
    }

    public double sigma() {
        return sigma;
    }

    public int window() {
        return window;
    }

    public int minSamples() {
        return minSamples;
    }

    public String profile() {
        return profile;
    }
}
