package k7m;

import runner.Types;
import readers.SliceQ7;

public final class ShadowClip {
    private ShadowClip() {}

    public static String preview(Types.ClusterRec cluster) {
        byte[] slice = SliceQ7.cueSlice(cluster);
        return cluster.clusterId + ":" + slice.length;
    }
}
