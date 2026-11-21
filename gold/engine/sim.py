"""
Exit-rule simulator. Walks bars inside each leg and applies a configurable rule set.

PESSIMISTIC INTRABAR RULE (fixed in PLAN.md): if a bar's range touches both a
protective level and a profit level, the PROTECTIVE one is assumed to fill first.
Within a bar we cannot know the path, so we never give ourselves the benefit.

All exits fill at the LEVEL for stop/target/lock/trail (they are resting orders),
and at the next bar's OPEN for decisions made on a bar close (flip, infant cut,
time stop) — because a decision made on a close can only be acted on afterwards.
Spread is charged half in, half out.
"""
import numpy as np
import pandas as pd


DEFAULTS = dict(
    # protective stop at entry
    stop_mode="st_line",     # "st_line" | "atr" | "fixed" | "none"
    stop_k=1.0,              # multiplier for atr mode
    stop_fixed=3.0,          # pts for fixed mode
    stop_buffer_atr=0.0,     # extra room BEYOND the stop level, in ATR  (v18.90 wick-proof idea)
    stop_floor_pts=0.0,      # absolute minimum stop distance in pts
    # early failure cut: if adverse excursion exceeds X pts within first N held bars -> leave
    infant_pts=0.0,          # 0 = off
    infant_bars=0,
    # hard profit lock: once peak >= arm, park a stop at peak - give, ratcheting
    lock_arm=0.0,            # 0 = off
    lock_give=0.0,
    # chandelier trail: stop = running extreme -/+ k*ATR, only once arm pts reached
    trail_k=0.0,             # 0 = off
    trail_arm=0.0,
    # fixed profit target
    target_pts=0.0,          # 0 = off
    # time stop in held bars
    max_bars=0,              # 0 = off
    # exit when the opposite signal confirms (fills next open)
    exit_on_flip=True,
)


def simulate(df, legs, p=None, spread=None, extra_cost=0.0):
    """
    Same BID/ASK model as replay.build_legs:
      LONG  entry = open + spread, exits tested/filled on the BID (bar high/low)
      SHORT entry = open,          exits tested/filled on the ASK (bar high/low + spread)
    One spread per round trip; stop-trigger timing correct in both directions.
    """
    P = dict(DEFAULTS); P.update(p or {})
    o = df["open"].values; h = df["high"].values
    l = df["low"].values
    n = len(df)
    out = []

    for r in legs.itertuples(index=False):
        d = r.dir
        e = r.entry_i
        if e >= n - 1:
            continue
        atr = r.atr if r.atr == r.atr else 1.0
        spr = spread if spread is not None else r.spread
        entry = o[e] + spr if d > 0 else o[e]
        adj = 0.0 if d > 0 else spr          # shorts exit on the ask

        if P["stop_mode"] == "st_line":
            dist = abs(entry - r.st_at_sig)
        elif P["stop_mode"] == "atr":
            dist = P["stop_k"] * atr
        elif P["stop_mode"] == "fixed":
            dist = P["stop_fixed"]
        else:
            dist = None
        if dist is not None:
            dist += P["stop_buffer_atr"] * atr
            dist = max(dist, P["stop_floor_pts"])
            stop = entry - d * dist
        else:
            stop = None; dist = np.nan

        last_held = r.exit_i - 1
        peak = 0.0; ext = entry
        exit_px = None; why = None; exit_i = None

        bi = e
        while bi <= min(last_held, n - 1):
            hi_x = h[bi] + adj                # exit-price high
            lo_x = l[bi] + adj                # exit-price low
            fav = (hi_x - entry) if d > 0 else (entry - lo_x)
            adv = (entry - lo_x) if d > 0 else (hi_x - entry)

            hit_stop = stop is not None and ((lo_x <= stop) if d > 0 else (hi_x >= stop))
            tgt = entry + d * P["target_pts"] if P["target_pts"] > 0 else None
            hit_tgt = tgt is not None and ((hi_x >= tgt) if d > 0 else (lo_x <= tgt))

            if hit_stop:
                exit_px, why, exit_i = stop, "STOP", bi; break
            if hit_tgt:
                exit_px, why, exit_i = tgt, "TARGET", bi; break

            if fav > peak:
                peak = fav
                ext = hi_x if d > 0 else lo_x

            nxt = bi + 1
            dec = None
            if P["infant_pts"] > 0 and (bi - e) < P["infant_bars"] and adv >= P["infant_pts"]:
                dec = "INFANT"
            elif P["max_bars"] > 0 and (bi - e + 1) >= P["max_bars"]:
                dec = "TIME"
            if dec and nxt <= n - 1:
                exit_px, why, exit_i = o[nxt] + adj, dec, nxt; break

            if P["lock_arm"] > 0 and peak >= P["lock_arm"]:
                lvl = entry + d * (peak - P["lock_give"])
                stop = lvl if stop is None else (max(stop, lvl) if d > 0 else min(stop, lvl))
            if P["trail_k"] > 0 and peak >= P["trail_arm"]:
                lvl = ext - d * P["trail_k"] * atr
                stop = lvl if stop is None else (max(stop, lvl) if d > 0 else min(stop, lvl))
            bi += 1

        if exit_px is None:
            xi = min(r.exit_i, n - 1)
            exit_px, why, exit_i = o[xi] + adj, ("FLIP" if P["exit_on_flip"] else "END"), xi

        net = (exit_px - entry) * d - extra_cost
        out.append(dict(k=r.k, ts=r.ts, dt=r.dt, dir=d, entry=entry, exit=exit_px,
                        net=net, why=why, bars=int(exit_i - e + 1),
                        peak=peak, avail=r.avail, stop_dist=dist, atr=atr,
                        hour=r.hour, dow=r.dow, spread=spr))
    return pd.DataFrame(out)


def score(tr, legs=None, gbp=0.733, lots=0.01, label=""):
    """Compact scorecard for one rule set."""
    if not len(tr):
        return dict(label=label, n=0)
    n = len(tr)
    net = tr.net.sum()
    days = max(len(set(pd.to_datetime(tr.dt).dt.date)), 1)
    eq = np.cumsum(tr.net.values) * gbp * (lots / 0.01)
    dd = float((np.maximum.accumulate(eq) - eq).max())
    av = tr.avail.sum()
    byw = tr.groupby("why").net.agg(["count", "sum"]).round(1)
    return dict(
        label=label, n=n, net_pt=round(float(net), 1),
        per_trade=round(float(net / n), 4),
        per_day_pt=round(float(net / days), 2),
        gbp=round(float(net * gbp * (lots / 0.01)), 2),
        gbp_day=round(float(net * gbp * (lots / 0.01) / days), 2),
        capture_pct=round(float(100 * net / av), 1) if av else None,
        maxdd_gbp=round(dd, 2),
        giveback_pt=round(float((tr.peak - tr.net.clip(lower=-1e9)).clip(lower=0).sum()), 0),
        med_bars=int(tr.bars.median()),
        exits=byw.to_dict("index"),
    )


def sweep(df, legs, grid, spread=None, base=None, extra_cost=0.0):
    """grid: list of (label, paramdict). Returns a DataFrame of scorecards."""
    rows = []
    for label, pp in grid:
        q = dict(base or {}); q.update(pp)
        tr = simulate(df, legs, q, spread=spread, extra_cost=extra_cost)
        s = score(tr, label=label)
        s.pop("exits", None)
        rows.append(s)
    return pd.DataFrame(rows)
