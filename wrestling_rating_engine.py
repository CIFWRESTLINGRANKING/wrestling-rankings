"""
California HS Wrestling Rating Engine — prototype
=================================================

A transparent, algorithmic rating + ranking engine for high school wrestlers.

Design choices (all documented inline so they're easy to challenge/tune):

  * RATING SYSTEM:  Glicko-2.  Chosen over plain Elo because it tracks a
    *rating deviation* (RD = uncertainty) and a *volatility* per wrestler.
    That gives us provisional ratings for free: a wrestler with 3 matches has
    a huge RD and is trusted far less than one with 30.

  * MARGIN OF VICTORY:  handled by *weighting each match's evidence* (the
    "w-factor" idea from DubStat / WrestleStat).  A pin is stronger evidence
    than a 3-2 decision, so it moves ratings more.  We do NOT distort the
    win-probability model — a win is still a win (score 1 / 0); we only scale
    how much each result counts.  Forfeits/defaults count as a result but get
    no MOV bonus.

  * STRENGTH OF SCHEDULE:  emergent.  Beating a 1900 earns more than beating a
    1300 automatically.  We never compute SoS as a separate number.

  * COLD START:  rankings sort by a CONSERVATIVE rating (r - 2*RD), i.e. "the
    system is ~95% sure you're at least this good."  A hot 3-match wrestler
    can't leapfrog a proven one until the matches back it up.

  * RATING DECAY:  RD inflates with inactivity (standard Glicko-2).  A wrestler
    who hasn't competed in months drifts back toward uncertainty and slides in
    the conservative ranking — desirable.

  * HEAD-TO-HEAD (the hybrid rule you picked):  the rating is the primary sort,
    but within a configurable band, a clean recent H2H win flips the order so
    the guy who won on the mat ranks ahead.  Outside the band, the body of work
    wins.  Cycles (A>B>C>A inside the band) fall back to rating.

This is a single-weight-class engine.  In production you run one instance per
(gender, weight class).  Cross-weight "pound-for-pound" is a separate, later
problem.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

SCALE = 173.7178          # Glicko-2 <-> Glicko-1 conversion constant
BASE_RATING = 1500.0
BASE_RD = 350.0
BASE_VOL = 0.06


@dataclass
class Config:
    tau: float = 0.5               # volatility constraint (0.3-0.6 typical)
    base_rating: float = BASE_RATING
    base_rd: float = BASE_RD
    base_vol: float = BASE_VOL
    period_days: float = 7.0       # one rating period = one week
    # conservative-rating multiplier for ranking (2 ~= 95% confidence floor)
    conservative_k: float = 2.5
    # hybrid H2H: only override inside this rating band (Glicko-1 scale points)
    h2h_band: float = 45.0
    h2h_max_passes: int = 6        # bounded swaps -> no infinite loops on cycles
    # Margin-of-victory weights ("w-factor"). Decision is the baseline = 1.0.
    mov_weights: dict = field(default_factory=lambda: {
        "fall": 1.40,        # pin
        "tech": 1.30,        # technical fall
        "major": 1.15,       # major decision
        "decision": 1.00,    # regular decision (baseline)
        "sv": 1.00,          # sudden victory / overtime — close, no bonus
        "forfeit": 0.10,     # no contest -> near-zero skill evidence
        "med_forfeit": 0.10, # injury/medical forfeit (kid hurt) -> same, but
                             # tracked separately so the audit can tell that a
                             # 0-loss record may be injury-related, not missing
        "default": 0.10,     # injury default mid-match -> near-zero evidence
        "dq": 1.00,
    })
    # Style weights: how much an off-season bout counts vs a folkstyle bout.
    # Freestyle/Greco use different rules, so they're informative but noisier
    # for predicting folkstyle, hence discounted. Tunable.
    style_weights: dict = field(default_factory=lambda: {
        "folkstyle": 1.00,   # the high school season — the thing we're ranking
        "freestyle": 0.65,   # off-season; correlated but different ruleset
        "greco": 0.55,       # furthest from folkstyle
    })


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #

@dataclass
class Bout:
    event_id: str
    day: float                 # days since season start (defines chronology)
    weight: int
    winner: str
    loser: str
    result: str = "decision"   # key into mov_weights
    section_w: Optional[str] = None
    section_l: Optional[str] = None
    style: str = "folkstyle"   # folkstyle | freestyle | greco  -> style_weights


@dataclass
class Wrestler:
    wid: str
    mu: float                  # rating on Glicko-2 internal scale
    phi: float                 # RD on internal scale
    sigma: float               # volatility
    last_period: float = 0.0   # period index of last competition
    n_matches: int = 0

    # --- convenient views on the human-readable Glicko-1 scale ---
    @property
    def rating(self) -> float:
        return self.mu * SCALE + BASE_RATING

    @property
    def rd(self) -> float:
        return self.phi * SCALE

    def conservative(self, k: float) -> float:
        """Lower-confidence-bound rating used for ranking (handles cold start)."""
        return self.rating - k * self.rd


# --------------------------------------------------------------------------- #
# Glicko-2 core
# --------------------------------------------------------------------------- #

def _g(phi: float) -> float:
    return 1.0 / math.sqrt(1.0 + 3.0 * phi * phi / (math.pi * math.pi))


def _E(mu: float, mu_j: float, phi_j: float) -> float:
    return 1.0 / (1.0 + math.exp(-_g(phi_j) * (mu - mu_j)))


def _new_volatility(sigma, phi, v, delta, tau, eps=1e-6):
    """Glickman's Illinois-method volatility update."""
    a = math.log(sigma * sigma)
    phi2, v_ = phi * phi, v

    def f(x):
        ex = math.exp(x)
        num = ex * (delta * delta - phi2 - v_ - ex)
        den = 2.0 * (phi2 + v_ + ex) ** 2
        return num / den - (x - a) / (tau * tau)

    A = a
    if delta * delta > phi2 + v_:
        B = math.log(delta * delta - phi2 - v_)
    else:
        k = 1
        while f(a - k * tau) < 0:
            k += 1
        B = a - k * tau

    fA, fB = f(A), f(B)
    while abs(B - A) > eps:
        C = A + (A - B) * fA / (fB - fA)
        fC = f(C)
        if fC * fB <= 0:
            A, fA = B, fB
        else:
            fA = fA / 2.0
        B, fB = C, fC
    return math.exp(A / 2.0)


def _age_rd(w: Wrestler, target_period: float, cfg: Config) -> None:
    """Inflate RD for inactivity (periods elapsed since last competition)."""
    elapsed = max(0.0, target_period - w.last_period)
    if elapsed <= 0:
        return
    w.phi = math.sqrt(w.phi * w.phi + w.sigma * w.sigma * elapsed)
    # cap RD at the base (a wrestler can't become *more* uncertain than a newcomer)
    w.phi = min(w.phi, cfg.base_rd / SCALE)


def _update_one(w: Wrestler, opponents, results, weights, cfg: Config):
    """
    Batch Glicko-2 update for one wrestler over the matches in a rating period.
    opponents: list[(mu_j, phi_j)]   results: list[score 1/0]   weights: list[w]
    Returns new (mu, phi, sigma).  Uses pre-period opponent snapshots (correct
    Glicko-2 batch semantics).
    """
    if not opponents:
        # no games: only RD changes (already handled by aging); volatility same
        return w.mu, w.phi, w.sigma

    v_inv = 0.0
    delta_sum = 0.0
    for (mu_j, phi_j), s, wt in zip(opponents, results, weights):
        g = _g(phi_j)
        E = _E(w.mu, mu_j, phi_j)
        v_inv += wt * g * g * E * (1.0 - E)
        delta_sum += wt * g * (s - E)
    v = 1.0 / v_inv
    delta = v * delta_sum

    sigma_p = _new_volatility(w.sigma, w.phi, v, delta, cfg.tau)
    phi_star = math.sqrt(w.phi * w.phi + sigma_p * sigma_p)
    phi_p = 1.0 / math.sqrt(1.0 / (phi_star * phi_star) + 1.0 / v)
    mu_p = w.mu + phi_p * phi_p * delta_sum
    return mu_p, phi_p, sigma_p


# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #

class RatingEngine:
    def __init__(self, cfg: Config | None = None):
        self.cfg = cfg or Config()
        self.wrestlers: dict[str, Wrestler] = {}
        # head-to-head log: (a, b) -> list of (day, winner)
        self.h2h: dict[tuple, list] = {}

    def _get(self, wid: str) -> Wrestler:
        if wid not in self.wrestlers:
            c = self.cfg
            self.wrestlers[wid] = Wrestler(
                wid, mu=(c.base_rating - BASE_RATING) / SCALE,
                phi=c.base_rd / SCALE, sigma=c.base_vol,
            )
        return self.wrestlers[wid]

    def _period(self, day: float) -> float:
        return day / self.cfg.period_days

    def ingest(self, bouts: list[Bout]) -> None:
        """Process bouts in chronological order, batched by event (= rating period)."""
        bouts = sorted(bouts, key=lambda b: (b.day, b.event_id))
        # group consecutive bouts of the same event together
        i = 0
        while i < len(bouts):
            j = i
            ev = bouts[i].event_id
            while j < len(bouts) and bouts[j].event_id == ev:
                j += 1
            self._ingest_event(bouts[i:j])
            i = j

    def _ingest_event(self, event_bouts: list[Bout]) -> None:
        cfg = self.cfg
        period = self._period(event_bouts[0].day)

        # 1. collect participants, age their RD to this event, snapshot pre-event state
        participants = set()
        for b in event_bouts:
            participants.add(b.winner)
            participants.add(b.loser)
        for wid in participants:
            _age_rd(self._get(wid), period, cfg)
        snap = {wid: (self.wrestlers[wid].mu, self.wrestlers[wid].phi)
                for wid in participants}

        # 2. build each wrestler's match list against PRE-event opponent snapshots
        matches: dict[str, list] = {wid: [] for wid in participants}
        for b in event_bouts:
            wt = cfg.mov_weights.get(b.result, 1.0) * \
                 cfg.style_weights.get(getattr(b, "style", "folkstyle"), 1.0)
            matches[b.winner].append((snap[b.loser], 1.0, wt))
            matches[b.loser].append((snap[b.winner], 0.0, wt))
            self._log_h2h(b)

        # 3. apply batched updates
        for wid in participants:
            w = self.wrestlers[wid]
            opp = [m[0] for m in matches[wid]]
            res = [m[1] for m in matches[wid]]
            wts = [m[2] for m in matches[wid]]
            w.mu, w.phi, w.sigma = _update_one(w, opp, res, wts, cfg)
            w.last_period = period
            w.n_matches += len(opp)

    def _log_h2h(self, b: Bout) -> None:
        key = tuple(sorted((b.winner, b.loser)))
        self.h2h.setdefault(key, []).append((b.day, b.winner))

    def recent_h2h_winner(self, a: str, b: str) -> Optional[str]:
        """Most recent head-to-head winner between a and b, or None if never met."""
        rec = self.h2h.get(tuple(sorted((a, b))))
        if not rec:
            return None
        return max(rec, key=lambda r: r[0])[1]

    # ---- prediction -------------------------------------------------------- #

    def win_probability(self, a: str, b: str) -> float:
        """P(a beats b), accounting for BOTH wrestlers' uncertainty (Glicko)."""
        wa, wb = self._get(a), self._get(b)
        q = math.log(10) / 400.0
        rd2 = math.sqrt(wa.rd ** 2 + wb.rd ** 2)
        g = 1.0 / math.sqrt(1.0 + 3.0 * (q * q) * (rd2 * rd2) / (math.pi ** 2))
        return 1.0 / (1.0 + 10.0 ** (-g * (wa.rating - wb.rating) / 400.0))

    # ---- ranking (hybrid H2H) --------------------------------------------- #

    def rankings(self, as_of_day: Optional[float] = None) -> list[Wrestler]:
        cfg = self.cfg
        # inflate everyone's RD to "now" so the inactive drift down
        if as_of_day is not None:
            target = self._period(as_of_day)
            for w in self.wrestlers.values():
                _age_rd(w, target, cfg)

        order = sorted(self.wrestlers.values(),
                       key=lambda w: w.conservative(cfg.conservative_k),
                       reverse=True)

        # hybrid head-to-head: bounded adjacent swaps inside the band
        ids = [w.wid for w in order]
        cons = {w.wid: w.conservative(cfg.conservative_k) for w in order}
        for _ in range(cfg.h2h_max_passes):
            swapped = False
            for k in range(len(ids) - 1):
                hi, lo = ids[k], ids[k + 1]      # hi is ranked above lo by rating
                if cons[hi] - cons[lo] > cfg.h2h_band:
                    continue                      # gap too big -> body of work wins
                if self.recent_h2h_winner(hi, lo) == lo:
                    ids[k], ids[k + 1] = lo, hi   # the guy who won on the mat goes up
                    swapped = True
            if not swapped:
                break
        by_id = {w.wid: w for w in order}
        return [by_id[i] for i in ids]


# --------------------------------------------------------------------------- #
# Backtester  (prequential / online: predict each bout BEFORE learning from it)
# --------------------------------------------------------------------------- #

def backtest(bouts: list[Bout], cfg: Config | None = None, warmup_matches: int = 4):
    """
    Walk bouts in order.  For each, predict the winner from current ratings,
    then update.  Report accuracy / Brier / log-loss.  "Settled" metrics only
    count bouts where both wrestlers already have >= warmup_matches (fair test).
    """
    eng = RatingEngine(cfg)
    bouts = sorted(bouts, key=lambda b: (b.day, b.event_id))

    n = n_correct = 0
    sn = sn_correct = 0
    brier = logloss = 0.0

    # group by event so predictions use pre-event ratings, like production
    i = 0
    while i < len(bouts):
        j = i
        ev = bouts[i].event_id
        while j < len(bouts) and bouts[j].event_id == ev:
            j += 1
        block = bouts[i:j]

        for b in block:
            wa, wb = eng._get(b.winner), eng._get(b.loser)
            settled = wa.n_matches >= warmup_matches and wb.n_matches >= warmup_matches
            p = eng.win_probability(b.winner, b.loser)  # P(actual winner wins)
            n += 1
            n_correct += (p >= 0.5)
            brier += (1.0 - p) ** 2
            logloss += -math.log(max(p, 1e-12))
            if settled:
                sn += 1
                sn_correct += (p >= 0.5)
        eng.ingest(block)
        i = j

    return {
        "engine": eng,
        "n_all": n,
        "acc_all": n_correct / n if n else float("nan"),
        "n_settled": sn,
        "acc_settled": sn_correct / sn if sn else float("nan"),
        "brier": brier / n if n else float("nan"),
        "logloss": logloss / n if n else float("nan"),
    }
