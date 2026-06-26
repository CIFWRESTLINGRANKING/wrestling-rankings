#!/usr/bin/env python3
"""Generalized carank DATA-page parser (all weights)."""
import re, json
from collections import defaultdict
from wrestling_rating_engine import Bout, RatingEngine, Config

GRADE_HIDE = {"Sr"}
SECTION_PHRASES = [("CENTRAL COAST","CC"),("NORTH COAST","NC"),("SAN DIEGO","SD"),
 ("SAC JOAQUIN","SJ"),("SACJOAQUIN","SJ"),("LOS ANGELES","LA"),("SAN FRANCISCO","SF"),
 ("NORTHERN","NS"),("SOUTHERN","SS"),("OAKLAND","OAK"),("CENTRAL","CS")]
DAY = {"CARL":40,"COS":42,"SOT":44,"MAD":50,"OAK":52,"MM":54,"DOW":56,"MAN":58,"LC":58,"SE":60,
 "NOR":60,"CV":62,"DP":62,"BB":64,"JR":64,"KM":66,"BA":68,"DUAL":70,"CM":75,"RT":80,"ZC":80,
 "AZ":82,"VE":84,"LAK":86,"UP":88,"SN":90,"TOC":95,"APT":95,"RE":95,"RED":96,"WL":96,"OV":98,
 "BAK":98,"NOG":99,"EV":78,"TD":100,"TOK":70,"LB":70,"CC":72,"EDI":74,"DB":110,"TL":112,
 "TIM":112,"MAT":114,"TV":120,"5C":120,"SL":122,"HL":124,"VDL":124,"KOTM":124,"EYL":126,
 "WYL":126,"RH":126,"AA":118,"EH":118,"AR":118,"MID":135,"CIT":135,"MC":136,"BVAL":140,
 "SD1":150,"SD2":150,"SD3":150,"SD4":150,"ELC":150,"HOL":150,"AC":150,"FW":150,"PIT":152,"MV":152,
 "MS":120,"SC":150,"WD":150,"SVl":150,"TC":150,"ML":150,"RIG":120,"KC":130,"SWL":160,
 "C1":160,"C2":160,"C3":160,"C4":160,"CSD":160,"CVC":160,"SJ1":162,"SJ2":162,"SJ3":162,"SJ5":162,
 "SJAA":162,"SFL":162,"PVL":162,"MRL":162,"BL":162,"DEL":162,"EAL":165,"N1":166,"NS1":166,
 "NC1":165,"NC2":165,"NC12":165,"CCN":168,"CCSS":170,"SSCE":168,"SSCO":168,"SSN":168,"SSI":168,
 "SSS":168,"SSE":168,"SSC":168,"RC":166,"SJS":172,"CS":174,"SSB":174,"SSG":174,"CCS":174,
 "SDS":174,"NCS":174,"NS":174,"LAS":174,"LA":174,"LA2":172}

def canon_team(t):
    t = (t or "").lower().replace("\u2019","").replace("`","")
    t = re.sub(r"[.,'\u2026)]","",t); t = re.sub(r"\s+"," ",t).strip()
    A = {"clovis n":"clovisnorth","clovis no":"clovisnorth","clovis north":"clovisnorth",
     "clovis e":"cloviseast","clovis east":"cloviseast","clovis w":"cloviswest",
     "bosco":"stjohnbosco","st john bosco":"stjohnbosco","st marys":"stmarys",
     "granite h":"granitehills","corona dm":"coronadelmar","mission o":"missionoak",
     "mission v":"missionviejo","palm des":"palmdesert","so torr":"southtorrance",
     "south h":"southhills","bella v":"bellavista","del oro":"deloro","del norte":"delnorte",
     "jf kenn":"jfkennedy","jf kennedy":"jfkennedy","central c":"centralcatholic",
     "no bak":"northbakersfield","north bak":"northbakersfield","mar vista":"marvista",
     "elk grove":"elkgrove","paloma v":"palomavalley","victor v":"victorvalley",
     "la serna":"laserna","la mirada":"lamirada","mt whitney":"mtwhitney",
     "silver cr":"silvercreek","silver creek":"silvercreek"}
    return A.get(t,t).replace(" ","")

def surname(n):
    n=(n or "").strip().rstrip("."); p=[x for x in re.split(r"\s+",n) if x]
    if len(p)>1 and len(p[0].rstrip("."))<=2: p=p[1:]
    return p[-1].lower() if p else ""

def classify(score):
    s=(score or "").strip(); sl=s.lower()
    if re.search(r"\d:\d\d",s) or "fall" in sl: return "fall"
    if "mfor" in sl or "mfr" in sl or "i-d" in sl: return "med_forfeit"
    if "forf" in sl or "fft" in sl: return "forfeit"
    if "dq" in sl or sl.startswith("def"): return "default"
    m=re.search(r"(\d+)\s*-\s*(\d+)",s)
    if m:
        marg=abs(int(m.group(1))-int(m.group(2)))
        if marg>=15: return "tech"
        if marg>=8: return "major"
    return "decision"

BOUT_RE=re.compile(r"(?P<ev>[A-Za-z0-9]+)\s*[:;]\s*(?P<wl>[dl])\.\s*(?P<opp>[A-Za-z][^()]*?)\s*"
    r"\((?P<team>[^)]+)\)\s*(?P<score>.*?)(?=(?:[A-Za-z0-9]+\s*[:;]\s*[dl]\.)|$)")
BLOCK_RE=re.compile(r"-\s*\*\*#?(\d+)\*\*")

def section_of(header):
    h=re.sub(r"\s+"," ",header).upper()
    for phrase,code in SECTION_PHRASES:
        if phrase in h: return code
    return "?"

def parse(weight,page_path,roster):
    text=open(page_path,encoding="utf-8").read()
    by_rank={r:(n,g,s) for r,n,g,s in roster}
    rwid={r:f"{surname(n)}|{canon_team(s)}" for r,n,g,s in roster}
    sur_idx=defaultdict(list)
    for r,n,g,s in roster: sur_idx[surname(n)].append((rwid[r],canon_team(s)))
    NAME={rwid[r]:by_rank[r][0] for r in by_rank}
    TEAM={rwid[r]:by_rank[r][2] for r in by_rank}
    GR={rwid[r]:by_rank[r][1] for r in by_rank}; SEC={}
    marks=list(BLOCK_RE.finditer(text)); seen,bouts=set(),[]
    for i,mk in enumerate(marks):
        rank=int(mk.group(1))
        if rank not in by_rank: continue
        seg=text[mk.end(): marks[i+1].start() if i+1<len(marks) else len(text)]
        swid=rwid[rank]; SEC[swid]=section_of(seg[:220]); seg1=re.sub(r"\s+"," ",seg)
        for m in BOUT_RE.finditer(seg1):
            wl,opp,team,score=m.group("wl"),m.group("opp"),m.group("team"),m.group("score")
            osur,oteam=surname(opp),canon_team(team); cands=sur_idx.get(osur,[])
            if len(cands)==1: owid=cands[0][0]
            elif len(cands)>1: owid=next((w for w,tk in cands if tk==oteam),f"{osur}|{oteam}")
            else:
                owid=f"{osur}|{oteam}"; NAME.setdefault(owid,opp.strip()); TEAM.setdefault(owid,team.strip())
            if owid==swid: continue
            win,los=(swid,owid) if wl=="d" else (owid,swid)
            method=classify(score); key=(frozenset((win,los)),m.group("ev"),method)
            if key in seen: continue
            seen.add(key)
            bouts.append(Bout(m.group("ev"),DAY.get(m.group("ev"),120),weight,win,los,method,
                              SEC.get(win,"?"),SEC.get(los,"?")))
    return bouts,NAME,TEAM,GR,SEC,rwid

def board(weight,page_path,roster):
    bouts,NAME,TEAM,GR,SEC,rwid=parse(weight,page_path,roster)
    eng=RatingEngine(Config()); eng.ingest(bouts)
    wl={}
    for b in bouts:
        wl.setdefault(b.winner,[0,0])[0]+=1; wl.setdefault(b.loser,[0,0])[1]+=1
    ranked=set(rwid.values()); rows=[]; rk=0
    for w in eng.rankings():
        if w.wid not in ranked: continue
        if GR.get(w.wid,"") in GRADE_HIDE: continue
        rk+=1
        rows.append(dict(rank=rk,name=NAME.get(w.wid,w.wid),team=TEAM.get(w.wid,""),
            section=SEC.get(w.wid,"?"),grade=GR.get(w.wid,""),
            record=f"{wl.get(w.wid,[0,0])[0]}-{wl.get(w.wid,[0,0])[1]}",
            rating=round(w.rating),rd=round(w.rd)))
    return rows,len(bouts)
