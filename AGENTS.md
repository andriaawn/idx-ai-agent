# IDX AI Agent — Codex Development Instructions

## 1. Project Overview

This repository contains the IDX AI Agent, a production-oriented Telegram bot for quantitative analysis and research of Indonesian Stock Exchange (IDX) equities.

The system combines:

- IDX stock universe resolution
- OHLCV market data
- Technical indicators
- Quantitative signal generation
- Risk/reward analysis
- Multi-timeframe analysis
- Market regime analysis
- Gemini LLM integration
- Telegram delivery
- Signal persistence
- Backtesting
- Research reporting

Production deployment runs on a VPS using systemd.

---

## 2. Core Development Rules

Before modifying code:

1. Inspect the relevant call chain.
2. Understand the existing implementation before changing it.
3. Modify only the modules required for the requested task.
4. Preserve existing working behavior.
5. Do not perform broad refactors unless explicitly requested.
6. Do not change unrelated modules.
7. Run relevant tests whenever Python is available.
8. Always run:

```bash
git diff --check
```

## 3. Local Python and Verification

- Use Python 3.11 through the project-local interpreter only:
  `\.venv\Scripts\python.exe`.
- Never use system `python` or default `py` for project validation.
- Do not recreate `.venv` unless explicitly instructed.
- Do not reinstall requirements unless dependencies are actually missing.
- Run local validation through `\.tools\verify.ps1`.
