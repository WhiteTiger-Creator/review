package com.marlin.app;

import com.marlin.v4.DecoyFold;
import com.marlin.w9.DecoyMark;
import com.marlin.x3.DecoyEcho;
import com.marlin.util.NibbleCore;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class R2Accum {
    private final DecoyFold fold = new DecoyFold();
    private final DecoyMark marks = new DecoyMark();
    private final DecoyEcho echo = new DecoyEcho();

    private final List<Map<String, Object>> runs = new ArrayList<>();
    private final List<Map<String, Object>> waves = new ArrayList<>();
    private final List<Map<String, Object>> rows = new ArrayList<>();
    private final List<Map<String, Object>> surfaces = new ArrayList<>();
    private final Map<String, String> earlyDigests = new LinkedHashMap<>();
    private int sealSeq = 0;

    public void noteRun(String lane, String wave, String pack) {
        Map<String, Object> r = new LinkedHashMap<>();
        r.put("lane", lane);
        r.put("wave", wave);
        r.put("pack", pack);
        runs.add(r);
    }

    public void noteWave(String name, int winIx, String digestHex) {
        Map<String, Object> w = new LinkedHashMap<>();
        w.put("name", name);
        w.put("win_ix", winIx);
        w.put("digest_hex", digestHex);
        waves.add(w);
    }

    public String localDigest(FeatView feat) {
        return fold.preview(feat);
    }

    public void rememberDigest(String key, String digest) {
        earlyDigests.put(key, digest);
        echo.record(digest);
    }

    public void ingest(
            FixtureReader.Rec rec,
            String side,
            EpochStride.Window win,
            byte[] coord,
            SlotCtx sealed,
            String pack,
            String wave,
            boolean occlude
    ) {
        String mark = marks.mark(coord);
        echo.record(mark);
        int term = coord.length == 0 ? 0 : NibbleCore.lo(coord[coord.length - 1] & 0xFF);
        int slotOk = occlude ? 0 : sealed.boundFlag();
        String dedupe = rec.id + "|" + side + "|" + NibbleCore.toHex(coord);
        for (Map<String, Object> existing : rows) {
            if (dedupe.equals(existing.get("_dedupe"))) {
                return;
            }
        }
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("_dedupe", dedupe);
        row.put("pair_id", rec.id);
        row.put("side", side);
        row.put("win_lo", win.lo);
        row.put("win_hi", win.hi);
        row.put("site_nib", term);
        row.put("slot_ok", slotOk);
        row.put("coord_hex", NibbleCore.toHex(coord));
        row.put("pack", pack);
        rows.add(row);

        sealSeq += 1;
        int histLo = coord.length == 0 ? 0 : NibbleCore.lo(coord[0] & 0xFF);
        int histHi = coord.length == 0 ? 0 : NibbleCore.hi(coord[0] & 0xFF);
        Map<String, Object> surf = new LinkedHashMap<>();
        surf.put("pack", pack);
        surf.put("wave", wave);
        surf.put("hist_lo", histLo);
        surf.put("hist_hi", histHi);
        surf.put("delta", histHi - histLo);
        surf.put("seal_seq", sealSeq);
        surf.put("freshness", sealed.freshness());
        surfaces.add(surf);
    }

    public Map<String, Object> snapshot() {
        List<Map<String, Object>> publicRows = new ArrayList<>();
        for (Map<String, Object> row : rows) {
            Map<String, Object> copy = new LinkedHashMap<>(row);
            copy.remove("_dedupe");
            publicRows.add(copy);
        }
        Map<String, Object> root = new LinkedHashMap<>();
        root.put("runs", rootList(runs));
        root.put("waves", rootList(waves));
        root.put("rank_rows", publicRows);
        root.put("shift_surfaces", rootList(surfaces));
        return root;
    }

    private static List<Map<String, Object>> rootList(List<Map<String, Object>> src) {
        List<Map<String, Object>> out = new ArrayList<>();
        for (Map<String, Object> m : src) {
            out.add(new LinkedHashMap<>(m));
        }
        return out;
    }
}
