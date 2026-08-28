# Tomorrow — do these in order

You don't need to understand the research. Just do this.

---

## 1. Do NOT run the EA live today  ⛔
Its own logs record -£252 across 188 losers. Nothing was fixed overnight.
Skip the live test. Nothing is lost by waiting.

## 2. Give me GitHub access (2 minutes)
Open: https://github.com/apps/claude/installations/select_target
Pick `veer7710` → select `signals` → Save.
Then tell me "pushed" and I'll upload everything.

**Until this is done, all work lives only in this temporary container.**
I've sent you backup files in the chat as insurance.

## 3. Install these on your PC (30 minutes, all free)

| What | Why | Where |
|---|---|---|
| **Ollama** | free local AI models for background work | https://ollama.com |
| **Python 3.11+** | needed for the MT5 bridge | https://python.org |
| `pip install MetaTrader5` | lets me pull YOUR broker's real tick data | run in terminal |

Skip Graphify for now — it only pays off on big codebases, and ours is small.
Skip Obsidian — `JARVIS/state/` already does that job.

## 4. Send me three things

1. **A screenshot of your gold symbol spec in MT5**
   (right-click XAUUSD → Specification). I need contract size, spread,
   commission, swap. Every result changes with these numbers.
2. **Which prop firm** you're using, and the account size.
3. **Your MT5 account history export** if you have one — real fills beat
   any backtest.

## 5. Then say this to me

> "Resume JARVIS. Run the 5 research jobs that got cut off, then start on
> daily-timeframe multi-market testing."

That's it. I'll pick up from the saved state with no re-explaining.

---

## What I'd tell you in one sentence

Your EA loses because it protects profits too early — I measured that as the
worst possible exit rule on four different markets — and because 748 settings
cannot be validated on 279 trades.

## What to stop believing

- ❌ "It just needs the exits fixed so it closes at the peak."
  Nothing closes at the peak. A perfect exit is 15x better than the best real
  one. That gap is permanent, for everybody.
- ❌ "A 70% win rate means it's working."
  Your old system won 70% and still lost money. 30% wins at 3R beats 53% at 1R.
- ❌ "40 funded accounts = 40x the income."
  Same strategy on 40 accounts is one bet with 40x leverage. They all fail on
  the same day. FTMO also caps you at $400k per *strategy*.

## What's genuinely good news

You now have a backtester that cannot lie to you. It has 17 tests, including
one that proves it finds no edge in pure random data. It killed 8 strategies
in about 30 seconds tonight — including two of mine.

That's the thing that stops the next year becoming another twenty versions
of v19.
