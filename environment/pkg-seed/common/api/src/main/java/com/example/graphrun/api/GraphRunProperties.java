package com.example.graphrun.api;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.nio.file.Path;

@ConfigurationProperties(prefix = "graphrun")
public class GraphRunProperties {

    private String policyPath = "/app/pkg/config/signing-policy.yaml";
    private String keyRoot = "/data/keys";
    private String runRoot = "/data/runs";
    private String output = "/output";
    private String mlflowCache = "/app/.cache/mlflow-release";
    private String repoRoot = "/app/pkg";

    public Path policyPath() {
        return Path.of(policyPath);
    }

    public void setPolicyPath(String policyPath) {
        this.policyPath = policyPath;
    }

    public Path keyRoot() {
        return Path.of(keyRoot);
    }

    public void setKeyRoot(String keyRoot) {
        this.keyRoot = keyRoot;
    }

    public Path runRoot() {
        return Path.of(runRoot);
    }

    public void setRunRoot(String runRoot) {
        this.runRoot = runRoot;
    }

    public Path output() {
        return Path.of(output);
    }

    public void setOutput(String output) {
        this.output = output;
    }

    public Path mlflowCache() {
        return Path.of(mlflowCache);
    }

    public void setMlflowCache(String mlflowCache) {
        this.mlflowCache = mlflowCache;
    }

    public Path repoRoot() {
        return Path.of(repoRoot);
    }

    public void setRepoRoot(String repoRoot) {
        this.repoRoot = repoRoot;
    }
}
