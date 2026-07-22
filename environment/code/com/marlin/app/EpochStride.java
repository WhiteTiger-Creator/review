package com.marlin.app;

import com.marlin.v4.CullY;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

public final class EpochStride {
    public static final class Window {
        public final int ix;
        public final int lo;
        public final int hi;

        public Window(int ix, int lo, int hi) {
            this.ix = ix;
            this.lo = lo;
            this.hi = hi;
        }
    }

    private final List<Window> windows;
    private final CullY cutter = new CullY();

    public EpochStride(List<Window> windows) {
        this.windows = new ArrayList<>(windows);
    }

    public List<Window> all() {
        return windows;
    }

    public Window byIx(int ix) {
        for (Window w : windows) {
            if (w.ix == ix) {
                return w;
            }
        }
        return windows.isEmpty() ? new Window(0, 0, 0) : windows.get(0);
    }

    public Window pick(FeatView feat, boolean ascending) {
        int mid = feat.len() == 0 ? 0 : feat.at(feat.len() / 2);
        FeatView probe = new FeatView(new int[] {mid});
        List<Window> order = new ArrayList<>(windows);
        if (!ascending) {
            java.util.Collections.reverse(order);
        }
        for (Window w : order) {
            AtomicInteger hits = new AtomicInteger();
            cutter.cullY(w.lo, w.hi, probe, (i, s) -> hits.incrementAndGet());
            if (hits.get() > 0) {
                return w;
            }
        }
        return byIx(0);
    }
}
