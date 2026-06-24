"""
CalGrappler results parser  ->  Bout objects
============================================

Reads a CalGrappler tournament results page (the Markdown/plain text of it) and
emits `Bout` records ready for the rating engine. Built against the real format
on pages like /2026-doc-buchanan-invitational-results/.

WHAT IT HANDLES
  * Weight tracking via section headers: "### 129", "**141**", or a bare "168".
    Each following match inherits the current weight until the next header.
  * Pairwise match lines in any of CalGrappler's round sections (Finals,
    Semi-Final Results, Quarter-Final Results), e.g.:
        (1) Freddy Bachmann – Faith Christian (PA) (10) dec. (4) Paul Ruiz – Buchanan (10), 2-1 UTB
        (1) Moses Mendoza – Gilroy (12) TF (15) Chris LaLonde – Roosevelt (CO) (12), 21-6
        (9) Chris Arreola – Clovis North (10) def. (1) Joseph Toscano – Buchanan (12), fall
    The WINNER is always listed first — that's the wrestling-results convention
    every one of these sources follows, and it's what lets us assign W/L.
  * "Last, First" names (normalized to "First Last").
  * Out-of-state tags: a trailing (PA)/(OK)/... marks a non-California wrestler;
    California teams carry no state tag, so absence => CA.

WHAT IT SKIPS (on purpose)
  * Placer lists ("1. Name – Team – DEC 6-1") and Pre-Seeds — these aren't clean
    pairwise bouts, and the same matches already appear in the round sections, so
    parsing them would double-count. We require the LOSER side to contain a team
    separator, which placer/seed lines lack.

RESULT METHOD
  Explicit tokens (TF/MD/DEC/fall/...) are used directly. A generic "def."/"DEF"
  is resolved from the trailing text: a method word (fall/tech/forfeit/dq) wins;
  otherwise the score margin is used (>=15 -> tech, 8-14 -> major, else decision).
  This margin rule is folkstyle-standard but is an INFERENCE — flagged per-bout
  in `.inferred` so you can audit it.

USAGE
    from calgrappler_parser import parse_calgrappler
    bouts = parse_calgrappler(page_text, event_id="DOCB", day=100,
                              weight_pool={129: 126})   # optional pooling
    # bouts -> list[Bout]; feed straight into RatingEngine

  fetch_url(url) is provided for live use in an unrestricted environment
  (CalGrappler is server-rendered, so requests + a tag strip is enough).
"""

from __future__ import annotations
import re
import unicodedata
from dataclasses import dataclass
from wrestling_rating_engine import Bout

US_STATES = {
    "AL","AK","AZ","AR","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS",
    "KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM",
    "NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA",
    "WA","WV","WI","WY",
}  # note: CA omitted on purpose — a CA tag would be redundant and CalGrappler
   # leaves California teams untagged.

# method token -> engine result key. Order matters for the regex (longest first).
_METHOD = {
    "fall": "fall", "pin": "fall",
    "tf": "tech", "tech": "tech",
    "md": "major", "major": "major",
    "dec": "decision", "sv": "decision", "ot": "decision",
    "mfor": "forfeit", "mff": "forfeit", "ff": "forfeit", "for": "forfeit",
    "forfeit": "forfeit", "default": "forfeit", "inj": "forfeit",
    "dq": "dq",
}
_GENERIC = {"def", "def.", "d", "d.", "defeated", "beat", "over", "vs", "vs."}

# Separator tokens with an OPTIONAL trailing period applied to all (so "dec.",
# "def.", "md.", "vs." all match). Longer tokens precede shorter so "fall"/"def"
# are tried before "f" at the same position.
_SEP = re.compile(
    r"\s(fall|pin|tech|major|forfeit|default|mfor|mff|tf|md|dec|def|dq|ff|for|sv|ot|vs|f)\.?\s",
    re.IGNORECASE,
)
_TEAMSEP = re.compile(r"\s[–-]\s")           # en-dash or hyphen with spaces
_SCORE = re.compile(r"(\d+)\s*-\s*(\d+)")
_SEED = re.compile(r"^\(\s*\w+\s*\)\s*")     # leading "(1) " / "(NS) "
_PARENS = re.compile(r"\(([^)]*)\)")


@dataclass
class ParsedBout:
    bout: Bout
    raw: str
    inferred: bool   # True if result method came from a margin heuristic


def _slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s


def is_weight_header(line: str):
    """Return the weight int if this line is a weight header, else None."""
    t = line.strip().strip("#").strip("*").strip()
    t = re.sub(r"\s*(lbs?\.?|pounds?)\s*$", "", t, flags=re.IGNORECASE)
    if re.fullmatch(r"\d{2,3}", t):
        return int(t)
    return None


def _parse_wrestler(block: str):
    """'(1) Freddy Bachmann – Faith Christian (PA) (10)' -> (name, team, state|None)."""
    block = _SEED.sub("", block.strip()).strip().strip(",")
    parts = _TEAMSEP.split(block, maxsplit=1)
    if len(parts) != 2:
        return None
    name, rest = parts[0].strip(), parts[1].strip()
    # the LAST wrestler on a line carries the trailing ", <score/method/time>";
    # cut everything from the first comma so it can't pollute the team/id.
    rest = rest.split(",", 1)[0].strip()
    if "," in name:                                  # "Last, First" -> "First Last"
        last, first = [p.strip() for p in name.split(",", 1)]
        name = f"{first} {last}"
    # pull trailing parenthesized tokens: state (2-letter) and/or grade (number)
    state = None
    for tok in _PARENS.findall(rest):
        tok = tok.strip()
        if tok.upper() in US_STATES:
            state = tok.upper()
    # team = rest with the trailing (state)/(grade) parens removed; keep inner
    # parens that are part of a team name (e.g. "Del Norte (Crescent City)")
    team = rest
    team = re.sub(r"\s*\((?:[A-Z]{2}|\d{1,2})\)\s*$", "", team)   # drop last tag
    team = re.sub(r"\s*\((?:[A-Z]{2}|\d{1,2})\)\s*$", "", team)   # and one more
    team = team.strip().strip(",").strip()
    return name, team, state


def _classify(token: str, trailing: str) -> tuple[str, bool]:
    """Return (engine_result_key, inferred?)."""
    tok = token.lower().strip(".")
    if tok in _METHOD and tok != "f":
        return _METHOD[tok], False
    if tok == "f":
        return "fall", False
    # generic 'def.' / 'd.' — resolve from trailing text
    tl = trailing.lower()
    for kw, res in (("fall", "fall"), ("pin", "fall"), ("tech", "tech"),
                    ("tf", "tech"), ("mfor", "forfeit"), ("mff", "forfeit"),
                    ("forfeit", "forfeit"), ("ff", "forfeit"), ("dq", "dq")):
        if kw in tl:
            return res, False
    m = _SCORE.search(trailing)
    if m:
        margin = abs(int(m.group(1)) - int(m.group(2)))
        if margin >= 15:
            return "tech", True
        if margin >= 8:
            return "major", True
        return "decision", True
    return "decision", True


def _parse_match_line(line: str, weight: int, event_id: str, day: float):
    """Return ParsedBout or None."""
    # try each separator token left->right, longest first; first valid split wins
    cands = sorted(_SEP.finditer(line), key=lambda m: (-len(m.group(1)), m.start()))
    for m in cands:
        token = m.group(1)
        left, right = line[:m.start()], line[m.end():]
        wl = _parse_wrestler(left)
        ll = _parse_wrestler(right)
        if not wl or not ll:
            continue                       # placer/seed line (loser has no team)
        w_name, w_team, w_state = wl
        l_name, l_team, l_state = ll
        result, inferred = _classify(token, right)
        w_sec = w_state if w_state else "CA"
        l_sec = l_state if l_state else "CA"
        b = Bout(event_id, day, weight,
                 _slug(f"{w_name}-{w_team}"), _slug(f"{l_name}-{l_team}"),
                 result, w_sec, l_sec)
        # stash display names on the bout object (handy downstream)
        b._w_name, b._l_name = w_name, l_name  # type: ignore[attr-defined]
        return ParsedBout(b, line.strip(), inferred)
    return None


def parse_calgrappler(text: str, event_id: str, day: float,
                      weight_pool: dict | None = None,
                      return_parsed: bool = False):
    """
    Parse CalGrappler results text into Bouts.
      weight_pool: optional {event_weight: pool_weight}, e.g. {129: 126}.
      return_parsed: if True, return list[ParsedBout] (with raw line + inferred
                     flag) for auditing; else list[Bout].
    """
    weight = None
    out: list[ParsedBout] = []
    for line in text.splitlines():
        wt = is_weight_header(line)
        if wt is not None:
            weight = weight_pool.get(wt, wt) if weight_pool else wt
            continue
        if weight is None or _SEP.search(line) is None:
            continue
        pb = _parse_match_line(line, weight, event_id, day)
        if pb:
            out.append(pb)
    # de-dupe identical (winner, loser, weight, event) rows
    seen, deduped = set(), []
    for pb in out:
        k = (pb.bout.winner, pb.bout.loser, pb.bout.weight, pb.bout.event_id)
        if k not in seen:
            seen.add(k)
            deduped.append(pb)
    return deduped if return_parsed else [pb.bout for pb in deduped]


def fetch_url(url: str) -> str:
    """Fetch + strip a CalGrappler page to text. Needs network (allowlist)."""
    import requests
    html = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"}).text
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
    html = re.sub(r"</(p|div|li|h\d|tr)>", "\n", html, flags=re.I)
    text = re.sub(r"<[^>]+>", "", html)
    text = re.sub(r"[ \t]+", " ", text)
    return text
