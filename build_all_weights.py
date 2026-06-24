"""
ALL WEIGHTS, BOYS + GIRLS  ->  one rankings.json (28 boards)
============================================================
Same engine, run once per (gender, weight) pool. No new math — wrestlers only
meet inside their own weight+gender, so each pool is independent.

Data here is CIF State (semifinals + medal matches), so most boards are
STATE-TOURNAMENT-THIN: top 4 is well connected, 5-8 trails off toward raw
placement. Boys 126 keeps the richer multi-event "returning" board we built.
Each weight upgrades to full depth as its section + regular-season brackets are
parsed (same parser, just more events).
"""
from wrestling_rating_engine import RatingEngine, Config
from techfall_parser import parse_techfall
from doc_buchanan_2026 import parse_docb, DOCB_DATA
import json, datetime

BOYS_WEIGHTS  = [106,113,120,126,132,138,144,150,157,165,175,190,215,285]
GIRLS_WEIGHTS = [100,105,110,115,120,125,130,135,140,145,155,170,190,235]

BOYS_DATA = """
106-1st/2nd: Michael Bernabe (Clovis (CS)) vs. Thales Silva (Buchanan (CS)) (MD, 12-1)
106-3rd/4th: Cash Mcclurg (Granite Hills (SD)) vs. Aiden Talavera (Reedley (CS)) (DEC, 7-0)
106-5th/6th: Luke Loren (St. John Bosco (SS)) vs. Tyler Sweet (Clovis North (CS)) (MD, 12-3)
106-7th/8th: Kingston Cruzat (Folsom (SJ)) vs. Nathiel Nava (Stockdale (CS)) (MD, 12-1)
106-Semi: Thales Silva (Buchanan (CS)) vs. Luke Loren (St. John Bosco (SS)) (DEC 5-4)
106-Semi: Michael Bernabe (Clovis (CS)) vs. Aiden Talavera (Reedley (CS)) (F 12-3 5:55)
113-1st/2nd: Anthony Garza (Clovis (CS)) vs. Max Murillo (Esperanza (SS)) (MD, 15-6)
113-3rd/4th: Thiago Silva (Buchanan (CS)) vs. Eli Mendoza (Gilroy (CC)) (DEC, 5-3)
113-5th/6th: Uriah Correa (Servite (SS)) vs. Phillip Hernandez (Clovis North (CS)) (DEC, 4-1)
113-7th/8th: Daniel Mendoza (Victor Valley (SS)) vs. Julius Villamil (Poway (SD)) (FALL, 4:41)
113-Semi: Max Murillo (Esperanza (SS)) vs. Thiago Silva (Buchanan (CS)) (TF 15-0 3:01)
113-Semi: Anthony Garza (Clovis (CS)) vs. Eli Mendoza (Gilroy (CC)) (MD 19-7)
120-1st/2nd: Rocklin Zinkin (Buchanan (CS)) vs. Samuel Sanchez (Esperanza (SS)) (DEC, 5-2)
120-3rd/4th: Henry Aslikyan (Birmingham (LA)) vs. Rene Cordero (Poway (SD)) (DEC, 7-3)
120-5th/6th: Aiden Garcia (Palma (CC)) vs. Zachary Samano (Chino (SS)) (DEC, 4-1)
120-7th/8th: Nathan Reynolds (St. John Bosco (SS)) vs. Troy Montero (La Mirada (SS)) (MD, 15-3)
120-Semi: Samuel Sanchez (Esperanza (SS)) vs. Henry Aslikyan (Birmingham (LA)) (DEC 2-1 UTB)
120-Semi: Rocklin Zinkin (Buchanan (CS)) vs. Aiden Garcia (Palma (CC)) (DEC 10-3)
132-1st/2nd: Ashton Besmer (Buchanan (CS)) vs. Slater Hicks (Valencia/Valencia (SS)) (DEC, 9-6)
132-3rd/4th: Arno Vardanyan (Birmingham (LA)) vs. Nathan Carrillo (St. John Bosco (SS)) (DEC, 4-2)
132-5th/6th: Jack Malinconico (Poway (SD)) vs. Cael Humphrey (Sultana (SS)) (DEC, 8-4)
132-7th/8th: Dominic Bozanic (Gilroy (CC)) vs. Joseph Guardado (Esperanza (SS)) (DEC, 4-1)
132-Semi: Slater Hicks (Valencia/Valencia (SS)) vs. Nathan Carrillo (St. John Bosco (SS)) (F 7:30)
132-Semi: Ashton Besmer (Buchanan (CS)) vs. Arno Vardanyan (Birmingham (LA)) (DEC 6-0)
138-1st/2nd: Moses Mendoza (Gilroy (CC)) vs. CJ Huerta (Buchanan (CS)) (TF, 24-8 5:12)
138-3rd/4th: Vinnie Gutierrez (Fountain Valley (SS)) vs. Raymond Rivera (Clovis (CS)) (MD, 10-2)
138-5th/6th: Matty Orbeta (Poway (SD)) vs. Orion Hill (Folsom (SJ)) (DEC, 6-2)
138-7th/8th: Zaydrein Hernandez (St. John Bosco (SS)) vs. Joseph Pavlov-Ramirez (Los Gatos (CC)) (DEC, 5-0)
138-Semi: Moses Mendoza (Gilroy (CC)) vs. Matty Orbeta (Poway (SD)) (F 5:35)
138-Semi: CJ Huerta (Buchanan (CS)) vs. Raymond Rivera (Clovis (CS)) (DEC 4-1)
144-1st/2nd: Jesse Grajeda (St. John Bosco (SS)) vs. Chris Arreola (Clovis North (CS)) (MD, 17-4)
144-3rd/4th: Joseph Toscano (Buchanan (CS)) vs. Kavi Garvey (Fountain Valley (SS)) (DEC, 4-0)
144-5th/6th: Diego Valdiviezo (Poway (SD)) vs. Ames-Michael Hoevker (Granite Hills (SD)) (DEC, 4-1)
144-7th/8th: Edward Sheeran (Pitman (SJ)) vs. Rocco Godinez (Centennial (SS)) (DEC, 8-5)
144-Semi: Chris Arreola (Clovis North (CS)) vs. Kavi Garvey (Fountain Valley (SS)) (DEC 1-0)
144-Semi: Jesse Grajeda (St. John Bosco (SS)) vs. Diego Valdiviezo (Poway (SD)) (MD 15-5)
150-1st/2nd: Michael Romero (St. John Bosco (SS)) vs. Ivan Arias (Buchanan (CS)) (DEC, 4-2)
150-3rd/4th: Tommy Holguin (Bellarmine (CC)) vs. Alias Raby (Anderson (NS)) (DEC, 15-12)
150-5th/6th: Joshua Requena (Camarillo (SS)) vs. Greg Torosian (Birmingham (LA)) (DEC, 3-2)
150-7th/8th: Carlos Valdiviezo (Poway (SD)) vs. Matthew Centeno (Esperanza (SS)) (MD, 10-1)
150-Semi: Michael Romero (St. John Bosco (SS)) vs. Tommy Holguin (Bellarmine (CC)) (DEC 4-0)
150-Semi: Ivan Arias (Buchanan (CS)) vs. Alias Raby (Anderson (NS)) (DEC 4-1 SV)
157-1st/2nd: Bailey Holman (Poway (SD)) vs. Wyatt Lewis (Del Norte (Cresent City) (NC)) (DEC, 4-1)
157-3rd/4th: Jacob Perez (Everett Alvarez (CC)) vs. Roman Arakelyan (Birmingham (LA)) (MD, 16-5)
157-5th/6th: Carlo Contino (Buchanan (CS)) vs. Dimetry Molina (Esperanza (SS)) (FALL, 3:51)
157-7th/8th: Chris Anguiano (Millikan (SS)) vs. Chase Young (Del Oro (SJ)) (MD, 10-1)
157-Semi: Wyatt Lewis (Del Norte (Cresent City) (NC)) vs. Jacob Perez (Everett Alvarez (CC)) (DEC 7-0)
157-Semi: Bailey Holman (Poway (SD)) vs. Dimetry Molina (Esperanza (SS)) (DEC 4-1)
165-1st/2nd: Slava Shahbazyan (Birmingham (LA)) vs. James Curoso (Clovis (CS)) (MD, 13-4)
165-3rd/4th: Kaleo Garcia (Gilroy (CC)) vs. Jesus Guzman (Lakeside (SS)) (MD, 12-3)
165-5th/6th: Mason Carnrite (Poway (SD)) vs. Blake Woodward (Buchanan (CS)) (DEC, 8-1)
165-7th/8th: Tigran Greyan (Valencia/Valencia (SS)) vs. Treyton Sheets (Frontier (CS)) (MD, 13-3)
165-Semi: James Curoso (Clovis (CS)) vs. Kaleo Garcia (Gilroy (CC)) (DEC 8-6)
165-Semi: Slava Shahbazyan (Birmingham (LA)) vs. Mason Carnrite (Poway (SD)) (DEC 9-2)
175-1st/2nd: Mario Carini (Poway (SD)) vs. Isai Fernandez (St. John Bosco (SS)) (DEC, 8-1)
175-3rd/4th: Mason Ontiveros (Pitman (SJ)) vs. Travis Grace (Gilroy (CC)) (DEC, 9-7)
175-5th/6th: Elijah Ornelas (Clovis North (CS)) vs. Ashton Lassig (Temecula Valley (SS)) (DEC, 5-0)
175-7th/8th: Patrick Roberts (Buchanan (CS)) vs. Kelan Stever (San Clemente (SS)) (TF, 17-2 2:26)
175-Semi: Isai Fernandez (St. John Bosco (SS)) vs. Mason Ontiveros (Pitman (SJ)) (DEC 4-2)
175-Semi: Mario Carini (Poway (SD)) vs. Travis Grace (Gilroy (CC)) (DEC 8-1)
190-1st/2nd: Jonathan Rocha (Clovis North (CS)) vs. Mason Savidan (St. John Bosco (SS)) (FALL, 3:10)
190-3rd/4th: Dom Dotson (Poway (SD)) vs. Carter Vannest (Pitman (SJ)) (TF, 17-1 1:16)
190-5th/6th: Noah Daniels (Sheldon (SJ)) vs. Gabriel Barragan (Esperanza (SS)) (FALL, 0:16)
190-7th/8th: Jackson Naven (Frontier (CS)) vs. Brady Wight (Vacaville (SJ)) (MD, 11-2)
190-Semi: Jonathan Rocha (Clovis North (CS)) vs. Dom Dotson (Poway (SD)) (DEC 6-3)
190-Semi: Mason Savidan (St. John Bosco (SS)) vs. Carter Vannest (Pitman (SJ)) (MD 16-3)
215-1st/2nd: David Calkins Jr. (Liberty (NC)) vs. Wes Burford (Oakdale (SJ)) (DEC, 6-5)
215-3rd/4th: Mick Moylan (Poway (SD)) vs. Kai Ford (Ponderosa (SJ)) (TF, 15-0 3:42)
215-5th/6th: Brian Haran (Gilroy (CC)) vs. Kaden Cryer (Moreno Valley (SS)) (DEC, 8-1)
215-7th/8th: Emilio Ayala (Kingsburg (CS)) vs. Jaxon Smith (Chaparral (SS)) (DEC, 4-3)
215-Semi: David Calkins Jr. (Liberty (NC)) vs. Mick Moylan (Poway (SD)) (DEC 5-3)
215-Semi: Wes Burford (Oakdale (SJ)) vs. Brian Haran (Gilroy (CC)) (DEC 4-2)
285-1st/2nd: Coby Merrill (JW North (SS)) vs. Andrew Arroyo (Clovis (CS)) (FALL, 0:37)
285-3rd/4th: Matthew Cooley (Oakdale (SJ)) vs. Noah Huss (Moorpark (SS)) (DEC, 4-2)
285-5th/6th: Sammy Seja (Buchanan (CS)) vs. Noah Larios (Imperial (SD)) (MFOR)
285-7th/8th: Nathaniel Espericueta (Frontier (CS)) vs. Carlos Sutton (Etiwanda (SS)) (MFOR)
285-Semi: Coby Merrill (JW North (SS)) vs. Noah Larios (Imperial (SD)) (TF 19-4 3:02)
285-Semi: Andrew Arroyo (Clovis (CS)) vs. Sammy Seja (Buchanan (CS)) (DEC 5-3)
"""

GIRLS_DATA = """
100-Final: Alexandria Marin (Buchanan (CS)) vs. Daniella Vazquez (Garces (CS)) (MD 10-0)
100-Semi: Daniella Vazquez (Garces (CS)) vs. Bailey Hoard (Monache (CS)) (DEC 11-8)
100-Semi: Alexandria Marin (Buchanan (CS)) vs. Eva Bhattacharya (Menlo-Atherton (CC)) (MD 10-2)
105-Final: Angelica Serratos (Santa Ana (SS)) vs. Marcia Nunez (Buchanan (CS)) (DEC 10-4)
105-Semi: Marcia Nunez (Buchanan (CS)) vs. Ava Fodera (Poway (SD)) (DEC 8-1)
105-Semi: Angelica Serratos (Santa Ana (SS)) vs. Sophia Lazaro (Northview (SS)) (MD 14-6)
110-Final: Christina Estrada (Buchanan (CS)) vs. Alexa Smith (Lutheran/Orange (SS)) (TF 18-3 2:08)
110-Semi: Christina Estrada (Buchanan (CS)) vs. Leila Witzerman (Peninsula (SS)) (F 1:12)
110-Semi: Alexa Smith (Lutheran/Orange (SS)) vs. Samantha Cornejo (Esperanza (SS)) (F 3:17)
115-Final: Aubree Gutierrez (Marina (SS)) vs. Skye Schneider (Elk Grove (SJ)) (F 5:38)
115-Semi: Skye Schneider (Elk Grove (SJ)) vs. Maggie Cornish (Tesoro (SS)) (DEC 4-1)
115-Semi: Aubree Gutierrez (Marina (SS)) vs. Trinity Garza (Buchanan (CS)) (F 4:34)
120-Final: SJ Martin (Granada (NC)) vs. Ava Ebrahimi (Poway (SD)) (MD 12-0)
120-Semi: SJ Martin (Granada (NC)) vs. Eliana Garcia (Northview (SS)) (F 2:13)
120-Semi: Ava Ebrahimi (Poway (SD)) vs. Evelyn Lopez (Hamilton (SS)) (DEC 6-3)
125-Final: Me`Kala James (Central East (CS)) vs. Angelina Borelli (Los Banos (SJ)) (DEC 9-2)
125-Semi: Angelina Borelli (Los Banos (SJ)) vs. AlexAndrea Corona (Monache (CS)) (MD 15-3)
125-Semi: Me`Kala James (Central East (CS)) vs. Kaiya Maggini (Del Oro (SJ)) (DEC 3-1)
130-Final: Madison Black (Newbury Park (SS)) vs. Camille Torres (Brawley (SD)) (DEC 3-0)
130-Semi: Camille Torres (Brawley (SD)) vs. Tamara Grace (Gilroy (CC)) (F 5:35)
130-Semi: Madison Black (Newbury Park (SS)) vs. Isabella Sermana (Cerritos (SS)) (F 4:56)
135-Final: Shayna Ward (Oakland Tech Senior H S (NC)) vs. Zahra Stewart (Orange Vista (SS)) (F 4:58)
135-Semi: Zahra Stewart (Orange Vista (SS)) vs. Lilyana Balderas (Anaheim (SS)) (F 4:51)
135-Semi: Shayna Ward (Oakland Tech Senior H S (NC)) vs. Lauren Zaragoza (Brawley (SD)) (MD 14-1)
140-Final: Yzabella Austin (Hughson (SJ)) vs. Dulcy Martinez (Central Catholic (SJ)) (MD 8-0)
140-Semi: Yzabella Austin (Hughson (SJ)) vs. Gianna Lopez (Peninsula (SS)) (F 1:25)
140-Semi: Dulcy Martinez (Central Catholic (SJ)) vs. Sumaya Lazaro (Northview (SS)) (F 2:32)
145-Final: Jestinah Solomua (Corona (SS)) vs. Haru Duus (Fremont (CC)) (F 3:14)
145-Semi: Jestinah Solomua (Corona (SS)) vs. Kirin Smith (Clovis West (CS)) (MD 16-4)
145-Semi: Haru Duus (Fremont (CC)) vs. Anakarla Hernandez (St Helena (NC)) (F 5:32)
155-Final: Natalie Blanco (Chino (SS)) vs. Mary Snider (Rancho Bernardo (SD)) (DEC 2-0)
155-Semi: Natalie Blanco (Chino (SS)) vs. Eva Garcia (Marina (SS)) (MD 11-2)
155-Semi: Mary Snider (Rancho Bernardo (SD)) vs. Symone Jewell (Northgate (NC)) (F 4:56)
170-Final: Leilani Lemus (Clovis (CS)) vs. Sophia Lopez (Upland (SS)) (F 0:34)
170-Semi: Leilani Lemus (Clovis (CS)) vs. Brooklyn Bittner (Rio Mesa (SS)) (F 1:37)
170-Semi: Sophia Lopez (Upland (SS)) vs. Berlynn Solia-Tago (Poly/Long Beach (SS)) (DEC 2-0)
190-Final: Estefany Caballero (Orange (SS)) vs. Emily Carvalho (Redwood -Visalia (CS)) (DEC 10-3)
190-Semi: Emily Carvalho (Redwood -Visalia (CS)) vs. Onyi Oragwam (Centennial (CS)) (DEC 6-5)
190-Semi: Estefany Caballero (Orange (SS)) vs. Rosalynn Diaz (Liberty (NC)) (MD 12-1)
235-Final: Gia Coons (Orange Vista (SS)) vs. Taya Maumausolo Matagi (Nipomo (CS)) (F 3:29)
235-Semi: Gia Coons (Orange Vista (SS)) vs. Marley Smith (Lassen (NS)) (DEC 4-1)
235-Semi: Taya Maumausolo Matagi (Nipomo (CS)) vs. Adelena Martinez (Hemet (SS)) (DEC 7-2)
"""


def meta_from_bouts(bouts):
    name, team, sec = {}, {}, {}
    for b in bouts:
        name[b.winner], team[b.winner], sec[b.winner] = b._w_name, b._w_team, b.section_w
        name[b.loser],  team[b.loser],  sec[b.loser]  = b._l_name, b._l_team, b.section_l
    return name, team, sec


def board_for(bouts, grades=None, top_n=40):
    """Rate everyone; hide out-of-state anchors and graduated seniors."""
    grades = grades or {}
    eng = RatingEngine(Config())
    eng.ingest(bouts)
    name, team, sec = meta_from_bouts(bouts)
    wl = {}
    for b in bouts:
        wl.setdefault(b.winner, [0, 0])[0] += 1
        wl.setdefault(b.loser, [0, 0])[1] += 1
    glabel = {9: "Fr", 10: "So", 11: "Jr"}
    out, rank = [], 0
    for w in eng.rankings():
        if sec.get(w.wid) == "OOS":            # rated anchor, hidden from board
            continue
        if grades.get(w.wid) == 12:            # graduated senior, hidden
            continue
        rank += 1
        rec = wl.get(w.wid, [0, 0])
        out.append({"rank": rank, "name": name[w.wid], "team": team.get(w.wid, ""),
                    "section": sec.get(w.wid, ""),
                    "grade": glabel.get(grades.get(w.wid), ""),
                    "record": f"{rec[0]}-{rec[1]}",
                    "rating": round(w.rating), "rd": round(w.rd)})
        if rank >= top_n:
            break
    return out


def rich_126_board():
    """Use the multi-event returning board for boys 126 (the flagship)."""
    from ca_126_fullseason import build_bouts, NAMES, SEC
    from returning_2026_27 import GRADE_2025_26, graduated
    eng = RatingEngine(Config())
    eng.ingest(build_bouts())
    wl = {}
    for b in build_bouts():
        wl.setdefault(b.winner, [0, 0])[0] += 1
        wl.setdefault(b.loser, [0, 0])[1] += 1
    out, rank = [], 0
    for w in eng.rankings():
        if SEC.get(w.wid) == "OOS" or graduated(w.wid):
            continue
        rank += 1
        rec = wl.get(w.wid, [0, 0])
        out.append({"rank": rank, "name": NAMES[w.wid], "team": "",
                    "section": SEC[w.wid],
                    "grade": {9: "Fr", 10: "So", 11: "Jr"}.get(GRADE_2025_26.get(w.wid), ""),
                    "record": f"{rec[0]}-{rec[1]}",
                    "rating": round(w.rating), "rd": round(w.rd)})
        if rank >= 40:
            break
    return out


def main():
    boys = parse_techfall(BOYS_DATA, "boys")
    girls = parse_techfall(GIRLS_DATA, "girls")

    # team -> section, learned from the (sectioned) CIF-State boys bouts,
    # so Doc B's CA wrestlers inherit a section; out-of-state stay "OOS".
    from techfall_parser import canon_team
    team_section = {}
    for b in boys:
        if b.section_w and b.section_w != "OOS":
            team_section[canon_team(b._w_team)] = b.section_w
        if b.section_l and b.section_l != "OOS":
            team_section[canon_team(b._l_team)] = b.section_l

    docb = parse_docb(DOCB_DATA, team_section)     # boys only; 126 omitted
    boys += docb
    grades = parse_docb.grades                     # wid -> grade

    by = {("boys", w): [] for w in BOYS_WEIGHTS}
    by.update({("girls", w): [] for w in GIRLS_WEIGHTS})
    for b in boys:
        by[("boys", b.weight)].append(b)
    for b in girls:
        by[("girls", b.weight)].append(b)

    boards = []
    for w in BOYS_WEIGHTS:
        wr = rich_126_board() if w == 126 else board_for(by[("boys", w)], grades)
        boards.append({"gender": "boys", "weight": w, "wrestlers": wr})
    for w in GIRLS_WEIGHTS:
        boards.append({"gender": "girls", "weight": w,
                       "wrestlers": board_for(by[("girls", w)])})

    data = {"generated": datetime.date.today().isoformat(),
            "title": "California HS Wrestling Rankings",
            "weights": boards}
    path = "/mnt/user-data/outputs/rankings.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

    print("ALL 28 BOARDS\n" + "-" * 48)
    for bd in boards:
        champ = bd["wrestlers"][0]["name"] if bd["wrestlers"] else "(no data)"
        n = len(bd["wrestlers"])
        print(f"  {bd['gender']:5} {bd['weight']:>3}  {n:>2} ranked   champ: {champ}")
    print(f"\nWrote {path}")


if __name__ == "__main__":
    main()
