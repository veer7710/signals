"""
Export candle data + REAL broker costs from MT5, for the JARVIS engine.

Run this ON THE WINDOWS PC that has MetaTrader 5 installed, with MT5 open and
logged in.

    pip install MetaTrader5
    python export_mt5_data.py

It writes JSON files into ./mt5_export/ . Copy that folder into the repo's
data/ directory and the research engine can use it immediately.

WHY THIS MATTERS MORE THAN IT LOOKS
Every backtest in this repo currently assumes a gold spread of 0.30 and $7/lot
commission. Those are reasonable guesses, not your broker's numbers. A strategy
that is profitable at 0.30 can be a loser at 0.60, so until real symbol specs
are in hand, every result carries an unquantified error bar. This script reads
the real values straight from the terminal.
"""
import json, os, sys, datetime

try:
    import MetaTrader5 as mt5
except ImportError:
    sys.exit("Run:  pip install MetaTrader5   (Windows only, MT5 must be installed)")

# Timeframes to pull. Daily is the priority: the published trend-following
# evidence is measured on daily-and-slower data, and this repo has none.
TIMEFRAMES = {
    "1d":  (mt5.TIMEFRAME_D1,  10000),   # ~40 years if the broker has it
    "4h":  (mt5.TIMEFRAME_H4,  30000),
    "1h":  (mt5.TIMEFRAME_H1,  50000),
    "15m": (mt5.TIMEFRAME_M15, 60000),
}

OUT = "mt5_export"


def main():
    if not mt5.initialize():
        sys.exit(f"MT5 initialize() failed: {mt5.last_error()}\n"
                 "Make sure MetaTrader 5 is running and you are logged in.")

    info = mt5.account_info()
    print(f"Connected: {info.server}  balance {info.balance} {info.currency}\n")
    os.makedirs(OUT, exist_ok=True)

    # Everything the broker offers, so the basket can be diversified.
    all_syms = [s.name for s in mt5.symbols_get()]
    print(f"Broker offers {len(all_syms)} symbols.")

    # Prefer a spread of asset classes over many correlated FX pairs.
    wanted_bits = ["XAU", "XAG", "GOLD", "SILVER", "OIL", "WTI", "BRENT", "NGAS",
                   "US30", "US500", "USTEC", "NAS", "SPX", "GER", "DAX", "UK100",
                   "JP225", "AUS200", "COPPER", "PLAT",
                   "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF",
                   "NZDUSD", "EURJPY", "GBPJPY", "EURGBP", "AUDJPY", "USDSEK",
                   "BTC", "ETH"]
    picked = []
    for s in all_syms:
        u = s.upper()
        if any(b in u for b in wanted_bits):
            picked.append(s)
    # de-duplicate broker suffixes (EURUSD, EURUSD.r, EURUSDm ...)
    seen, syms = set(), []
    for s in sorted(picked, key=len):
        key = "".join(ch for ch in s.upper() if ch.isalnum())[:6]
        if key not in seen:
            seen.add(key); syms.append(s)
    print(f"Selected {len(syms)} symbols for export.\n")

    specs = {}
    for sym in syms:
        if not mt5.symbol_select(sym, True):
            continue
        si = mt5.symbol_info(sym)
        tick = mt5.symbol_info_tick(sym)
        if si is None:
            continue
        # THE REAL COSTS — this is the most valuable part of the file
        specs[sym] = {
            "digits": si.digits,
            "point": si.point,
            "spread_points": si.spread,
            "spread_price": si.spread * si.point,
            "live_spread_price": (tick.ask - tick.bid) if tick else None,
            "contract_size": si.trade_contract_size,
            "tick_value": si.trade_tick_value,
            "tick_size": si.trade_tick_size,
            "volume_min": si.volume_min,
            "volume_step": si.volume_step,
            "volume_max": si.volume_max,
            "stops_level": si.trade_stops_level,
            "swap_long": si.swap_long,
            "swap_short": si.swap_short,
            "currency_profit": si.currency_profit,
        }
        for label, (tf, count) in TIMEFRAMES.items():
            rates = mt5.copy_rates_from_pos(sym, tf, 0, count)
            if rates is None or len(rates) < 300:
                continue
            rows = [[int(r["time"]), float(r["open"]), float(r["high"]),
                     float(r["low"]), float(r["close"])] for r in rates]
            clean = "".join(ch for ch in sym if ch.isalnum()).upper()
            with open(f"{OUT}/{clean}_{label}.json", "w") as f:
                json.dump(rows, f, separators=(",", ":"))
            span = (rows[-1][0] - rows[0][0]) / 31557600
            print(f"  {sym:<12} {label:<4} {len(rows):>6} bars  {span:>5.1f} years")

    with open(f"{OUT}/SYMBOL_SPECS.json", "w") as f:
        json.dump(specs, f, indent=1)

    print(f"\nDone. {len(specs)} symbols exported to ./{OUT}/")
    print("SYMBOL_SPECS.json holds your real spreads, commissions basis and swaps.")
    print("Copy the whole folder into the repo's data/ directory.")
    mt5.shutdown()


if __name__ == "__main__":
    main()
