"""
fargo_step -- apply Fargo 2026 projected weights to the assembled boards,
inside the auto pipeline (call from build_rankings_auto right before
rankings.json is written).

DESIGN, and why:

1. MOVES, not annotations. Per Jeff (Aug 24 2026): the board is forward-
   looking for 2026-27, and Fargo weight is the projection. A wrestler whose
   Fargo weight differs from his carank board weight is moved to the Fargo
   weight's board.

2. Arrivals are APPENDED, flagged, and never interleaved. Ratings are per-
   weight pools rated in isolation; a 106-pool rating and a 113-pool rating
   share no scale, so inserting an arrival "by rating" would be a cross-pool
   comparison the math does not support. Natives keep their engine order
   (which encodes H2H tiebreaks); arrivals go below them, ordered among
   themselves by origin-board rank, each row carrying:
       "proj": true, "origin_weight": <wt>
   so the widget can render "(from 106)" instead of implying the position
   was earned against this field. Everything renumbers sequentially.

3. Seniors cannot sneak back in. Moves apply only to wrestlers already on
   the assembled boards, which are post-GRADE_HIDE. A Fargo name absent from
   every board (graduated, or never ranked) is reported, not inserted.

4. Idempotent by construction. A wrestler already at his Fargo weight is a
   no-op, so when carank goes live for 2026-27 and lists kids at their real
   new weights, this step converges to doing nothing -- live season data
   supersedes the projection without any switch to flip.

5. Every move is logged to stdout so the Action log is the audit trail.

Phase 2 (NOT this file): true placement for arrivals via a combined-pool
rerun -- the 106/113 pools are provably connected (Garza-McClurg,
Silva-Villamil edges) -- pending a read of carank_gen.board() internals to
rule out surname collisions (three Silvas at 106-120 alone).
"""
from fargo_weights import (fargo_weight_map, ALIASES, FARGO_CREDENTIALS,
                           ARRIVAL_H2H)

_DIV_RANK = {"Junior": 0, "16U": 1}


def _place_key(cred):
    p = cred["place"]
    return (9 if p == "AA" else int(p), _DIV_RANK.get(cred["division"], 2))


def _seed_arrivals(arrivals, weight):
    """Split arrivals into (seeded, appended) and order the seeded group.

    Seeded: arrivals holding a Fargo AA credential AT this weight, ordered by
    (place, division), then adjusted by folkstyle H2H (H2H beats credential).
    Pull-up: an uncredentialed arrival with a winning H2H over a seeded
    arrival seeds directly above him -- a kid you beat three times cannot be
    seeded over you by a medal (see Garza/Thiago Silva at 120).
    SUNSET is automatic: seeding touches only 'proj' arrivals, and a wrestler
    stops being an arrival the moment live carank lists him at this weight.
    """
    seeded = [r for r in arrivals
              if FARGO_CREDENTIALS.get(r["name"], {}).get("weight") == weight]
    seeded.sort(key=lambda r: _place_key(FARGO_CREDENTIALS[r["name"]]))
    for r in seeded:
        c = FARGO_CREDENTIALS[r["name"]]
        p = c["place"]
        r["seed_reason"] = (f"Fargo {c['division']} "
                            f"{'champ' if p == 1 else ('2nd' if p == 2 else 'AA')}"
                            f" ({weight})")
    rest = [r for r in arrivals if r not in seeded]

    changed = True
    while changed:                       # bounded: each pass only moves up
        changed = False
        # pull-up: uncredentialed arrival with winning H2H over a seeded one
        for r in list(rest):
            for i, s in enumerate(seeded):
                rec = ARRIVAL_H2H.get((r["name"], s["name"]))
                if rec:
                    rest.remove(r)
                    seeded.insert(i, r)
                    r["seed_reason"] = f"H2H {rec} over {s['name']}"
                    changed = True
                    break
            if changed:
                break
        # override: within seeded, winner of a direct H2H sits above the loser
        for i in range(len(seeded)):
            for j in range(i):
                rec = ARRIVAL_H2H.get((seeded[i]["name"], seeded[j]["name"]))
                if rec:
                    w = seeded.pop(i)
                    seeded.insert(j, w)
                    w["seed_reason"] += f"; H2H {rec} over {seeded[j+1]['name']}"
                    changed = True
                    break
            if changed:
                break
    # annotate any direct H2H between seeded arrivals even when the credential
    # order already agrees -- the H2H is the unambiguous justification and the
    # widget should show it (16U gold vs Junior silver is arguable; 3-2 isn't)
    for i in range(len(seeded)):
        for j in range(i + 1, len(seeded)):
            rec = ARRIVAL_H2H.get((seeded[i]["name"], seeded[j]["name"]))
            if rec and f"H2H {rec}" not in seeded[i]["seed_reason"]:
                seeded[i]["seed_reason"] += (f"; H2H {rec} over "
                                             f"{seeded[j]['name']}")
    return seeded, rest


def apply_fargo_moves(boards, verbose=True):
    """boards: {weight:int -> [row dicts with 'name','rank',...]} for BOYS.
    Mutates and returns (boards, report). Rows gain 'proj'/'origin_weight'
    only when moved."""
    fmap = {}
    for flo_name, wt in fargo_weight_map().items():
        fmap[ALIASES.get(flo_name, flo_name)] = wt

    where = {}
    for wt, rows in boards.items():
        for r in rows:
            where[r["name"]] = wt

    moves, stays, absent = [], [], []
    for name, target in sorted(fmap.items()):
        cur = where.get(name)
        if cur is None:
            absent.append((name, target))
        elif cur == target:
            stays.append(name)
        else:
            moves.append((name, cur, target))

    for name, cur, target in moves:
        if target not in boards:
            if verbose:
                print(f"FARGO STEP: skip {name}: no {target} board in this build")
            continue
        rows = boards[cur]
        row = next(r for r in rows if r["name"] == name)
        rows.remove(row)
        row["proj"] = True
        row["origin_weight"] = cur
        boards[target].append(row)
        if verbose:
            print(f"FARGO STEP: {name}: {cur} -> {target} "
                  f"(was #{row['rank']} at {cur})")

    # seeded arrivals above natives; uncredentialed arrivals below, by origin
    # rank; then renumber every board sequentially
    for wt, rows in boards.items():
        natives = [r for r in rows if not r.get("proj")]
        arrivals = [r for r in rows if r.get("proj")]
        seeded, appended = _seed_arrivals(arrivals, wt)
        appended.sort(key=lambda r: (r["rank"], r["origin_weight"]))
        boards[wt] = seeded + natives + appended
        for i, r in enumerate(boards[wt], 1):
            r["rank"] = i
        if verbose:
            for r in seeded:
                print(f"FARGO STEP: seeded #{r['rank']} at {wt}: {r['name']} "
                      f"[{r['seed_reason']}]")

    report = {"moved": [(n, c, t) for n, c, t in moves],
              "stayed": stays, "not_on_boards": absent}
    if verbose:
        print(f"FARGO STEP: {len(report['moved'])} moved, {len(stays)} already "
              f"at Fargo weight, {len(absent)} in Fargo data but not on any "
              f"board (graduated or unranked): "
              f"{', '.join(n for n, _ in absent) or 'none'}")
    return boards, report
