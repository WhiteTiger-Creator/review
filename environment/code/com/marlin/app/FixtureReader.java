package com.marlin.app;

import com.marlin.w9.MeshT;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

public final class FixtureReader {
    public static final class Rec {
        public final String id;
        public final int sa;
        public final int sb;
        public final int[] feats;
        public final byte[] hist;

        public Rec(String id, int sa, int sb, int[] feats, byte[] hist) {
            this.id = id;
            this.sa = sa;
            this.sb = sb;
            this.feats = feats;
            this.hist = hist;
        }
    }

    private final MeshT packer = new MeshT();

    public List<Rec> load(Path path) throws IOException {
        byte[] raw = Files.readAllBytes(path);
        ByteBuffer buf = ByteBuffer.wrap(raw).order(ByteOrder.LITTLE_ENDIAN);
        byte[] magic = new byte[4];
        buf.get(magic);
        if (!"TLF1".equals(new String(magic, StandardCharsets.US_ASCII))) {
            throw new IOException("bad magic");
        }
        int count = buf.getShort() & 0xFFFF;
        List<Rec> out = new ArrayList<>(count);
        for (int i = 0; i < count; i++) {
            int idLen = buf.get() & 0xFF;
            byte[] idb = new byte[idLen];
            buf.get(idb);
            String id = new String(idb, StandardCharsets.US_ASCII);
            int sa = buf.getShort() & 0xFFFF;
            int sb = buf.getShort() & 0xFFFF;
            int n = buf.get() & 0xFF;
            int[] feats = new int[n];
            for (int j = 0; j < n; j++) {
                feats[j] = buf.getShort();
            }
            int width = buf.get() & 0xFF;
            byte[] hist = new byte[width];
            buf.get(hist);
            out.add(new Rec(id, sa, sb, feats, hist));
        }
        return out;
    }

    public byte[] packHist(byte[] hist, int width) {
        return packer.meshT(hist, width);
    }
}
