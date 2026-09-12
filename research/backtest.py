"""
backtest.py -- one strategy runner used by every test and by every EA spec.

Reports CAPTURE RATIO (exit / peak) because "it went to £15 and closed at £4"
is an exit-geometry question and you cannot fix it without the number.
"""
import numpy as np
import core

class Result:
    def __init__(self, trades, days, cost):
        self.t = trades; self.days = days; self.cost = cost
    def stats(self):
        t = self.t
        if not t: return dict(n=0)
        pts = np.array([x["pts"] for x in t])
        pk  = np.array([x["peak"] for x in t])
        R   = np.array([x["R"] for x in t])
        wins = pts > 0
        cap = np.where(pk > 1e-9, np.clip(pts, 0, None) / np.maximum(pk, 1e-9), np.nan)
        gp = pts[wins].sum(); gl = -pts[~wins].sum()
        eq = np.cumsum(pts); peak = np.maximum.accumulate(eq)
        dd = float((peak - eq).max()) if len(eq) else 0.0
        return dict(
            n=len(t), per_day=len(t)/self.days if self.days else 0,
            win=float(wins.mean()),
            pts=float(pts.mean()), total=float(pts.sum()),
            R=float(R.mean()),
            pf=float(gp/gl) if gl > 0 else float("inf"),
            peak=float(pk.mean()),
            capture=float(np.nanmean(cap)),
            maxdd_pts=dd,
            bars=float(np.mean([x["bars"] for x in t])),
            expect_gbp=float(pts.mean()*0.787),
        )

def run(d, signals, *, stop_fn, exit_cfg, cost=0.15, max_bars=120,
        one_at_a_time=True, session_mask=None):
    """signals: list of (bar_idx_of_signal, direction).
    Entry at OPEN of signal_idx+1 (R1). Costs charged both sides.
    exit_cfg keys:
      mode      'fixed' | 'trail_atr' | 'giveback' | 'lock' | 'hybrid'
      rr        target in R (fixed / hybrid)
      trail     ATR multiple (trail_atr)
      give      fraction of run-up handed back (giveback)
      arm       R of profit before trail arms
      lock_step R granularity of the ratchet (lock / hybrid)
      stall     bars without a new peak before closing (0 = off)
    """
    a = core.atr(d, 14); n = d["n"]; out = []; busy_until = -1
    for si, sd in signals:
        j = si + 1
        if j >= n - 1 or np.isnan(a[si]) or a[si] <= 0: continue
        if one_at_a_time and j < busy_until: continue
        if session_mask is not None and not session_mask[j]: continue
        e = d["o"][j] + sd*cost
        stop_d = stop_fn(d, si, sd, a[si])
        if stop_d <= 0: continue
        stop = e - sd*stop_d
        targ = e + sd*exit_cfg.get("rr", 2.0)*stop_d
        peak = 0.0; peak_bar = j; exit_px = None; k = j
        for k in range(j, min(j+max_bars, n)):
            hi, lo = d["h"][k], d["l"][k]
            fav = (hi - e)*sd if sd > 0 else (e - lo)
            if fav > peak: peak, peak_bar = fav, k
            # --- stop first (R3) ---
            hit_s = lo <= stop if sd > 0 else hi >= stop
            if hit_s:
                exit_px = d["o"][k] if (d["o"][k]-stop)*sd < 0 else stop
                break
            m = exit_cfg["mode"]
            if m in ("fixed", "hybrid"):
                hit_t = hi >= targ if sd > 0 else lo <= targ
                if hit_t:
                    exit_px = d["o"][k] if (d["o"][k]-targ)*sd > 0 else targ
                    break
            # --- ratchet the stop on this bar's close ---
            c_ = d["c"][k]
            if m == "trail_atr":
                cand = c_ - sd*exit_cfg["trail"]*a[k]
            elif m == "giveback":
                cand = (e + sd*peak*(1.0-exit_cfg["give"])
                        if peak >= exit_cfg.get("arm",0.0)*stop_d else stop)
            elif m in ("lock","hybrid"):
                step = exit_cfg.get("lock_step",0.5)*stop_d
                steps = int(peak/step) if step > 0 else 0
                cand = (e + sd*(steps-1)*step*exit_cfg.get("lock_keep",1.0)
                        if steps >= 2 else stop)
            else:
                cand = stop
            stop = max(stop,cand) if sd > 0 else min(stop,cand)
            st = exit_cfg.get("stall",0)
            if st and (k-peak_bar) >= st:
                exit_px = c_; k += 1; break
        if exit_px is None:
            exit_px = d["c"][min(k, n-1)]
        pts = (exit_px - e)*sd - cost
        out.append(dict(i=j, dir=sd, pts=pts, R=pts/stop_d, peak=peak,
                        peak_R=peak/stop_d, bars=k-j+1, stop_d=stop_d))
        busy_until = k+1
    days = (d["t"][-1]-d["t"][0])/86400.0*(5/7)
    return Result(out, days, cost)

def stop_struct(buf=0.25, look=3):
    def f(d, si, sd, av):
        w = slice(max(0,si-look), si+1)
        ext = d["l"][w].min() if sd > 0 else d["h"][w].max()
        return abs(d["o"][si+1]-ext) + buf*av
    return f

def stop_atr(mult=1.0):
    return lambda d, si, sd, av: mult*av
