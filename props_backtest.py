"""Walk-forward backtest + calibration for props_model.

There are no free historical prop PRICES, so this measures *calibration*: when the
model says 60%, does the over hit ~60%? For each player-game (weeks 3-18) it builds the
projection from data strictly before that week, evaluates synthetic lines spread
around the projection, and compares predicted P(over) with what happened.

  fit seasons  (default 2022-2023): tune K/DECAY, ALPHA/BETA, and the dispersion
                                    (sigma for yardage, r for counts) per market
  test seasons (default 2024-2025): held-out reliability bins, Brier, log loss, ECE,
                                    plus the naive "hit X of last Y games" baseline
                                    that the X sheets use, for comparison

Writes data/props/calibration.json (read by props_model.edge_board to gate leans).

Run:  python3 props_backtest.py            # ~1-3 min
"""

import json
import math
import os
import sys
from datetime import datetime, timezone

import props_model as pmod
from props_model import MARKET_STAT, POSITIONS, YARDAGE

USAGE = {  # min average usage in prior games to be a "regular" with a priced prop
    "pass_yds": ("attempts", 15), "pass_tds": ("attempts", 15),
    "pass_ints": ("attempts", 15), "rush_yds": ("carries", 4),
    "rec_yds": ("targets", 2.5), "receptions": ("targets", 2.5),
    "anytime_td": (None, 0),
}
BINS = [(i / 10, (i + 1) / 10) for i in range(10)]


def _usage_ok(market, rows):
    col, lo = USAGE[market]
    if col is None:
        return sum((r.get("carries") or 0) + (r.get("targets") or 0) for r in rows) / \
            len(rows) >= 4
    return sum(r.get(col) or 0 for r in rows) / len(rows) >= lo


def collect(seasons, log=print):
    """Samples with the pieces needed to re-project under any (K, DECAY, ALPHA, BETA)."""
    out = []
    for s in seasons:
        h = pmod.History(s - 1, s)
        for (season, pid), rows in h.by_player.items():
            if season != s:
                continue
            last = h.by_player.get((s - 1, pid), [])
            for r in rows:
                wk = r["week"]
                if wk < 3 or wk > 18:
                    continue
                prior_rows = [x for x in rows if x["week"] < wk]
                if len(prior_rows) < 2:
                    continue
                imp, opp = h.implied_points(s, wk, r["team"])
                for m, f in MARKET_STAT.items():
                    if r["position"] not in POSITIONS[m] or not _usage_ok(m, prior_rows):
                        continue
                    xs = [f(x) for x in prior_rows]
                    prior = (sum(f(x) for x in last) / len(last)) if len(last) >= 4 else (
                        h.pos_mean(s, r["position"], m, wk) or 0.0)
                    of = h.opp_factor(s, opp, r["position"], m, wk, pmod.PARAMS["K_OPP"]) \
                        if opp else 1.0
                    out.append({"season": s, "market": m, "xs": xs, "prior": prior,
                                "of": of, "sf": (imp / pmod.PARAMS["LG_IMPLIED"]) if imp
                                else 1.0, "y": f(r)})
        log(f"  {s}: {len(out)} samples so far")
    return out


def _mean(sm, K, DECAY, a, b):
    xs = sm["xs"]
    n = len(xs)
    w = [DECAY ** (n - 1 - i) for i in range(n)]
    base = (sum(wi * x for wi, x in zip(w, xs)) + K * sm["prior"]) / (sum(w) + K)
    return max(base, 0.0) * (max(sm["of"], 0.2) ** a) * (max(sm["sf"], 0.3) ** b)


def _lines(market, mean):
    if market in YARDAGE:
        return sorted({math.floor(mean * k) + 0.5 for k in (0.6, 0.8, 1.0, 1.2, 1.4)
                       if mean * k >= 1})
    if market == "anytime_td":
        return [0.5]
    c = math.floor(mean)
    return [x + 0.5 for x in range(max(c - 2, 0), c + 2)]


def _logloss(p, hit):
    p = min(max(p, 1e-4), 1 - 1e-4)
    return -math.log(p if hit else 1 - p)


def fit(samples, log=print):
    P = json.loads(json.dumps(pmod.PARAMS))
    by_m = {}
    for sm in samples:
        by_m.setdefault(sm["market"], []).append(sm)
    var = {m: (sum(s["y"] ** 2 for s in v) / len(v) - (sum(s["y"] for s in v) / len(v)) ** 2)
           or 1.0 for m, v in by_m.items()}
    # 1. shared K / DECAY on normalized MSE (ALPHA/BETA at defaults)
    best = None
    for K in (1.0, 2.0, 3.0, 5.0):
        for D in (0.7, 0.8, 0.9, 1.0):
            err = 0.0
            for m, v in by_m.items():
                a, b = P["ALPHA"][m], P["BETA"][m]
                err += sum((s["y"] - _mean(s, K, D, a, b)) ** 2 for s in v) / len(v) / var[m]
            if best is None or err < best[0]:
                best = (err, K, D)
    P["K"], P["DECAY"] = best[1], best[2]
    log(f"  K={P['K']} DECAY={P['DECAY']}")
    # 2. per-market ALPHA / BETA
    grid = (0.0, 0.25, 0.5, 0.75, 1.0)
    for m, v in by_m.items():
        bb = None
        for a in grid:
            for b in grid:
                e = sum((s["y"] - _mean(s, P["K"], P["DECAY"], a, b)) ** 2 for s in v)
                if bb is None or e < bb[0]:
                    bb = (e, a, b)
        P["ALPHA"][m], P["BETA"][m] = bb[1], bb[2]
    log(f"  ALPHA={P['ALPHA']}\n  BETA={P['BETA']}")
    # 3. dispersion by log loss over synthetic lines
    for m, v in by_m.items():
        means = [_mean(s, P["K"], P["DECAY"], P["ALPHA"][m], P["BETA"][m]) for s in v]
        cands = ([x / 10 for x in range(12, 46, 2)] if m in YARDAGE
                 else [1.5, 2, 3, 5, 8, 12, 20, 40, 1e6])
        bb = None
        for c in cands:
            Q = dict(P, SIGMA=dict(P["SIGMA"]), R=dict(P["R"]))
            (Q["SIGMA"] if m in YARDAGE else Q["R"])[m] = c
            ll = 0.0
            for s, mu in zip(v, means):
                for ln in _lines(m, mu):
                    ll += _logloss(pmod.p_over(mu, ln, m, Q), s["y"] > ln)
            if bb is None or ll < bb[0]:
                bb = (ll, c)
        (P["SIGMA"] if m in YARDAGE else P["R"])[m] = bb[1]
    log(f"  SIGMA={P['SIGMA']}\n  R={P['R']}")
    return P


def evaluate(samples, P):
    res = {}
    by_m = {}
    for sm in samples:
        by_m.setdefault(sm["market"], []).append(sm)
    for m, v in by_m.items():
        bins = [{"lo": lo, "hi": hi, "n": 0, "ps": 0.0, "hits": 0} for lo, hi in BINS]
        brier = ll = nb_brier = 0.0
        n = 0
        for s in v:
            mu = _mean(s, P["K"], P["DECAY"], P["ALPHA"][m], P["BETA"][m])
            for ln in _lines(m, mu):
                p = pmod.p_over(mu, ln, m, P)
                hit = s["y"] > ln
                naive = sum(1 for x in s["xs"] if x > ln) / len(s["xs"])
                brier += (p - hit) ** 2
                nb_brier += (naive - hit) ** 2
                ll += _logloss(p, hit)
                n += 1
                b = bins[min(int(p * 10), 9)]
                b["n"] += 1
                b["ps"] += p
                b["hits"] += hit
        out_bins = [{"lo": b["lo"], "hi": b["hi"], "n": b["n"],
                     "pred": round(b["ps"] / b["n"], 3) if b["n"] else None,
                     "obs": round(b["hits"] / b["n"], 3) if b["n"] else None}
                    for b in bins]
        ece = sum(b["n"] * abs(b["pred"] - b["obs"]) for b in out_bins if b["n"]) / n
        res[m] = {"n": n, "players_games": len(v), "brier": round(brier / n, 4),
                  "naive_brier": round(nb_brier / n, 4), "logloss": round(ll / n, 4),
                  "ece": round(ece, 4), "bins": [b for b in out_bins if b["n"]]}
    return res


def run(fit_seasons=(2022, 2023), test_seasons=(2024, 2025), log=print):
    log("collecting fit samples…")
    fs = collect(fit_seasons, log)
    P = fit(fs, log)
    log("collecting test samples…")
    ts = collect(test_seasons, log)
    res = evaluate(ts, P)
    params = {k: P[k] for k in ("K", "DECAY", "ALPHA", "BETA", "SIGMA", "R")}
    out = {"built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
           "fit_seasons": list(fit_seasons), "test_seasons": list(test_seasons),
           "params": params, "markets": res}
    os.makedirs(os.path.dirname(pmod.CALIB_PATH), exist_ok=True)
    tmp = pmod.CALIB_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(out, f, indent=1)
    os.replace(tmp, pmod.CALIB_PATH)
    return out


def main():
    out = run()
    print(f"\nHeld-out {out['test_seasons']}:  market  n  Brier(model)  Brier(naive hit-rate)"
          "  ECE")
    for m, r in out["markets"].items():
        print(f"  {m:11} {r['n']:6}  {r['brier']:.4f}  {r['naive_brier']:.4f}  {r['ece']:.4f}")
        print("     " + "  ".join(f"{b['pred']:.2f}→{b['obs']:.2f}({b['n']})"
                                   for b in r["bins"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
