"""Independent reference reducer for the gondola-schedule threshold report.

This mirrors docs/spec.md with a structure independent of report.py. It is
kept here in solution/ (not in the verifier) as a second implementation used
to generate the static differential corpus under tests/; it is not consulted
at grading time."""


def reference_ledger(config_text, events_text):
    users, groups, routed_to = {}, {}, {}
    for raw in config_text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        f = line.split()
        if f[0] == "GOND":
            assert len(f) == 5
            soft, hard, grace = int(f[2]), int(f[3]), int(f[4])
            assert soft >= 0 and hard >= 0 and grace >= 0 and hard >= soft
            users[f[1]] = {"soft": soft, "hard": hard, "grace": grace}
        elif f[0] == "LINE":
            assert len(f) in (5, 6)
            soft, hard, grace = int(f[2]), int(f[3]), int(f[4])
            reserve = int(f[5]) if len(f) == 6 else 0
            assert soft >= 0 and hard >= 0 and grace >= 0 and reserve >= 0
            assert hard >= soft
            groups[f[1]] = {
                "soft": soft,
                "hard": hard,
                "grace": grace,
                "reserve": reserve,
            }
        elif f[0] == "ROUTE":
            assert len(f) == 3
            routed_to[f[1]] = f[2]
        else:
            raise ValueError("bad directive")
    for u in users:
        assert u in routed_to and routed_to[u] in groups

    events = []
    for raw in events_text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        f = line.split()
        assert len(f) == 4
        tick, kind, user, blocks = int(f[0]), f[1], f[2], int(f[3])
        assert tick >= 0 and user in users and blocks > 0
        assert kind in ("BOARD", "ALIGHT")
        events.append((tick, kind, user, blocks))

    ust = {u: {"usage": 0, "run": False, "start": 0, "debt": []} for u in users}
    gst = {g: {"usage": 0, "run": False, "start": 0, "rused": 0} for g in groups}

    def ceiling(q, usage, run_, start, tick):
        if usage > q["soft"] and run_ and tick > start + q["grace"]:
            return q["soft"]
        return q["hard"]

    def update_timer(soft, usage, st, tick):
        started = False
        if usage > soft:
            if not st["run"]:
                st["run"] = True
                st["start"] = tick
                started = True
        else:
            st["run"] = False
        return started

    out = []
    for tick, kind, user, blocks in events:
        group = routed_to[user]
        uq, gq = users[user], groups[group]
        us, gs = ust[user], gst[group]
        if kind == "ALIGHT":
            remaining = blocks
            repaid = 0
            while remaining > 0 and us["debt"]:
                top = us["debt"][-1]
                take = min(remaining, top)
                top -= take
                remaining -= take
                repaid += take
                if top == 0:
                    us["debt"].pop()
                else:
                    us["debt"][-1] = top
            if repaid > 0:
                gs["rused"] -= repaid
                out.append("%d RETURN %s %d" % (tick, user, repaid))
            if remaining > 0:
                us["usage"] = max(0, us["usage"] - remaining)
                update_timer(uq["soft"], us["usage"], us, tick)
                gs["usage"] = max(0, gs["usage"] - remaining)
                update_timer(gq["soft"], gs["usage"], gs, tick)
            continue

        n = blocks
        if uq["hard"] - us["usage"] < n:
            out.append("%d REJECT GOND_LIMIT" % tick)
            continue
        if gq["hard"] - gs["usage"] < n:
            out.append("%d REJECT LINE_LIMIT" % tick)
            continue
        uc = ceiling(uq, us["usage"], us["run"], us["start"], tick)
        gc = ceiling(gq, gs["usage"], gs["run"], gs["start"], tick)
        user_room = max(0, uc - us["usage"])
        group_room = max(0, gc - gs["usage"])
        grant = min(n, user_room, group_room)
        shortfall = n - grant
        if shortfall > 0:
            if gq["reserve"] - gs["rused"] < shortfall:
                out.append("%d REJECT STANDBY_EMPTY" % tick)
                continue

        out.append("%d BOARDED" % tick)
        started_u = started_g = False
        if grant > 0:
            us["usage"] += grant
            started_u = update_timer(uq["soft"], us["usage"], us, tick)
            gs["usage"] += grant
            started_g = update_timer(gq["soft"], gs["usage"], gs, tick)
        if shortfall > 0:
            gs["rused"] += shortfall
            us["debt"].append(shortfall)
        if started_u:
            out.append("%d SURGE_START GOND %s" % (tick, user))
        if started_g:
            out.append("%d SURGE_START LINE %s" % (tick, group))
        if shortfall > 0:
            out.append("%d STANDBY %s %d" % (tick, user, shortfall))
    return out

