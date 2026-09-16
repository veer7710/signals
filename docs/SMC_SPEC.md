# SMC / ICT / Liquidity — Implementable Spec for an M1 XAUUSD MT5 EA

**Sourcing rule for this document.** WebFetch/curl are blocked in this environment; only
WebSearch (result summaries) worked. Every claim is tagged `[own knowledge]` or
`[search summary]`. Nothing here was read from a primary page. Search summaries establish
only *what practitioners say the concept is*, never that it works. No performance claim in
this document is sourced; the only measured numbers are this repo's own (`docs/FINDINGS.md`).

## 0. Conventions (binding on all pseudocode)

| Item | Definition |
|---|---|
| Indexing | Chronological: `i-1` older than `i`. `i` = most recently **closed** M1 bar. MT5 `iHigh(sym,PERIOD_M1,k)` maps as `k = Bars-1-i`; never read shift 0 for logic. |
| Data | `O,H,L,C[i]`, `V[i]` = tick volume, `T[i]` = bar open time (UTC). One timeframe (M1). |
| `A[i]` | ATR(14) on M1, Wilder, computed from bars `<= i`. M1 XAUUSD reference: **A ≈ 2.1 price units ($2.10)** (`docs/FINDINGS.md` §0). |
| `MV[i]` | median(`V[i-59..i]`) — tick-volume baseline. |
| `body[i]` | `abs(C[i]-O[i])`; `rng[i] = H[i]-L[i]`; `bodyfrac = body/max(rng,tick)`. |
| Confirmation | Every object carries `confirmed_at = j`. It may be used for decisions on bars `> j` only. A rule needing bar `i+3` is written "confirmed at `i+3`". No object is ever back-dated onto a chart for signalling. |
| Costs | Round-trip $0.20–0.35 on 0.01 lot. Any zone thinner than 0.35 is noise (`FINDINGS` §7). |
| Prior evidence | FVG, OB, BOS, CHoCH, MSS+displacement and plain unconsumed sweeps all scored **≤ random** as leg-start markers on gold. Treat every section below as a *hypothesis definition*, not a validated signal. |

---

## 1. Swing labelling (prerequisite — everything structural depends on it)

Most descriptions are ambiguous here. This is the exact algorithm.

```
# Fractal pivot, two scales. R bars must CLOSE after the pivot bar.
def pivots(R):                       # R = 3 (minor), 15 (major)
  p = i - R
  isHigh = H[p] >  max(H[p-R..p-1]) and H[p] >= max(H[p+1..i])   # strict left, >= right
  isLow  = L[p] <  min(L[p-R..p-1]) and L[p] <= min(L[p+1..i])
  # ties: strict-left / non-strict-right makes the FIRST of equal extremes the pivot.
  emit(type, price=H[p] or L[p], bar=p, confirmed_at=i)

# Alternation filter -> the swing sequence used by BOS/CHoCH/MSS/ranges
swings = []                          # alternating H,L,H,L...
on new pivot P:
  if swings empty or P.type != swings[-1].type: swings.append(P)
  else:                              # same type twice: keep the extreme
    if (P.type=='H' and P.price > swings[-1].price) or
       (P.type=='L' and P.price < swings[-1].price): swings[-1] = P
    # else discard P entirely
```

Consequences to accept, not patch: (1) a swing is known `R` bars late, always; (2) replacing
`swings[-1]` re-dates the *last* swing only — never an already-broken one; (3) minor (R=3) and
major (R=15) sequences are maintained independently and never mixed.

---

## 2. Liquidity primitives

### 2.1 BSL / SSL
**Def.** BSL = the aggregate of resting buy-stop and buy-limit-to-stop orders **above** a price
level; SSL = resting sell-stops **below** one. Detectable proxy: BSL rests immediately above a
confirmed swing high (stops of shorts, breakout buy-stops); SSL immediately below a confirmed
swing low. `[search summary + own knowledge]` No order-flow data exists in MT5 OHLC, so BSL/SSL
is **defined as a price level with an attached expectation**, never observed.

```
pool = {side:'BSL'|'SSL', level, born_at, hits, consumed:false, members:[]}
on confirmed swing high h: add_or_merge(BSL, h.price)
on confirmed swing low  l: add_or_merge(SSL, l.price)
add_or_merge(side, px):  # equal-highs merge
  for p in pools[side] if not p.consumed:
     if abs(p.level-px) <= tol_atr*A[i]:
         p.level = (side=='BSL') ? max(p.level,px) : min(p.level,px)
         p.hits += 1; p.members.append(px); return
  pools[side].append(new pool(level=px, hits=1))
```
**Params.** `R=3`, `tol_atr=0.10` (=$0.21 on M1 gold), `max_live=3` eligible.
**Invalidation.** Consumed on being run (§2.3) — one event per level, ever. Also expire after
`pool_ttl=1440` M1 bars.
**Fails when.** Broker-specific wicks create phantom pools; M1 spread ($0.20–0.35) is 10–17% of
`tol_atr`, so merging is spread-sensitive. Expect the level to be wrong by ±1 spread always.

### 2.2 Equal highs/lows; what makes a pool significant
**Def.** An equal-high pool = ≥2 confirmed swing highs within `tol_atr*A` of each other, with at
least `min_sep=5` bars between members. `[own knowledge]`
**Significance score** (make it a number, not an adjective):
`sig = w1*hits + w2*log(1+bars_since_born) + w3*(pool_range_untouched) + w4*is_session_extreme`
with defaults `w=(1.0, 0.3, 0.5, 1.0)`. **Only `hits` and `is_session_extreme` are worth testing
first**; the rest are unfalsifiable decoration until `hits` is shown to matter.
**Invalidation.** Any close beyond the level by `> 0.25*A` de-lists the pool (it is now a broken
level, not a pool).
**Fails when.** On M1 gold, equal highs within $0.21 occur constantly; `hits>=2` pools are not
rare and therefore carry little information. Expect `sig` to be near-uninformative — test it as a
*filter on sweeps*, never as a standalone signal.

### 2.3 Sweep / stop run / turtle soup — **ABSORPTION vs EXPANSION**
This is the most important definition in the document. Everything else can be cut before this.

**Def.** A **run** of pool `P` (level `Lv`) at bar `i` = `L[i] < Lv - pierce_min*A[i]` (SSL) or
`H[i] > Lv + pierce_min*A[i]` (BSL), with `P.consumed == false` and `P` among the nearest
`max_live` eligible pools. The pool is consumed at `i` regardless of outcome.
A run is **not yet a signal**. It resolves into exactly one of three states by bar `i+K`:

| State | SSL run condition (mirror for BSL) | Meaning |
|---|---|---|
| **ABSORPTION** (pierce-and-reclaim / turtle soup) | ∃ `j ∈ [i, i+K]` with `C[j] > Lv + reclaim_min*A[i]`, **and** no `C[m] < Lv - break_min*A[i]` for `m ∈ [i,j]` | Stops filled into resting opposite orders; run failed. Long bias. |
| **EXPANSION** (decisive break) | ∃ `j ∈ [i, i+K]` with `C[j] < Lv - break_min*A[i]` **and** `min(C[i..j])` never reclaimed `Lv` | Level was a supply of liquidity used to *fuel* continuation. Short bias. |
| **UNRESOLVED** | neither by `i+K` | **Discard. No trade.** Most descriptions silently drop this class; it is typically the largest. |

```
# Scalars — report these, do not just classify
D  = Lv - L[i]                       # pierce depth (price units)
RR = (C[j] - Lv) / max(D, tick)      # reclaim ratio; ABSORPTION iff RR >= reclaim_ratio_min
EX = (Lv - C[j]) / A[i]              # extension;     EXPANSION  iff EX >= break_min
VS = V[i] / MV[i]                    # pierce-bar volume spike
VD = V[j] / V[i]                     # volume decay after pierce (absorption expects VD < 1)
state machine, evaluated on each closed bar i+1..i+K, emits at the FIRST bar that resolves it:
   signal = {kind, pool, pierce_bar=i, confirmed_at=j, D, RR, EX, VS, VD}
```
**Params (M1 gold).** `pierce_min=0.05*A ($0.11 — must exceed spread; if spread>0.25 raise to 0.12*A)`,
`reclaim_min=0.05*A`, `break_min=0.35*A`, `reclaim_ratio_min=0.5`, `K=3` bars, `max_live=3`,
`VS_min=1.5` (optional filter).
**Invalidation.** ABSORPTION dies if `C` closes back beyond `Lv - break_min*A` at any later bar.
EXPANSION dies on a close back inside the pool. Both die at `signal_ttl=30` M1 bars if unentered.
**Fails when.** Measured on this repo's data, unconditioned sweeps scored lift **0.95–1.02**
(≤ random) and the "not consumed" variant **0.83–0.96**. Only *consumed-pool + nearest-N* framing
was even neutral. Expect ≥60% of runs to land UNRESOLVED at `K=3`; expect the absorption/expansion
split to be roughly 50/50, which is exactly why unconditioned "sweep = reversal" fails.

---

## 3. Order flow objects

### 3.1 Order block (OB)
**Def.** Bullish OB = the last down-close candle (`C<O`) at index `b` immediately before a
displacement leg up (§3.4) whose leg origin is `b`. Zone = `[L[b], H[b]]` (body-only variant:
`[L[b], O[b]]`). `[search summary]` Mirror for bearish.
```
on displacement_up confirmed at bar d (leg start s):
   b = largest index < s+1 with C[b] < O[b] and b >= s-ob_lookback
   if none: no OB.  zone=[L[b],H[b]]; confirmed_at = d
```
**Params.** `ob_lookback=5`, `zone_mode='full'|'body'` (test both), `ob_ttl=240` bars,
`min_zone=0.35` price units (cost floor).
**Invalidation.** (a) *Mitigated*: price trades into the zone — OB is used once, then dead;
(b) *Broken*: a **body close** beyond the far edge (`C < L[b]` for a bullish OB) kills it and
creates a breaker candidate (§3.2). `[search summary]` The body-close test is the only thing
separating mitigation from breaker.
**Fails when.** OB scored ≤ random here. Ambiguity sources: which candle counts as "last
opposing" when the leg starts on a doji; full vs body zone changes hit rate by a large margin;
`ob_lookback` is a free parameter that trivially overfits. Expect `lift ≈ 1.0`.

### 3.2 Breaker / mitigation block
| | Breaker | Mitigation block |
|---|---|---|
| Origin | A failed OB: price closed **through** it | An OB revisited but **held** (wick in, body out) |
| Role | Flips: old bullish OB → resistance | Unchanged: same-direction retest |
| Trigger | `C[k] < L[b]` (bullish OB) at `k`, then a later **return** to `[L[b],H[b]]` | wick enters zone, `C` stays beyond |
| Confirmed at | `k` (flip), signal at the return bar | the retest bar |

`[search summary]` **Params.** `breaker_ttl=480`, requires the break leg to itself be a
displacement (else the "failure" is noise). **Invalidation.** Breaker dies on a body close back
through the zone in the original direction. **Fails when.** A breaker is an OB plus two extra
conditional steps; each step cuts sample size ~3–5× while the per-event edge is unproven. This is
the classic "looks great in hindsight, n=20 in a backtest" object.

### 3.3 FVG / IFVG / BPR
**Def.** Bullish FVG confirmed at `i`: `L[i] > H[i-2]` → gap `[H[i-2], L[i]]`, middle candle
`i-1`. Bearish: `H[i] < L[i-2]` → `[H[i], L[i-2]]`. `[own knowledge]`
**IFVG:** an FVG with a **body close** through its far edge; the same zone is then re-armed with
the opposite polarity, `confirmed_at` = that close.
**BPR:** the price-overlap of a bullish FVG and a bearish FVG formed within `bpr_window=20` bars:
`[max(lo_bull,lo_bear), min(hi_bull,hi_bear)]`, non-empty only.
**Params.** `min_gap = 0.25*A (~$0.53)` — **mandatory**, an unfiltered M1 gold FVG is often
smaller than the spread; `fill_mode='touch'|'50%'|'full'`; `fvg_ttl=240`.
**Invalidation.** touch/50%/full fill per `fill_mode`, or TTL.
**Fails when.** Measured lift 1.02/1.05 — decoration. M1 produces dozens per hour; with no size
filter the concept is trivially unfalsifiable ("price always returns to *an* FVG"). The size
filter is what makes it testable.

### 3.4 Displacement (vs a merely large candle)
**Def.** A displacement is a *directional, gap-creating, structure-breaking* move — not one big
bar. All four must hold, confirmed at `i`: `[own knowledge]`
```
1) range:     sum(rng[i-n+1..i]) >= disp_k * median(rng[last 50])        # n = 1..3 bars
2) direction: abs(C[i]-O[i-n+1]) >= disp_body * sum(rng[i-n+1..i])        # net/gross efficiency
3) imbalance: an FVG of >= min_gap was created inside the window          # THE separator
4) structure: the window closed beyond a confirmed swing (BOS or CHoCH)
```
**Params.** `disp_k=2.0`, `disp_body=0.60`, `n<=3`, `min_gap=0.25*A`.
**Invalidation.** A close back inside the created FVG within `disp_ttl=30` bars retires the
displacement label.
**Fails when.** Condition (1) alone is a news spike; on M1 gold at 13:00–14:00 UTC (1.7–1.8×
median range, `FINDINGS` §6) condition (1) fires on volatility, not intent. Measured lift for the
plain displacement bar: **1.01–1.03**. Conditions (2)+(3) are the only parts that are not
restating "big bar".

---

## 4. Structure, ranges, and time

### 4.1 BOS / CHoCH / MSS
```
state ∈ {bull, bear, none}; uses §1 swings at scale R
last_H = most recent confirmed swing H; last_L = most recent confirmed swing L
on closed bar i:
  if C[i] > last_H.price:
      event = (state == bear) ? 'CHoCH_bull' : 'BOS_bull';  state = bull
  elif C[i] < last_L.price:
      event = (state == bull) ? 'CHoCH_bear' : 'BOS_bear';  state = bear
  confirmed_at = i          # close-through only; a wick through is NOT a break
MSS_bull  := CHoCH_bull  AND  the breaking window qualifies as displacement (§3.4)
                        AND  the origin low of that leg was itself a pool run (§2.3)
```
**Params.** `R=3` internal / `R=15` external; `break_mode='close'` (wick mode is a different,
separately-tested hypothesis).
**Invalidation.** Structure state flips only on the next opposing close-through. A BOS level is
consumed when broken; it is not reusable.
**Fails when.** All three scored ≤ random here. `R` is the whole result: `R=3` on M1 gold gives a
BOS every few minutes (meaningless); `R=15` gives few and late. There is no principled `R` — it
must be swept as a parameter and reported as a curve, not a point.

### 4.2 Premium / discount, equilibrium, OTE
**Def.** Dealing range = `[low, high]` of the two most recent opposing **external** (R=15) swings,
where the leg is the impulse from one to the other. `EQ = 0.5`. Above EQ = premium (sell zone),
below = discount (buy zone). OTE = retracement band **0.62–0.79**, midpoint **0.705**.
`[search summary]`
```
if leg is up (low L0 at t0 -> high H0 at t1>t0):
    r(p) = (H0 - p) / (H0 - L0)                       # retracement fraction
    OTE zone = [H0 - 0.79*(H0-L0), H0 - 0.62*(H0-L0)]; confirmed_at = t1's pivot confirm bar
```
**Params.** `ote_lo=0.62`, `ote_hi=0.79`, `R_range=15`, `require_discount=true`.
**Invalidation.** Range dies when price closes beyond either extreme (new leg); OTE dies at
retracement `> 1.0` (leg origin taken out).
**Fails when.** Circular: the range is defined by swings that are only confirmed 15 bars late, so
the OTE zone moves as the leg extends. This is the single biggest repaint trap in SMC. Only the
"confirmed_at" version is testable, and it is materially worse than the hindsight version.

### 4.3 Internal vs external liquidity
**Def.** External = the R=15 swing extremes bounding the current dealing range (the range's own
high/low). Internal = all R=3 swings strictly inside that range. `[own knowledge]` Claim to test:
internal liquidity is taken before external.
**Params.** `R_int=3`, `R_ext=15`. **Invalidation.** Reclassify on every new external swing.
**Fails when.** Tautological as usually stated — price inside a range must touch interior levels
before exiting it. Only the *ordering* claim (all internal pools consumed before the external one
breaks) is falsifiable.

### 4.4 Inducement
**Def.** Given a target POI `Z` (OB/FVG/pool) and current price `p`, the inducement is the nearest
**minor** (R=3) opposing pool strictly between `p` and `Z` whose prominence `< ind_max*A`.
`[own knowledge]` Claim: it is swept before `Z` is reached.
**Params.** `ind_max=0.5*A`, must be within `ind_dist=3*A` of `Z`.
**Invalidation.** Dies when swept or when `Z` dies. **Fails when.** Unfalsifiable as normally
stated because the inducement is identified *after* seeing which level got swept. The definition
above (chosen before the sweep, from a fixed rule) is the only version that can be tested — and it
will lose most of its apparent hit rate.

### 4.5 Killzones and session opens (UTC + DST)
`[search summary]` for the ranges, `[own knowledge]` for the DST mechanics.

| Zone | Local definition | UTC (winter) | UTC (summer) |
|---|---|---|---|
| Asia | 19:00–22:00 ET | 00:00–03:00 | 23:00–02:00 |
| London KZ | 02:00–05:00 ET | 07:00–10:00 | 06:00–09:00 |
| NY AM KZ | 07:00–10:00 ET | 12:00–15:00 | 11:00–14:00 |
| NY PM KZ | 13:30–16:00 ET | 18:30–21:00 | 17:30–20:00 |
| NY equity open | 09:30 ET | 14:30 | 13:30 |

**DST is not optional.** Never store a UTC constant. Derive from exchange local time:
```
us_dst(t_utc):  # 2nd Sun Mar 02:00 local -> 1st Sun Nov 02:00 local
  m=month(t); if m>3 and m<11: return true; if m<3 or m>11: return false
  s = (m==3) ? second_sunday(3) : first_sunday(11)
  return (m==3) ? (t >= s + 07:00 UTC) : (t < s + 06:00 UTC)
eu_dst: last Sun Mar 01:00 UTC -> last Sun Oct 01:00 UTC
```
There are ~3 weeks in March and ~1 in late October where EU and US DST disagree; London and NY
killzones shift **independently** in those windows. Broker server time (usually EET, UTC+2/+3)
must never be used directly — call `TimeGMT()` and convert.
**Fails when.** `FINDINGS` §6: hour-of-day predicts **range, not direction** (drift ±0.13 max), and
gating ATR-scaled strategies by hour did **not** help. Killzones are a *position-sizing / cost*
variable, not an entry edge.

### 4.6 PDH/PDL, PWH/PWL, opening range
**Def.** PDH/PDL = high/low of the previous *trading day*; available only after the boundary bar.
**The day boundary is a free parameter and it changes the level**: 00:00 UTC vs 17:00 ET (CME
settle) vs broker EET midnight give different PDH. Default: **17:00 ET**, DST-aware.
PWH/PWL = high/low of the previous week, week boundary = Sunday 17:00 ET open (same DST rule);
they are ordinary pools with a longer `pool_ttl` and `is_session_extreme=1` in §2.2's `sig`.
Opening range `OR(sess, n)` = `[min L, max H]` over the first `n` M1 bars from the session open;
confirmed at open+`n`.
**Params.** `n ∈ {15, 30}`, sessions = London open, NY equity open.
**Invalidation.** PDH/PDL become ordinary consumed pools once run (§2.3). OR dies at session end.
**Fails when.** OR break at 13:00 UTC measured +$2.91/trade, **t=0.97, CI [−2.74, +8.96]** — the
best of the families tested here and still not significant.

### 4.7 Liquidity voids
**Def.** Not "a big candle". A void is a *price interval with abnormally low time-at-price*:
```
window W=240 bars; bucket size b=0.1*A
touch[k] = count of bars in W whose [L,H] covers bucket k
void = maximal contiguous run of buckets with touch[k] <= void_max, width >= void_w*A
```
**Params.** `W=240`, `b=0.1*A`, `void_max=2`, `void_w=0.75*A`. **Invalidation.** Dies when
`touch[k] > void_max` for the median bucket (the void has been filled).
**Fails when.** Overlaps ~90% with the FVG set on M1, so it is not an independent hypothesis —
test it as a *scale-up* of FVG, not as a new concept.

### 4.8 SMT divergence
**Def.** At a confirmed pivot on symbol A at bar time `t`, compare to symbol B's value at the same
`t`: bullish SMT = A makes a lower low vs its prior swing low while B does **not**. `[search
summary]` For XAUUSD the candidates are XAGUSD (positive), DXY/EURUSD (inverse — flip the test).
```
require exact timestamp alignment; if B has no bar at t -> skip (do NOT interpolate)
bullish_SMT at confirm bar j:  A.L(swing_now) < A.L(swing_prev)  AND  B.L(t_now) >= B.L(t_prev)
```
**Params.** `partner='XAGUSD'`, `R=3`, requires `|rolling corr(60)| >= 0.5` else skip.
**Invalidation.** Dies when B confirms the same low, or at `smt_ttl=60` bars.
**Fails when.** M1 gold/silver correlation is unstable and quote timestamps differ by broker feed;
below ~M5 most "divergences" are feed-latency artefacts. This is the most likely concept here to
be pure noise on M1.

---

## 5. WHAT TO ACTUALLY BUILD FIRST

Ranked by (expected edge × unambiguity of coding × testability on OHLC alone). Blunt.

| # | Build | Why | Effort |
|---|---|---|---|
| 1 | **Sweep resolver: ABSORPTION / EXPANSION / UNRESOLVED** (§2.3) with `D, RR, EX, VS, VD` logged | The only place this repo's own data showed *any* signal of life, and only under consumption + nearest-N. Splitting the 50/50 outcome is the whole thesis. | 1 day |
| 2 | **Pool engine with consumption + nearest-N eligibility** (§2.1–2.2) | Prerequisite to #1; already exists (`research/core.py:sweep_engine`) — extend, don't rewrite. | 0.5 day |
| 3 | **Session/DST clock + opening range** (§4.5–4.6) | Cheap, deterministic, zero ambiguity, and hour-of-day is the one replicated effect in this repo. Use for **sizing and cost gating**, not entries. | 0.5 day |
| 4 | **Displacement with all 4 conditions** (§3.4) | Only worth it as a *conditioning variable on #1* ("did the expansion actually displace?"). Never as an entry. | 0.5 day |
| 5 | **PDH/PDL/PWH/PWL as pools, with the day-boundary as a swept parameter** | Turns a religious argument into a 3-value parameter test. | 0.5 day |
| 6 | **FVG with a mandatory `min_gap=0.25*A`** | Only as a *filter* (does an absorption signal with an FVG behind it beat one without?). Measured 1.02 standalone — do not ship it as a trigger. | 0.5 day |
| 7 | **Swing labeller + BOS/CHoCH** (§1, §4.1) | Needed for ranges/OTE and for §4.3's ordering test. Ship as *state*, never as a trigger. | 1 day |

**Would NOT build (now, and in this order of refusal):**

- **SMT divergence.** Needs a second synchronised M1 feed; broker timestamp skew alone can
  manufacture the pattern. Highest infrastructure cost, lowest prior. Refuse.
- **Breaker blocks.** OB + failure + return = three conditional gates on top of a base object that
  already measured ≤ random. Sample size collapses to n≈20–40; you cannot distinguish it from luck.
- **Mitigation blocks.** Same object as a breaker with the opposite verdict, separated only by a
  body close. Until OBs beat random, this is a coin-flip on a coin-flip.
- **Inducement.** As normally stated it is chosen retrospectively — unfalsifiable. Build only the
  fixed-rule version in §4.4, and only after #1 works.
- **OTE / premium-discount as an entry.** The range repaints for `R_range` bars. Honest version is
  much weaker than the marketed version; low priority.
- **Liquidity voids.** ~90% redundant with FVG. Not an independent hypothesis.
- **Standalone OB / FVG / BOS / CHoCH / MSS entries.** Already measured at or below random on this
  data. Rebuilding them as triggers is re-running a failed experiment.

**Unfalsifiable as usually stated → how to make them falsifiable:**

| Concept | Why unfalsifiable | Falsifiable restatement |
|---|---|---|
| Inducement | Identified after the sweep | Rule-selected *before* (§4.4), logged, then scored |
| "Price returns to the FVG" | Always true for *some* FVG | Fix `min_gap`, fix `fvg_ttl`, fix which FVG (nearest unfilled), measure fill rate vs a random-gap control |
| Internal-before-external | Geometrically forced | Score only the *ordering*: were **all** internal pools consumed before the external break? |
| "Pool significance" | Adjective | The `sig` formula in §2.2, with `hits` tested alone first |
| OB "institutional orders" | Unobservable | Drop the mechanism entirely; measure the zone's hit/reaction rate only |
| Killzone edge | "Best times to trade" | Split range-effect from drift-effect: ATR-normalised return, not raw |
| Displacement | "Strong move" | The 4-condition test, with each condition ablated |

---

## 6. HOW TO TEST EACH ONE

Common protocol (non-negotiable, from `FINDINGS`): **de-trended M1 data** (per-bar drift removed);
entry at next bar's open; cost $0.15/side; stop wins ties; **matched random-entry null with
identical geometry, direction mix and trade count**; bootstrap 95% CI; and a **best-of-N null line**
(≈ lift 1.16 at 10 variants) that any winner must clear. A single lift > 1 is not a result.

| Concept | Event definition | Forward horizon | Control / null it must beat | Sample needed |
|---|---|---|---|---|
| **Absorption sweep** | §2.3 ABSORPTION, resolved at `j<=i+3` | 30 / 60 / 120 M1 bars; also 1R at stop = swept extreme ± 0.25A | Random entry, same bar-of-day distribution, same direction mix; **and** the EXPANSION arm of the same pool set | ≥400 events/arm for a 5pp win-rate edge at 80% power |
| **Expansion sweep** | §2.3 EXPANSION | same | Absorption arm + random | ≥400 |
| **Unresolved rate** | fraction landing UNRESOLVED | n/a | n/a — this is a *descriptive* check; if >80%, `K` is too small | any |
| **Pool `hits`** | absorption events split by `hits=1` vs `hits>=2` | 60 bars | Each other (paired by day), not random | ≥250/cell |
| **Nearest-N** | sweep lift as a function of `max_live ∈ {1,2,3,5,10,40}` | 60 bars | Monotonicity is the result; a non-monotone curve = noise | ≥300/cell |
| **Displacement conditions** | 4-condition ablation (16 cells) | 60 bars | Full-condition vs each ablation, paired | ≥200/cell; report best-of-16 null (~lift 1.25) |
| **FVG as filter** | absorption signals with/without a `>=0.25A` FVG in the reclaim leg | 60 bars | Each other, paired by event | ≥200/arm |
| **Opening range** | first close beyond `OR(sess,n)` | To session end, ATR-trailed 3.0 | Random entry in the same session window (kills the volatility artefact) | ≥500 (prior: n=209, t=0.97) |
| **Killzone** | ATR-normalised forward return by UTC hour | 15 / 60 bars | Zero drift. Test **|return|** separately from **signed return** | ≥3000 bars/hour-bucket |
| **PDH/PDL** | run of PDH/PDL, by boundary ∈ {00:00 UTC, 17:00 ET, broker} | 60 bars | Ordinary swing pools of equal age at the same distance | ≥150/boundary |
| **BOS/CHoCH** | close-through at `R ∈ {3,5,8,15,25}` | 60 bars | Random; report the full `R` curve, not the best `R` | ≥300/cell |
| **Internal→external ordering** | % of external breaks preceded by all internal pools consumed | to the break | A shuffled-pool control with identical level geometry | ≥150 ranges |
| **Inducement** | rule-selected inducement swept before `Z` reached | until `Z` hit or dead | Random minor pivot in the same interval | ≥200 |
| **OTE** | first touch of `[0.62,0.79]` using `confirmed_at` levels only | 60 bars | Touch of `[0.20,0.38]` (mirror band) on the same legs | ≥300 |
| **OB / breaker** | first touch of zone | 60 bars | Random zone of equal width at equal distance | ≥300 (expect ~n=30 for breakers → **that is the reason not to build it**) |

**Stop rule for the whole programme.** If #1 (absorption vs expansion) does not separate the two
arms by more than the best-of-N null line on ≥400 events per arm, none of the downstream objects
in this document are worth coding, because every one of them is a filter on a base rate that is
not there.

---

**Sources consulted (search-result summaries only, never fetched):**
[theinnercircletraders.com — killzones](https://www.theinnercircletraders.com/ict-trading-strategy-london-open-model/) ·
[ictkillzone.com — breaker vs mitigation](https://www.ictkillzone.com/ict-breaker-vs-mitigation) ·
[theinnercircletraders.com — order block](https://www.theinnercircletraders.com/ict-order-block/) ·
[luxalgo.com — OTE](https://www.luxalgo.com/library/concept/optimal-trade-entry/) ·
[luxalgo.com — SMT divergence](https://www.luxalgo.com/library/concept/smart-money-technique-divergence/) ·
[innercircletrader.net — fibonacci levels](https://innercircletrader.net/tutorials/ict-fibonacci-levels/)
