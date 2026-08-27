# Known limitations (what JARVIS genuinely cannot do today)

## Hard blocks — cannot be engineered around from this container
- **No MT5 / MetaEditor.** This is a Linux cloud container. MT5's strategy
  tester, tick data, and real broker execution live on Veer's Windows PC.
  JARVIS can WRITE and REVIEW MQL5; it cannot compile or tick-test it here.
- **No live broker connection.** No account credentials, and none should be
  placed in this repo.
- **Cannot see Veer's screen, Instagram, YouTube, or TradingView account.**
  Those need either an authorised MCP connector or local automation on his
  own machine. Chart *images* can be read if uploaded.
- **Cannot scrape TradingView.** Against their ToS and technically blocked.
  Chart data comes from the committed `data/` files or an authorised data API.

## Data limitations
- `data/` has 1h candles (~2.4 yrs) and 15m (~70 days). No tick data, so
  intrabar sequencing is approximated — hence the ties-lose rule.
- No volume for spot FX. No news/economic-calendar feed yet.
- Gold history covers a strong bull market. Any long-biased strategy will
  look better than it is. This is the single biggest data risk.

## Statistical limitations
- 2 years of one symbol is a small sample. 224 trades gives wide error bars.
- Testing many strategies on the same data creates multiple-comparison bias;
  every extra variant tried makes the best one look better than it is.

## Not yet built
Voice interface, dashboard UI, task scheduler, model router, business/
ecommerce/education engines. Deliberate — foundation first.
