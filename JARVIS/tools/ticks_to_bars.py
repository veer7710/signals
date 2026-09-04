"""
Tick -> OHLC bar builder, with the REAL bid/ask spread carried through.

SOURCE: github.com/FX-Data/FX-Data-XAUUSD-DS, year branches, Dukascopy-derived
XAUUSD tick files. Format, verified by hand against the historical gold price:

    2018.03.27 10:00:00.635,13.48641,13.48842,0.00,0.00
    date time (ms)          bid      ask      vol  vol

PRICE IS SCALED BY 1/100. 13.48641 x 100 = 1348.64, which is exactly where gold
traded in March 2018, and (ask-bid) x 100 = 0.201 points, which matches the
0.20-0.46 spread Veer measured off his own PU Prime terminal. Both volume
columns are identically zero in this feed and are NOT used for anything.

WHY THIS MATTERS MORE THAN THE BARS: this project has spent ninety experiments
ASSUMING a spread (`Costs.spread = 0.46`) because it had no bid/ask data. E-089
made the whole M1 question turn on cost/stop <= 0.11, and E-096 made a 40-pound
account turn on a 2.7-point stop, both computed from an assumed number. This
feed carries a real, per-tick, time-stamped spread, so those become measurements.

Bars are built from the BID (the sell side), which is what a chart shows, and
each bar additionally records:
    spread_mean / spread_max   the real cost of trading inside that bar
    ticks                      how many quotes formed it - a thin bar is a
                               different object from a busy one and the
                               difference is invisible in OHLC alone

Run:  python3 JARVIS/tools/ticks_to_bars.py <year> [months...]
"""
from __future__ import annotations
import os, sys, csv, json, glob, datetime, collections

SRC = "/home/user/fx-data/fx-data-xauusd-ds/XAUUSD"
OUT = "/home/user/signals/data"
SCALE = 100.0
TFS = {"M1": 60, "M5": 300, "M15": 900}


def parse(path):
    with open(path, newline="") as f:
        for row in csv.reader(f):
            if len(row) < 3:
                continue
            try:
                t = datetime.datetime.strptime(row[0][:19], "%Y.%m.%d %H:%M:%S")
                bid = float(row[1]) * SCALE
                ask = float(row[2]) * SCALE
            except (ValueError, IndexError):
                continue
            if bid <= 0 or ask <= 0 or ask < bid:
                continue                      # crossed or empty quote: drop it
            yield int(t.replace(tzinfo=datetime.timezone.utc).timestamp()), bid, ask


def build(year, months=None):
    pat = os.path.join(SRC, str(year), "*" if months is None else "[0-9][0-9]")
    files = []
    for d in sorted(glob.glob(os.path.join(SRC, str(year), "*"))):
        mm = os.path.basename(d)
        if months and mm not in months:
            continue
        files += sorted(glob.glob(os.path.join(d, "*.csv")))
    print(f"{year}: {len(files)} tick files")

    bars = {tf: {} for tf in TFS}
    n_ticks = 0
    for k, path in enumerate(files):
        if k % 250 == 0:
            print(f"  {k}/{len(files)} ... {n_ticks:,} ticks")
        for ts, bid, ask in parse(path):
            n_ticks += 1
            sp = ask - bid
            for tf, sec in TFS.items():
                b = (ts // sec) * sec
                d = bars[tf].get(b)
                if d is None:
                    bars[tf][b] = [bid, bid, bid, bid, sp, sp, 1]
                else:
                    if bid > d[1]: d[1] = bid
                    if bid < d[2]: d[2] = bid
                    d[3] = bid
                    d[4] += sp
                    if sp > d[5]: d[5] = sp
                    d[6] += 1
    print(f"  {n_ticks:,} ticks total")

    os.makedirs(OUT, exist_ok=True)
    for tf, d in bars.items():
        rows = [[b, v[0], v[1], v[2], v[3],
                 round(v[4] / v[6], 5), round(v[5], 5), v[6]]
                for b, v in sorted(d.items())]
        # [ts, o, h, l, c, spread_mean, spread_max, ticks] - the first five are
        # exactly engine.load()'s format, so the extra columns are additive and
        # nothing downstream breaks.
        p = os.path.join(OUT, f"GOLD_{tf}_{year}.json")
        with open(p, "w") as f:
            json.dump(rows, f)
        sp = [r[5] for r in rows]
        print(f"  {tf}: {len(rows):,} bars -> {p}")
        print(f"       spread mean {sum(sp)/len(sp):.3f}  "
              f"median {sorted(sp)[len(sp)//2]:.3f}  "
              f"p95 {sorted(sp)[int(len(sp)*0.95)]:.3f} points")
    return bars


if __name__ == "__main__":
    yr = sys.argv[1] if len(sys.argv) > 1 else "2018"
    mo = sys.argv[2:] or None
    build(yr, mo)
