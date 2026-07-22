#!/usr/bin/env python3
"""Prepaid gondola-schedule threshold report builder.

Reads a line-config text file and a boarding-stream text file, replays the usage
events against the configured allocations, and writes the decision ledger to
standard output, one record per line.

The full output contract -- the gondola-and-line conjunction, the
threshold/limit limits, the surge-window lifecycle, the inclusive surge boundary,
the shared line standby pool with standby/return debt, and the canonical ledger
ordering -- is documented in docs/spec.md.

Only `build_ledger` needs to change. The argument handling, file reading,
parsing/validation, error reporting, and printing are fixed.
"""

import sys


class InputError(Exception):
    """Malformed input, an unknown gondola, or any structural violation of
    the config / event contract in docs/spec.md."""


def parse_config(text):
    """Parse the line-config text into (gonds, lines, routed_to).

    gonds[name]      -> {"soft", "hard", "grace"}
    lines[name]     -> {"soft", "hard", "grace", "reserve"}
    routed_to[name] -> line name
    """
    gonds, lines, routed_to = {}, {}, {}
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        f = line.split()
        directive = f[0]
        if directive == "GOND":
            if len(f) != 5:
                raise InputError("config line %d: GOND expects 5 fields" % lineno)
            name = f[1]
            soft, hard, grace = (
                _int(f[2], lineno, "soft"),
                _int(f[3], lineno, "hard"),
                _int(f[4], lineno, "grace"),
            )
            if soft < 0 or hard < 0 or grace < 0:
                raise InputError("config line %d: negative parameter" % lineno)
            if hard < soft:
                raise InputError("config line %d: hard < soft" % lineno)
            if name in gonds:
                raise InputError("config line %d: duplicate gondola %s" % (lineno, name))
            gonds[name] = {"soft": soft, "hard": hard, "grace": grace}
        elif directive == "LINE":
            # LINE accepts an optional 6th field: the shared standby pool capacity
            # (default 0 when omitted).
            if len(f) not in (5, 6):
                raise InputError("config line %d: LINE expects 5 or 6 fields" % lineno)
            name = f[1]
            soft, hard, grace = (
                _int(f[2], lineno, "soft"),
                _int(f[3], lineno, "hard"),
                _int(f[4], lineno, "grace"),
            )
            reserve = _int(f[5], lineno, "pool") if len(f) == 6 else 0
            if soft < 0 or hard < 0 or grace < 0 or reserve < 0:
                raise InputError("config line %d: negative parameter" % lineno)
            if hard < soft:
                raise InputError("config line %d: hard < soft" % lineno)
            if name in lines:
                raise InputError("config line %d: duplicate line %s" % (lineno, name))
            lines[name] = {"soft": soft, "hard": hard, "grace": grace, "reserve": reserve}
        elif directive == "ROUTE":
            if len(f) != 3:
                raise InputError("config line %d: ROUTE expects 3 fields" % lineno)
            if f[1] in routed_to:
                raise InputError("config line %d: duplicate member %s" % (lineno, f[1]))
            routed_to[f[1]] = f[2]
        else:
            raise InputError("config line %d: unknown directive" % lineno)

    for user in gonds:
        if user not in routed_to:
            raise InputError("gondola %s has no line" % user)
        if routed_to[user] not in lines:
            raise InputError("gondola %s maps to unknown line %s" % (user, routed_to[user]))
    return gonds, lines, routed_to


def parse_events(text, gonds):
    """Parse the boarding-stream text into a list of (tick, kind, user, mb)."""
    events = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        f = line.split()
        if len(f) != 4:
            raise InputError("event line %d: expected 4 fields" % lineno)
        tick = _int(f[0], lineno, "tick")
        if tick < 0:
            raise InputError("event line %d: negative tick" % lineno)
        kind, user = f[1], f[2]
        if user not in gonds:
            raise InputError("event line %d: unknown gondola %s" % (lineno, user))
        mb = _int(f[3], lineno, "mb")
        if mb <= 0:
            raise InputError("event line %d: non-positive MB count" % lineno)
        if kind not in ("BOARD", "ALIGHT"):
            raise InputError("event line %d: unknown event %r" % (lineno, kind))
        events.append((tick, kind, user, mb))
    return events


def _int(s, lineno, what):
    try:
        return int(s)
    except ValueError:
        raise InputError("line %d: bad %s value %r" % (lineno, what, s))

def build_ledger(config_text, events_text):
    users, groups, routed_to = parse_config(config_text)
    events = parse_events(events_text, users)

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



def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: report.py <line-config> <boarding-stream>\n")
        return 2
    try:
        with open(argv[1], "r") as fh:
            config_text = fh.read()
        with open(argv[2], "r") as fh:
            events_text = fh.read()
    except OSError as exc:
        sys.stderr.write("cannot read input: %s\n" % exc)
        return 1
    try:
        lines = build_ledger(config_text, events_text)
    except InputError as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 1
    sys.stdout.write("".join(line + "\n" for line in lines))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
