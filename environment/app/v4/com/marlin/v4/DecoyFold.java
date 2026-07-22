package com.marlin.v4;

import com.marlin.app.FeatView;
import com.marlin.util.NibbleCore;

public final class DecoyFold {
    public String preview(FeatView feat) {
        if (feat == null || feat.len() == 0) {
            return "0000";
        }
        int acc = 0;
        for (int i = 0; i < feat.len(); i++) {
            acc = (acc * 33 + feat.at(i)) & 0xFFFF;
        }
        byte[] raw = new byte[] {(byte) ((acc >> 8) & 0xFF), (byte) (acc & 0xFF)};
        return NibbleCore.toHex(raw);
    }
}
