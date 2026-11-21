"""
Bar-by-bar replay + the pre-registered measures from research/PLAN.md.

Execution model (fixed in PLAN.md, do not change here):
  signal confirms on close of bar i  ->  fill at OPEN of bar i+1
  entry costs spread/2, exit costs spread/2  (full round trip charged)
  holding window for excursions = bars i+1 .. j  (j = bar the opposite signal confirms)
  exit fill = open(j+1)
No lookahead: nothing from bar >i influences the decision at bar i.
"""
import sys, os, json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine import clean_signals, pine_atr


# ---------------------------------------------------------------- data
def load_bars(path, tz_note=""):
    """Accepts csv/parquet with ts/open/high/low/close (+ optional spread, volume)."""
    if path.endswith(".parquet"):
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    ren = {"time": "ts", "datetime": "ts", "date": "ts", "timestamp": "ts",
           "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"}
    df = df.rename(columns={k: v for k, v in ren.items() if k in df.columns})
    if not np.issubdtype(df["ts"].dtype, np.number):
        df["ts"] = pd.to_datetime(df["ts"], utc=True, format="mixed").view("int64") // 10**9
    df = df.sort_values("ts").drop_duplicates("ts").reset_index(drop=True)
    for c in ("open", "high", "low", "close"):
        df[c] = df[c].astype(float)
    df["dt"] = pd.to_datetime(df["ts"], unit="s", utc=True)
    return df


def data_health(df):
    gaps = np.diff(df["ts"].values)
    modal = int(pd.Series(gaps).mode().iloc[0]) if len(gaps) else 0
    inside = gaps[gaps == modal].size
    big = gaps[gaps > 3 * 3600]
    bad_ohlc = int(((df.high < df.low) | (df.close > df.high) | (df.close < df.low)
                    | (df.open > df.high) | (df.open < df.low)).sum())
    return {
        "bars": int(len(df)),
        "first": str(df.dt.iloc[0]), "last": str(df.dt.iloc[-1]),
        "span_days": round((df.ts.iloc[-1] - df.ts.iloc[0]) / 86400, 1),
        "modal_gap_s": modal,
        "pct_bars_contiguous": round(100 * inside / max(len(gaps), 1), 2),
        "gaps_over_3h": int(big.size),
        "largest_gap_h": round(float(big.max()) / 3600, 1) if big.size else 0.0,
        "price_min": round(float(df.close.min()), 2),
        "price_max": round(float(df.close.max()), 2),
        "ohlc_violations": bad_ohlc,
    }


# ---------------------------------------------------------------- legs
def build_legs(df, factor=1.2, atr_period=7, spread=0.30, spread_col="spread",
               extra_cost=0.0):
    """
    One row per signal = one leg held to the opposite signal.

    BID/ASK MODEL (bars are BID bars, as an MT5 chart shows):
      LONG  : buy at the ASK  -> entry = open + spread ; exits happen on the BID,
              so trigger tests and exit fills use the bar's own high/low.
      SHORT : sell at the BID -> entry = open          ; exits happen on the ASK,
              so trigger tests and exit fills use high+spread / low+spread.
    Exactly one spread is therefore paid per round trip, and stop-trigger timing is
    correct for both directions (charging half each side would make short stops
    trigger later than they really do).
    `extra_cost` is commission etc. in price units, charged once per round trip.
    """
    h = df["high"].values; l = df["low"].values
    c = df["close"].values; o = df["open"].values
    n = len(df)
    d, buy, sell, st = clean_signals(h, l, c, factor, atr_period)
    atr14 = pine_atr(h, l, c, 14)

    spr = (df[spread_col].values if (spread_col and spread_col in df)
           else np.full(n, spread))
    sig = np.where(buy | sell)[0]
    sig = sig[(sig + 1) < n]

    rows = []
    for k, i in enumerate(sig):
        direction = 1 if buy[i] else -1
        e = i + 1
        j = sig[k + 1] if k + 1 < len(sig) else n - 2
        x = min(j + 1, n - 1)
        if x <= e:
            continue
        s_in, s_out = spr[e], spr[x]
        if direction > 0:
            entry = o[e] + s_in          # pay the ask
            exit_ = o[x]                 # sell back at the bid
        else:
            entry = o[e]                 # sell at the bid
            exit_ = o[x] + s_out         # buy back at the ask

        held = slice(e, j + 1)
        # excursions in the price we could actually EXIT at
        if direction > 0:
            best, worst = float(h[held].max()), float(l[held].min())
        else:
            best = float(l[held].min()) + s_in
            worst = float(h[held].max()) + s_in
        mfe = (best - entry) * direction
        mae = (entry - worst) * direction
        avail = mfe

        infant = {}
        for nb in (1, 2, 3, 5):
            s2 = slice(e, min(e + nb, j + 1))
            if s2.start >= s2.stop:
                infant[f"mae{nb}"] = 0.0; infant[f"mfe{nb}"] = 0.0
            else:
                if direction > 0:
                    bb, ww = float(h[s2].max()), float(l[s2].min())
                else:
                    bb, ww = float(l[s2].min()) + s_in, float(h[s2].max()) + s_in
                infant[f"mfe{nb}"] = (bb - entry) * direction
                infant[f"mae{nb}"] = (entry - ww) * direction

        prev_ext = np.nan
        if k > 0:
            pe = slice(sig[k - 1] + 1, i + 1)
            if pe.start < pe.stop:
                prev_ext = float(h[pe].max()) if direction < 0 else float(l[pe].min())

        net = (exit_ - entry) * direction - extra_cost
        rows.append(dict(
            k=k, sig_i=int(i), entry_i=int(e), exit_i=int(x),
            ts=int(df.ts.iloc[i]), dt=df.dt.iloc[i],
            dir=direction, entry=entry, exit=exit_,
            net=net,
            gross=(o[x] - o[e]) * direction,
            avail=avail, mfe=mfe, mae=mae,
            giveback=mfe - net,
            bars=int(j + 1 - e),
            atr=float(atr14[i]) if atr14[i] == atr14[i] else np.nan,
            spread=float(s_in),
            st_at_sig=float(st[i]),
            lag=abs(entry - prev_ext) if prev_ext == prev_ext else np.nan,
            hour=int(df.dt.iloc[i].hour), dow=int(df.dt.iloc[i].dayofweek),
            **infant))
    return pd.DataFrame(rows), d, buy, sell, st


def efficiency_ratio(close, n=10):
    c = np.asarray(close, float)
    out = np.full(len(c), np.nan)
    if len(c) <= n:
        return out
    net = np.abs(c[n:] - c[:-n])
    path = pd.Series(np.abs(np.diff(c, prepend=c[0]))).rolling(n).sum().values[n:]
    with np.errstate(divide="ignore", invalid="ignore"):
        out[n:] = np.where(path > 0, net / path, np.nan)
    return out


# ---------------------------------------------------------------- measures
def q(a, p):
    a = np.asarray(a, float); a = a[~np.isnan(a)]
    return float(np.percentile(a, p)) if a.size else float("nan")


def bucket_table(legs, by, label, min_n=0):
    g = legs.groupby(by)
    t = pd.DataFrame({
        "n": g.size(),
        "net_per_trade": g["net"].mean().round(3),
        "net_total": g["net"].sum().round(1),
        "avail_per_trade": g["avail"].mean().round(2),
        "capture_%": (100 * g["net"].sum() / g["avail"].sum()).round(1),
    })
    t.index.name = label
    return t[t.n >= min_n]


def report(legs, df, gbp_per_pt=0.733, out=None):
    L = legs
    lines = []
    P = lines.append
    span = (df.ts.iloc[-1] - df.ts.iloc[0]) / 86400
    tdays = len(set(df.dt.dt.date))

    P("=" * 78)
    P("HOLD-TO-FLIP BENCHMARK  (the number every added rule must beat)")
    P("=" * 78)
    n = len(L)
    net = L.net.sum(); gross = L.gross.sum(); cost = gross - net
    P(f"trades {n}   calendar days {span:.0f}   trading days {tdays}   "
      f"trades/day {n/max(tdays,1):.1f}")
    P(f"GROSS pts {gross:+.1f}    spread cost {cost:.1f}    NET pts {net:+.1f}")
    P(f"NET per trade {net/max(n,1):+.4f} pt    NET per trading day {net/max(tdays,1):+.2f} pt")
    P(f"in GBP @0.01 lot: net {net*gbp_per_pt:+.2f}  per day {net*gbp_per_pt/max(tdays,1):+.2f}  "
      f"cost {cost*gbp_per_pt:.2f}")
    verdict = ("EDGE (>= +0.30/trade)" if net/max(n,1) >= 0.30 else
               "MARGINAL (0..+0.30)" if net/max(n,1) >= 0 else
               "NEGATIVE — raw signal not tradeable on its own")
    P(f"PRE-REGISTERED VERDICT: {verdict}")

    P("")
    P("TREND CAPTURE  [primary]")
    P(f"  available total {L.avail.sum():.0f} pt   captured {net:.0f} pt   "
      f"capture {100*net/max(L.avail.sum(),1e-9):.1f}%")
    P(f"  sum MFE {L.mfe.sum():.0f} pt   sum giveback {L.giveback.sum():.0f} pt")
    for thr in (2, 5, 10, 20, 40):
        s = (L.avail >= thr).mean() * 100
        sub = L[L.avail >= thr]
        P(f"  legs offering >={thr:>2} pt: {s:5.1f}%  (n={len(sub):5d})  "
          f"their net/trade {sub.net.mean():+.3f}  their total net {sub.net.sum():+.0f}")

    P("")
    P("DISTRIBUTIONS (pt)")
    for col in ("avail", "net", "mfe", "mae", "giveback", "lag", "bars", "atr"):
        P(f"  {col:9s} p10 {q(L[col],10):8.2f}  p25 {q(L[col],25):8.2f}  "
          f"med {q(L[col],50):8.2f}  p75 {q(L[col],75):8.2f}  p90 {q(L[col],90):8.2f}  "
          f"max {np.nanmax(L[col].values):9.2f}")

    P("")
    P("SIGNAL LAG — how much of the move was already gone when the signal printed")
    P(f"  lag/ATR ratio: med {np.nanmedian((L.lag/L.atr).values):.2f}  "
      f"(1.2 expected from the band distance alone)")
    P(f"  execution slip (signal close -> next open), med "
      f"{np.nanmedian(np.abs(L.entry - df.close.values[L.sig_i.values]) ):.3f} pt")

    P("")
    P("FAKES (avail < 2x spread — never offered the round trip)")
    fake = L[L.avail < 2 * L.spread]
    P(f"  {len(fake)} of {n} = {100*len(fake)/max(n,1):.1f}% of legs, "
      f"net {fake.net.sum():+.0f} pt ({100*fake.net.sum()/min(net,-1e-9) if net<0 else 0:.0f}% of loss)")

    P("")
    P("WINNERS vs LOSERS — adverse excursion in the first N held bars")
    w = L[L.net > 0]; lo = L[L.net <= 0]
    P(f"  winners n={len(w)}  avg net {w.net.mean():+.3f}  losers n={len(lo)}  avg net {lo.net.mean():+.3f}")
    for nb in (1, 2, 3, 5):
        P(f"  first {nb} bar(s): winners med MAE {q(w[f'mae{nb}'],50):.2f} p75 {q(w[f'mae{nb}'],75):.2f}"
          f"   |   losers med MAE {q(lo[f'mae{nb}'],50):.2f} p75 {q(lo[f'mae{nb}'],75):.2f}")

    P("")
    P("BY SESSION (UTC hour)  — action is SIZE, never refusal")
    sess = pd.cut(L.hour, bins=[-1, 6, 11, 15, 20, 23],
                  labels=["00-06 Asia", "07-11 London", "12-15 Overlap", "16-20 NY", "21-23 Late"])
    P(bucket_table(L.assign(sess=sess), "sess", "session").to_string())

    P("")
    P("BY HOUR (UTC)")
    P(bucket_table(L, "hour", "hour").to_string())

    P("")
    P("BY ATR QUINTILE (volatility regime)")
    L2 = L.dropna(subset=["atr"]).copy()
    L2["atrq"] = pd.qcut(L2.atr, 5, labels=["Q1 quiet", "Q2", "Q3", "Q4", "Q5 wild"])
    P(bucket_table(L2, "atrq", "atr_quintile").to_string())

    P("")
    P("BY WEEKDAY (0=Mon)")
    P(bucket_table(L, "dow", "dow").to_string())

    P("")
    P("WALK-FORWARD HALVES (same measure, two disjoint periods)")
    mid = L.ts.iloc[len(L) // 2]
    for name, sub in (("H1", L[L.ts < mid]), ("H2", L[L.ts >= mid])):
        P(f"  {name}: n={len(sub)}  net {sub.net.sum():+.0f} pt  "
          f"net/trade {sub.net.mean():+.4f}  capture {100*sub.net.sum()/max(sub.avail.sum(),1e-9):.1f}%")

    P("")
    P("EQUITY PATH @0.01 lot on a 50 GBP account (hold-to-flip, no other rules)")
    eq = 50 + np.cumsum(L.net.values) * gbp_per_pt
    peak = np.maximum.accumulate(eq)
    dd = peak - eq
    P(f"  end {eq[-1]:.2f}   max drawdown {dd.max():.2f} GBP   "
      f"min equity {eq.min():.2f}   ruin(<=0) {'YES' if eq.min()<=0 else 'no'}")
    daily = L.assign(day=L.dt.dt.date).groupby("day").net.sum() * gbp_per_pt
    P(f"  worst day {daily.min():+.2f} GBP   best day {daily.max():+.2f} GBP   "
      f"median day {daily.median():+.2f} GBP   days {len(daily)}")

    txt = "\n".join(lines)
    if out:
        open(out, "w").write(txt)
    return txt


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--spread", type=float, default=0.30)
    ap.add_argument("--spread-col", default="spread")
    ap.add_argument("--factor", type=float, default=1.2)
    ap.add_argument("--atr", type=int, default=7)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    df = load_bars(a.path)
    print(json.dumps(data_health(df), indent=1))
    legs, d, b, s, st = build_legs(df, a.factor, a.atr, a.spread, a.spread_col)
    legs.to_parquet(a.out + ".legs.parquet") if a.out else None
    print(report(legs, df, out=a.out))
