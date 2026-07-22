package com.marlin.tools;

import com.marlin.app.N6Pass;

import java.nio.file.Path;

public final class CliEntry {
    public static void main(String[] args) throws Exception {
        String lane = "chrono";
        for (int i = 0; i < args.length; i++) {
            if ("--lane".equals(args[i]) && i + 1 < args.length) {
                lane = args[i + 1];
            }
        }
        Path env = Path.of("/app/environment");
        Path out = Path.of("/app/output/gate_ledger.json");
        if (!"chrono".equals(lane)) {
            throw new IllegalArgumentException("unsupported lane: " + lane);
        }
        new N6Pass(env, out).chrono();
    }
}
