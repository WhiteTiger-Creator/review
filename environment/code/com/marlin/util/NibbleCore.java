package com.marlin.util;

public final class NibbleCore {
    private NibbleCore() {}

    public static int lo(int value) {
        return value & 0x0F;
    }

    public static int hi(int value) {
        return (value >> 4) & 0x0F;
    }

    public static int pack(int high, int low) {
        return ((high & 0x0F) << 4) | (low & 0x0F);
    }

    public static String toHex(byte[] raw) {
        if (raw == null || raw.length == 0) {
            return "";
        }
        StringBuilder sb = new StringBuilder(raw.length * 2);
        for (byte b : raw) {
            sb.append(String.format("%02x", b & 0xFF));
        }
        return sb.toString();
    }
}
