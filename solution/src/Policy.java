package com.acme.wallet.sdjwt;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;

/** The verifier's disclosure policy and the smallest release that satisfies it. */
final class Policy {

    /** Either the claim paths to release, or the policy paths this credential cannot cover. */
    static final class Release {
        final Set<String> paths;
        final List<String> missing;

        Release(Set<String> paths, List<String> missing) {
            this.paths = paths;
            this.missing = missing;
        }
    }

    private final List<String> required = new ArrayList<>();
    private final List<List<String>> alternatives = new ArrayList<>();

    @SuppressWarnings("unchecked")
    Policy(Map<String, Object> document) {
        Object demanded = document.get("required");
        if (demanded instanceof List) {
            for (Object path : (List<Object>) demanded) {
                required.add((String) path);
            }
        }
        Object groups = document.get("alternatives");
        if (groups instanceof List) {
            for (Object group : (List<Object>) groups) {
                List<String> options = new ArrayList<>();
                for (Object path : (List<Object>) group) {
                    options.add((String) path);
                }
                alternatives.add(options);
            }
        }
    }

    /** The disclosures a claim path cannot travel without. */
    private static Set<String> needed(String path, Map<String, Object> resolved, Map<String, String> held) {
        Set<String> out = new LinkedHashSet<>();
        for (String step : Paths.ancestors(path)) {
            if (held.containsKey(step)) {
                out.add(step);
            }
        }
        Object value = Paths.lookup(resolved, path);
        if (value instanceof List) {
            int size = ((List<?>) value).size();
            for (int index = 0; index < size; index++) {
                String element = Paths.element(path, index);
                if (held.containsKey(element)) {
                    out.add(element);
                }
            }
        }
        return out;
    }

    /** Work out the smallest release, or report why the credential falls short. */
    Release release(Map<String, Object> resolved, Map<String, String> held) {
        Set<String> missing = new TreeSet<>(Json.BY_UTF8);
        for (String path : required) {
            if (Paths.lookup(resolved, path) == null) {
                missing.add(path);
            }
        }
        for (List<String> group : alternatives) {
            boolean any = false;
            for (String option : group) {
                if (Paths.lookup(resolved, option) != null) {
                    any = true;
                    break;
                }
            }
            if (!any) {
                missing.addAll(group);
            }
        }
        if (!missing.isEmpty()) {
            return new Release(null, new ArrayList<>(missing));
        }

        Set<String> base = new LinkedHashSet<>();
        for (String path : required) {
            base.addAll(needed(path, resolved, held));
        }
        int[] choice = new int[alternatives.size()];
        Set<String> best = null;
        while (true) {
            Set<String> chosen = new LinkedHashSet<>(base);
            boolean possible = true;
            for (int group = 0; group < alternatives.size(); group++) {
                String option = alternatives.get(group).get(choice[group]);
                if (Paths.lookup(resolved, option) == null) {
                    possible = false;
                    break;
                }
                chosen.addAll(needed(option, resolved, held));
            }
            if (possible && (best == null || chosen.size() < best.size())) {
                best = chosen;
            }
            int group = alternatives.size() - 1;
            while (group >= 0) {
                choice[group]++;
                if (choice[group] < alternatives.get(group).size()) {
                    break;
                }
                choice[group] = 0;
                group--;
            }
            if (group < 0) {
                break;
            }
        }
        return new Release(best, List.of());
    }
}
