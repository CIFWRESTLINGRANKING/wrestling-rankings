# Automated Weekly Rankings (carank pull)

This is a turnkey, hands-off weekly rebuild of the **boys** boards from the live
carank pages. It replaces the old workflow where pages were hand-condensed each
session: now the job fetches carank directly, extracts the roster **and** the
bouts from the page itself, recomputes ratings, and updates `rankings.json` —
with no human in the loop.

## What goes where in your repo

Drop these into the **root** of your `wrestling-rankings` repo:

```
wrestling_rating_engine.py        (the Glicko engine - you already have this)
carank_gen.py                     (the proven bout parser/linker - you already have this)
carank_auto.py                    (NEW: self-contained roster+bout extractor)
build_rankings_auto.py            (NEW: loops 14 weights, writes rankings.json)
rankings.json                     (your live board file - already in the repo)
.github/workflows/weekly-rankings.yml   (NEW: the weekly schedule)
```

That's it. No `pip install` — everything is Python standard library.

## How it behaves (this is the important part)

**It runs every Sunday (13:00 UTC ≈ 5–6am Pacific)** and can also be run on demand
from the repo's **Actions** tab ("Run workflow").

Three guardrails make it honest instead of just busy:

1. **Change detection.** It only commits if `rankings.json` actually changed.
   While carank is stamped **FINAL** (offseason, like right now), every rebuild
   produces identical output, no diff is found, and **nothing is committed**. No
   fake "updated" commits. The moment carank goes live for 2026-27, the boards
   start moving automatically.

2. **Honesty guard.** If carank is blocked, empty, or its format changed, a weight
   returns 0 bouts and is **skipped — its existing board is left untouched.** If
   fewer than 10 of 14 weights succeed, the whole run **exits non-zero and shows a
   red X**, committing nothing, rather than publishing a broken or half-built board.

3. **Truth stamp.** Every successful build writes `generated` (UTC timestamp) and
   `source` into `rankings.json`, so the live file always tells you when and from
   what it was last built. Check those fields anytime to know if the board is fresh.

## The one thing to verify on the first real run

I could not test the live fetch from here (my build environment can't reach
external sites). carank is a static Neocities site with no bot-detection we've
seen, so an open GitHub runner should reach it fine — but **the first scheduled
run (or a manual "Run workflow") is the real test.** If that run goes green and
commits (once carank is live) or goes green with "nothing to commit" (while FINAL),
the fetch works. If it goes red with "0 bouts" across weights, carank changed its
page format or blocked the runner, and the parser front-end (`carank_auto.py`,
`html_to_text` / `extract_roster`) would need a tweak — but your existing board is
safe either way, because the guard never overwrites it on failure.

To test now without waiting for Sunday: push these files, open **Actions →
Weekly Rankings Rebuild → Run workflow**. While carank is FINAL you should see a
green run that says "No change… nothing to commit" — that confirms the fetch and
parse work end to end.

## Known rough edge

Roster names are extracted from the page and de-glued automatically
(`MichaelBernabe` → `Michael Bernabe`), with Mc/Mac names protected. Unusual
multi-part or hyphenated names are the most likely to need a look on first live
run. Grades drive the senior-hide (graduated seniors stay in the rating math but
are hidden from the displayed board), so a stale grade on carank would mis-show a
wrestler — same caveat as before, worth a spot-check when the season opens.

## Still on the to-do list (unchanged by this)

- Relabel the widget's "Record" column to "H2H (tracked)" — records reflect only
  carank-ingested bouts, not full season records. (Pending next widget rewrite.)
- Girls boards remain placeholders (carank has no girls data).
- This pulls boys only, since that's what carank covers.
