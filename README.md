# FX Research Pipeline

A systematic research pipeline for testing whether a rule-based intraday
FX continuation strategy has a real, repeatable edge — built to replace
gut-feel discretionary trading with something that can actually be
measured, audited, and trusted.

## FX trading, in a nutshell

The foreign exchange (FX) market is where currencies are bought and
sold against each other — EUR/USD, GBP/USD, and so on. It's the
largest, most liquid financial market in the world, open nearly 24
hours a day across different regional sessions (Asia, London, New
York). Traders try to profit from short-term price movements by
predicting whether a currency pair will rise or fall over a given
window, using a stop-loss and take-profit to define risk before
entering.

That sounds simple. In practice, most retail traders lose money — not
because the market is unbeatable, but because of *how* they trade it.

## The real problem: psychology, not analysis

The single biggest reason discretionary traders underperform isn't a
lack of chart-reading skill. It's a handful of well-documented
behavioral patterns that quietly erode an account over time:

- **Revenge trading** — taking an oversized, low-quality trade
  immediately after a loss to "win it back."
- **Moving stops** — widening a stop-loss mid-trade because closing it
  "feels wrong," turning a small planned loss into a large unplanned one.
- **FOMO entries** — chasing a move after it's already happened,
  buying the top or selling the bottom of a swing everyone else already
  caught.
- **Inconsistent position sizing** — risking 0.5% on one trade and 5%
  on the next "high conviction" one, with no consistent logic.
- **Overtrading** — taking marginal setups out of boredom or the urge
  to "be in the market," diluting the good setups with noise.
- **Recency and confirmation bias** — overweighting the last few
  trades' outcomes, or only remembering the wins that confirm a belief.

None of these are stupidity. They're normal human responses to
uncertainty and loss — which is exactly why they're so hard to
eliminate through willpower alone, trade after trade, for years.

**A fully rule-based system sidesteps this by design, not by
discipline.** If entries, exits, position sizing, and daily loss limits
are all defined in code before a single trade is placed, there's no
moment where fear or excitement gets a vote. The system either
generates a signal that meets every defined condition, or it doesn't —
and every trade it takes was already decided long before the market
moved.

**Important honesty check**: removing psychology from execution does
*not* automatically mean the strategy is profitable. A perfectly
disciplined execution of a bad idea still loses money — it just loses
in a measurable, analyzable way instead of an emotional, untraceable
one. That's the actual point of this project: not to promise an edge,
but to build the infrastructure to honestly find out whether one
exists, and to keep it honest as it's discovered.

## What this pipeline actually does

Starting from raw historical tick data, it:

1. Downloads and decodes 5-minute bid/ask bars for GBPUSD, EURUSD,
   EURJPY, GBPJPY.
2. Converts timestamps to Singapore time and assigns each bar to a
   trading "day" that starts at 06:00 SGT.
3. Runs a deterministic state machine — Asian session sweep → shallow
   closeback → rebreak confirmation → entry — with zero discretionary
   judgment involved.
4. Applies portfolio-level risk rules (max trades per day, daily loss
   stop, one trade per pair per day) across all four pairs at once.
5. Simulates every trade bar-by-bar against real market data to
   produce an honest trade log — not a hypothetical one.
6. Breaks results down by pair, direction, month, and day of week to
   surface real patterns instead of hiding behind one aggregate number.

## Current progress

This project started by auditing an existing backtest and finding it
was **not trustworthy as originally built** — a real indexing bug was
silently placing trades on the wrong bar, and a separate data-pipeline
bug was silently building results from incomplete data. Both are now
found, fixed, and permanently guarded against with automated tests.

As of now:

- The core engine has been verified correct — not just read, but
  chart-audited trade-by-trade against raw market data, and
  stress-tested with synthetic ground-truth cases designed to catch
  exactly the kind of bugs that plagued the original version.
- Historical data collection is in progress across all four pairs.
- Early results are **statistically inconclusive** — not a confirmed
  edge, not a confirmed failure. That's the honest current state, and
  it's stated here rather than dressed up either way.
- One interesting, cross-pair-consistent early signal has emerged
  (a long/short performance asymmetry) that's flagged for deeper
  investigation once more data is available — not yet treated as a
  conclusion.

Full technical documentation — architecture, every file's purpose, and
the complete list of findings and fixes — is in
[`PROJECT_STATUS.md`](./PROJECT_STATUS.md). The full timestamped
research log, including every parameter test and its result, is in
[`RESEARCH_LOG.md`](./RESEARCH_LOG.md).

## Setup

See [`PROJECT_STATUS.md`](./PROJECT_STATUS.md) for the full pipeline
walkthrough and command reference.
