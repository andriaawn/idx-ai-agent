"""IDX ticker extraction and validation for user-provided text."""

import asyncio
import re
from typing import ClassVar, Iterable, List, Optional, Set

from src.data.universe import IDXUniverseRefresher


class TickerResolver:
    """Extract only valid IDX tickers and return Yahoo Finance's ``.JK`` form."""

    _CANDIDATE_PATTERN = re.compile(
        r"(?<![A-Za-z0-9])([A-Za-z]{4})(?:\.JK)?(?![A-Za-z0-9])",
        re.IGNORECASE,
    )
    _default_resolver: ClassVar[Optional["TickerResolver"]] = None
    _cache_lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    def __init__(self, valid_tickers: Iterable[str]):
        self._valid_tickers: Set[str] = {
            normalized
            for ticker in valid_tickers
            if (normalized := self._normalize_symbol(ticker))
        }

    @staticmethod
    def _normalize_symbol(value: str) -> str:
        symbol = str(value).strip().upper()
        if symbol.endswith(".JK"):
            symbol = symbol[:-3]
        return symbol if re.fullmatch(r"[A-Z]{4}", symbol) else ""

    @classmethod
    async def default(cls) -> "TickerResolver":
        """Build and cache a resolver from the configured IDX universe source."""
        if cls._default_resolver is None:
            async with cls._cache_lock:
                if cls._default_resolver is None:
                    stocks = await IDXUniverseRefresher.fetch_idx_stocks()
                    cls._default_resolver = cls(stock["ticker"] for stock in stocks)
        return cls._default_resolver

    def resolve_candidate(self, candidate: str) -> Optional[str]:
        """Return the canonical Yahoo IDX ticker only when it is in the universe."""
        symbol = self._normalize_symbol(candidate)
        return f"{symbol}.JK" if symbol and symbol in self._valid_tickers else None

    def extract(self, text: str) -> List[str]:
        """Return ordered, deduplicated valid IDX tickers from free-form text."""
        resolved: List[str] = []
        seen: Set[str] = set()
        for match in self._CANDIDATE_PATTERN.finditer(text):
            ticker = self.resolve_candidate(match.group(0))
            if ticker and ticker not in seen:
                seen.add(ticker)
                resolved.append(ticker)
        return resolved

    @classmethod
    async def resolve_ticker(cls, candidate: str) -> Optional[str]:
        return (await cls.default()).resolve_candidate(candidate)

    @classmethod
    async def resolve_text(cls, text: str) -> List[str]:
        return (await cls.default()).extract(text)
