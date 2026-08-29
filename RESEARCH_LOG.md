# Research Log

## Train/Holdout Split — committed 2026-08-25

- Development window: 2021-01-01 to 2024-12-31. All hypothesis formation,
  attribution analysis, and rule tuning happens ONLY on this window.
- Holdout window: 2025-01-01 onward. Untouched until the engine and rules
  are fully frozen based on development-window findings. Touched exactly
  once, after freezing, no further tuning based on the result.

## Engine status at time of commitment

- amdx.py index bug fixed and regression-tested (test_amdx_state_machine.py)
- portfolio.py daily P&L causality verified (test_portfolio_causality.py)
- ATR causality + continuous-history policy verified (test_atr_policy.py)
- Manually chart-audited trades: GBPUSD x2, GBPJPY x1 (Jan 2021) -- all
  reconciled against raw tick-derived OHLC, not just visually
- Known gap: GBPJPY 2021-01-31 19:00-23:59 UTC, Dukascopy server-side
  503/timeout, confirmed persistent across 2 retries, documented not fixed

## Parameter test — 2026-08-28

Hypothesis: setup_expiry_minutes=180 does not appear in doc 3's rule spec
(only in the separate, unrelated 15-min intraday report) and may explain
why GBPUSD signal frequency (49.3% of days) is ~1.7x higher than the
original report's implied frequency (~29.3%). Testing effect by setting
expiry to 1440 (effectively no meaningful cap within the trading window)
and comparing raw candidate count for GBPUSD 2021 (baseline: 132).

## Parameter test RESULT — 2026-08-28

setup_expiry_minutes 180 -> 1440: candidates went 132 -> 141 (+6.8%),
moving AWAY from the original report's implied lower frequency, not
toward it. Conclusion: expiry does NOT explain the 1.7x frequency gap --
ruled out as primary cause. Reverting to 180 (original test value; true
'no expiry' would need testing separately if pursued further).

Next candidate to check: closeback_max_fraction (0.20 in our yaml) --
compare against doc 3's actual closeback depth distribution, and check
whether amdx.py's closeback logic matches the spec's 'no midpoint reclaim'
condition exactly.

## Parameter test RESULT — 2026-08-28

closeback_max_fraction 0.20 -> 0.10: candidates 132 -> 103 (-22%), a much
more sensitive lever than expiry. BUT trade quality did not improve
(win_rate 35.2%->34.0%, avg_r -0.121->-0.150) -- tightening did not
filter out weaker signals, arguing against 0.20 admitting junk.

Reframing: matching the original report's implied frequency (29.3%) is
not necessarily the right target. The original notebooks had documented
defects (post-selection, exit-time-aware bug, timezone inconsistency).
Our implementation is chart-audited (4 trades, 2 pairs, 2 months, zero
discrepancies) -- stronger evidence of correctness than matching an
external number from known-flawed code. Reverting closeback to 0.20
(documented spec value). Not pursuing further frequency-matching;
returning focus to aggregate expectancy once balanced 4-pair data is ready.

## Code check — 2026-08-28

first_valid_rebreak_only=true in yaml is never parsed by config.py, but
amdx.py's state machine already takes the first rebreak by construction
(no further scanning after rebreak=True). Confirmed non-functional but
also non-bug -- ruled out as a frequency-gap explanation. Remaining
candidate: genuine year-to-year variance (2021 alone vs original's
blended 2021-2025 average) -- can't resolve without more data.

## Finding — 2026-08-28

Stale-parquet bug confirmed real: GBPUSD total_r improved from -15.5R to
-9.0R after force-rebuilding with check_stale_parquets.py verification.
All prior numbers in this log before this point should be treated as
provisional/superseded.

New finding, corrected data: long trades are weaker than or equal to
short trades in ALL FOUR pairs. Aggregate: long total_r=-5.0 (100% of
the loss), short total_r=0.0 exactly across 80 trades. Cross-pair
consistent, unlike the day-of-week finding which kept flipping.
Candidate hypothesis for the eventual iteration phase: does this
strategy have an inherent long/short asymmetry? Worth re-checking once
balanced multi-pair, multi-month data is available.

## Download status — 2026-08-28

EURUSD/EURJPY/GBPJPY 2021-2022 download running at --workers 2 --timeout
12. Slow (progress checkpoints every 50 jobs can take a while when a job
hits its retry/backoff cycle) but confirmed NOT stalled -- verified via
repeated manifest Length/LastWriteTime checks showing real progress.
Decision: stop tuning worker count further: 2 is the only setting that's
been reliably stable all session (4 fails ~95% of new downloads even
after the SSL crash-fix; 3 has mixed/inconclusive evidence). Letting it
run unattended going forward rather than continuing to restart/tune.
