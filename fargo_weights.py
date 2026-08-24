"""
FARGO 2026 -> projected folkstyle weight for 2026-27 boards
===========================================================
Source: FloWrestling championship-side bracket results, 2026 USMC Junior
Nationals (Junior Boys Freestyle + 16U Boys Freestyle), cross-checked against
USA Wrestling and WIN Magazine recaps.

Every California entrant found on the championship side is listed with the
Fargo weight class he actually competed at. Consolation-side-only entrants are
NOT captured here -- Flo publishes championship side only. See KNOWN_GAPS.

Keys are (name, fargo_weight). Names are as printed by Flo, which does not
carry school, so matching to rankings.json is by name. See ALIASES for the
cases where Flo's spelling differs from the board's.
"""

# --- Junior Boys Freestyle, CA entrants, championship side -------------------
JUNIOR = {
    106: ["Luke Loren", "Frank Fuentes", "Cody Holtberg", "Rex Kohner",
          "Luca Gordon"],
    113: ["Thales Silva", "Jax Vang", "Xavier Garcia", "Eisa Scrapper",
          "Gabriel Martinez", "Brodie Henderson", "Eli Mayer"],
    120: ["Aiden Garcia", "Anthony Garza", "Thiago Silva", "Declan Leonard",
          "Caden Herrera", "Camm Colgate", "Ethan Waxberg", "Zack Samano",
          "Mason Schlaht", "Julius Mark Villamil"],
    126: ["Samuel Sanchez", "Rene Cordero", "Timothy Walker Jr",
          "Xamian Munoz", "Phillip Green", "Dominic Cabot"],
    132: ["Luke Schoch", "Cole Cronan", "Micah Garcia", "Nathaniel Mitchell"],
    138: ["Matthew Orbeta", "Cael Humphrey", "Brian Miller",
          "Landon Salindong", "Ames-Michael Hoevker", "Cruz Contreras",
          "Christian Ripa"],
    144: ["Jesse Grajeda", "James Ruiz", "Michael Terrell", "Jameson Moore",
          "Sergio Gomez", "Steven Frink", "Helo Blackwell"],
    150: ["Jack Malinconico", "Marcello Calavitta", "Jack Bronte",
          "Justice Commendatore"],
    157: ["Tommy Holguin", "Diego Valdiviezo", "Dimetry Molina",
          "Carlos Valdiviezo", "Demian Garcia"],
    165: ["Jacob Perez", "Chris Anguiano", "Christian Stoeber",
          "Andrew Peterson"],
    175: ["Mario Carini", "Mason Carnrite", "Kelan Stever", "Benjamin Rosen",
          "Jude Holiday"],
    190: ["Mason Savidan", "Mason Ontiveros", "James Holiday",
          "Gabriel Barragan", "Efosa Osayande"],
    215: ["Daniel Moylan", "Carter Vannest", "Adan Castillo",
          "Rocco Biasotti"],
    285: ["Matthew Cooley", "Noah Larios", "Eli Swartz", "Israel Pinzon"],
}

# --- 16U Boys Freestyle, CA entrants seen on championship side ---------------
# PARTIAL. Flo's 16U article was only retrieved down to 113 in this pass.
SIXTEEN_U = {
    106: ["Sebastian Gutierrez", "Cameron Bartlow"],
    113: ["Michael Bernabe"],
    120: ["Thiago Silva"],   # returning 16U champ moving up (USAW day-1 preview)
}

# Names that appear in BOTH divisions at different weights. Junior wins,
# since Junior is the older/heavier bracket and better predicts next season.
DIVISION_CONFLICTS = ["Thiago Silva"]

# Flo's printed name -> rankings.json board name.
# Flo bracket lines carry no school, so these were resolved by hand and
# confirmed by Jeff (Aug 24, 2026). Exact-string matching silently drops
# these to "unmatched" without them.
ALIASES = {
    "Nathaniel Mitchell": "Nate Mitchell",              # Del Oro, 126 -> 132
    "Helo Blackwell": "Jonah Helo Blackwell",           # Central Catholic, 144 = 144
    "Christian Stoeber": "Christian Acosta Stoeber",    # Fountain Valley, 165 = 165
    "Daniel Moylan": "Daniel Mick Moylan",              # Poway, 215 = 215
}

# Sergio Gomez (St. John Bosco) matched exactly: board 157, Fargo 144.
# -13 is the only downward move in the set and runs against the July-heavier
# pattern. CONFIRMED same wrestler by Jeff (Aug 24, 2026) -- he cut for Fargo.
# Left here as a note because a future reviewer will flag it again otherwise.
CONFIRMED_OUTLIERS = {"Sergio Gomez": "cut down for Fargo; 157 -> 144 is real"}

KNOWN_GAPS = """
1. Consolation-side-only CA entrants are missing. Flo publishes the
   championship side only. A wrestler who lost his first bout never appears.
2. 16U coverage is partial (106/113/120 only).
3. Greco entrants are excluded by design -- freestyle only, matching the
   existing rankings.json ingest policy.
4. Flo bracket lines carry no school, so all matching is by name.
"""


def fargo_weight_map():
    """name -> fargo weight. Junior takes precedence over 16U."""
    out = {}
    for wt, names in SIXTEEN_U.items():
        for n in names:
            out[n] = wt
    for wt, names in JUNIOR.items():
        for n in names:
            out[n] = wt
    return out


# --- Fargo credentials & folkstyle H2H, for preseason arrival seeding --------
# Credential = All-American finish (top 8) at a specific Fargo weight.
# place: 1/2 for known finals results; "AA" where the medal is confirmed but
# the exact placement match result was not (sorts below any known place).
# Sources: Flo finals/champions articles + USAW state-by-state recap.
FARGO_CREDENTIALS = {
    "Luke Loren":      {"division": "Junior", "place": 1,    "weight": 106},
    "Frank Fuentes":   {"division": "Junior", "place": 2,    "weight": 106},
    "Thales Silva":    {"division": "Junior", "place": 2,    "weight": 113},
    "Michael Bernabe": {"division": "16U",    "place": 1,    "weight": 113},
    "Thiago Silva":    {"division": "Junior", "place": "AA", "weight": 120},
    "Aiden Garcia":    {"division": "Junior", "place": "AA", "weight": 120},
    "Samuel Sanchez":  {"division": "Junior", "place": 1,    "weight": 126},
    "Jesse Grajeda":   {"division": "Junior", "place": 1,    "weight": 144},
    "Mario Carini":    {"division": "Junior", "place": 2,    "weight": 175},
    "Mason Ontiveros": {"division": "Junior", "place": "AA", "weight": 190},
    "Daniel Mick Moylan": {"division": "Junior", "place": 2, "weight": 215},
    # Jacob Perez (Jr AA 165), Sebastian Gutierrez / Cameron Bartlow (16U 106)
    # are not on any board; Mason McDonnell's 16U medal weight is unconfirmed.
}

# Folkstyle 2025-26 head-to-heads BETWEEN FARGO ARRIVALS, from carank pages.
# (winner, loser): "W-L". Used only to order/pull-up arrivals during seeding.
ARRIVAL_H2H = {
    ("Michael Bernabe", "Thales Silva"): "3-2",   # incl. Central Section final
    ("Anthony Garza",   "Thiago Silva"): "3-0",
}
