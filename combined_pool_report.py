#!/usr/bin/env python3
"""
combined_pool_report.py -- DIAGNOSTIC ONLY. Rates two weight classes as ONE
Glicko pool and prints the combined order. Writes nothing; the Action log is
the entire output.

WHY: cross-board placement (e.g. a 126 wrestler moving to the 132 board) has
no defensible answer inside per-weight pools -- the scales are independent.
But wrestlers DO cross weights during the season (Schoch won Overfelt at 132;
Castaneda won Reno at 132), so adjacent pools share real bouts. Rating the
union puts arrivals and natives on one scale legitimately.

WHY NOT carank_gen.parse DIRECTLY: it keys wrestlers as surname|team, which
collides for Jackson Humphrey (126, Sultana) vs Cael Humphrey (132, Sultana).
This script resolves opponents with first-initial awareness and DROPS bouts
it cannot resolve unambiguously, reporting the count -- a dropped bout is
honest; a fused phantom wrestler is not.

Usage: python3 combined_pool_report.py [wt_a] [wt_b]   (default: 126 132)
"""
import re, sys
from collections import defaultdict

import carank_auto as A
import carank_gen as G
from grad_overrides import is_graduated
from wrestling_rating_engine import Bout, RatingEngine, Config

WT_A = int(sys.argv[1]) if len(sys.argv) > 1 else 126
WT_B = int(sys.argv[2]) if len(sys.argv) > 2 else 132
OFFSET = 100  # renumber second page's ranks so BLOCK marks stay unique


def first_initial(name):
    name = (name or "").strip()
    return name[0].upper() if name else ""


def load(wt, rank_offset=0):
    text = A.html_to_text(A.fetch_page(wt))
    if rank_offset:
        text = G.BLOCK_RE.sub(
            lambda m: "- **#%d**" % (int(m.group(1)) + rank_offset), text)
    roster = A.extract_roster(text)   # ranks reflect the (renumbered) marks
    return text, roster


def main():
    text_a, roster_a = load(WT_A)
    text_b, roster_b = load(WT_B, OFFSET)
    print(f"pool {WT_A}: {len(roster_a)} roster | pool {WT_B}: {len(roster_b)} roster")

    wrestlers = {}
    by_surteam = defaultdict(list)
    def register(rk, nm, gr, sc, wt):
        wid = f"{first_initial(nm)}{G.surname(nm)}|{G.canon_team(sc)}"
        wrestlers[wid] = dict(name=nm, team=sc, grade=gr, weight=wt)
        by_surteam[(G.surname(nm), G.canon_team(sc))].append(wid)
        return wid
    for rk, nm, gr, sc in roster_a: register(rk, nm, gr, sc, WT_A)
    for rk, nm, gr, sc in roster_b: register(rk, nm, gr, sc, WT_B)

    collisions = {k: v for k, v in by_surteam.items() if len(set(v)) > 1}
    for (sur, tm), wids in collisions.items():
        print(f"COLLISION surname+team '{sur}|{tm}': "
              f"{[wrestlers[w]['name'] for w in set(wids)]} -- "
              f"resolving by first initial; initial-less bouts dropped")

    by_sur = defaultdict(set)
    for wid, w in wrestlers.items():
        by_sur[G.surname(w["name"])].add(wid)

    def resolve(opp, team):
        sur, tm = G.surname(opp), G.canon_team(team)
        cands = [w for w in by_sur.get(sur, ())
                 if w.split("|")[1] == tm] or list(by_sur.get(sur, ()))
        if not cands:
            return "external"
        if len(cands) == 1:
            return cands[0]
        ini = first_initial(opp)
        exact = [w for w in cands if w.startswith(ini)]
        return exact[0] if len(exact) == 1 else None

    bouts, seen = [], set()
    dropped_ambig = ext = 0
    for text, roster, wt in ((text_a, roster_a, WT_A), (text_b, roster_b, WT_B)):
        marks = list(G.BLOCK_RE.finditer(text))
        roster_by_rank = {rk: (nm, gr, sc) for rk, nm, gr, sc in roster}
        for i, mk in enumerate(marks):
            rank = int(mk.group(1))
            if rank not in roster_by_rank:
                continue
            nm, gr, sc = roster_by_rank[rank]
            swid = f"{first_initial(nm)}{G.surname(nm)}|{G.canon_team(sc)}"
            seg = re.sub(r"\s+", " ",
                         text[mk.end(): marks[i+1].start() if i+1 < len(marks)
                              else len(text)])
            for m in G.BOUT_RE.finditer(seg):
                owid = resolve(m.group("opp"), m.group("team"))
                if owid == "external":
                    ext += 1; continue
                if owid is None:
                    dropped_ambig += 1; continue
                if owid == swid:
                    continue
                win, los = (swid, owid) if m.group("wl") == "d" else (owid, swid)
                method = G.classify(m.group("score"))
                key = (frozenset((win, los)), m.group("ev"), method)
                if key in seen:
                    continue
                seen.add(key)
                bouts.append(Bout(m.group("ev"), G.DAY.get(m.group("ev"), 120),
                                  0, win, los, method, "?", "?"))
    print(f"bouts ingested: {len(bouts)} | cross-only external skipped: {ext} "
          f"| dropped ambiguous (collision, no initial): {dropped_ambig}")

    bridge = sum(1 for b in bouts
                 if b.winner in wrestlers and b.loser in wrestlers
                 and wrestlers[b.winner]["weight"] != wrestlers[b.loser]["weight"])
    print(f"CROSS-POOL BRIDGE BOUTS ({WT_A}<->{WT_B}): {bridge}")
    if bridge == 0:
        print("NO BRIDGES: combined ordering is NOT meaningful across pools. "
              "Report below is per-pool order only; do not use it for placement.")

    eng = RatingEngine(Config()); eng.ingest(bouts)
    wl = defaultdict(lambda: [0, 0])
    for b in bouts:
        wl[b.winner][0] += 1; wl[b.loser][1] += 1

    print(f"\n=== COMBINED {WT_A}+{WT_B} ORDER (returners only, engine order) ===")
    rk = 0
    for w in eng.rankings():
        info = wrestlers.get(w.wid)
        if not info: continue
        if info["grade"] == "Sr" or is_graduated(info["name"]): continue
        rk += 1
        wr, ls = wl[w.wid]
        print(f"#{rk:>3} [{info['weight']}] {info['name']:<24} "
              f"{info['team'][:16]:<16} {info['grade']:<2} {wr}-{ls} "
              f"R{round(w.rating)}\u00b1{round(w.rd)}")


if __name__ == "__main__":
    main()
