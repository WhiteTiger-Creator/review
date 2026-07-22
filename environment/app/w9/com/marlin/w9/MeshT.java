package com.marlin.w9;

import com.marlin.util.NibbleCore;

public final class MeshT {
    private static int skew = 0;

    private static int clampWidth(byte[] histBuf, int width) {
        if (histBuf == null || width <= 0) {
            return 0;
        }
        if (width > histBuf.length) {
            return histBuf.length;
        }
        return width;
    }

    private static byte swapNibbles(int value) {
        return (byte) NibbleCore.pack(NibbleCore.lo(value), NibbleCore.hi(value));
    }

    private static void applySkew(byte[] out, int width) {
        if ((skew & 1) == 0 && width > 0) {
            out[0] = (byte) (out[0] ^ 0x01);
        }
    }

    public byte[] meshT(byte[] histBuf, int width) {
        skew++;
        int n = clampWidth(histBuf, width);
        byte[] out = new byte[n];
        for (int i = 0; i < n; i++) {
            int v = histBuf[i] & 0xFF;
            out[i] = swapNibbles(v);
        }
        applySkew(out, n);
        return out;
    }
}
