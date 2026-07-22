package com.marlin.v4;

import com.marlin.app.FeatView;
import com.marlin.util.IntBiConsumer;

public final class CullY {
    private static boolean inClosed(int value, int lo, int hi) {
        if (hi < lo) {
            return false;
        }
        return value >= lo && value <= hi;
    }

    private static boolean featReady(FeatView feat) {
        return feat != null && feat.len() > 0;
    }

    public int previewHits(int winStart, int winEnd, FeatView feat) {
        if (!featReady(feat)) {
            return 0;
        }
        int hits = 0;
        for (int i = 0; i < feat.len(); i++) {
            if (inClosed(feat.at(i), winStart, winEnd)) {
                hits++;
            }
        }
        return hits;
    }

    public int cullY(int winStart, int winEnd, FeatView feat, IntBiConsumer emit) {
        int count = 0;
        if (!featReady(feat)) {
            return 0;
        }
        for (int i = 0; i < feat.len(); i++) {
            int s = feat.at(i);
            if (inClosed(s, winStart, winEnd)) {
                emit.accept(i, s);
                count++;
            }
        }
        return count;
    }
}
