#!/usr/bin/env python3
"""
tournament_ingest.py - fold in-season tournament results (Boutboard etc.) into
the boards on EVERY build, from data files committed under tournaments/.

WHY THIS EXISTS
  The weekly Action rebuilds the boards from carank. Before this module, any
  tournament ingest done by hand (Gilroy, Sept 2026) lived only in the
  committed rankings.json, so the next Sunday rebuild silently threw it away
  (that is exactly what happened on 2026-09-13). Tournament results now live
  as data (tournaments/*.tsv) and are re-applied deterministically on top of
  the carank base every time the board is built. Nothing is lost on rebuild.

DATA FILE FORMAT  (tournaments/YYYY-MM-DD_<slug>.tsv)
  '# key: value' header lines (event, date, source, style, level), then a TSV
  with columns:
    gender weight match round cons result score
    w_first w_last w_team l_first l_last l_team
  result codes: D (decision) M (major) T (tech fall) F (fall) DQ,
                FF (forfeit) MF (medical forfeit) INJ (injury default)
  Winner is always the w_* wrestler.

IDENTITY (the fix for the first-initial+surname key)
  Boutboard gives FULL first and last names, so the primary key is the full
  normalized name (accents, case, punctuation, Jr/III suffixes and carank's
  HM/- prefixes removed; a parenthetical nickname like "Jonah (Helo)" yields
  both names as candidates). Only if there is no exact full-name hit do we try
  a fuzzy match: same gender, same surname, first name within edit distance 1
  or sharing a 3-letter prefix, AND exactly one such board wrestler. Club
  names (Bay Area Dragons WC) are not school names, so team is used only to
  break a tie between several same-name board wrestlers, never required.
  Every non-exact match is printed so the Action log is the audit trail.

RATING (one Glicko-2 rating period per event, two passes)
  Board wrestlers start from their board rating/RD; everyone else starts at
  1500/350. sigma = 0.06 for all (rankings.json does not persist volatility).
  No RD aging (consistent with the CAUSAW/Fargo ingests).
  Pass 1: every participant updated simultaneously from pre-event snapshots.
          Non-board entrants keep their pass-1 result.
  Pass 2: board wrestlers re-updated, using non-board opponents' PASS-1
          ratings/RDs instead of the 1500/350 prior, so beating an unknown kid
          who turned out to be good counts as beating a good kid.
  Bout weights: decision 1.0, major 1.15, tech fall 1.30, fall 1.30 (tech and
  pin weigh the same), DQ 1.0. Forfeits, medical forfeits and injury defaults
  are not contested bouts and are excluded from ratings AND records.
  Style weight from the file's '# style:' header via Config.style_weights:
  folkstyle 1.0, freestyle 0.65, greco 0.55 (multiplies the bout weight).

BOARD ENTRY (evidence-based, replaces the RD<150 statistical gate)
  A non-board entrant who wins at least one contested bout over a board
  wrestler of the same gender at a varsity FOLKSTYLE event ('# level: varsity',
  '# style: folkstyle') is placed on the board at
  the weight he/she competed at, flagged provisional with
  weight_source="competed_unconfirmed". Others with RD < 200 go to the watch
  list.

ORDER
  On any board that gained a result, rows are ordered by rating (ties: lower
  RD), then graded head-to-head from the tournament bouts: a win reorders an
  adjacent pair when the rating gap is within the result's allowance
  (decision 50, major 100, tech/fall 175). Fargo weight-move rows ('proj')
  are ordered by rating like everyone else (Jeff, 2026-10-10); a Fargo
  medal at a new weight no longer seeds anyone to the top. Untouched boards
  keep their existing order. Everything renumbers sequentially.
"""
import glob
import math
import os
import re
import unicodedata
from collections import Counter, defaultdict

from wrestling_rating_engine import SCALE, BASE_RATING, Config, Wrestler, _update_one

BASE_RD = 350.0
SIGMA = 0.06
RESULT_WEIGHT = {"D": 1.00, "M": 1.15, "T": 1.30, "F": 1.30, "DQ": 1.00}
NON_CONTESTED = {"FF", "MF", "INJ"}
H2H_ALLOWANCE = {"D": 50, "DQ": 50, "M": 100, "T": 175, "F": 175}
WATCH_RD_MAX = 200
SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}
PREFIX_RE = re.compile(r"^\s*(?:HM|-)\s+")

COLS = ["gender", "weight", "match", "round", "cons", "result", "score",
        "w_first", "w_last", "w_team", "l_first", "l_last", "l_team"]


# --------------------------------------------------------------------------- #
# names
# --------------------------------------------------------------------------- #
def _ascii(s):
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()


def _tokens(s):
    s = _ascii(s).lower().replace("-", " ")
    s = re.sub(r"[^a-z ]", " ", s)
    return [t for t in s.split() if t and t not in SUFFIXES]


def strip_prefix(name):
    """carank roster names can carry the last-week token ('HM', '-')."""
    return PREFIX_RE.sub("", name or "").strip()


def name_keys(first, last):
    """All normalized full-name keys for a wrestler. A parenthetical in the
    first name ('Jonah (helo)') yields keys for both names."""
    nick = re.findall(r"\(([^)]*)\)", first or "")
    base_first = re.sub(r"\([^)]*\)", " ", first or "")
    lt = _tokens(last)
    keys = []
    for f in [base_first] + nick:
        ft = _tokens(f)
        if ft and lt:
            keys.append(" ".join(ft + lt))
            keys.append(" ".join(ft[:1] + lt))   # drop middle names
    return list(dict.fromkeys(keys))


def board_name_keys(full):
    toks = _tokens(strip_prefix(full))
    if len(toks) < 2:
        return [" ".join(toks)] if toks else []
    keys = [" ".join(toks)]
    # "Julius Mark Villamil" -> also "julius villamil"; two-word surnames kept
    keys.append(f"{toks[0]} {toks[-1]}")
    if len(toks) >= 3:
        keys.append(" ".join([toks[0]] + toks[-2:]))
    return list(dict.fromkeys(keys))


def _edit1(a, b):
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    if len(a) > len(b):
        a, b = b, a
    i = j = d = 0
    while i < len(a) and j < len(b):
        if a[i] != b[j]:
            d += 1
            j += 1
            if d > 1:
                return False
        else:
            i += 1
            j += 1
    return True


def _team_tokens(t):
    stop = {"wc", "wa", "hs", "high", "school", "the", "rtc", "tc", "elite", "club"}
    return {x for x in _tokens(t) if x not in stop and len(x) > 2}


def _load_aliases(folder):
    """tournaments/name_aliases.txt: 'Name As Printed = Board Name' per line,
    for identities Jeff has confirmed. Confirmed aliases match exactly and are
    no longer logged as fuzzy."""
    path = os.path.join(folder, "name_aliases.txt")
    out = {}
    if os.path.exists(path):
        for l in open(path, encoding="utf-8"):
            l = l.split("#")[0]
            if "=" in l:
                a, b = (x.strip() for x in l.split("=", 1))
                if a and b:
                    out[" ".join(_tokens(a))] = b
    return out


def _norm_team(t):
    return " ".join(_ascii(t or "").lower().split())


def _load_out_of_state(folder):
    """tournaments/out_of_state_teams.txt: one team/club name per line ('#'
    comments allowed). Their wrestlers are still rated (they are real
    opponents) but never enter a California board or the watch list."""
    path = os.path.join(folder, "out_of_state_teams.txt")
    if not os.path.exists(path):
        return set()
    return {_norm_team(l.split("#")[0]) for l in open(path, encoding="utf-8")
            if l.split("#")[0].strip()}


# --------------------------------------------------------------------------- #
# data files
# --------------------------------------------------------------------------- #
def load_event(path):
    meta, rows = {}, []
    header = None
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
        r = dict(zip(header, f))
        r["weight"] = int(float(r["weight"]))
        rows.append(r)
    meta.setdefault("date", os.path.basename(path)[:10])
    meta.setdefault("event", os.path.basename(path))
    meta["path"] = path
    return meta, rows


def load_all(folder="tournaments"):
    events = [load_event(p) for p in sorted(glob.glob(os.path.join(folder, "*.tsv")))]
    events.sort(key=lambda e: e[0]["date"])
    return events


# --------------------------------------------------------------------------- #
# identity resolution
# --------------------------------------------------------------------------- #
class Resolver:
    def __init__(self, boards, log):
        """boards: {(gender, weight): [rows]}"""
        self.log = log
        self.by_key = defaultdict(list)          # (gender, key) -> [(g, w, row)]
        self.by_surname = defaultdict(list)      # (gender, last tok) -> [...]
        for (g, w), rows in boards.items():
            for r in rows:
                ent = (g, w, r)
                for k in board_name_keys(r["name"]):
                    self.by_key[(g, k)].append(ent)
                toks = _tokens(strip_prefix(r["name"]))
                if toks:
                    self.by_surname[(g, toks[-1])].append(ent)
        self.cache = {}
        self.aliases = {}

    @staticmethod
    def _uniq(ents):
        seen, out = set(), []
        for e in ents:
            if id(e[2]) not in seen:
                seen.add(id(e[2]))
                out.append(e)
        return out

    def resolve(self, gender, first, last, team):
        ck = (gender, first, last, team)
        if ck in self.cache:
            return self.cache[ck]
        res = self._resolve(gender, first, last, team)
        self.cache[ck] = res
        return res

    def _resolve(self, gender, first, last, team):
        label = f"{first} {last} ({team})"
        alias = self.aliases.get(" ".join(_tokens(f"{first} {last}")))
        if alias:
            first, last = alias.split(" ", 1)
        for k in name_keys(first, last):
            ents = self._uniq(self.by_key.get((gender, k), []))
            if len(ents) == 1:
                return ents[0]
            if len(ents) > 1:
                tt = _team_tokens(team)
                hit = [e for e in ents if tt & _team_tokens(e[2].get("team", ""))]
                if len(hit) == 1:
                    self.log(f"  MATCH (team tiebreak) {label} -> {hit[0][2]['name']} "
                             f"[{hit[0][1]}]")
                    return hit[0]
                self.log(f"  AMBIGUOUS {label}: {[e[2]['name'] for e in ents]} "
                         f"-> treated as non-board")
                return None
        # fuzzy: same surname, first name within edit 1 or same 3-letter prefix
        lt = _tokens(last)
        ft = _tokens(re.sub(r"\([^)]*\)", " ", first or ""))
        if not lt or not ft:
            return None
        cands = []
        for e in self._uniq(self.by_surname.get((gender, lt[-1]), [])):
            btoks = _tokens(strip_prefix(e[2]["name"]))
            if len(btoks) < 2:
                continue
            bf = btoks[0]
            if _edit1(bf, ft[0]) or (len(bf) >= 3 and bf[:3] == ft[0][:3]):
                cands.append(e)
        if len(cands) == 1:
            self.log(f"  MATCH (fuzzy) {label} -> {cands[0][2]['name']} "
                     f"({cands[0][2].get('team','')}) [{cands[0][1]}]")
            return cands[0]
        if len(cands) > 1:
            self.log(f"  AMBIGUOUS (fuzzy) {label}: {[e[2]['name'] for e in cands]}")
        return None


# --------------------------------------------------------------------------- #
# glicko helpers
# --------------------------------------------------------------------------- #
def _w(rating, rd):
    return Wrestler("x", mu=(rating - BASE_RATING) / SCALE, phi=rd / SCALE, sigma=SIGMA)


def _period(states, bouts, cfg, opp_override=None):
    """One Glicko-2 period. states: id -> (rating, rd). bouts: [(win, los, wt)].
    opp_override: id -> (rating, rd) used as the OPPONENT snapshot for those ids.
    Returns id -> (rating, rd) for every participant."""
    snap = {}
    for i, (r, d) in states.items():
        if opp_override and i in opp_override:
            r, d = opp_override[i]
        snap[i] = ((r - BASE_RATING) / SCALE, d / SCALE)
    games = defaultdict(list)
    for win, los, wt in bouts:
        games[win].append((snap[los], 1.0, wt))
        games[los].append((snap[win], 0.0, wt))
    out = {}
    for i, g in games.items():
        w = _w(*states[i])
        mu, phi, _ = _update_one(w, [x[0] for x in g], [x[1] for x in g],
                                 [x[2] for x in g], cfg)
        out[i] = (mu * SCALE + BASE_RATING, phi * SCALE)
    return out


def _add_record(rec, w, l):
    try:
        a, b = (int(x) for x in (rec or "0-0").split("-"))
    except ValueError:
        a, b = 0, 0
    return f"{a + w}-{b + l}"


# --------------------------------------------------------------------------- #
# main entry
# --------------------------------------------------------------------------- #
def apply_tournaments(data, folder="tournaments", verbose=True):
    """Mutates data (the rankings.json dict). Returns a report dict."""
    log = print if verbose else (lambda *a, **k: None)
    cfg = Config()
    events = load_all(folder)
    if not events:
        log("TOURNAMENTS: no data files; nothing applied")
        return {"events": []}

    boards = {(b["gender"], b["weight"]): b["wrestlers"] for b in data["weights"]}
    for rows in boards.values():
        for r in rows:
            r["name"] = strip_prefix(r["name"])

    entrants = {}            # eid -> dict(state, wins_over_board, weights Counter, ...)
    touched = set()
    h2h = {}                 # (id(winner_row), id(loser_row)) -> (date, result)
    report = {"events": []}

    for meta, rows in events:
        log(f"TOURNAMENT {meta['date']} {meta['event']}: {len(rows)} bouts in file")
        res = Resolver(boards, log)
        res.aliases = _load_aliases(folder)
        ids, row_of, states = {}, {}, {}

        def ident(g, wt, first, last, team):
            ent = res.resolve(g, first, last, team)
            if ent:
                row = ent[2]
                i = ("B", id(row))
                row_of[i] = (ent[0], ent[1], row)
                states.setdefault(i, (float(row["rating"]), float(row["rd"])))
                return i
            key = (g, (name_keys(first, last) or [f"{first} {last}".lower()])[0])
            i = ("E",) + key
            if i not in entrants:
                entrants[i] = {"gender": g, "first": first, "last": last,
                               "team": team, "rating": BASE_RATING, "rd": BASE_RD,
                               "w": 0, "l": 0, "board_wins": [],
                               "weights": Counter()}
            entrants[i]["weights"][wt] += 1
            if team and team.strip().upper() not in ("CA", "NONE", "UNATTACHED", ""):
                entrants[i]["team"] = team          # latest real club/school wins
            states.setdefault(i, (entrants[i]["rating"], entrants[i]["rd"]))
            return i

        style = meta.get("style", "folkstyle").lower()
        style_w = cfg.style_weights.get(style)
        if style_w is None:
            raise ValueError(f"{meta['path']}: unknown style '{style}'")
        # only a varsity folkstyle event can put a new wrestler on a board
        entry_ok = (meta.get("level", "").lower() == "varsity" and style == "folkstyle")

        bouts, skipped = [], Counter()
        for b in rows:
            if b["result"] in NON_CONTESTED:
                skipped[b["result"]] += 1
                continue
            wt = RESULT_WEIGHT.get(b["result"])
            if wt is None:
                skipped["unknown:" + b["result"]] += 1
                continue
            wt *= style_w
            g = b["gender"]
            wi = ident(g, b["weight"], b["w_first"], b["w_last"], b["w_team"])
            li = ident(g, b["weight"], b["l_first"], b["l_last"], b["l_team"])
            if wi == li:
                skipped["self"] += 1
                continue
            bouts.append((wi, li, wt, b))

        simple = [(w, l, wt) for w, l, wt, _ in bouts]
        p1 = _period(states, simple, cfg)
        ent_p1 = {i: v for i, v in p1.items() if i[0] == "E"}
        p2 = _period(states, simple, cfg, opp_override=ent_p1)

        n_board = 0
        for i, (r, d) in p2.items():
            if i[0] != "B":
                continue
            g, wt, row = row_of[i]
            row["rating"], row["rd"] = round(r), round(d)
            touched.add((g, wt))
            n_board += 1
        for i, (r, d) in ent_p1.items():
            entrants[i]["rating"], entrants[i]["rd"] = r, d

        # records + H2H + board wins
        rec = defaultdict(lambda: [0, 0])
        for wi, li, wt, b in bouts:
            rec[wi][0] += 1
            rec[li][1] += 1
            if wi[0] == "B" and li[0] == "B":
                h2h[(wi[1], li[1])] = (meta["date"], b["result"])
            if entry_ok and wi[0] == "E" and li[0] == "B":
                entrants[wi]["board_wins"].append(
                    (row_of[li][2]["name"], b["result"], b["score"], meta["event"]))
        for i, (w, l) in rec.items():
            if i[0] == "B":
                row = row_of[i][2]
                row["record"] = _add_record(row.get("record"), w, l)
            else:
                entrants[i]["w"] += w
                entrants[i]["l"] += l

        report["events"].append({"event": meta["event"], "date": meta["date"],
                                 "style": style,
                                 "bouts_rated": len(bouts),
                                 "board_wrestlers_updated": n_board,
                                 "excluded": dict(skipped)})
        log(f"  rated {len(bouts)} contested bouts; {n_board} board wrestlers updated; "
            f"excluded {dict(skipped)}")

    # ---- board entry for entrants with a win over a board wrestler ----------
    oos = _load_out_of_state(folder)
    promoted, watch = [], []
    for i, e in entrants.items():
        name = f"{e['first']} {e['last']}".strip()
        if _norm_team(e["team"]) in oos:
            if e["board_wins"]:
                log(f"  ENTRY skipped {name} ({e['team']}): out-of-state team")
            continue
        cw = e["weights"].most_common(1)[0][0]
        if e["board_wins"]:
            key = (e["gender"], cw)
            if key not in boards:
                log(f"  ENTRY skipped {name}: no {e['gender']} {cw} board")
                continue
            boards[key].append({
                "rank": None, "name": name, "team": e["team"], "section": "",
                "grade": "", "record": f"{e['w']}-{e['l']}",
                "rating": round(e["rating"]), "rd": round(e["rd"]),
                "provisional": True, "weight_source": "competed_unconfirmed",
                "entry_reason": "beat " + "; ".join(
                    f"{n} ({r} {s}, {ev})" for n, r, s, ev in e["board_wins"])})
            touched.add(key)
            promoted.append((e["gender"], cw, name))
            log(f"  ENTRY {e['gender']} {cw}: {name} ({e['team']}) "
                f"R{round(e['rating'])}±{round(e['rd'])} - beat "
                f"{', '.join(n for n, *_ in e['board_wins'])}")
        elif e["rd"] < WATCH_RD_MAX:
            watch.append({"name": name, "gender": e["gender"], "competed_weight": cw,
                          "team": e["team"], "rank": None,
                          "rating": round(e["rating"]), "rd": round(e["rd"]),
                          "record": f"{e['w']}-{e['l']}",
                          "weight_source": "competed_unconfirmed",
                          "status": "provisional"})

    # ---- reorder touched boards -------------------------------------------
    def allowance_ok(winner, loser):
        rec = h2h.get((id(winner), id(loser)))
        if not rec:
            return False
        return loser["rating"] - winner["rating"] <= H2H_ALLOWANCE.get(rec[1], 50)

    for key in touched:
        rows = boards[key]
        mid = list(rows)
        mid.sort(key=lambda r: (-r["rating"], r["rd"]))
        for _ in range(8):
            swapped = False
            for k in range(len(mid) - 1):
                hi, lo = mid[k], mid[k + 1]
                if allowance_ok(lo, hi) and not allowance_ok(hi, lo):
                    mid[k], mid[k + 1] = lo, hi
                    swapped = True
            if not swapped:
                break
        rows[:] = mid
        for n, r in enumerate(rows, 1):
            r["rank"] = n

    watch.sort(key=lambda w: (-w["rating"], w["rd"]))
    data["watch"] = watch
    data["watch_notes"] = (
        "Tournament entrants not on any board, with RD below 200. Rated from a "
        "1500/350 prior over the tournament data in tournaments/; not comparable "
        "to board ratings. competed_weight is the weight wrestled, not a board "
        "placement. An entrant joins the board (provisional) the first time he or "
        "she beats a board wrestler in a contested bout at a varsity event.")
    data["tournaments"] = report["events"]
    report["promoted"] = promoted
    report["watch"] = len(watch)
    log(f"TOURNAMENTS: {len(promoted)} entered boards, {len(watch)} on watch list, "
        f"{len(touched)} boards reordered")
    return report


if __name__ == "__main__":
    # offline check: apply tournaments to a carank-only rankings.json
    import json
    import sys
    src = sys.argv[1] if len(sys.argv) > 1 else "rankings.json"
    out = sys.argv[2] if len(sys.argv) > 2 else None
    d = json.load(open(src, encoding="utf-8"))
    apply_tournaments(d)
    if out:
        json.dump(d, open(out, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
