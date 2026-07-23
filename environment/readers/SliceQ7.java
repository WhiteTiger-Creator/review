package readers;

import runner.Types;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public final class SliceQ7 {
    private static final Pattern HEX_PAIR = Pattern.compile("([0-9a-fA-F]{2})");

    private SliceQ7() {}

    public static byte[] cueSlice(Types.ClusterRec cluster) {
        Matcher m = HEX_PAIR.matcher(cluster.cueBytes);
        List<Byte> out = new ArrayList<>();
        while (m.find()) {
            out.add((byte) Integer.parseInt(m.group(1), 16));
        }
        while (out.size() < 8) {
            out.add((byte) 0);
        }
        byte[] arr = new byte[out.size()];
        for (int i = 0; i < out.size(); i++) {
            arr[i] = out.get(i);
        }
        if (cluster.boundary) {
            arr[4] = (byte) (arr[4] | 0x01);
        }
        return arr;
    }

    public static Map<String, byte[]> allSlices(Types.PackDoc pack) {
        Map<String, byte[]> map = new HashMap<>();
        for (Types.ClusterRec rec : pack.clusters) {
            map.put(rec.clusterId, cueSlice(rec));
        }
        return map;
    }
}
