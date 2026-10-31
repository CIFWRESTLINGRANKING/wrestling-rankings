"""
weight_history.py - carry each wrestler's 2025-26 tournament weights forward
into his 2026-27 board placement.

THE GAP THIS CLOSES (Jeff, 2026-10-31): board weight was carank's final
(February) weight. Julian Holguin (Bellarmine) won Elk Grove Mettler at 132
and took 3rd at Zinkin at 132, then cut to 126 for the postseason - so he
sat on the 126 board for 2026-27 even though a year older he will not be
lighter than he was last December.

RULE (same for everyone):
  * Read every tournament placement on the wrestler's carank block, e.g.
    "1st Elk Grove Curt Mettler (132)". League, section, division, regional
    and dual results are ignored - those are the postseason cut weight
    (already the board weight) or team events.
  * Projected weight = the highest weight he wrestled at TWO or more
    tournaments last season (the second-highest tournament weight). One
    outing up a weight is not enough.
  * Snap up to a real board weight (e.g. 162 -> 165).
  * Only moves UP, and only if that beats his current board weight
    (carank + Fargo projection). Never moves anyone down.
  * Manual placements in weight_overrides.py run AFTER this and win; a
    wrestler listed there is skipped here.
  * A Fargo projection (row has "proj") is newer evidence (summer 2026) and
    is left alone.
  * Fall 2026 competed weights (Gilroy, Super 32, Freakshow) are NOT used:
    wrestlers had not cut (standing decision). Use weight_overrides.py when
    Jeff confirms a fall weight.

A moved wrestler is placed by rating on his new board (same as a manual
override) and carries weight_source "history", origin_weight and a
weight_reason listing the tournaments. Idempotent: once carank lists him at
the new weight, he is already there and nothing happens.
"""
import re
import unicodedata

BOYS_WEIGHTS = [106, 113, 120, 126, 132, 138, 144, 150, 157, 165, 175, 190, 215, 285]
MIN_EVENTS = 2

GRADE_RE = re.compile(r"(FRESHMAN|SOPHOMORE|JUNIOR|SENIOR)")
# "1st Elk Grove Curt Mettler (132)", "3-2 Qtrs. Top 12 Reno TOC (157)", "I-D, ... (165)"
PLACE_RE = re.compile(
    r"((?:\d{1,2}(?:st|nd|rd|th)|\d+-\d+|I-D,?|DNP)\s[^()]{2,60}?)\s*\((\d{3})\)")
# not a weight signal: postseason/league/section (that's the cut weight) or duals
SKIP_RE = re.compile(r"league|section|\bdiv\b|div\.|regional|\breg\.|conf\.|conference|"
                     r"athl\.|athletic|duals|masters", re.I)


def _norm(n):
    n = unicodedata.normalize("NFKD", n or "").encode("ascii", "ignore").decode()
    n = re.sub(r"^\s*(?:HM|-)\s+", "", n)
    return re.sub(r"\s+", " ", re.sub(r"[^a-z ]", "", n.lower())).strip()


def extract_history(text):
    """From html_to_text() output, return {norm_name: [(event, weight), ...]}."""
    import carank_auto as A
    import carank_gen as G
    marks = list(G.BLOCK_RE.finditer(text))
    hist = {}
    for i, mk in enumerate(marks):
        seg = text[mk.end(): marks[i + 1].start() if i + 1 < len(marks) else len(text)]
        gm = GRADE_RE.search(seg[:120])
        if not gm:
            continue
        raw = re.sub(r"^\s*(?:HM|-)\s+", "", seg[:gm.start()].lstrip(" 0123456789"))
        name = A.split_name(raw)
        body = seg[gm.end():]
        cut = body.find("KEY HEAD-TO-HEADS")
        body = re.sub(r"\s+", " ", body[:cut] if cut >= 0 else body[:1500])
        events = [(m.group(1).strip(), int(m.group(2))) for m in PLACE_RE.finditer(body)]
        if events:
            hist.setdefault(_norm(name), events)
    return hist


def projected_weight(events):
    """Highest weight wrestled at MIN_EVENTS+ tournaments, snapped to a board weight."""
    ws = sorted((w for ev, w in events if not SKIP_RE.search(ev)), reverse=True)
    if len(ws) < MIN_EVENTS:
        return None, []
    floor = ws[MIN_EVENTS - 1]
    target = next((b for b in BOYS_WEIGHTS if b >= floor), None)
    used = [(ev, w) for ev, w in events if not SKIP_RE.search(ev) and w >= floor]
    return target, used


def apply_history_moves(data, history, verbose=True):
    """Move boys wrestlers up to their projected weight. Returns list of moves."""
    try:
        from weight_overrides import OVERRIDES
        manual = {_norm(n) for (g, n) in OVERRIDES if g == "boys"}
    except ImportError:
        manual = set()
    boards = {b["weight"]: b["wrestlers"] for b in data["weights"] if b["gender"] == "boys"}
    plan = []
    for wt, rows in boards.items():
        for row in rows:
            key = _norm(row["name"])
            events = history.get(key)
            if not events or key in manual or row.get("proj"):
                continue
            target, used = projected_weight(events)
            if target and target > wt and target in boards:
                plan.append((wt, target, row, used))
    for cur, target, row, used in plan:
        boards[cur].remove(row)
        row["origin_weight"] = cur
        row["weight_source"] = "history"
        row["weight_reason"] = "2025-26: " + "; ".join(f"{ev} ({w})" for ev, w in used)
        dest = boards[target]
        pos = next((i for i, r in enumerate(dest) if r["rating"] < row["rating"]), len(dest))
        dest.insert(pos, row)
        if verbose:
            print(f"WEIGHT HISTORY: {row['name']}: {cur} -> {target} (#{pos + 1}) "
                  f"- {row['weight_reason']}")
    for rows in boards.values():
        for n, r in enumerate(rows, 1):
            r["rank"] = n
    if verbose:
        print(f"WEIGHT HISTORY: {len(plan)} wrestlers moved up")
    return plan
