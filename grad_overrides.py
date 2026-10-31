"""Manually-confirmed graduated seniors (Class of 2026).

These are dropped from every returning board, regardless of weight. Most are
wrestlers who never appeared at Doc Buchanan, so the automatic grade filter
(which only knows Doc B grades) can't catch them. As manual review surfaces
more graduating seniors, add their names here — spelling as it appears on the
board is fine; matching ignores case, accents, and spacing.
"""
import re
import unicodedata


def _norm(name):
    n = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", n.lower()).strip()


_GRADUATED_NAMES = [
    # 120
    "Henry Aslikyan", "Zachary Samano", "Troy Montero",
    # 126
    "Issac Torres", "Ricardo Ortiz", "Aaron Klein", "Jake Simmons",
    # 132  (Jack Malinconico removed 2026-10-31: senior in 2026-27, not graduated -- Jeff, 2026-10-12)
    "Arno Vardanyan", "Dominic Bozanic",
    # 138
    "Zaydrein Hernandez", "Raymond Rivera",
    # 144
    "Edward Sheeran", "Ames-Michael Hoevker",
]

# Not graduated, but no longer in California: dropped from every board the same way.
_LEFT_CALIFORNIA_NAMES = [
    "Chris Anderson",   # Liberty (Brentwood), 126 -- moved to Arizona (Jeff, 2026-10-31)
]

GRADUATED = {_norm(n) for n in _GRADUATED_NAMES + _LEFT_CALIFORNIA_NAMES}


def is_graduated(name):
    return _norm(name) in GRADUATED
