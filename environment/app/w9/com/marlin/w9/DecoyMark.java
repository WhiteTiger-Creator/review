package com.marlin.w9;

import com.marlin.util.NibbleCore;

public final class DecoyMark {
    public String mark(byte[] buf) {
        if (buf == null || buf.length == 0) {
            return "00";
        }
        int acc = 0;
        for (byte b : buf) {
            acc = (acc + (b & 0xFF)) & 0xFF;
        }
        return NibbleCore.toHex(new byte[] {(byte) acc});
    }
}
