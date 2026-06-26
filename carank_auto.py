#!/usr/bin/env python3
"""
carank_auto.py - self-contained carank parser for unattended (GitHub Action) use.

Unlike the session pipeline (which read hand-condensed pages/CA{wt}.txt files),
this fetches a LIVE carank CA{wt}Data page and extracts BOTH the roster
(rank, name, grade, school, section) AND the bouts directly from the page,
with no human in the loop. It then reuses the proven carank_gen.board()
rating/linking logic unchanged - only the data SOURCE differs.

Public API:
    fetch_page(wt)        -> raw page text (HTTP; used in the Action)
    board_from_text(wt,t) -> (rows, n_bouts, n_roster)   [testable offline]
    board_auto(wt)        -> (rows, n_bouts, n_roster)   [fetch + parse]
"""
import re, html as _html, tempfile, os, urllib.request
import carank_gen as G   # BOUT_RE, BLOCK_RE, classify, surname, canon_team, section_of, DAY, GRADE_HIDE, SECTION_PHRASES, board

CARANK_URL = "https://carank.neocities.org/CA{wt}Data"
GRADE_MAP  = {"FRESHMAN": "Fr", "SOPHOMORE": "So", "JUNIOR": "Jr", "SENIOR": "Sr"}
GRADE_RE   = re.compile(r"(FRESHMAN|SOPHOMORE|JUNIOR|SENIOR)")
# first placement/record token that marks the END of the school+section header
PLACEMENT_RE = re.compile(r"\s(?:\d{1,2}(?:st|nd|rd|th)|\d+-\d+|MFOR|DEF|Cons\.?|HM)\b")


def fetch_page(wt, timeout=30):
    """HTTP GET the live carank page. Works from an open network (GitHub runner)."""
    url = CARANK_URL.format(wt=wt)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (cif-rankings-bot)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def html_to_text(raw):
    """Strip HTML to rendered-ish text so BLOCK_RE / BOUT_RE apply to live pages."""
    t = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    t = re.sub(r"(?is)<br\s*/?>", "\n", t)
    t = re.sub(r"(?is)</(td|tr|p|div|li|h\d)>", " ", t)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    return _html.unescape(t)


def split_name(glued):
    """'MichaelBernabe' -> 'Michael Bernabe'; keep already-spaced names; protect Mc/Mac."""
    g = re.sub(r"\s+", " ", glued).strip()
    s = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", g)          # break lower->Upper boundaries
    s = re.sub(r"\bMc (?=[A-Z])", "Mc", s)              # rejoin McClurg
    s = re.sub(r"\bMac (?=[A-Z])", "Mac", s)            # rejoin MacEachern
    return s.strip()


def extract_roster(text):
    """Pull (rank, name, grade, school) per wrestler block straight from the page."""
    marks = list(G.BLOCK_RE.finditer(text))
    roster = []
    for i, mk in enumerate(marks):
        rank = int(mk.group(1))
        seg = text[mk.end(): marks[i + 1].start() if i + 1 < len(marks) else len(text)]
        gm = GRADE_RE.search(seg[:120])
        if not gm:
            continue
        name = split_name(seg[:gm.start()].lstrip(" 0123456789"))
        grade = GRADE_MAP[gm.group(1)]
        after = seg[gm.end():]
        plc = PLACEMENT_RE.search(after)
        region = after[:plc.start()] if plc else after[:60]
        # section phrase is glued at the END of the school name; prefer the LAST match
        best = None
        for phrase, code in G.SECTION_PHRASES:
            idx = region.rfind(phrase)
            if idx != -1 and (best is None or idx > best[0]):
                best = (idx, code)
        school = region[:best[0]].strip() if best else region.strip()
        roster.append((rank, name, grade, school))
    return roster


def board_from_text(wt, text):
    """Extract roster+bouts from page text, run the proven engine, return board rows."""
    roster = extract_roster(text)
    if not roster:
        return [], 0, 0
    # carank_gen.board() reads from a file path; write the live text to a temp file
    fd, path = tempfile.mkstemp(suffix=f"_CA{wt}.txt", text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        rows, n_bouts = G.board(int(wt), path, roster)
    finally:
        os.unlink(path)
    return rows, n_bouts, len(roster)


def board_auto(wt):
    """Full path: fetch live page, convert, parse, rate."""
    raw = fetch_page(wt)
    text = html_to_text(raw)
    return board_from_text(wt, text)


if __name__ == "__main__":
    import sys
    src = sys.argv[1] if len(sys.argv) > 1 else "fixtures/carank106_raw.txt"
    wt = sys.argv[2] if len(sys.argv) > 2 else "106"
    text = open(src, encoding="utf-8").read()
    rows, nb, nr = board_from_text(wt, text)
    print(f"{src}: {nr} wrestlers in roster, {nb} bouts parsed, {len(rows)} shown (seniors hidden)\n")
    for r in rows:
        print(f"  #{r['rank']:<2} {r['name']:20s} {r['team'][:16]:16s} {r['section']:3s} "
              f"{r['grade']:2s} {r['record']:>5s}  R{r['rating']}\u00b1{r['rd']}")
