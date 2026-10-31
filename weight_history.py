"""
weight_history.py - put wrestlers at the weight they wrestled at the most
recent CUT event (a tournament where guys make their competition weight).

WHY (Jeff, 2026-10-31): not every tournament says anything about weight.
At World Challenge, Arballo Holiday Hammer, Gilroy or Freakshow the guys
don't cut much; at Super 32 or Doc B they cut, and that is where they will
end up. Only cut events can move a wrestler. (An earlier version of this
file carried last season's carank tournament weights forward; Jeff dropped
that - early-season events like Mettler and Zinkin are not a weight signal,
and last season is not this season.)

HOW AN EVENT BECOMES A CUT EVENT: its file carries the header line
    # weight_signal: cut
Two kinds of file count:
  * tournaments/*.tsv            bout files (both wrestlers' weights)
  * tournaments/weights/*.tsv    entrant lists: gender, weight, first, last,
                                 team - every CA entrant, not just bouts
                                 between two board wrestlers
No header = no weight signal (default). Tag Doc B, Five Counties, state,
etc. the same way when their files are added.

RULE:
  * For each boys board wrestler found at a cut event (same name matching as
    tournament_ingest), take his weight at the LATEST cut event.
  * Move him to that board - up or down. A cut event this season beats
    carank's February weight and a summer Fargo projection.
  * Identity guard: a jump of more than 2 weight classes is NOT applied, only
    logged ("check identity") - set it in weight_overrides.py once confirmed.
  * Manual placements (weight_overrides.py) are skipped here and applied
    after, so Jeff's calls always win.
  * Placed by rating on the new board; row carries weight_source "cut_event",
    origin_weight and weight_reason.
"""
import glob
import os
import re
import unicodedata

BOYS_WEIGHTS = [106, 113, 120, 126, 132, 138, 144, 150, 157, 165, 175, 190, 215, 285]
MAX_CLASS_JUMP = 2


def _norm(n):
    n = unicodedata.normalize("NFKD", n or "").encode("ascii", "ignore").decode()
    n = re.sub(r"^\s*(?:HM|-)\s+", "", n)
    return re.sub(r"\s+", " ", re.sub(r"[^a-z ]", "", n.lower())).strip()


def _read(path):
    meta, header, rows = {}, None, []
    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        if not line.strip():
            continue
        if line.startswith("#"):
            k, _, v = line[1:].partition(":")
            meta[k.strip()] = v.strip()
            continue
        f = line.split("\t")
        if header is None:
            header = f
            continue
        rows.append(dict(zip(header, f)))
    meta.setdefault("date", os.path.basename(path)[:10])
    meta.setdefault("event", os.path.basename(path))
    return meta, rows


def cut_event_entries(folder="tournaments"):
    """[(date, event, gender, weight, first, last, team)] from cut-tagged files."""
    out = []
    paths = sorted(glob.glob(os.path.join(folder, "*.tsv")) +
                   glob.glob(os.path.join(folder, "weights", "*.tsv")))
    for p in paths:
        meta, rows = _read(p)
        if meta.get("weight_signal", "").lower() != "cut":
            continue
        for r in rows:
            wt = int(float(r["weight"]))
            if "w_first" in r:      # bout file: both sides
                for s in ("w", "l"):
                    out.append((meta["date"], meta["event"], r["gender"], wt,
                                r[s + "_first"], r[s + "_last"], r.get(s + "_team", "")))
            else:                   # entrant list
                out.append((meta["date"], meta["event"], r["gender"], wt,
                            r["first"], r["last"], r.get("team", "")))
    return out


def apply_cut_event_weights(data, folder="tournaments", verbose=True):
    from tournament_ingest import Resolver, _load_aliases
    try:
        from weight_overrides import OVERRIDES
        manual = {_norm(n) for (g, n) in OVERRIDES if g == "boys"}
    except ImportError:
        manual = set()
    log = print if verbose else (lambda *a, **k: None)
    boards = {(b["gender"], b["weight"]): b["wrestlers"] for b in data["weights"]}
    res = Resolver(boards, lambda *a, **k: None)
    res.aliases = _load_aliases(folder)

    latest = {}   # id(row) -> (date, event, weight, cur_weight, row)
    for date, event, g, wt, first, last, team in cut_event_entries(folder):
        if g != "boys":
            continue
        ent = res.resolve(g, first, last, team)
        if not ent:
            continue
        _, cur, row = ent
        prev = latest.get(id(row))
        if prev is None or date > prev[0] or (date == prev[0] and wt > prev[2]):
            latest[id(row)] = (date, event, wt, cur, row)

    moved = []
    for date, event, wt, cur, row in latest.values():
        target = next((b for b in BOYS_WEIGHTS if b >= wt), None)
        if target is None or target == cur or ("boys", target) not in boards:
            continue
        if _norm(row["name"]) in manual:
            log(f"CUT EVENT: {row['name']} wrestled {wt} at {event}; manual override applies")
            continue
        jump = abs(BOYS_WEIGHTS.index(target) - BOYS_WEIGHTS.index(cur))
        if jump > MAX_CLASS_JUMP:
            log(f"CUT EVENT: {row['name']} ({row.get('team','')}) board {cur}, wrestled "
                f"{wt} at {event} - {jump} classes, NOT moved (check identity)")
            continue
        boards[("boys", cur)].remove(row)
        for k in ("proj", "seed_reason"):
            row.pop(k, None)
        row["origin_weight"] = cur
        row["weight_source"] = "cut_event"
        row["weight_reason"] = f"{event} ({date}): {wt}"
        dest = boards[("boys", target)]
        pos = next((i for i, r in enumerate(dest) if r["rating"] < row["rating"]), len(dest))
        dest.insert(pos, row)
        moved.append((row["name"], cur, target))
        log(f"CUT EVENT: {row['name']}: {cur} -> {target} (#{pos + 1}) - wrestled {wt} at {event}")
    for (g, _), rows in boards.items():
        if g == "boys":
            for n, r in enumerate(rows, 1):
                r["rank"] = n
    log(f"CUT EVENT: {len(moved)} wrestlers moved")
    return moved
