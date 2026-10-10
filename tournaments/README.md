# In-season tournament results

Each `.tsv` file here is one tournament. The build (`build_rankings_auto.py`,
via `tournament_ingest.py`) re-applies every file, oldest first, on top of the
carank base on every run. A weekly carank rebuild can no longer erase a
tournament ingest. Committing a new file here triggers a rebuild right away.

File name: `YYYY-MM-DD_<slug>.tsv` (first day of the event).

Header lines, then the TSV:

```
# event: SCWAY World Challenge (Fresno)
# date: 2026-10-10
# source: boutboard tournamentId=fsdtb6kgn7igb8x
# style: folkstyle
# level: varsity
gender  weight  match  round  cons  result  score  w_first  w_last  w_team  l_first  l_last  l_team
```

`result` is one of D, M, T, F, DQ, FF, MF, INJ. The winner is always `w_*`.
Only varsity boys and HS girls belong here (no frosh-soph, JV, MS or youth).
FF, MF and INJ are kept for completeness but are not rated or counted in records.

To get a Boutboard event into this format, use `tools/boutboard_scrape.js`
(steps are in the file).
