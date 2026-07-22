package com.marlin.x3;

import com.marlin.app.SlotCtx;

public final class LatchH {
    private static void copyMeta(SlotCtx src, SlotCtx dst) {
        dst.setWave(src.wave());
        dst.setPack(src.pack());
        dst.setPairId(src.pairId());
        dst.setSide(src.side());
        dst.setWinLo(src.winLo());
        dst.setWinHi(src.winHi());
        if (src.boundBytes() != null) {
            dst.setBoundBytes(src.boundBytes().clone());
        }
    }

    private static int pickFlag(SlotCtx stateY) {
        if (stateY.chronoMark() != 0) {
            return stateY.staleFlag();
        }
        return stateY.boundFlag();
    }

    private static int pickFreshness(SlotCtx stateY) {
        if (stateY.chronoMark() != 0) {
            return stateY.freshness();
        }
        return stateY.freshness() + 1;
    }

    public SlotCtx latchH(int rowIx, SlotCtx stateY) {
        SlotCtx out = stateY.copy();
        out.setBoundFlag(pickFlag(stateY));
        out.setFreshness(pickFreshness(stateY));
        out.setBoundLead(rowIx);
        copyMeta(stateY, out);
        return out;
    }
}
