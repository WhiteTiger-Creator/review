package com.culvert.merge;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

public final class Fuser {
    public record PartitionView(int[] labels, boolean marked) {}

    public record ScoreView(Scorer.ScoreRow[] rows) {}

    public record Result(String[] rankOrder, String groupDigest) {}

    public static Result reconcile_c(PartitionView partitionData, ScoreView scoreData) {
        Scorer.ScoreRow[] rows = scoreData.rows();
        String[] ids = new String[rows.length];
        for (int i = 0; i < rows.length; i++) {
            ids[i] = rows[i].id();
        }
        if (partitionData.marked()) {
            String[] flipped = new String[ids.length];
            for (int i = 0; i < ids.length; i++) {
                flipped[i] = ids[ids.length - 1 - i];
            }
            return new Result(flipped, digest(flipped));
        }
        return new Result(ids, digest(ids));
    }

    private static String digest(String[] rank) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            for (String id : rank) {
                md.update(id.getBytes(StandardCharsets.UTF_8));
            }
            byte[] raw = md.digest();
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < 8; i++) {
                sb.append(String.format("%02x", raw[i]));
            }
            return sb.toString();
        } catch (Exception ex) {
            throw new IllegalStateException(ex);
        }
    }
}
