package runner;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

public final class Checks {
    private Checks() {}

    public static int cueHash(byte[] cue) {
        int sum = 0;
        for (byte b : cue) {
            sum += b & 0xff;
        }
        return sum % 1009;
    }

    public static int armSalt(int armId) {
        return (armId * 131) % 997;
    }

    public static int labelRank(String label) {
        return switch (label) {
            case "L0" -> 0;
            case "L1" -> 1;
            case "L2" -> 2;
            case "L3" -> 3;
            default -> 0;
        };
    }

    public static String sha256Hex(String input) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] dig = md.digest(input.getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder();
            for (byte b : dig) {
                sb.append(String.format("%02x", b));
            }
            return sb.toString();
        } catch (NoSuchAlgorithmException ex) {
            throw new IllegalStateException(ex);
        }
    }

    public static String witnessRef(int armId, String clusterId, int margin) {
        String raw = armId + "|" + clusterId + "|" + margin;
        return "w-" + sha256Hex(raw).substring(0, 12);
    }

    public static boolean o1Feasible(Types.BarrierCert cert) {
        for (int m : cert.marginVec) {
            if (m < 0) {
                return false;
            }
        }
        return true;
    }
}
