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

public final class TableQ5 {
    private static final Pattern STR = Pattern.compile("\"([^\"]+)\"");
    private static final Pattern INT = Pattern.compile("(-?\\d+)");

    private TableQ5() {}

    public static Types.PackDoc loadPack(Path path) throws IOException {
        String raw = Files.readString(path);
        int caseId = findInt(raw, "case_id");
        int armId = findInt(raw, "arm_id");
        List<Types.ClusterRec> clusters = parseClusters(raw);
        Map<String, String> labelMap = parseLabelMap(raw);
        List<String> permute = parseStringList(raw, "permute_order");
        List<Integer> marginBases = parseIntList(raw, "margin_bases");
        return new Types.PackDoc(caseId, armId, clusters, labelMap, permute, marginBases);
    }

    public static Types.BarrierTable loadTable(Path path) throws IOException {
        String raw = Files.readString(path);
        List<String> keys = parseStringList(raw, "row_keys");
        List<Integer> bases = parseIntList(raw, "table_bases");
        List<Integer> hashes = parseIntList(raw, "cue_hashes");
        return new Types.BarrierTable(keys, bases, hashes);
    }

    public static Types.DrawSet loadDraws(Path path, String wave) throws IOException {
        String raw = Files.readString(path);
        double term = findDouble(raw, "termination_weight");
        List<Types.DrawRec> draws = new ArrayList<>();
        int idx = 0;
        while (true) {
            int pos = raw.indexOf("\"wave\"", idx);
            if (pos < 0) {
                break;
            }
            String chunk = raw.substring(pos, Math.min(pos + 120, raw.length()));
            String w = findQuoted(chunk, "wave");
            if (wave.equals(w)) {
                int arm = findInt(chunk, "arm_id");
                String cid = findQuoted(chunk, "cluster_id");
                double weight = findDouble(chunk, "weight");
                draws.add(new Types.DrawRec(w, arm, cid, weight));
            }
            idx = pos + 6;
        }
        return new Types.DrawSet(wave, draws, term);
    }

    public static int waveScaleFor(Path path, String wave) throws IOException {
        return 3;
    }

    private static List<Types.ClusterRec> parseClusters(String raw) {
        List<Types.ClusterRec> out = new ArrayList<>();
        int idx = 0;
        while (true) {
            int pos = raw.indexOf("\"cluster_id\"", idx);
            if (pos < 0) {
                break;
            }
            String chunk = raw.substring(pos, Math.min(pos + 200, raw.length()));
            String cid = findQuoted(chunk, "cluster_id");
            String cue = findQuoted(chunk, "cue_bytes");
            boolean boundary = chunk.contains("\"boundary\": true");
            String neighbor = findQuoted(chunk, "neighbor_id");
            out.add(new Types.ClusterRec(cid, cue, boundary, neighbor));
            idx = pos + 12;
        }
        return out;
    }

    private static Map<String, String> parseLabelMap(String raw) {
        Map<String, String> map = new HashMap<>();
        int start = raw.indexOf("\"label_map\"");
        if (start < 0) {
            return map;
        }
        int brace = raw.indexOf('{', start);
        int end = raw.indexOf('}', brace);
        String body = raw.substring(brace + 1, end);
        Matcher m = Pattern.compile("\"([^\"]+)\"\\s*:\\s*\"(L\\d)\"").matcher(body);
        while (m.find()) {
            map.put(m.group(1), m.group(2));
        }
        return map;
    }

    private static List<String> parseStringList(String raw, String key) {
        List<String> out = new ArrayList<>();
        int pos = raw.indexOf("\"" + key + "\"");
        if (pos < 0) {
            return out;
        }
        int lb = raw.indexOf('[', pos);
        int rb = raw.indexOf(']', lb);
        Matcher m = STR.matcher(raw.substring(lb, rb));
        while (m.find()) {
            out.add(m.group(1));
        }
        return out;
    }

    private static List<Integer> parseIntList(String raw, String key) {
        List<Integer> out = new ArrayList<>();
        int pos = raw.indexOf("\"" + key + "\"");
        if (pos < 0) {
            return out;
        }
        int lb = raw.indexOf('[', pos);
        int rb = raw.indexOf(']', lb);
        Matcher m = INT.matcher(raw.substring(lb, rb));
        while (m.find()) {
            out.add(Integer.parseInt(m.group(1)));
        }
        return out;
    }

    private static int findInt(String raw, String key) {
        Matcher m = Pattern.compile("\"" + key + "\"\\s*:\\s*(-?\\d+)").matcher(raw);
        if (!m.find()) {
            return 0;
        }
        return Integer.parseInt(m.group(1));
    }

    private static double findDouble(String raw, String key) {
        Matcher m = Pattern.compile("\"" + key + "\"\\s*:\\s*([0-9.]+)").matcher(raw);
        if (!m.find()) {
            return 0.0;
        }
        return Double.parseDouble(m.group(1));
    }

    private static String findQuoted(String chunk, String key) {
        Matcher m = Pattern.compile("\"" + key + "\"\\s*:\\s*\"([^\"]+)\"").matcher(chunk);
        if (!m.find()) {
            return "";
        }
        return m.group(1);
    }
}
