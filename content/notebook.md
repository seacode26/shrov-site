## The one design decision

The LLM never touches the order API.

```
market data ──> Context Builder (deterministic)
                     │
                     v
             Agent (LLM) ──> Proposal
                     │
                     v
             Risk Gate (pure Python) ──reject──> journal + reason
                     │ accept
                     v
             Broker (ib_async) ──> IBKR paper
```

A proposal is journalled *before* the gate runs, so agent judgment is scored
separately from execution luck. A rejected proposal that would have been a
winner is a finding about the limits, not about the agent.

## First connection: run preflight

```bash
python preflight.py --port 4002
```

Checks connection, paper-account prefix, NAV, contract lookup, whether quotes
come back live or delayed (i.e. whether subscription sharing actually took
effect), historical-data permission, and the volume-units question below.
Places no orders. Each check catches its own failure so one break doesn't mask
the rest.

### Market data on a paper account

Sharing is opt-in: **Client Portal → Settings → Account Settings → Paper
Trading Account → Yes**, then choose which live username's subscriptions to
share. You cannot consume the shared data on live and paper simultaneously.

`reqHistoricalData` requires a Level 1 streaming subscription — delayed mode
does **not** bypass it, and without one you get error 162. IBKR's free
**US Real-Time Non-Consolidated Streaming Quotes** (Cboe One + IEX) satisfies
this, but it is not the NBBO, and the SEC Vendor Display Rule means TWS won't
show it in the order ticket without a paid consolidated subscription.

### The volume-units question — unresolved

`ExecutionModel.max_participation` caps orders at a share of bar volume, which
assumes that number is consolidated share volume. Two things can make it wrong,
neither of which announces itself:

- IBKR reports historical stock volume in **round lots** (×100), not shares.
- A non-consolidated feed may carry **venue-limited** volume (~10× low).

Either would make the model far more restrictive than intended — 100× or 10×.
`preflight.py` pulls a liquid name and reports which case it's looking at.
Settle this before running any strategy whose results you intend to believe.

## Paper-only enforcement

Two real checks and one weak one, because this is the only bug here that costs
money:

- `IBKRPaper.connect` drops the connection unless every managed account starts
  with `DU`/`DF`. **This is the load-bearing check.**
- The gate rejects `NOT_PAPER_ACCOUNT` on a separate code path, so a caller
  that bypasses the broker wrapper is still stopped.
- `IBKRPaper.__init__` refuses any port outside `{7497, 4002}`. Weaker than it
  looks, and originally overstated here: **the port proves nothing about the
  session**. Gateway's API port is a config value, and a Gateway logged into a
  *live* account will happily serve it on 4002. Observed in practice on
  2026-09-08, where port 4002 returned live accounts.
  The port check only catches typing the live port; the account prefix is what
  actually protects you.

## What the sandbox lies about

Paper is a correctness harness, not a performance oracle:

- **Fills are optimistic.** Simulated against the NBBO with no queue position,
  so any passive/limit strategy will look better than it is.
- **No market impact, ever.** Size is free.
- **Delayed data by default.** `quote()` returns a `delayed` flag — if it is
  `True`, fills against those prices are not evidence of anything.
- Paper accounts reset and occasionally drift from what your journal thinks.

Performance claims come from replay backtests over journalled snapshots with an
explicit slippage model (milestone 4), not from these fills.

## Risk limits

Defaults in `labtrader/config.py`. Limits live in code, not in prompts — a
prompt is a suggestion, this is a constraint.

| Limit | Default |
|---|---|
| Max single position | 5% NAV |
| Max sector | 25% NAV |
| Max gross exposure | 100% (no margin) |
| Orders per agent per day | 10 |
| Notional per agent per day | $50,000 |
| Drawdown halt | 15%, manual re-arm |
| Limit price deviation | 10% from reference |
| Shorting | disabled |
| Session | RTH only |

**De-risking is always allowed.** A limit only bites if the trade makes an
already-bad number worse — otherwise a risk-reducing agent gets locked out
exactly when it is needed. See `TestDeRiskingAlwaysAllowed`.

The drawdown halt is the deliberate exception: it blocks selling too, so
flattening after a 15% loss is a human decision.

## Backtesting (milestone 4)

```bash
python backtest.py
```

Runs on a synthetic random walk, so it works with no data at all. Those numbers
are meaningless by construction — the walk has no structure to find.

For real bars without waiting on IBKR entitlements (prices back-adjusted for
splits and dividends; volume left raw, see the module docstring):

```bash
python fetch_yahoo.py --years 2 --out data/bars.csv
```

Once IBKR entitlements exist, that is the source of record:

```bash
python fetch_bars.py --port 4002 --years 3 --out data/bars.csv
```

```bash
python backtest.py --bars data/bars.csv
```

### Timing convention

> A strategy decides at the close of day *t* using data through day *t*, and
> its orders execute against day *t+1*'s bar.

The first half is enforced structurally: `MarketView` is pinned to one date and
has no method that returns a later bar, so look-ahead is not something to
remember to avoid. `test_no_attribute_exposes_the_full_series` fails if a
refactor ever hands a strategy the whole series.

The second half falls out of the engine: accepted proposals sit in `pending`
and are only touched on the next iteration. Unfilled day orders expire, which
matches the `tif="DAY"` the live broker sends.

### The replay uses the *same* gate

`replay()` calls the same `evaluate()` as the live path, with a
`DU-REPLAY` account id to satisfy the paper-prefix check. A backtest that gates
differently from production is testing something other than what will run.

### Execution model

Three assumptions, all configurable, ordered by how much they were measured to
matter:

| Assumption | Default | Effect |
|---|---|---|
| `half_spread_bps` | 1.5bps | charged whenever an order **takes** liquidity |
| `max_participation` | 10% of bar volume | large orders fill partially |
| `slippage_bps` | 2bps | impact, market orders only |
| `require_through_limit` | `True` | a touch is not a fill |

**Crossing is not free.** A market order, or a limit priced at or through the
bar's open, takes liquidity and pays `half_spread_bps`. A limit resting away
from the market pays nothing — it provides liquidity, and only fills when price
comes to it. Until this existed, momentum posted marketable limits 0.2% through
the market and crossed 6,680 times at exactly zero modelled cost, at ~29x
annual turnover.

Sweeping the assumption against equal-weighting the same 111 names:

| half-spread | return | vs SPY | vs equal-weight |
|---|---|---|---|
| 0.0bps | +392.9% | +130.2% | +68.6% |
| 1.5bps (default) | +367.9% | +105.3% | +43.6% |
| 5.0bps | +316.8% | +54.1% | **−7.5%** |

Momentum's edge over equal-weight is roughly the size of the cost assumption,
and inverts by 5bps. Combined with an information ratio of 0.14 (t=0.42 over
9.2 years), **the excess over equal-weight is not established.** The advantage
over SPY is more robust, but SPY is the wrong comparison for a survivorship-
biased universe.

### Measured, not assumed

```bash
python spreads.py --port 4002 --rounds 3
```

Samples real quoted bid/ask across the universe and writes `data/spreads.json`.
Reads only. Falls back to the delayed tier, which does expose two-sided quotes.

Measured 2026-09-08, 112 names, 3 rounds, delayed feed:

| | half-spread |
|---|---|
| universe median | **1.91 bps** |
| p25 / p75 | 1.12 / 3.12 |
| min (SPY) / max (DE) | 0.20 / 9.16 |
| **trade-weighted for momentum** | **2.40 bps** |

The 1.5bps default was too low. Momentum shows no tilt toward wide or tight
names — its 20 most-traded average 2.04bps against 2.12 for its least-traded —
so the trade-weighted figure is close to the simple mean of what it touches.

Three limits on what this proves. These are **quoted** spreads, an upper bound
on the effective cost since real fills often land inside the quote. They are
**today's** spreads applied to a nine-year backtest, and spreads have generally
narrowed, so historical cost was probably higher. And the feed is delayed by
15-20 minutes, which perturbs a snapshot more than a level.

### Cost sensitivity without re-running

Re-running a backtest at a different spread does not measure the spread. One
different fill changes the position, which changes every later proposal. On
real data, raising the half-spread from 1.91 to 2.40bps *increased* the
measured excess — path divergence, not a cost effect — so the rows of such a
sweep are not comparable and the sweep answers nothing.

`labtrader/costs.py` holds the order sequence fixed and charges it differently.
`sensitivity()` is anchored so the reference assumption reproduces the realised
return exactly (verified: +367.94% against a realised +367.90%), and only fills
with `Fill.crossed` pay — **70% of momentum's notional crosses, 30% rests.**

| half-spread | drag/yr | return | vs equal-weight |
|---|---|---|---|
| 0.00 | 0.00% | +381.6% | +57.2% |
| 1.91 (universe median) | 0.40% | +364.3% | +40.0% |
| **2.40 (measured)** | **0.50%** | **+359.9%** | **+35.6%** |
| 6.00 | 1.25% | +329.1% | +4.8% |
| 8.00 | 1.66% | +312.8% | −11.5% |

`breakeven_bps()` gives the number directly: momentum stops beating
equal-weight at a **6.59bps** half-spread, and SPY at **14.63bps**, against a
measured 2.40. So the edge survives roughly a 2.7x error in the spread
estimate.

That is a real margin, and it does not make the edge significant — the
information ratio is still 0.14 (t=0.42 over 9.2 years). Cost is no longer the
reason to doubt it; sample size is.

On synthetic bars, through-vs-touch moved only **+0.4%** of ~3,000 passive
orders — much less than the framing "paper trading flatters passive strategies"
would suggest. It should bite harder on real data, where limits cluster at
round numbers that get touched exactly and not traded through, but that is
unmeasured. Treat the conservative default as cheap insurance, not a proven
correction.

`--optimistic` relaxes all three. Note that comparing a run against its own
optimistic twin is confounded: once one fill differs, positions differ and all
subsequent proposals diverge. To measure the fill model itself, hold the order
flow fixed and re-simulate it under both.

### Scoring

Return is the least interesting output. `labtrader/metrics.py` also reports:

- **turnover** — LLM agents overtrade and simulated commissions do not hurt
- **concentration** — HHI and effective names, the NBER paper's complaint
- **overlap** — `mean_pairwise_overlap` across independent runs, the herding measure
- **calibration** — bucketed by the confidence the agent *stated*, scored on
  every proposal including gate-rejected ones. A well-calibrated agent that
  loses money is more promising than a lucky one that does not.

## Alerting

Silence is the failure mode: a run that did not happen looks exactly like a run
that decided to do nothing. A heartbeat goes out on every run, so a quiet phone
on a weekday means something is broken.

```bash
python -m labtrader.notify --discover   # after messaging your bot once
python -m labtrader.notify --test
```

Credentials live in a gitignored `.env` (see `.env.example`), never in code.
No dependencies — the Telegram Bot API is plain HTTPS.

`Notifier.send` returns a bool and never raises on ordinary failures: Telegram
being down is not a reason to skip a rebalance or abandon half-submitted
orders. Containment stops at `BaseException` so Ctrl+C still works.

## Walk-forward (the thing that makes comparisons mean anything)

```bash
python wf.py --bars data/bars_10y.csv
```

Testing ten strategies on one window and keeping the best is how a backtest
lies. The winner is whichever one best fit that window's noise. `walkforward.py`
selects on a training window and measures on the *next* window, so nothing is
ever scored on the data that chose it.

The output to read is not the winner's return. It is:

| diagnostic | means |
|---|---|
| `selection hit rate` | how often the in-sample winner beat the median next fold; 50% is a coin flip |
| `rank correlation` | Spearman, in-sample vs out-of-sample rank; 0 = last window says nothing |
| `average candidate` | equal weight across all candidates — the bar selection must beat |
| `always X` | committing to one strategy and never re-choosing |
| `perfect hindsight` | upper bound, not achievable |

**Result on 2016–2026, 14 folds, six candidates: selection did not work.**
Hit rate 36%, rank correlation +0.04, and walk-forward selection returned
+53.2% against +50.1% for simply averaging every candidate. Committing to one
strategy and never re-choosing (`always trend-daily`, +115.4%) beat adaptive
selection by 62 points, and buy-and-hold SPY beat everything at +184%.

Four configurations were tried (rolling/anchored × return/Sharpe). The best,
anchored-on-return, showed a 64% hit rate — which is 9 of 14 folds, p=0.21
alone and p=0.61 after accounting for having tried four. That is not evidence,
and searching configurations for the best hit rate is the same error one level
up. The script now prints that p-value and says so.

Candidates carry their own `RiskLimits`, because scoring a strategy under
limits that forbid its trades measures the limits (see `TRENDCASH_LIMITS`).
Strategies are passed as factories, never instances — they carry state across a
run, and reusing one silently corrupts every fold after the first.

## Overnight vs intraday

```bash
python fetch_yahoo.py --years 10 --adjust split --out data/bars_10y_split.csv
python overnight.py --bars data/bars_10y_split.csv
```

Splits each name's price return into two legs that multiply back to it:
`overnight = open(t)/close(t-1)`, `intraday = close(t)/open(t)`.

**Use a split-only file.** The usual `adjclose/close` adjustment cancels out of
the intraday leg (same factor on open and close) but not the overnight one,
where consecutive bars carry different factors — that credits every dividend to
an overnight gap. `--adjust split` exists for this.

Note that Yahoo's raw `quote` values are **already split-adjusted**; verified
against NVDA's 2024 10-for-1, which runs 120.89 → 121.79 straight through. So
`--adjust split` applies no factor at all. Applying one double-adjusts and was
wrong by 40× for NVDA before this was caught. `test_overnight.py` fails if the
committed file ever shows a split-shaped gap.

**SPY, 2016–2026, the one unbiased read:**

| leg | cumulative | annualised | Sharpe | bps/session |
|---|---|---|---|---|
| overnight | +138.3% | +9.10% | 0.81 | 3.72 |
| intraday | +47.6% | +3.98% | 0.35 | 1.92 |

The effect is real and it is not stable. 2022 was −14.7% overnight and 2023
+4.3%, against +22.3% in 2024. Break-even round-trip cost is 3.72bps — one
round trip per session means the mean *is* the hurdle — leaving roughly
+3.7%/yr at 2bps and nothing at 5bps.

The all-names figure (+17.6%/yr overnight) is **survivorship-biased**: the
universe is 20 mega-caps chosen today. Dropping the five biggest winners takes
it to +11.3%/yr. Prefer the SPY row.

This is a measurement, not a strategy. Capturing the overnight leg needs
MOC/MOO execution the daily-bar replay engine cannot represent — it fills
against the *next* bar — so it is deliberately not wired into the harness.

### Walk-forward on 112 names

Full output in `results/`. Primary configuration was **pre-registered as
rolling/return** before running, precisely so the anchored variant could not be
cherry-picked afterwards.

| | rolling (primary) | anchored (check) |
|---|---|---|
| walk-forward selection | **+100.2%** | +283.3% |
| average candidate | **+114.5%** | +117.6% |
| always mom-k20-20d | +287.0% | +298.0% |
| always mom-k20-60d | +282.3% | +303.5% |
| buy-and-hold SPY | +185.4% | +185.4% |
| perfect hindsight | +605.0% | +638.9% |
| selection hit rate | **36%** | 71% |
| rank correlation | +0.11 | +0.39 |
| churn | 54% | 15% |

**Primary result: selection failed again, harder.** At 36% it did worse than a
coin flip and worse than simply averaging every candidate. Committing to one
momentum variant beat adaptive selection by 187 points. This is the second
independent reproduction, now on a universe five times larger.

**In 0 of 14 folds did selection pick the actual best candidate.** In the last
three folds it had rotated into `trend-monthly` — which had won folds 8, 9 and
10 — exactly as momentum won the next three by +13.9%, +12.1% and +24.8%. Plain
performance chasing.

**Anchored disagrees, and there is a mechanism.** Training on all history rather
than a rolling two years produces a more stable ranking (churn 15% vs 54%) and
never chases into trend-monthly. That is a plausible hypothesis, *not* a result:
p=0.09 on its own, ~0.17 across two configurations, and adopting it because it
scored better is the cherry-pick this section exists to prevent.

**The robust finding is about momentum, not about selecting.** A momentum
variant was the best candidate in **10 of 14 out-of-sample folds** (p=0.004
against a 2-in-6 null), in both configurations, at both a 20-day and a 60-day
lookback. Two different parameterisations landing within 5 points of each other
(+287% / +282%) is weak evidence the effect is not a fitted artifact.

Caveat that walk-forward does not address: momentum turns over ~29x NAV/year and
`ExecutionModel` charges no spread on limit orders. At that turnover a 1-2bps
effective spread is roughly 0.5-0.9%/yr compounding against these numbers.

## Scout (milestone 5)

The first agent. Sees price-derived features for the whole universe and its own
book, returns names to hold, and emits `Proposal`s judged by the **same**
`evaluate()` as everything else. It can ask for anything; the gate decides.

Needs an API key (`ANTHROPIC_API_KEY`, or `ant auth login`) and `pip install
anthropic`. **Not yet run against the live API** — everything below the network
call is covered by 40 tests using a scripted client.

```python
from labtrader.llm import AnthropicClient, CachingClient
from labtrader.scout import Scout
scout = Scout(CachingClient(AnthropicClient()), k=20, target_weight=0.045)
```

### Billing and the spend guardrail

API usage bills to **Anthropic Console** — pay-as-you-go, separate from any
Claude subscription (Max covers claude.ai, Desktop and Claude Code, not
programmatic API calls). Set a spend limit in the Console.

In code, cap the calls. Composition order matters:

```python
client = CachingClient(CallBudget(AnthropicClient(), max_calls=500))
```

The budget wraps the *network* client and the cache wraps the budget, so cache
hits are free and uncounted and only paid calls are charged against it.
Reversing them caps re-runs that cost nothing. A budget stop reaches Scout as a
held book and a `failures` increment, not a crash.

**The cache invalidation trap:** the key covers system + user + schema, so one
word changed in `SYSTEM` misses all ~462 entries. Prompt iteration costs ~$21
*per iteration*. Test prompt changes on a one-year window (~50 calls, ~$2)
before running the full history.

**Caching is not an optimisation.** A nine-year weekly backtest is ~462 calls;
without a cache each re-run costs that again *and returns different answers*,
so the harness loses reproducibility — the one property it exists for.
`CachingClient` keys on system + user + schema and writes atomically.

Estimated first full backtest: **~$21** at Opus 5 rates (~1,559 input tokens
per call). Cached re-runs are free.

### What it's built to test

The NBER result: LLM agents converge on concentrated, high-valuation,
heavily-covered names and don't beat passive benchmarks. So Scout's prompt
carries **returns and volatility only** — no market cap, no sector, no company
names. A test asserts none of those leak into the rendered table. If Scout
still drifts to mega-caps, that came from the model's priors, not the prompt.

`mean_pairwise_overlap()` in `metrics.py` is the measurement: run Scout several
times and see whether independent instances converge on the same names. That
is the herding experiment the earlier `--seeds` flag could not do, because it
only perturbed a lookback.

### Failure handling

A model outage or an unusable reply **holds the book** rather than flattening
it, and increments `scout.failures` — a run with many failures is not a result.
Hallucinated symbols are dropped before the gate so the rejection histogram
stays about judgment rather than spelling. Out-of-range confidences are passed
through deliberately: clamping would hide miscalibration, and the gate records
it as `BAD_CONFIDENCE`.

### What the API actually costs

Measured prompt: 1,559 input tokens for the 112-name table. Output is the
unknown — thinking bills as output and cannot be predicted from the prompt,
so `AnthropicClient.usage()` records it and turns the estimate into a
measurement after the first real call. Watch `output_per_input`: above ~2,
thinking dominates the bill and `effort` is the lever.

**Measured, 2026-09-08, one real call at `effort=medium`:** 4,383 input and
1,108 output tokens, **$0.0496 per call**. That makes a full nine-year backtest
**$22.92** and a year of weekly running **$2.48**.

Two corrections to the estimates that preceded it. Input was **2.8x higher**
than a chars/4 heuristic predicted — the schema is billed too, and a dense
numeric table tokenises badly. Output landed at the *low* end, so
`output_per_input` is **0.25**: thinking does not dominate this call, and
`effort` is therefore not the cost lever it would be on a harder task. The two
errors happened to cancel.

**Running it is nearly free.** Scout rebalances weekly — 50 calls a year:

| cadence | calls/yr | @1k out | @2k out | @4k out |
|---|---|---|---|---|
| weekly (Scout today) | 50 | $1.64 | $2.89 | $5.39 |
| daily | 252 | $8.26 | $14.56 | $27.16 |
| three agents mixed | 352 | — | $20.34 | — |

**Developing it is where the money goes.** One full nine-year backtest is 462
calls ≈ **$27**. The cache keys on system + user + schema, so *any* prompt edit
re-pays the whole thing:

| iterations | on full history | on a 1-year window |
|---|---|---|
| 5 | $134 | $14 |
| 15 | $401 | $43 |
| 30 | $801 | $87 |

**Iterate on a one-year window, then run full history once the prompt is
settled.** That single habit is worth ~90% of the development bill. `CallBudget`
enforces the ceiling in code.

## The veto agent (`labtrader/veto.py`)

Scout as a *picker* turned out to be momentum wearing a hat — every visible
pick sat in Momentum's top 20, because four of its five features were momentum
features. An agent can only express what its inputs allow.

`Vetoed` wraps any strategy. The strategy proposes; the agent may drop some of
those buys and may do nothing else — it cannot add a name, resize one, or veto
a sell.

Three reasons this is the better experiment:

- **Cleanly measurable.** Same strategy, with and without, over identical order
  flow. `test_a_veto_that_never_fires_reproduces_the_strategy_exactly` is the
  control — if the wrapper did anything of its own, no comparison would mean
  anything.
- **Bounded downside.** The worst an over-eager veto can do is leave you in
  cash. It can never take a position you did not already want.
- **Asks something momentum cannot answer.** A cross-sectional rank is blind to
  regime, so the prompt carries market context — index return, breadth, median
  volatility — which is the one input a rank does not already contain.

**Fail-open, deliberately.** An outage or a nonsense reply lets everything
through. That is the opposite of Scout and for the right reason: Scout *was*
the strategy, so failing meant doing nothing; a veto is a filter, so failing
means not filtering. An outage must never be able to stop a book trading.

**Sells are never shown to it**, let alone vetoed. Blocking a de-risking order
is the one thing a risk check must not do — the same principle as the gate's
"de-risking is always allowed".

### First live call, 2026-09-08

Vetoed **3 of 20 (15%)** on reasons a cross-sectional rank structurally cannot
produce: CRM for realised volatility of 87.9% against a 24.2% index median,
ORCL and TSLA for negative 60d returns despite ranking on 20d — momentum
picking up a bounce inside a downtrend.

Cheaper than the picker, too: **$0.0223 a call** against $0.0496, since it
screens 20 names rather than 112. A full backtest is **$10.30**, weekly running
**$1.11/yr**.

### Result: the veto lost money

463 rebalances, zero model failures, $9.48. Full output in
`results/veto_ab_2026-09-08.txt`.

| | return | maxDD | Sharpe | turnover |
|---|---|---|---|---|
| momentum | **+361.7%** | 27.5% | 1.04 | 29.8x |
| momentum + veto | **+249.8%** | 24.4% | 0.99 | 29.3x |
| buy-and-hold SPY | +262.7% | | | |
| equal-weight 111 | +324.3% | | | |

**−111.9 points.** It bought a 3.1-point drawdown reduction for a third of the
return, and Sharpe fell. The vetoed strategy underperforms both benchmarks; the
unvetoed one beat them.

Two diagnostics say why, and neither is "the model was unlucky".

**It vetoed the wrong names.** Over the following 5 sessions the vetoed
candidates returned **+0.633%** against **+0.343%** for the kept ones — the
veto systematically removed the *better* half (t = +1.38, so not significant,
but pointing the wrong way). Its stated reasons were sound-sounding — high
realised volatility, negative longer-horizon returns — and in this universe
those were the names that went up.

**It never adapted.** The veto rate sat between 16.7% and 21.2% every single
year, with 2022 (21.2%) indistinguishable from 2021 (16.7%). It was sold as
regime awareness and delivered a **flat ~19% haircut** — which a rule could
apply for free, and which is exactly the failure mode the design was meant to
avoid.

The one thing it did do is cut the drawdown, which is what indiscriminately
holding back ~19% of buying does.

## The small-cap test

The capacity argument said a small account's structural edge lives where
institutions cannot trade. Every failure above happened in 112 mega-caps, so
that argument was never actually tested. 109 small/mid caps, hand-picked and
therefore maximally survivorship-biased, at **23x lower dollar volume**
(median $39.8M/day against $919M).

| | momentum | equal-weight | index | edge vs EW | maxDD | Sharpe |
|---|---|---|---|---|---|---|
| large cap (111) | +361.7% | +324.3% | SPY +262.7% | **+37.4%** | 27.5% | 1.04 |
| small cap (109) | +374.1% | +360.9% | IWM +134.4% | **+13.3%** | 44.5% | 0.82 |

The edge is **smaller**, not larger. Drawdown is far worse and Sharpe is lower.

And the survivorship contamination is worse too: equal-weighting my hand-picked
small caps returned +360.9% against IWM's +134.4% — a **+226 point** construction
premium, against +150 for the large-cap set. Hand-recalling small caps selects
survivors hard, and 6 of 116 tickers had already delisted, roughly 3x the
large-cap attrition.

### Why the capacity argument fails

Breakeven half-spread against equal-weighting the same universe:

| | breakeven | measured |
|---|---|---|
| large cap | 6.76 bps | 2.40 bps — clears it |
| small cap | **4.08 bps** | **14.27 bps — 3.5x over** |

Measured 2026-09-09 on the live feed. Quoted half-spread by universe:

| | median | p25 | p75 | p90 | max |
|---|---|---|---|---|---|
| large cap | 1.91 | 1.12 | 3.12 | 4.50 | 9.16 |
| small cap | **10.02** | 4.88 | 18.79 | 29.56 | **53.49** (ATNI) |

Trade-weighted for what momentum actually buys: **14.27 bps** — worse than the
universe median, because momentum's picks skew toward the thinner, more
volatile names. Against a 4.08 bps breakeven, the +13.3% edge becomes
**−73.5%**.

The argument was self-defeating and it took running it to see why. Institutions
avoid these names *because the trading costs are prohibitive*. Those same costs
apply to a $100k account running 26x annual turnover. **The friction that
protects an anomaly from arbitrage also consumes it for you** — you do not get
to collect an edge that exists only because collecting it is too expensive.

A low-turnover strategy might reach it. A weekly rebalance cannot.

## Low turnover: the cost problem is solved, the signal problem replaces it

Full surface in `results/turnover_sweep_2026-09-09.txt`. 12 configurations per
universe (lookback 60/120/250 × hold 21/63/126/252), costs applied through
`costs.sensitivity()` rather than by re-running, position-age rule disabled so
it cannot force closes inside a 252-session hold.

**Costs stop mattering.** Turnover falls from 22–30x to 0.6–3.6x. In small caps
the spread drag collapses from 43 points at the weekly baseline to under 2 at an
annual hold. The 14.27bps toll that killed the fast version is no longer the
binding constraint.

**But the surface is a random field.** Excess over equal-weight ranges from
−228 to +225 points with a standard deviation of ~129, and the largest swing
from a *single* parameter step is **302 points** (large cap, hold 126, lookback
120→250). A real effect produces a gradient. This does not.

Main effects are the only honest read, and they are weak:

| | large | small |
|---|---|---|
| lookback 60d | −18.8 | −159.3 |
| lookback 120d | −45.2 | −42.2 |
| **lookback 250d** | **+109.8** | **+0.8** |
| hold 21d | +151.4 | −16.2 |
| hold 252d | −97.8 | −97.7 |

Long formation with a short hold — the canonical 12-1 momentum specification —
is the only direction that shows up in both universes, and it is a **prior from
the literature rather than a post-hoc pick**, which is the one thing that makes
it worth noting at all.

**The standout cell is what selection looks like.** look=250/hold=21 in large
caps returned +225% over equal-weight, or **+4.82%/yr**. But it was chosen from
12 cells whose mean is +15.2 and whose sd is 129 — under a pure-noise null the
expected maximum of 12 draws sits ~210 points above the mean. The observed 225
is almost exactly what noise produces when you sort it. And at 9.2 years, even
an information ratio of 0.5 only reaches t=1.52.

Slowing down fixed the cost problem and revealed that there was never enough
statistical power to see the signal underneath it.

### Pre-registered test of the standout cell

`look=250 / hold=21`, single configuration, no sweep. Year-by-year excess over
equal-weight:

| | large cap | small cap |
|---|---|---|
| years positive | **5 / 9** | **4 / 9** |
| mean excess | +5.5%/yr | +3.9%/yr |
| t | **1.07** | **1.32** |

The large-cap +225% comes almost entirely from three years — 2020 (+26.3%),
2024 (+19.9%), 2026 (+24.9%). Six of nine years are flat or negative. That is
the shape of a few lucky stretches, not an edge.

Both t-statistics are what a sweep's best cell looks like when you test it
honestly. Confirmed noise.

## Market-neutral construction (`labtrader/neutral.py`)

Long the top of a cross-sectional ranking, short the bottom, equal dollars each
side. The signal is a parameter, not baked in — because the argument for this
is Grinold's law, `IR = IC × √breadth`, and our momentum implied an IC of
**0.020** (a perfectly normal quant IC) against a breadth of ~50. The signal was
never the problem. Fifty uncorrelated signals at that same IC would give IR 1.0.

**Two bugs this exposed, both real.**

*The book did not stay neutral.* Dollar-neutral at entry decays asymmetrically:
a losing short **grows** as a share of the book while a losing long shrinks. On
a 21-session calendar this drifted to **$103k net short on $100k of capital** and
took NAV to **−$12,091**. Selection now stays on the slow calendar (turnover is
expensive) while the hedge is trued up whenever net exposure exceeds a
`drift_band` of NAV. Real neutral books rebalance the hedge continuously for
exactly this reason.

*`SimPortfolio` had no margin logic.* A long-only book cannot lose more than it
invests, so this never mattered. With shorts it matters enormously — simulating
losses no broker would have permitted produces numbers that are not merely
wrong but unfalsifiable, since no real path reaches them. `margin_call()` now
liquidates when equity falls below 25% of gross, and `ReplayResult.margin_calls`
records it. **Any non-zero count means the run hit a wall and everything after
it is a different experiment.**

### Result

| book | return | vol | Sharpe | beta | maxDD | turn | MC |
|---|---|---|---|---|---|---|---|
| long-only momentum | +519.0% | 22.3% | 1.04 | 0.96 | 30.1% | 3.7x | 0 |
| L/S momentum 12-1 | −49.9% | 22.1% | −0.25 | −0.14 | 55.9% | 8.0x | 1 |
| L/S reversal 5d | +0.9% | 17.1% | 0.09 | 0.08 | 32.0% | 31.3x | 0 |
| L/S low volatility | −45.2% | 17.3% | −0.31 | −0.31 | 51.2% | 5.2x | 1 |
| L/S combined | −40.9% | 20.1% | −0.20 | 0.05 | 55.8% | 6.3x | 1 |
| buy-and-hold SPY | +242.7% | | | | | | |

**Beta collapsed from 0.96 to roughly zero — the construction works.** The
variance reduction did not arrive with it: volatility stayed near 20% rather
than falling to the ~6% the argument assumed, because the short leg brings its
own risk rather than merely cancelling the long leg's.

And the alpha is negative. Shorting the bottom of a momentum ranking in a
decade-long bull market loses money, which is not a subtle finding. Three of
five books hit margin calls.

## Breadth: are 31 signals actually 31 signals? (`labtrader/signals.py`, `labtrader/factors.py`)

The neutral construction removed the market factor and volatility barely moved,
which killed the variance-reduction half of the argument. That left breadth:
`IR = IC × √breadth` only pays the square root if the bets are **independent**.
Thirty-one signals that all say "buy what went up" are one bet with thirty
spare copies.

`labtrader/signals.py` holds 31 signals across six declared families —
momentum, reversal, volatility, liquidity, technical, shape — drawn from the
published anomaly literature. Every one states the prior that fixes its sign
*before* seeing data, because choosing signs afterwards is 31 free parameters
and would fit anything. Two pairs (`illiquidity`/`small_dollar_vol`,
`dist_200ma`/`ma_cross_50_200`) are deliberate near-duplicates: positive
controls for the matrix.

`labtrader/factors.py` measures two different correlations, because they can
disagree and the disagreement is informative:

- **score correlation** — do two signals rank the same names on the same day?
- **IC correlation** — do two signals win and lose on the same days? This is
  the one that governs portfolio variance.

The headline is `effective_breadth`: the participation ratio of the
correlation matrix's eigenvalues, `(ΣΛ)²/ΣΛ²`. It equals N for N independent
signals and 1 for N identical ones, so it is directly the number that belongs
under Grinold's square root — not the count in the catalog.

```bash
python correlations.py --universe large
```

This uses forward returns as a label, which is future data no strategy can
see. That is legitimate *here* because nothing here trades: it is a one-time
measurement of the library, taken to decide whether to keep building. The
docstring says loudly that migrating this arithmetic into a `propose()` makes
it look-ahead.

### Controls first

The instrument is tested against a signal that *is* the forward return (must
measure IC ≈ 1) and against pure noise (must measure IC ≈ 0 and effective
breadth ≈ the signal count). An instrument that cannot see a perfect edge
cannot be trusted when it reports none, and one that finds structure in noise
would flatter every result.

### Result — 112 large caps, 447 sampled days, 2016–2026

| | score correlation | IC correlation |
|---|---|---|
| signals in catalog | 31 | 31 |
| **effective breadth** | **8.40** | **5.57** |
| √breadth (the multiplier) | 2.90× | 2.36× |
| √31 if independent | 5.57× | 5.57× |
| top-3 eigenvalue share | 53.9% | 65.5% |
| mean \|correlation\| | 0.207 | 0.300 |
| clusters at \|r\| ≥ 0.5 | 6 (one holds 24) | 5 (one holds 25) |

**Twenty-five of the thirty-one signals form a single cluster.** Momentum,
reversal, moving averages, RSI, Bollinger, drawdown depth, close location,
volatility and skew are all chained together at |r| ≥ 0.5. Only
`negative_skew` and `rev_1d` stand alone, with `vol_trend`/`volume_shock` and
`illiquidity`/`small_dollar_vol` as two-name pairs — and that second pair is
one of the duplicates planted as a control.

Some correlations are near-identities the labels concealed: `mom_1m` vs
`rev_21d` is **−0.97** (they are the same number with opposite signs),
`mom_12_1` vs `mom_accel` is −0.94, `lowvol_60` vs `downside_dev` is +0.97.

### No signal has a measurable edge

| | |
|---|---|
| signals at \|t\| ≥ 2 | **0** (1.6 expected by chance at 5%) |
| best \|t\| | 1.55 (`downside_dev`) |
| signs matching their a-priori prior | 13/31 — binomial p = 0.24, i.e. a coin flip |
| mean individual \|IC\| | 0.0140 |
| mean individual IC (signed) | **−0.0058** |

t-stats are deflated by `√(horizon/stride)` for overlapping forward windows.
Without that correction they would be twice as large, which is the difference
between "nothing here" and two apparent discoveries.

### The theory was confirmed; the inputs are empty

Equal-weighting N independent signals should multiply IC by √N_eff. It did:

| | |
|---|---|
| combined IC | −0.0130 (t = −0.55) |
| lift over mean signed IC | **2.22×** |
| lift predicted from IC breadth 5.57 | **2.36×** |

**The breadth machinery works about as advertised — it just amplified a
negative number.**

How well it works is less precise than that 6% gap suggests, and the small-cap
replication below is what shows it: the denominator is a mean IC of −0.006,
close enough to zero that the ratio is unstable. Across both universes the
combination lifts by 2.2–3.7× against a prediction of 2.4–2.5×. That confirms
the framework *directionally* — combining is worth roughly what the eigenvalues
say, not √31 and not nothing — but the large-cap agreement to within 6% was
luck, not precision.

The arithmetic that follows is unforgiving. At the measured IC of 0.014, a
usable IR needs about 1,300 independent bets a year for IR 0.5, or 5,100 for
IR 1.0. What 31 signals actually supply:

| | bets/yr | IR | years to t=2 |
|---|---|---|---|
| 5.57 breadth × monthly | 67 | 0.11 | 305 |
| 5.57 breadth × weekly | 290 | 0.24 | 70 |
| 8.40 breadth × weekly | 437 | 0.29 | 47 |

And weekly rebalancing was already ruled out by the turnover work — costs eat
it. **Adding more price-derived signals does not fix this.** Going from 3
signals to 31 bought effective breadth of 5.57; the marginal signal is adding
roughly 0.2 of a bet, and the shortfall is two orders of magnitude.

Anything that changes the answer has to be **genuinely orthogonal information**
— not another transformation of the same OHLCV series that every one of these
31 signals is computed from. That is the only remaining place an LLM could
plausibly help: as a source of *new* features from text, not as a decision
maker over the same prices.

### Small caps replicate it

Same 31 signals, 110 small caps, same window — as a check that this is not a
large-cap artifact. It is not.

| | large | small |
|---|---|---|
| effective breadth (IC) | 5.57 | **6.19** |
| effective breadth (score) | 8.40 | **8.85** |
| largest cluster at \|r\| ≥ 0.5 | 25 of 31 | **24 of 31** |
| signals at \|t\| ≥ 2 | 0 | 1 |
| mean individual IC (signed) | −0.0058 | −0.0039 |
| combined IC | −0.0130 | −0.0145 |
| combination lift | 2.22× | 3.71× |
| lift predicted | 2.36× | 2.49× |

The same pairs top the matrix in both universes — `mom_1m`/`rev_21d` at −0.97,
`lowvol_60`/`downside_dev` at +0.97 — which is what a structural result looks
like rather than a fitted one.

The one signal reaching |t| ≥ 2 is **`illiquidity` at +2.06** (IC +0.0289).
Against 1.6 expected by chance across 31 tests, one hit is not a discovery. And
it is the same self-defeating trade the capacity work already ran into: the
measured trade-weighted spread on this universe is **14.27 bps**, several times
the edge on offer. The one signal that shows up is the one we cannot harvest.
