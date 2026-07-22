package com.marlin.app;

import com.marlin.x3.LatchH;
import com.marlin.util.JsonEmit;
import com.marlin.util.NibbleCore;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public final class N6Pass {
    private final Path envRoot;
    private final Path outPath;
    private final FixtureReader reader = new FixtureReader();
    private final LatchH sealer = new LatchH();

    public N6Pass(Path envRoot, Path outPath) {
        this.envRoot = envRoot;
        this.outPath = outPath;
    }

    public void chrono() throws Exception {
        EpochStride stride = loadStride();
        R2Accum accum = new R2Accum();
        String[] packs = new String[] {"a2_blob_01", "b7_byte_02", "c8_ln_03"};
        for (String pack : packs) {
            List<FixtureReader.Rec> recs = reader.load(envRoot.resolve("packs").resolve(pack + ".tlf"));
            runWave(accum, stride, recs, pack, "shuffle", false, false);
            runWave(accum, stride, recs, pack, "chrono", true, true);
        }
        for (String pack : packs) {
            List<FixtureReader.Rec> recs = reader.load(envRoot.resolve("packs").resolve(pack + ".tlf"));
            runWave(accum, stride, recs, pack, "chrono", true, true);
        }
        JsonEmit.writeSheet(outPath, accum.snapshot());
    }

    private void runWave(
            R2Accum accum,
            EpochStride stride,
            List<FixtureReader.Rec> recs,
            String pack,
            String wave,
            boolean chrono,
            boolean ingestRows
    ) {
        accum.noteRun("chrono", wave, pack);
        int winIx = 0;
        String digest = "0000";
        int freshCursor = 0;
        for (FixtureReader.Rec rec : recs) {
            FeatView feat = new FeatView(rec.feats);
            String d = accum.localDigest(feat);
            accum.rememberDigest(rec.id + ":fold", d);
            digest = d;
            freshCursor = processSide(
                    accum, stride, rec, "a", pack, wave, chrono, true, freshCursor, ingestRows);
            freshCursor = processSide(
                    accum, stride, rec, "b", pack, wave, chrono, false, freshCursor, ingestRows);
            winIx = stride.pick(feat, true).ix;
        }
        accum.noteWave(wave, winIx, digest);
    }

    private int processSide(
            R2Accum accum,
            EpochStride stride,
            FixtureReader.Rec rec,
            String side,
            String pack,
            String wave,
            boolean chrono,
            boolean ascending,
            int freshCursor,
            boolean ingestRows
    ) {
        FeatView feat = new FeatView(rec.feats);
        EpochStride.Window win = stride.pick(feat, ascending);
        EpochStride.Window other = stride.pick(feat, !ascending);
        boolean occlude = win.ix != other.ix;

        byte[] coord = reader.packHist(rec.hist, rec.hist.length);
        int rowIx = "a".equals(side) ? rec.sa : rec.sb;
        int packedBit = NibbleCore.hi(coord[0] & 0xFF) & 1;

        SlotCtx state = new SlotCtx();
        state.setPairId(rec.id);
        state.setSide(side);
        state.setWave(wave);
        state.setPack(pack);
        state.setWinLo(win.lo);
        state.setWinHi(win.hi);
        state.setBoundBytes(coord);
        state.setChronoMark(chrono ? 1 : 0);
        state.setBoundFlag(packedBit);
        state.setStaleFlag(1 - packedBit);
        state.setFreshness(freshCursor);

        SlotCtx sealed = sealer.latchH(rowIx, state);
        if (ingestRows) {
            accum.ingest(rec, side, win, coord, sealed, pack, wave, occlude);
        }
        return sealed.freshness();
    }

    private EpochStride loadStride() throws Exception {
        Path meta = envRoot.resolve("data").resolve("window_meta.json");
        String text = Files.readString(meta, StandardCharsets.UTF_8);
        List<EpochStride.Window> windows = new ArrayList<>();
        Pattern p = Pattern.compile(
                "\\{\\s*\"ix\"\\s*:\\s*(\\d+)\\s*,\\s*\"lo\"\\s*:\\s*(\\d+)\\s*,\\s*\"hi\"\\s*:\\s*(\\d+)\\s*\\}"
        );
        Matcher m = p.matcher(text);
        while (m.find()) {
            windows.add(new EpochStride.Window(
                    Integer.parseInt(m.group(1)),
                    Integer.parseInt(m.group(2)),
                    Integer.parseInt(m.group(3))
            ));
        }
        return new EpochStride(windows);
    }
}
