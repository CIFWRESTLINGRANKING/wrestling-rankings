#!/usr/bin/env python3
"""
build_rankings_auto.py - unattended weekly rebuild of the boys boards from LIVE carank.

Run by the GitHub Action. For each boys weight it fetches the live carank page,
extracts roster+bouts, recomputes ratings, and splices the result into rankings.json.

SAFETY GUARDS (the whole point - so the job can't silently lie):
  * HONESTY GUARD: if a weight returns 0 bouts (fetch blocked / page moved / format
    changed), that weight is SKIPPED and its existing board is left untouched - the
    job never publishes an empty or half-built board. If too many weights fail, it
    exits non-zero so the Action shows red instead of committing garbage.
  * CHANGE DETECTION: the caller (workflow) only commits if rankings.json actually
    changed, so a frozen/FINAL carank produces no commits (no fake "updated" noise).
  * STAMP: writes 'generated' (UTC) and 'source' so the live JSON always tells the
    truth about when and from what it was last built.

Usage:  python3 build_rankings_auto.py [path/to/rankings.json]
Exit codes: 0 = ok (built or legitimately unchanged), 1 = too many weights failed.
"""
import json, sys, datetime
import carank_auto as A

BOYS_WEIGHTS = [106, 113, 120, 126, 132, 138, 144, 150, 157, 165, 175, 190, 215, 285]
MIN_OK_WEIGHTS = 10          # require most weights to succeed or fail the run loudly
OUT = sys.argv[1] if len(sys.argv) > 1 else "rankings.json"


def main():
    data = json.load(open(OUT, encoding="utf-8"))
    by_key = {(b["gender"], b["weight"]): b for b in data["weights"]}

    ok, failed, total_bouts = [], [], 0
    for wt in BOYS_WEIGHTS:
        try:
            rows, n_bouts, n_roster = A.board_auto(wt)
        except Exception as e:
            failed.append((wt, f"fetch/parse error: {e}"))
            print(f"  {wt:>3}: FAIL - {e}")
            continue
        if n_bouts == 0 or not rows:
            failed.append((wt, "0 bouts (blocked/empty/format change)"))
            print(f"  {wt:>3}: SKIP - 0 bouts; leaving existing board untouched")
            continue
        key = ("boys", wt)
        if key in by_key:
            by_key[key]["wrestlers"] = rows
        else:
            data["weights"].append({"gender": "boys", "weight": wt, "wrestlers": rows})
        total_bouts += n_bouts
        ok.append(wt)
        print(f"  {wt:>3}: ok - {n_roster} roster, {n_bouts} bouts, {len(rows)} shown")

    if len(ok) < MIN_OK_WEIGHTS:
        print(f"\nHONESTY GUARD TRIPPED: only {len(ok)}/{len(BOYS_WEIGHTS)} weights "
              f"succeeded (need >= {MIN_OK_WEIGHTS}). NOT writing rankings.json.")
        print("Failures:", failed)
        return 1

    data["generated"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    data["source"] = "carank.neocities.org (automated)"
    json.dump(data, open(OUT, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"\nWrote {OUT}: {len(ok)} weights updated, {total_bouts} total bouts, "
          f"{len(failed)} skipped.")
    if failed:
        print("Skipped (left untouched):", failed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
