"""
staged.py -- multi-stage exit engine (partials + breakeven + runner trail).

This is how a real trader with a 70-90% "win rate" actually gets one: bank a
partial early so most trades close green, push the stop to breakeven so the
rest are free, and let a runner trail. The headline win rate is real; the
question this file answers is what it COSTS in expectancy, and whether there
is a setting where you get both.

Fill rules unchanged: entry at next bar open, stop wins intrabar ties, a bar
that gaps through a level fills at that bar's open, cost charged per unit
traded on entry and on every exit leg.
"""
import numpy as np
import core

def run_staged(d, signals, *, stop_fn, cfg, cost=0.15, max_bars=160,
               one_at_a_time=True, session_mask=None, target_fn=None):
    """cfg:
        tp1_R, f1     first partial: target in R, fraction of position closed
        tp2_R, f2     second partial
        be_at_R       move stop to breakeven once this R is reached (0=off)
        be_lock_R     park the stop this far ABOVE entry when BE triggers
        trail_atr     ATR multiple for the runner
        arm_R         runner trail arms only at this R
        struct_tp     if True and target_fn given, tp1 is the structure level
    """
    a = core.atr(d, 14); n = d["n"]; out = []; busy = -1
    f1, f2 = cfg.get("f1", 0.0), cfg.get("f2", 0.0)
    tp1R, tp2R = cfg.get("tp1_R", 0.0), cfg.get("tp2_R", 0.0)
    beR, lockR = cfg.get("be_at_R", 0.0), cfg.get("be_lock_R", 0.0)
    trailM, armR = cfg.get("trail_atr", 3.0), cfg.get("arm_R", 1.0)

    for si, sd in signals:
        j = si + 1
        if j >= n - 1 or np.isnan(a[si]) or a[si] <= 0: continue
        if one_at_a_time and j < busy: continue
        if session_mask is not None and not session_mask[j]: continue
        stop_d = stop_fn(d, si, sd, a[si])
        if stop_d <= 0: continue
        e = d["o"][j] + sd * cost
        stop = e - sd * stop_d
        tp1 = e + sd * tp1R * stop_d if f1 > 0 else None
        if cfg.get("struct_tp") and target_fn is not None:
            lvl = target_fn(d, si, sd)
            if lvl is not None:
                want = (lvl - e) * sd
                # a structure target is only usable if it is beyond a minimum
                # and not so far the partial never fills
                if 0.3 * stop_d <= want <= 4.0 * stop_d:
                    tp1 = lvl
        tp2 = e + sd * tp2R * stop_d if f2 > 0 else None

        rem = 1.0                      # fraction still open
        realised = 0.0                 # P/L in price units, position-weighted
        peak = 0.0; k = j; beDone = False; armed = False
        hit1 = hit2 = False

        for k in range(j, min(j + max_bars, n)):
            hi, lo, op, cl = d["h"][k], d["l"][k], d["o"][k], d["c"][k]
            fav = (hi - e) * sd if sd > 0 else (e - lo)
            if fav > peak: peak = fav

            # --- stop first, on whatever is left (R3) ---
            hit_s = lo <= stop if sd > 0 else hi >= stop
            if hit_s:
                px = op if (op - stop) * sd < 0 else stop
                realised += rem * (px - e) * sd
                realised -= rem * cost
                rem = 0.0
                break

            # --- partial 1 ---
            if not hit1 and tp1 is not None:
                t = hi >= tp1 if sd > 0 else lo <= tp1
                if t:
                    px = op if (op - tp1) * sd > 0 else tp1
                    realised += f1 * (px - e) * sd
                    realised -= f1 * cost
                    rem -= f1; hit1 = True
            # --- partial 2 ---
            if hit1 and not hit2 and tp2 is not None and rem > 1e-9:
                t = hi >= tp2 if sd > 0 else lo <= tp2
                if t:
                    px = op if (op - tp2) * sd > 0 else tp2
                    take = min(f2, rem)
                    realised += take * (px - e) * sd
                    realised -= take * cost
                    rem -= take; hit2 = True
            if rem <= 1e-9:
                k += 1
                break

            # --- breakeven push ---
            if beR > 0 and not beDone and peak >= beR * stop_d:
                cand = e + sd * lockR * stop_d
                stop = max(stop, cand) if sd > 0 else min(stop, cand)
                beDone = True

            # --- runner trail ---
            if peak >= armR * stop_d:
                armed = True
                cand = cl - sd * trailM * a[k]
                stop = max(stop, cand) if sd > 0 else min(stop, cand)

        if rem > 1e-9:                                  # timed out
            kk = min(k, n - 1)
            realised += rem * (d["c"][kk] - e) * sd
            realised -= rem * cost
        realised -= cost                                 # entry cost, full size
        out.append(dict(i=j, dir=sd, pts=realised, R=realised / stop_d,
                        peak=peak, peak_R=peak / stop_d, bars=k - j + 1,
                        stop_d=stop_d, hit1=hit1, hit2=hit2, armed=armed))
        busy = k + 1
    return out

def summarise(trades, days):
    if not trades: return dict(n=0)
    pts = np.array([t["pts"] for t in trades])
    R   = np.array([t["R"] for t in trades])
    w = pts > 0
    gp, gl = pts[w].sum(), -pts[~w].sum()
    eq = np.cumsum(pts); pk = np.maximum.accumulate(eq)
    return dict(n=len(trades), per_day=len(trades)/days if days else 0,
                win=float(w.mean()), pts=float(pts.mean()), R=float(R.mean()),
                total=float(pts.sum()),
                pf=float(gp/gl) if gl > 0 else float("inf"),
                avgW=float(pts[w].mean()) if w.any() else 0.0,
                avgL=float(pts[~w].mean()) if (~w).any() else 0.0,
                maxdd=float((pk-eq).max()) if len(eq) else 0.0,
                p1=float(np.mean([t["hit1"] for t in trades])),
                t_=float(pts.mean()/(pts.std(ddof=1)/np.sqrt(len(pts))))
                   if len(pts) > 2 and pts.std() > 0 else 0.0)

def next_pool_target(d, si, sd, left=3, right=3, lookback=200):
    """Structure target: the nearest un-taken swing level in the trade's
    direction. This is a TP 'based on analysis' rather than a fixed multiple."""
    lo = max(0, si - lookback)
    best = None
    for i in range(si - right - 1, lo, -1):
        if i - left < 0: break
        w = slice(i - left, i + right + 1)
        if sd > 0:
            if d["h"][i] == d["h"][w].max() and d["h"][i] > d["c"][si]:
                if best is None or d["h"][i] < best: best = d["h"][i]
        else:
            if d["l"][i] == d["l"][w].min() and d["l"][i] < d["c"][si]:
                if best is None or d["l"][i] > best: best = d["l"][i]
    return best
