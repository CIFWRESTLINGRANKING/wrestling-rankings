"""
weight_overrides.py - manual 2026-27 weight placements, set by Jeff.

A wrestler listed here is moved to the given board on every build (after the
Fargo projection step, before tournaments are applied). Unlike a Fargo move
he is NOT a 'proj' arrival: he becomes a native of the new board and is
placed by rating, because this is a confirmed placement, not a projection.
Idempotent: a wrestler already on the target board is left alone.
Matching ignores case, accents, spacing and carank's HM/- prefixes.
"""
import re
import unicodedata

# (gender, name) -> weight
OVERRIDES = {
    ("boys", "Paul Ruiz"): 138,     # Jeff, 2026-10-10: Buchanan, wrestling 138 this year
}


def _norm(n):
    n = unicodedata.normalize("NFKD", n or "").encode("ascii", "ignore").decode()
    n = re.sub(r"^\s*(?:HM|-)\s+", "", n)
    return re.sub(r"\s+", " ", n.lower()).strip()


def apply_weight_overrides(data, verbose=True):
    boards = {(b["gender"], b["weight"]): b["wrestlers"] for b in data["weights"]}
    for (gender, name), target in OVERRIDES.items():
        key = _norm(name)
        if (gender, target) not in boards:
            print(f"WEIGHT OVERRIDE: no {gender} {target} board; skip {name}")
            continue
        found = [(w, r) for (g, w), rows in boards.items() if g == gender
                 for r in rows if _norm(r["name"]) == key]
        if not found:
            if verbose:
                print(f"WEIGHT OVERRIDE: {name} not on any {gender} board; nothing to move")
            continue
        if len(found) > 1:
            # keep the copy already at the target (or the first), drop the rest
            keep = next((x for x in found if x[0] == target), found[0])
            for w, r in found:
                if r is not keep[1]:
                    boards[(gender, w)].remove(r)
            found = [keep]
        cur, row = found[0]
        if cur == target:
            continue
        boards[(gender, cur)].remove(row)
        for k in ("proj", "origin_weight", "seed_reason"):
            row.pop(k, None)
        row["weight_source"] = "manual"
        dest = boards[(gender, target)]
        # place by rating
        pos = next((i for i, r in enumerate(dest) if r["rating"] < row["rating"]), len(dest))
        dest.insert(pos, row)
        for rows in (boards[(gender, cur)], dest):
            for n, r in enumerate(rows, 1):
                r["rank"] = n
        if verbose:
            print(f"WEIGHT OVERRIDE: {row['name']}: {cur} -> {target} (#{pos + 1})")
    return data
