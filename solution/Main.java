// Cosign quorum auditor — reference implementation. JDK 21 standard library
// only; no javax.crypto. The keyed MAC and the order-dependent aggregate
// combine are hand-rolled from scratch (fixed 64-bit constants, defined word
// order over [rid, sid, digest], two mixing rounds per absorbed word, a
// multi-round finalize). The roster is replayed positionally: enroll/remove
// change the active signer set at and after their line, a key rotate voids that
// signer's cosignatures recorded before it, and every release is verified from
// the ledger lines above the authorize query only.

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;

public final class Main {

    static final String RESULT_PATH = "/app/output/result.json";

    // --- hand-rolled keyed MAC / aggregate constants (64-bit) ---
    static final long C0 = 0x736f6d6570736575L;
    static final long C1 = 0x646f72616e646f6dL;
    static final long C2 = 0x6c7967656e657261L;
    static final long PAD = 0x0f0f0f0f0f0f0f0fL;
    static final long FIN = 0xff00ff00ff00ff00L;
    static final long SEED = 0xc3d2e1f0a1b2c3d4L;
    static final long MULT = 0x9e3779b97f4a7c15L;

    static long rotl(long x, int r) {
        return (x << r) | (x >>> (64 - r));
    }

    // In-place 3-word mixing round; state carried in a length-3 array.
    static void rnd(long[] v) {
        long v0 = v[0], v1 = v[1], v2 = v[2];
        v0 = v0 + v1;
        v1 = rotl(v1, 13); v1 ^= v0;
        v0 = rotl(v0, 32);
        v2 = v2 + v0;
        v0 = rotl(v0, 16); v0 ^= v2;
        v2 = rotl(v2, 21);
        v1 = v1 + v2; v2 ^= v1;
        v[0] = v0; v[1] = v1; v[2] = v2;
    }

    static long mac(long key, long rid, long sid, long digest) {
        long[] v = new long[] {key ^ C0, rotl(key, 32) ^ C1, key ^ C2};
        long[] words = new long[] {rid, sid, digest};
        for (long w : words) {
            v[0] = v[0] + w;
            v[2] = v[2] ^ w;
            rnd(v);
            rnd(v);
        }
        v[2] ^= PAD;
        rnd(v);
        rnd(v);
        v[1] ^= FIN;
        rnd(v);
        return v[0] ^ v[1] ^ v[2];
    }

    static long combine(List<Long> tags) {
        long acc = SEED;
        for (long t : tags) {
            acc ^= t;
            acc = rotl(acc, 7);
            acc = acc + MULT;
            acc ^= rotl(t, 40);
        }
        acc ^= acc >>> 33;
        acc = acc * 0xff51afd7ed558ccdL;
        acc ^= acc >>> 33;
        acc = acc * 0xc4ceb9fe1a85ec53L;
        acc ^= acc >>> 33;
        return acc;
    }

    static String hex(long x) {
        return String.format("%016x", x);
    }

    static long u(String s) {
        return Long.parseUnsignedLong(s, 16);
    }

    // --- ledger records ---
    sealed interface Rec permits EnrollRec, RemoveRec, RotateRec, ReleaseRec,
            CosignRec, AuthorizeRec, AnchorRec, VouchRec {}
    record EnrollRec(String sid, String key) implements Rec {}
    record RemoveRec(String sid) implements Rec {}
    record RotateRec(String sid, String key) implements Rec {}
    record ReleaseRec(String rid, long k, String digest) implements Rec {}
    record CosignRec(String rid, String sid, String tag) implements Rec {}
    record AuthorizeRec(long seq, String rid, String claim) implements Rec {}
    record AnchorRec(String sid) implements Rec {}
    record VouchRec(String voucher, String target) implements Rec {}

    // Signer standing requires at least this many distinct already-standing
    // vouchers (section 5.5).
    static final int STANDING_THRESHOLD = 2;

    static boolean isId(String t) {
        if (t.length() != 16) return false;
        for (int i = 0; i < 16; i++) {
            char c = t.charAt(i);
            if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) return false;
        }
        return true;
    }

    static Long asLong(String t) {
        try {
            return Long.parseLong(t);
        } catch (NumberFormatException e) {
            return null;
        }
    }

    static List<Rec> parse(String text) {
        List<Rec> recs = new ArrayList<>();
        for (String raw : text.split("\n", -1)) {
            String line = raw.strip();
            if (line.isEmpty() || line.startsWith("#")) continue;
            String[] f = line.split(" ", -1);
            for (String tok : f) if (tok.isEmpty()) return null;
            switch (f[0]) {
                case "enroll" -> {
                    if (f.length != 3 || !isId(f[1]) || !isId(f[2])) return null;
                    recs.add(new EnrollRec(f[1], f[2]));
                }
                case "remove" -> {
                    if (f.length != 2 || !isId(f[1])) return null;
                    recs.add(new RemoveRec(f[1]));
                }
                case "rotate" -> {
                    if (f.length != 3 || !isId(f[1]) || !isId(f[2])) return null;
                    recs.add(new RotateRec(f[1], f[2]));
                }
                case "release" -> {
                    if (f.length != 4 || !isId(f[1]) || !isId(f[3])) return null;
                    Long k = asLong(f[2]);
                    if (k == null) return null;
                    recs.add(new ReleaseRec(f[1], k, f[3]));
                }
                case "cosign" -> {
                    if (f.length != 4 || !isId(f[1]) || !isId(f[2]) || !isId(f[3]))
                        return null;
                    recs.add(new CosignRec(f[1], f[2], f[3]));
                }
                case "authorize" -> {
                    if (f.length != 4 || !isId(f[2]) || !isId(f[3])) return null;
                    Long seq = asLong(f[1]);
                    if (seq == null) return null;
                    recs.add(new AuthorizeRec(seq, f[2], f[3]));
                }
                case "anchor" -> {
                    if (f.length != 2 || !isId(f[1])) return null;
                    recs.add(new AnchorRec(f[1]));
                }
                case "vouch" -> {
                    if (f.length != 3 || !isId(f[1]) || !isId(f[2])) return null;
                    recs.add(new VouchRec(f[1], f[2]));
                }
                default -> {
                    return null;
                }
            }
        }
        return recs;
    }

    static boolean schemaOk(List<Rec> recs) {
        Set<String> releases = new HashSet<>();
        Set<String> enrolled = new HashSet<>();
        for (Rec r : recs) {
            if (r instanceof ReleaseRec rr && !releases.add(rr.rid())) return false;
            if (r instanceof EnrollRec er) enrolled.add(er.sid());
        }
        long qi = 0;
        for (Rec r : recs) {
            if (r instanceof ReleaseRec rr) {
                if (rr.k() < 0) return false;
            } else if (r instanceof CosignRec cr) {
                if (!releases.contains(cr.rid()) || !enrolled.contains(cr.sid()))
                    return false;
            } else if (r instanceof RemoveRec rm) {
                if (!enrolled.contains(rm.sid())) return false;
            } else if (r instanceof RotateRec ro) {
                if (!enrolled.contains(ro.sid())) return false;
            } else if (r instanceof AnchorRec an) {
                if (!enrolled.contains(an.sid())) return false;
            } else if (r instanceof VouchRec vr) {
                if (!enrolled.contains(vr.voucher()) || !enrolled.contains(vr.target()))
                    return false;
                if (vr.voucher().equals(vr.target())) return false;
            } else if (r instanceof AuthorizeRec ar) {
                if (ar.seq() < 0 || ar.seq() != qi) return false;
                qi++;
            }
        }
        return true;
    }

    // Latest enroll/rotate key for sid at index <= upto, or null.
    static String keyInForce(List<Rec> recs, String sid, int upto) {
        String key = null;
        for (int i = 0; i <= upto && i < recs.size(); i++) {
            Rec r = recs.get(i);
            if (r instanceof EnrollRec er && er.sid().equals(sid)) key = er.key();
            else if (r instanceof RotateRec ro && ro.sid().equals(sid)) key = ro.key();
        }
        return key;
    }

    // Active iff latest enroll/remove for sid at index < upto is an enroll.
    static boolean isActive(List<Rec> recs, String sid, int upto) {
        Boolean st = null;
        for (int i = 0; i < upto && i < recs.size(); i++) {
            Rec r = recs.get(i);
            if (r instanceof EnrollRec er && er.sid().equals(sid)) st = Boolean.TRUE;
            else if (r instanceof RemoveRec rm && rm.sid().equals(sid)) st = Boolean.FALSE;
        }
        return Boolean.TRUE.equals(st);
    }

    // Section 5.5: signer standing at position `upto`. Standing gating is
    // active only if the whole file declares at least one anchor line;
    // otherwise this returns null, meaning "gating inactive, everyone
    // qualifies regardless of standing".
    static Set<String> standingSet(List<Rec> recs, int upto) {
        Set<String> anchors = new HashSet<>();
        for (Rec r : recs) if (r instanceof AnchorRec an) anchors.add(an.sid());
        if (anchors.isEmpty()) return null; // gating inactive

        // Distinct vouchers declared (at or above `upto`, i.e. index < upto)
        // for each target.
        Map<String, Set<String>> vouchersOf = new HashMap<>();
        for (int i = 0; i < upto && i < recs.size(); i++) {
            if (recs.get(i) instanceof VouchRec vr) {
                vouchersOf.computeIfAbsent(vr.target(), k -> new HashSet<>())
                          .add(vr.voucher());
            }
        }

        Set<String> standing = new HashSet<>();
        for (String a : anchors) {
            if (isActive(recs, a, upto)) standing.add(a);
        }
        boolean changed = true;
        while (changed) {
            changed = false;
            for (Map.Entry<String, Set<String>> e : vouchersOf.entrySet()) {
                String target = e.getKey();
                if (standing.contains(target)) continue;
                if (!isActive(recs, target, upto)) continue;
                long standingVouchers =
                        e.getValue().stream().filter(standing::contains).count();
                if (standingVouchers >= STANDING_THRESHOLD) {
                    standing.add(target);
                    changed = true;
                }
            }
        }
        return standing;
    }

    // Qualifying signers among cosign lines with index < upto: returns the
    // sid-sorted map of signer -> valid tag. Uses only lines above upto.
    static TreeMap<String, Long> qualifiers(List<Rec> recs, String rid,
                                            String digest, int upto) {
        TreeMap<String, Long> qual = new TreeMap<>();
        Set<String> standing = standingSet(recs, upto); // null => gating inactive
        for (int i = 0; i < upto && i < recs.size(); i++) {
            if (!(recs.get(i) instanceof CosignRec cr) || !cr.rid().equals(rid))
                continue;
            String sid = cr.sid();
            String kf = keyInForce(recs, sid, i);
            if (kf == null) continue;
            boolean voided = false;
            for (int j = i + 1; j < upto && j < recs.size(); j++) {
                if (recs.get(j) instanceof RotateRec ro && ro.sid().equals(sid)) {
                    voided = true;
                    break;
                }
            }
            if (voided) continue;
            if (!isActive(recs, sid, upto)) continue;
            if (standing != null && !standing.contains(sid)) continue;
            long correct = mac(u(kf), u(rid), u(sid), u(digest));
            if (!hex(correct).equals(cr.tag())) continue;
            qual.put(sid, correct);
        }
        return qual;
    }

    public static void main(String[] args) throws IOException {
        if (args.length != 1) System.exit(2);
        byte[] bytes;
        try {
            bytes = Files.readAllBytes(Path.of(args[0]));
        } catch (IOException e) {
            System.exit(1);
            return;
        }
        String text = new String(bytes, StandardCharsets.UTF_8);
        if (!java.util.Arrays.equals(text.getBytes(StandardCharsets.UTF_8), bytes)) {
            System.exit(3);
        }
        List<Rec> recs = parse(text);
        if (recs == null) System.exit(3);

        long releaseCount = recs.stream().filter(r -> r instanceof ReleaseRec).count();
        long authorizeCount = recs.stream().filter(r -> r instanceof AuthorizeRec).count();

        if (!schemaOk(recs)) {
            emit("malformed", List.of(), List.of(), new long[4], 0, 0);
            System.exit(0);
        }

        Map<String, ReleaseRec> byRid = new HashMap<>();
        for (Rec r : recs) if (r instanceof ReleaseRec rr) byRid.put(rr.rid(), rr);

        List<String> decisions = new ArrayList<>();
        long[] counts = new long[4]; // authorized, under_threshold, tag_mismatch, unknown
        Set<String> declaredAbove = new HashSet<>();

        for (int i = 0; i < recs.size(); i++) {
            Rec r = recs.get(i);
            if (r instanceof ReleaseRec rr) {
                declaredAbove.add(rr.rid());
            } else if (r instanceof AuthorizeRec ar) {
                String v;
                long cos;
                String agg;
                if (!declaredAbove.contains(ar.rid())) {
                    v = "unknown_release";
                    cos = 0;
                    agg = hex(0L);
                } else {
                    ReleaseRec rel = byRid.get(ar.rid());
                    TreeMap<String, Long> q = qualifiers(recs, ar.rid(), rel.digest(), i);
                    cos = q.size();
                    agg = hex(combine(new ArrayList<>(q.values())));
                    if (cos < rel.k()) v = "under_threshold";
                    else if (!agg.equals(ar.claim())) v = "tag_mismatch";
                    else v = "authorized";
                }
                switch (v) {
                    case "authorized" -> counts[0]++;
                    case "under_threshold" -> counts[1]++;
                    case "tag_mismatch" -> counts[2]++;
                    default -> counts[3]++;
                }
                decisions.add("{\"seq\": " + ar.seq() + ", \"verdict\": \"" + v
                        + "\", \"cosigners\": " + cos + ", \"aggregate\": \"" + agg + "\"}");
            }
        }

        List<String> relJson = new ArrayList<>();
        for (Rec r : recs) {
            if (r instanceof ReleaseRec rr) {
                TreeMap<String, Long> q =
                        qualifiers(recs, rr.rid(), rr.digest(), recs.size());
                long cos = q.size();
                String agg = hex(combine(new ArrayList<>(q.values())));
                boolean authorized = cos >= rr.k();
                relJson.add("{\"id\": \"" + rr.rid() + "\", \"authorized\": " + authorized
                        + ", \"cosigners\": " + cos + ", \"aggregate\": \"" + agg + "\"}");
            }
        }

        emit("ok", decisions, relJson, counts, releaseCount, authorizeCount);
        System.exit(0);
    }

    static void emit(String status, List<String> decisions, List<String> releases,
                     long[] c, long releaseCount, long authorizeCount) throws IOException {
        String json = "{\"status\": \"" + status + "\", \"decisions\": ["
                + String.join(", ", decisions) + "], \"releases\": ["
                + String.join(", ", releases) + "], \"authorized_count\": " + c[0]
                + ", \"under_threshold_count\": " + c[1]
                + ", \"tag_mismatch_count\": " + c[2]
                + ", \"unknown_count\": " + c[3]
                + ", \"release_count\": " + releaseCount
                + ", \"authorize_count\": " + authorizeCount + "}";
        try {
            Files.createDirectories(Path.of("/app/output"));
            Files.writeString(Path.of(RESULT_PATH), json + "\n");
        } catch (IOException e) {
            // stdout copy still emitted below
        }
        System.out.println(json);
    }
}
