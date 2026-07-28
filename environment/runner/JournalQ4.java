package runner;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public final class JournalQ4 {
    private static final Pattern INT = Pattern.compile("(-?\\d+)");

    private JournalQ4() {}

    public static boolean matchesFingerprint(Types.JournalSnap snap, int caseId, int armId, String runMode,
            String wave) {
        return snap.caseId == caseId && snap.runMode.equals(runMode);
    }

    public static Types.JournalSnap read(Path path) throws IOException {
        String raw = Files.readString(path, StandardCharsets.UTF_8);
        Types.JournalSnap snap = new Types.JournalSnap();
        snap.caseId = findInt(raw, "case_id");
        snap.armId = findInt(raw, "arm_id");
        snap.runMode = findQuoted(raw, "run_mode");
        snap.wave = findQuoted(raw, "wave");
        snap.epoch = findInt(raw, "epoch");
        snap.barrierMargins = parseIntList(raw, "barrier_margins");
        return snap;
    }

    public static void write(Path path, Types.JournalSnap snap) throws IOException {
        StringBuilder sb = new StringBuilder();
        sb.append("{\n");
        sb.append("  \"case_id\": ").append(snap.caseId).append(",\n");
        sb.append("  \"arm_id\": ").append(snap.armId).append(",\n");
        sb.append("  \"run_mode\": \"").append(snap.runMode).append("\",\n");
        sb.append("  \"wave\": \"").append(snap.wave).append("\",\n");
        sb.append("  \"epoch\": ").append(snap.epoch).append(",\n");
        sb.append("  \"barrier_margins\": [");
        for (int i = 0; i < snap.barrierMargins.size(); i++) {
            if (i > 0) {
                sb.append(", ");
            }
            sb.append(snap.barrierMargins.get(i));
        }
        sb.append("]\n}\n");
        Files.createDirectories(path.getParent());
        Files.writeString(path, sb.toString(), StandardCharsets.UTF_8);
    }

    private static int findInt(String raw, String key) {
        Matcher m = Pattern.compile("\"" + key + "\"\\s*:\\s*(-?\\d+)").matcher(raw);
        if (!m.find()) {
            return 0;
        }
        return Integer.parseInt(m.group(1));
    }

    private static String findQuoted(String raw, String key) {
        Matcher m = Pattern.compile("\"" + key + "\"\\s*:\\s*\"([^\"]*)\"").matcher(raw);
        if (!m.find()) {
            return "";
        }
        return m.group(1);
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
}
