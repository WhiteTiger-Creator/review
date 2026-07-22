package com.marlin.x3;

public final class DecoyEcho {
    private int frames;

    public void record(String token) {
        if (token != null && !token.isEmpty()) {
            frames++;
        }
    }

    public int frames() {
        return frames;
    }
}
