# IDX AI Agent — Codex Handoff

## Last Updated

2026-08-09

---

# 1. Current Repository State

The IDX AI Agent is an operational prototype for Indonesian equity research.
It is not yet production-grade or decision-grade for strategy performance
claims.

## Git State

- Branch: `main`
- Latest commit: `d4c7caf feat: integrate MTF and market regime scoring`
- Previous relevant commit: `d97a26b fix: format Telegram markdown responses`
- `main` is currently ahead of `origin/main` by one commit.

The MTF/regime work is committed in `d4c7caf`. It contains exactly:

- `src/agents/reporter.py`
- `src/agents/tools.py`
- `src/analysis/multi_timeframe.py`
- `src/backtesting/engine.py`
- `src/signals/scoring.py`
- `tests/test_agent.py`
- `tests/test_quant_engine.py`
- `tests/test_signal_engine.py`

## Current Uncommitted Changes

Keep these outside unrelated work unless explicitly requested:

- `src/agents/llm_agent.py` is modified but uncommitted. It changes the Gemini
  model list to `MODELS = ["gemini-3.5-flash", "gemini-3.1-flash-lite"]`.
  This is a separate pre-existing change and is **not** part of `d4c7caf`.
- `.venv/` is untracked. It is a local Python 3.11.9 environment and must never
  be committed.
- `AGENTS.md`, `CODEX_HANDOFF.md`, and `tools/` are untracked local files.
  Do not alter `AGENTS.md` or `tools/vps-diagnostics.ps1` during unrelated work.

---

# 2. Validated State

After the MTF/regime implementation, the local `.venv` successfully ran:

```text
python -m unittest tests.test_signal_engine tests.test_quant_engine tests.test_backtest
14 tests, OK

python -m unittest tests.test_agent
6 tests, OK

python -m unittest discover -s tests -p "test_*.py"
33 tests, OK

python -m compileall -q src tests
PASS

git diff --check
PASS
```

Windows `LF → CRLF` Git warnings are informational only.

---

# 3. Completed Work

## 3.1 Ticker Resolution

Natural-language ticker extraction and resolution are implemented against the
IDX universe before market-data requests.

- `.JK` normalization is applied for Yahoo Finance symbols.
- Invalid symbols such as `COBA` are rejected when absent from the IDX universe.
- Stable implementation: `src/data/ticker_resolver.py`

Examples:

```text
CUAN -> CUAN.JK
DSSA -> DSSA.JK
BBCA -> BBCA.JK
COBA -> invalid when absent from the IDX universe
```

## 3.2 Telegram Formatting and Delivery

Telegram delivery supports:

- Gemini Markdown to Telegram HTML conversion.
- Bold, italic, headings, lists, links, inline code, and fenced code blocks.
- HTML escaping.
- Safe 4,000-character chunking with formatting tags closed and reopened at
  chunk boundaries.
- `/analyze` and natural-language Gemini responses both use this formatting path.

Stable implementation:

- `src/telegram/messages.py`
- `src/telegram/handlers.py`

## 3.3 Quant, MTF, and Market Regime

Base quant analysis and risk planning exist. Commit `d4c7caf` adds validated,
direction-aware MTF and market-regime integration:

- Bullish MTF/regime confirmation contributes to `BUY` scoring.
- Bearish MTF/regime confirmation is supported at scorer level for future `SELL`
  workflows, but the current system remains long-only and does not generate
  executable short signals.
- Opposing, neutral, or unavailable context contributes zero related points.
- No dummy default such as `mtf_score=50` or `regime_status="BULLISH"` remains
  in the live or backtest scoring path.
- Weekly or IHSG fetch failures degrade to explicit unavailable context instead
  of aborting valid daily analysis.
- Invalid or fewer-than-50-bar HTF data cannot influence MTF scoring.
- Backtest explicitly does not fabricate historical MTF or IHSG context.

## 3.4 Persistence

Persistence schema and scan-signal persistence exist. Reliability, foreign-key,
and scheduler integration still require audit.

## 3.5 Backtest

An event-driven backtest engine exists. It remains a prototype and must not be
used as decision-grade evidence of strategy performance.

## 3.6 Charting

No charting implementation or chart-data contract exists yet. Do not begin
charting until the data-integrity and chart-data-contract prerequisites below
are complete.

---

# 4. Known Limitations and Technical Debt

## 4.1 Data Integrity

- `MarketDataNormalizer` currently calls `ffill()`/`bfill()` before validation.
  This can conceal missing source OHLCV data before `MarketDataValidator` sees it.
- Data freshness, as-of metadata, timezone normalization, and provider
  adjustment policy are not yet robustly defined.

## 4.2 Indicators

- RSI zero-loss behavior needs audit.
- Very short history can cause snapshot or indicator edge cases.
- These cases need deterministic test coverage.

## 4.3 Persistence Reliability

- Signal persistence may depend on `Instrument` rows already existing.
- Universe synchronization and startup behavior need review.
- Silent persistence failures should be eliminated.

## 4.4 Backtest Hardening

- Entry/exit timing and open-position handling require hardening.
- Position sizing and capital allocation are not sufficiently realistic.
- Intrabar stop/target ambiguity needs an explicit policy.

## 4.5 Provider Resilience

- yfinance needs freshness, retry/rate-limit, and cache review.
- Provider fallback policy needs review.
- `GoogleFinanceProvider` exists but is not confirmed as an active fallback.

## 4.6 LLM Change Outside Scope

`src/agents/llm_agent.py` has the separate uncommitted model-list change noted
above. Do not validate, commit, revert, or mix it into unrelated work unless
explicitly requested.

## 4.7 Charting Prerequisite

Before charting, define a structured chart-data contract containing at minimum:

- OHLCV series and timestamps
- timezone and as-of metadata
- timeframe and provider/source
- indicator series
- support/resistance
- setup, entry, stop loss, and targets
- MTF status/direction
- market regime
- chart annotations

---

# 5. Next Recommended Task

Do **not** start charting yet.

The next engineering phase is **data-integrity audit and hardening**:

1. Audit `MarketDataNormalizer` versus `MarketDataValidator`.
2. Ensure missing or invalid source OHLCV cannot be silently repaired before
   validation.
3. Audit minimum-history behavior for indicators.
4. Fix the RSI zero-loss edge case if confirmed.
5. Add deterministic tests for missing OHLCV, invalid OHLC, short history, and
   RSI edge cases.
6. Define freshness, as-of, and timezone metadata policy.
7. Audit persistence reliability.
8. Harden backtest behavior.
9. Define the chart-data contract.
10. Only then begin charting.
