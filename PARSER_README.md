# CalGrappler parser → Bout objects

Turns a CalGrappler tournament results page into `Bout` records for the rating
engine, so you stop hand-entering matches.

## Files
- `calgrappler_parser.py` — the parser (stdlib only; `requests` needed only for live fetch).
- `test_parser.py` — runs it on real Doc Buchanan text and checks the tricky cases.

## The whole pipeline
```python
from calgrappler_parser import parse_calgrappler, fetch_url
from wrestling_rating_engine import RatingEngine, Config

text  = fetch_url("https://www.calgrappler.com/2026-doc-buchanan-invitational-results/")
bouts = parse_calgrappler(text, event_id="DOCB", day=100, weight_pool={129: 126})

eng = RatingEngine(Config())
eng.ingest(bouts)
for i, w in enumerate(eng.rankings(as_of_day=101)[:40], 1):
    print(i, w.wid, round(w.rating))
```
Run `parse_calgrappler(..., return_parsed=True)` to get `ParsedBout` objects that
also carry the raw source line and an `.inferred` flag (see below) for auditing.

## What it does
- **Tracks weight** from section headers (`### 129`, `**141**`, or a bare `168`)
  and attaches it to every following match.
- **Reads pairwise match lines** from the Finals / Semi-Final / Quarter-Final
  sections. The winner is always listed first (the universal results convention),
  which is how W/L is assigned.
- **Resolves messy result codes**: `TF`→tech, `MD`→major, `DEC`/`dec.`→decision,
  `F`/`fall`→fall, `MFF`/`mfor`→forfeit, `DQ`→dq. A generic `def.`/`DEF` is
  resolved from the trailing text — an explicit method word wins, otherwise the
  score margin is used (≥15 → tech, 8–14 → major, else decision). Margin-based
  calls are flagged `inferred=True` so you can audit them.
- **Tags out-of-state wrestlers** from a trailing `(PA)`/`(OK)`/… ; California
  teams have no state tag, so absence ⇒ CA (`section="CA"`). Rate everyone, then
  filter the leaderboard to `section == "CA"`.
- **Optional weight pooling** (`weight_pool={129: 126}`) because kids shift a few
  pounds in-season; 126/127/129 are the same competitive class.
- **Skips** placer lists and pre-seed lists on purpose — they aren't clean
  pairwise bouts and would double-count matches already in the round sections.

## Known limits (be honest about these)
- Built for CalGrappler's layout. Other sources (tech-fall's `A vs. B (DEC 6-1)`,
  Yahoo/Flo's `126 A TF B, 20-4`) need their own small adapters — same idea,
  different line shape.
- **Identity resolution is by `name + team` slug.** Spelling variants
  ("Issac"/"Isaac", "St. John Bosco"/"Bosco") still produce different IDs. This
  is the single biggest real-world data problem; a name-alias table is the next
  piece to build.
- Margin-inferred major/tech can be wrong when a result is reported oddly; trust
  explicit `MD`/`TF` over inference, and review `.inferred` rows.
- Dual-meet results mostly aren't on CalGrappler at all — that gap is unchanged.

## Two bugs caught by `test_parser.py` (kept as regression checks)
1. `dec.`/`def.` lines (the most common result) were dropped because the
   separator pattern didn't allow a trailing period. Fixed.
2. The last wrestler on a line had the trailing score (`, 7-1`) leaking into
   their team/ID, so the same wrestler got different IDs in different matches.
   Fixed by cutting at the first comma before parsing the team.
