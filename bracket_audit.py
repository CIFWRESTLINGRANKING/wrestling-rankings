"""
Data-completeness audit — catch missing backside/consolation bouts everywhere
=============================================================================
The Torres problem (placed 7th, but 0 losses in our data) has a clean tell:
at a tournament, ONLY the champion goes undefeated. Any other wrestler showing
zero losses has losses we didn't ingest — almost always consolation-bracket
matches the free recaps skip.

This runs on every board so the gap is surfaced as a visible flag for backfill
instead of silently inflating a ranking. It tags each suspect wrestler with
`incomplete=True` (the widget can mark them) and returns a per-board report.

Signals:
  * undefeated but not #1  -> missing backside losses (the Torres case)
  * only 0-1 bouts in data -> rating rests on almost nothing
"""


def audit_board(board):
    """Tag suspect wrestlers in-place; return list of (rank, name, record, why)."""
    flags = []
    seen = {}
    for w in board.get("wrestlers", []):
        seen.setdefault(w["name"], []).append(w["rank"])
    dupes = {n: rks for n, rks in seen.items() if len(rks) > 1}
    for w in board.get("wrestlers", []):
        try:
            wins, losses = (int(x) for x in w["record"].split("-"))
        except (ValueError, KeyError):
            continue
        ffw = w.get("ffw", 0)          # forfeit/injury wins (padding)
        why = []
        if w["name"] in dupes:
            why.append(f"DUPLICATE — same name at ranks {dupes[w['name']]} "
                       f"(identity split); merge")
        if losses == 0 and w["rank"] > 1:
            # an injury default can leave a real 0-loss line, so don't assert
            # "missing data" outright — flag for verification either way.
            if ffw:
                why.append(f"0 losses but {ffw} win(s) by forfeit/injury default "
                           f"— verify (injured-out, or backside loss missing)")
            else:
                why.append("undefeated but not #1 — missing backside loss, "
                           "or an injury default not recorded as a loss")
        elif ffw and wins and ffw >= wins:
            why.append(f"record padded by {ffw} forfeit/injury win(s) — thin real evidence")
        if wins + losses <= 1:
            why.append(f"only {wins + losses} bout in data — low confidence")
        if why:
            w["incomplete"] = True
            flags.append((w["rank"], w["name"], w["record"], "; ".join(why)))
    return flags


def audit_all(boards):
    """Audit every board; print a report and return {(gender,weight): flags}."""
    report = {}
    print("\nDATA-COMPLETENESS AUDIT  (backfill checklist for next iteration)")
    print("-" * 64)
    total = 0
    for bd in boards:
        flags = audit_board(bd)
        if not flags:
            continue
        report[(bd["gender"], bd["weight"])] = flags
        total += len(flags)
        print(f"  {bd['gender']} {bd['weight']}:")
        for rank, name, rec, why in flags:
            print(f"    #{rank:<2} {name:<20} {rec:<5} {why}")
    print(f"\n  {total} wrestlers flagged for backside/sample backfill.")
    print("  (Champions and wrestlers with real losses in-data are NOT flagged.)")
    return report
