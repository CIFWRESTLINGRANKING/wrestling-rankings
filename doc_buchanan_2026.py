"""
2026 Doc Buchanan Invitational  ->  Bouts for every BOYS weight
================================================================
Real quarterfinals + semifinals + finals, all 14 weights, grade-tagged
(source: calgrappler.com). Doc B is a boys national event, so this deepens
the boys boards only — girls need an equivalent girls all-weights tournament.

126 (Doc B "129") is intentionally OMITTED here: the 126 board already ingests
Doc Buchanan via ca_126_fullseason, so re-adding it would double-count.

Wrestler ids match techfall_parser exactly  ->  "b:" + slug(name + '-' + team)
so a kid's Doc B and CIF-State results merge into one rating. Team-string
variants across sources (e.g. "Del Norte" vs "Del Norte (Cresent City)") will
NOT merge yet — that's the known identity-resolution gap, flagged, not hidden.
"""
from __future__ import annotations
import re, unicodedata
from wrestling_rating_engine import Bout
from techfall_parser import make_wid, canon_team

# Doc B weight -> CIF weight (129/126 omitted on purpose)
DOCB_TO_CIF = {109:106, 116:113, 123:120, 135:132, 141:138, 147:144,
               153:150, 160:157, 168:165, 178:175, 193:190, 218:215, 288:285}

_METHOD = {"fall":"fall","f":"fall","def":"fall","pin":"fall","tf":"tech",
           "md":"major","maj":"major","dec":"decision","sv":"decision",
           "mfor":"med_forfeit","mff":"med_forfeit","ff":"forfeit","for":"forfeit","dq":"dq"}
_METHODS_RE = r"DEF|DEC|MD|TF|FALL|MAJ|F|def\.?|dec\.?|md\.?|tf\.?|fall|maj\.?|f\.?"
_SPLIT = re.compile(r"\s+(" + _METHODS_RE + r")\s+", re.I)
_HEADER = re.compile(r"^\s*#{0,3}\s*\*{0,2}\s*(\d{3})\s*\*{0,2}\s*$")
_SEED = re.compile(r"^\s*\((?:\d+|NS|NR)\)\s*", re.I)


def _slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def _pop_parens(s):
    """Strip trailing (grade) and (ST) tags -> (team, grade, state)."""
    grade, state = None, None
    s = s.strip()
    while s.endswith(")"):
        i = s.rfind("(")
        if i < 0:
            break
        tok = s[i + 1:-1].strip()
        if tok.isdigit():
            grade = int(tok)
        elif re.fullmatch(r"[A-Za-z]{2}", tok):
            state = tok.upper()
        else:
            break                       # a real "(City)" part of the team name
        s = s[:i].strip()
    return s.strip(), grade, state


def _part(side):
    """'(5) Lincoln Valdez – Pomona (CO) (10), 6-4' -> (name, team, grade, oos)."""
    side = _SEED.sub("", side).strip()
    if " – " in side:
        name, rest = side.split(" – ", 1)
    elif " - " in side:
        name, rest = side.split(" - ", 1)
    else:
        name, rest = side, ""
    name = name.strip()
    if "," in name:                      # "Grajeda, Jesse" -> "Jesse Grajeda"
        last, first = [p.strip() for p in name.split(",", 1)]
        name = f"{first} {last}"
    # the loser segment carries a trailing ", <score/time/result>" AFTER the
    # wrestler's tags — strip it so it can't leak into the team / hide a (ST) tag
    rest = re.sub(r"\)\s*,.*$", ")", rest.strip())   # "Pomona (CO) (10), 6-4" -> "Pomona (CO) (10)"
    if "," in rest and not rest.endswith(")"):
        rest = rest.split(",", 1)[0].strip()          # no-tag fallback
    team, grade, state = _pop_parens(rest)
    return name, team, grade, bool(state)


def _classify(method, score):
    m = method.lower().strip(".")
    res = _METHOD.get(m, "decision")
    if m == "def" and "fall" not in score.lower() and not re.search(r"\d", score):
        res = "fall"
    return res


def parse_docb(text, team_section=None, event_id="DOCB_2026", day=70):
    """Parse Doc B match lines into Bouts. team_section: slug(team)->SEC for CA."""
    team_section = team_section or {}
    bouts, weight = [], None
    grades = {}
    for raw in text.splitlines():
        h = _HEADER.match(raw)
        if h:
            weight = DOCB_TO_CIF.get(int(h.group(1)))
            continue
        if weight is None or " – " not in raw:
            continue
        parts = _SPLIT.split(raw.strip(), maxsplit=1)
        if len(parts) != 3:
            continue
        wside, method, lside = parts
        wn, wt, wg, w_oos = _part(wside)
        ln, lt, lg, l_oos = _part(lside)
        if not wn or not ln:
            continue
        wid = make_wid("boys", wn, wt)
        lid = make_wid("boys", ln, lt)
        wsec = "OOS" if w_oos else team_section.get(canon_team(wt), "")
        lsec = "OOS" if l_oos else team_section.get(canon_team(lt), "")
        b = Bout(event_id, day, weight, wid, lid,
                 _classify(method, lside), wsec, lsec)
        b._w_name, b._l_name = wn, ln
        b._w_team, b._l_team = wt, lt
        bouts.append(b)
        if wg and not w_oos: grades[wid] = wg
        if lg and not l_oos: grades[lid] = lg
    parse_docb.grades = grades           # wid -> grade (for the graduate filter)
    return bouts


# --- real data: quarterfinals + semifinals + finals (126/"129" omitted) ------
DOCB_DATA = """
### 109
(1) Thales Silva – Buchanan (9) def. (8) Kayden Khim – Clovis West (9), fall
(5) Lincoln Valdez – Pomona (CO) (10) md (4) Tyler Sweet – Clovis North (10), 11-3
(3) Luke Loren – St. John Bosco (9) md (6) Jax Vang – Buchanan (10), 13-3
(2) Michael Bernabe – Clovis (9) tf (NS) Kingston Cruzat – Folsom (12), 15-0
(1) Thales Silva – Buchanan (9) dec. (5) Lincoln Valdez – Pomona (CO) (10), 6-4
(2) Michael Bernabe – Clovis (9) dec. (3) Luke Loren – St. John Bosco (9), 6-3
(2) Michael Bernabe – Clovis (9) DEC (1) Thales Silva – Buchanan (9), 6-1
### 116
(1) Jorge Rios – St. John Bosco (10) md (8) Phillip Hernandez – Clovis North (9), 9-0
(5) Thiago Silva – Buchanan (9) def. (4) Michael Rundell – Oak Park River Forest (IL) (11), fall
(3) Anthony Garza – Clovis (11) def. (6) Max Murillo – Esperanza (11), fall
(2) Turner Ross – Edmond North (OK) (11) tf (7) Eli Mendoza – Gilroy (10), 22-4
(1) Jorge Rios – St. John Bosco (10) dec. (5) Thiago Silva – Buchanan (9), 4-2
(3) Anthony Garza – Clovis (11) dec. (2) Turner Ross – Edmond North (OK) (11), 13-6
(1) Jorge Rios – St. John Bosco (10) DEC (3) Anthony Garza – Clovis (11), 4-1
### 123
(1) Rocklin Zinkin – Buchanan (12) tf (9) Hunter Juaregui – Fountain Valley (12), 20-3
(12) Zachary Samano – Chino (11) dec. (4) Carlos Melgoza – Kingsburg (12), 1-0
(8) Darion Johnson – West Linn (OR) (10) dec. (3) JR Ortega – Grandview (CO) (11), 8-6
(2) Cameron Sontz – Delbarton (NJ) (11) md (7) Steve Romero – Toppenish (WA) (12), 10-2
(1) Rocklin Zinkin – Buchanan (12) md. (12) Zachary Samano – Chino (11), 18-5
(2) Cameron Sontz – Delbarton (NJ) (11) md. (8) Darion Johnson – West Linn (OR) (10), 11-0
(1) Rocklin Zinkin – Buchanan (12) DEF (2) Cameron Sontz – Delbarton (NJ) (11), FALL
### 135
(1) Ashton Besmer – Buchanan (12) tf (NS) Jack Maliniconico – Poway (11), 19-4
(5) Sal Borrometi – St. Peter's Prep (NJ) (12) def. (4) Eric Casula – Stillwater (OK) (12), fall
(3) Nathan Carrillo – St. John Bosco (12) dec. (6) Max Cumbee – Imm. Con. (IL) (11), 3-2
(2) Slater Hicks – Valencia (11) dec. (7) Cael Humphrey – Sultana (11), 4-3
(1) Ashton Besmer – Buchanan (12) def. (5) Sal Borrometi – St. Peter's Prep (NJ) (12), fall
(2) Slater Hicks – Valencia (11) dec. (3) Nathan Carrillo – St. John Bosco (12), 11-9
(1) Ashton Besmer – Buchanan (12) MD (2) Slater Hicks – Valencia (11), 10-2
### 141
(1) Moses Mendoza – Gilroy (12) tf (8) Vinnie Gutierrez – Fountain Valley (11), 20-3
(5) Matty Orbeta – Poway (11) dec. (13) Angel Serrano – Pomona (CO) (12), 4-0
(NS) Mathius Garza – Etiwanda (11) def. (3) CJ Huerta – Buchanan (12), fall
(15) Chris LaLonde – Roosevelt (CO) (12) dec. (7) Gino Schinina – St. Peter's Prep (NJ) (12), 7-4
(1) Moses Mendoza – Gilroy (12) def. (5) Matty Orbeta – Poway (11), fall
(15) Chris LaLonde – Roosevelt (CO) (12) md (NS) Mathius Garza – Etiwanda (11), 8-0
(1) Moses Mendoza – Gilroy (12) TF (15) Chris LaLonde – Roosevelt (CO) (12), 21-6
### 147
(9) Chris Arreola – Clovis North (10) def. (1) Joseph Toscano – Buchanan (12), fall
(4) Tommy Verrette – Edmond North (OK) (12) dec. (5) Drake Hooiman – SLAM Academy (NV) (12), 4-1
(11) Laudan Henry – St. Peter's Prep (NJ) (12) dec. (NS) Diego Valdiviezo – Poway (11), 9-3
(2) Jesse Grajeda – St. John Bosco (11) dec. (10) Gideon Gonzalez – Bergen Catholic (NJ) (10), 7-4
(4) Tommy Verrette – Edmond North (OK) (12) dec. (9) Chris Arreola – Clovis North (10), 2-1
(2) Jesse Grajeda – St. John Bosco (11) def. (11) Laudan Henry – St. Peter's Prep (NJ) (12), mfor
(2) Jesse Grajeda – St. John Bosco (11) DEC (4) Tommy Verrette – Edmond North (OK) (12), 7-3
### 153
(1) Joe Bachmann – Faith Christian (PA) (11) dec. (8) Tommy Holguin – Bellarmine Prep (12), 5-3
(5) Nick Schwartz – Delbarton (NJ) (10) def. (4) Alias Raby – Anderson (12), fall
(3) Michael Romero – St. John Bosco (11) md (6) Garrison Sartain – Edmond North (OK) (11), 15-4
(2) Ivan Arias – Buchanan (12) dec. (7) Jacob Morris – South Anchorage (AK) (11), 7-1
(1) Joe Bachmann – Faith Christian (PA) (11) dec. (5) Nick Schwartz – Delbarton (NJ) (10), 6-2
(3) Michael Romero – St. John Bosco (11) dec. (2) Ivan Arias – Buchanan (12), 4-2
(3) Michael Romero – St. John Bosco (11) DEC (1) Joe Bachmann – Faith Christian (PA) (11), 3-2
### 160
(1) Austin Paris – Layton (UT) (12) dec. (9) Alex Gutierrez – Central Catholic (12), 5-1
(NS) Daniel Acosta – Randall (TX) (12) def. (12) Tigran Greyan – Valencia (12), fall
(14) Jacob Perez – Everett Alverez (12) dec. (NS) Aiden Arnett – Imm. Con. (IL) (10), 11-8
(2) Christopher Creason – El Diamante (12) md (10) Chris Anguiano – Millikan (11), 8-0
(1) Austin Paris – Layton (UT) (12) md. (NS) Daniel Acosta – Randall (TX) (12), 12-1
(2) Christopher Creason – El Diamante (12) def. (14) Jacob Perez – Everett Alverez (12), fall
(2) Christopher Creason – El Diamante (12) MD (1) Austin Paris – Layton (UT) (12), 12-3
### 168
(1) Jayden James – Delbarton (NJ) (12) tf (9) Blake Woodward – Buchanan (12), 20-5
(4) James Curoso – Clovis (10) dec. (5) Zane Gerlach – South Anchorage (AK) (11), 4-2
(3) Slava Shahbazyan – Birmingham (12) md (6) Kaleo Garcia – Gilroy (12), 13-3
(2) Josh Piparo – St. Peter's Prep (NJ) (11) md (10) Gunner Lopez – Grandview (CO) (12), 10-0
(1) Jayden James – Delbarton (NJ) (12) tf. (4) James Curoso – Clovis (10), 24-5
(3) Slava Shahbazyan – Birmingham (12) def. (2) Josh Piparo – St. Peter's Prep (NJ) (11), mfor
(1) Jayden James – Delbarton (NJ) (12) TF (3) Slava Shahbazyan – Birmingham (12), 18-2
### 178
(1) Joseph Jeter – Edmond North (OK) (12) def. (8) Travis Grace – Gilroy (12), fall
(4) Mason Ontiveros – Pitman (12) dec. (5) Brody Kelly – Immaculate Conception (IL) (12), 4-2
(3) Mario Carini – Poway (11) dec. (6) Isai Fernandez – St. John Bosco (10), 1-0
(2) Nick Singer – Faith Christian (PA) (11) dec. (7) Kalob Ybarra – Pomona (CO) (12), 5-3
(4) Mason Ontiveros – Pitman (12) dec. (1) Joseph Jeter – Edmond North (OK) (12), 8-5
(3) Mario Carini – Poway (11) dec. (2) Nick Singer – Faith Christian (PA) (11), 9-7
(3) Mario Carini – Poway (11) DEC (4) Mason Ontiveros – Pitman (12), 8-1
### 193
(1) C.J. Betz – Delbarton (NJ) (12) tf (8) Dom Dotson – Poway (12), 21-6
(5) Ladd Holman – Juab (UT) (11) md (4) Jay Singer – Faith Christian (PA) (12), 10-2
(3) Jonathan Rocha – Clovis North (12) dec. (6) Jaxon Penovich – St. Viator (IL) (12), 4-0
(2) Adam Waters – Faith Christian (PA) (12) tf (7) Carter Vannest – Pitman (12), 21-6
(5) Ladd Holman – Juab (UT) (11) dec. (1) C.J. Betz – Delbarton (NJ) (12), 1-0
(2) Adam Waters – Faith Christian (PA) (12) dec. (3) Jonathan Rocha – Clovis North (12), 7-3
(2) Adam Waters – Faith Christian (PA) (12) DEC (5) Ladd Holman – Juab (UT) (11), 9-6
### 218
(1) Cael Weidemoyer – Faith Christian (PA) (12) dec. (9) Satoshi Davis – SLAM Academy (NV) (10), 10-6
(4) David Calkins Jr. – Liberty-Brentwood (12) tf (NS) Brody Buzzard – Harrisburg (OR) (12), 21-4
(11) Wes Burford – Oakdale (11) def. (3) Adan Castillo – Clovis (11), fall
(2) Mick Moylan – Poway (11) dec. (10) Brian Haran – Gilroy (12), 4-0
(4) David Calkins Jr. – Liberty-Brentwood (12) dec. (1) Cael Weidemoyer – Faith Christian (PA) (12), 4-1
(11) Wes Burford – Oakdale (11) dec. (2) Mick Moylan – Poway (11), 6-5
(11) Wes Burford – Oakdale (11) DEC (4) David Calkins Jr. – Liberty-Brentwood (12), 8-5
### 288
(1) Mark Effendian – Faith Christian (PA) (12) def. (8) Anthony Sebastian – Imm. Con. (IL) (11), fall
(13) Andrew Arroyo – Clovis (10) dec. (5) Redmond Lindsey – Bixby (OK) (11), 1-0
(3) Zayne Candeleria – Sunnyside (AZ) (12) dec. (11) Sammy Seja – Buchanan (10), 11-6
(2) Trayvn Boger – South Summit (UT) (12) def. (7) Champion Dyes – Mullen (CO) (11), fall
(1) Mark Effendian – Faith Christian (PA) (12) def. (13) Andrew Arroyo – Clovis (10), fall
(3) Zayne Candeleria – Sunnyside (AZ) (12) dec. (2) Trayvn Boger – South Summit (UT) (12), 7-2
(1) Mark Effendian – Faith Christian (PA) (12) DEF (3) Zayne Candeleria – Sunnyside (AZ) (12), FALL
"""

if __name__ == "__main__":
    bouts = parse_docb(DOCB_DATA)
    print(f"parsed {len(bouts)} Doc B bouts across "
          f"{len(set(b.weight for b in bouts))} weights")
    print(f"grades captured: {len(parse_docb.grades)} wrestlers")
    for b in bouts[:4]:
        print(f"  {b.weight}: {b._w_name} ({b.section_w}) def {b._l_name} "
              f"({b.section_l}) [{b.result}]")
