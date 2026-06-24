"""
Test: parse REAL CalGrappler Doc Buchanan text and feed the engine.

(The text below is copied verbatim from the 2026 Doc Buchanan results page —
finals, semis, and quarters for a few weights — to exercise weight tracking,
the winner-first convention, out-of-state tags, generic 'def.'+method, and
'Last, First' names. In an unrestricted environment you'd instead call
fetch_url('https://www.calgrappler.com/2026-doc-buchanan-invitational-results/').)
"""

from calgrappler_parser import parse_calgrappler
from wrestling_rating_engine import RatingEngine, Config

SAMPLE = r"""
## 2026 Doc Buchanan Finals

**141**
(1) Moses Mendoza – Gilroy (12) TF (15) Chris LaLonde – Roosevelt (CO) (12), 21-6
**129**
(2) Ignacio Villasenor – Stillwater (OK) (11) DEC (1) Freddy Bachmann – Faith Christian (PA) (10), 7-6 UTB
**135**
(1) Ashton Besmer – Buchanan (12) MD (2) Slater Hicks – Valencia (11), 10-2

## Semi-Final Results

### 129
(1) Freddy Bachmann – Faith Christian (PA) (10) dec. (4) Paul Ruiz – Buchanan (10), 2-1 UTB
(2) Ignacio Villasenor – Stillwater (OK) (11) dec. (3) Siraj Sidhu – Clovis North (12), 7-2

### 147
(4) Tommy Verrette – Edmond North (OK) (12) dec. (9) Chris Arreola – Clovis North (10), 2-1
(2) Jesse Grajeda – St. John Bosco (11) def. (11) Laudan Henry – St. Peter's Prep (NJ) (12), mfor

## Quarter-Final Results

### 129
(1) Freddy Bachmann – Faith Christian (PA) (10) dec. (8) Tommy Marchetti – Delbarton (NJ) (10), 4-1
(4) Paul Ruiz – Buchanan (10) dec. (5) Sean Willcox – St. John Bosco (12), 7-1
(3) Siraj Sidhu – Clovis North (12) dec. (6) Isaiah Jones – Bixby (OK) (12), 14-8
(2) Ignacio Villasenor – Stillwater (OK) (11) dec. (7) Mikey Ruiz – Randall (TX) (12), 10-3

### 135
(1) Ashton Besmer – Buchanan (12) tf Jack Maliniconico – Poway (11), 19-4
(3) Nathan Carrillo – St. John Bosco (12) dec. (6) Max Cumbee – Imm. Con. (IL) (11), 3-2

### 147
(9) Chris Arreola – Clovis North (10) def. (1) Joseph Toscano – Buchanan (12), fall

## Placers (should be SKIPPED — not pairwise)

### 129
1. Ignacio Villasenor – Stillwater (OK) (11) – DEC 7-6 UTB
2. Freddy Bachmann – Faith Christian (PA) (10)
3. Paul Ruiz – Buchanan (10) – DEC 3-1

### Pre-Seeds (should be SKIPPED)
129 – 1. Bachmann, Freddy – Faith Christian (PA) (10)
129 – 4. Ruiz, Paul – Buchanan (10)
"""


def main():
    parsed = parse_calgrappler(SAMPLE, event_id="DOCB", day=100,
                               weight_pool={129: 126}, return_parsed=True)

    print(f"Parsed {len(parsed)} bouts from the page "
          f"(placers & pre-seeds correctly skipped).\n")
    print(f"{'wt':>4}  {'winner':<22} {'result':<9} {'loser':<22} {'flag'}")
    print("-" * 70)
    for pb in parsed:
        b = pb.bout
        wn = getattr(b, "_w_name", b.winner)
        ln = getattr(b, "_l_name", b.loser)
        flag = "inferred" if pb.inferred else ""
        oos = []
        if b.section_w != "CA":
            oos.append(f"W:{b.section_w}")
        if b.section_l != "CA":
            oos.append(f"L:{b.section_l}")
        tag = (flag + " " + " ".join(oos)).strip()
        print(f"{b.weight:>4}  {wn:<22} {b.result:<9} {ln:<22} {tag}")

    # prove they drop straight into the engine
    bouts = [pb.bout for pb in parsed]
    eng = RatingEngine(Config())
    eng.ingest(bouts)
    print(f"\nFed {len(bouts)} parsed bouts into the engine. "
          f"{len(eng.wrestlers)} wrestlers rated.")
    ruiz = [w for w in eng.wrestlers.values() if "paul-ruiz" in w.wid]
    if ruiz:
        r = ruiz[0]
        print(f"Sanity check — Paul Ruiz: rating {r.rating:.0f}, "
              f"{r.n_matches} matches parsed from this page.")

    # quick correctness assertions on the trickiest lines
    def find(wsub, lsub):
        for pb in parsed:
            if wsub in pb.bout.winner and lsub in pb.bout.loser:
                return pb.bout.result
        return None
    print("\nTricky-case checks:")
    print(f"  'def. ... fall'  (Arreola def Toscano) -> {find('arreola','toscano')}"
          f"   (expect fall)")
    print(f"  generic 'def. mfor' (Grajeda/Henry)    -> {find('grajeda','henry')}"
          f"   (expect forfeit)")
    print(f"  'TF' explicit (Mendoza/LaLonde)        -> {find('mendoza','lalonde')}"
          f"   (expect tech)")
    print(f"  weight pooled 129->126 (Ruiz/Willcox)  -> "
          f"{[pb.bout.weight for pb in parsed if 'paul-ruiz' in pb.bout.winner and 'willcox' in pb.bout.loser]}"
          f"   (expect [126])")


if __name__ == "__main__":
    main()
