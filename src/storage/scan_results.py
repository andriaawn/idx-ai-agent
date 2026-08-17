"""Persistence and retrieval for the latest shared market scan."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select

from src.storage.database import AsyncSessionLocal
from src.storage.models import ScanCandidate, ScanRun


async def save_scan_snapshot(scan_results: List[Dict[str, Any]], total_scanned: int) -> int:
    """Store one immutable scan run and return its candidate count."""
    async with AsyncSessionLocal() as session:
        scan_run = ScanRun(
            created_at=datetime.utcnow(),
            total_scanned=total_scanned,
            candidate_count=len(scan_results),
        )
        session.add(scan_run)
        await session.flush()

        for result in scan_results:
            ticker = result["ticker"]
            score = result["score_breakdown"]
            setup = result.get("setup")
            risk = result.get("risk_plan")
            snapshot = result.get("snapshot")
            session.add(ScanCandidate(
                scan_run_id=scan_run.id,
                ticker=ticker[:-3] if ticker.endswith(".JK") else ticker,
                signal_type=score.signal_type,
                setup_name=setup.setup_type.value if setup else "NO_SETUP",
                score=score.total_score,
                reference_price=getattr(snapshot, "close", None),
                entry_price=getattr(risk, "entry_price", None),
                stop_loss=getattr(risk, "stop_loss", None),
                target_1=getattr(risk, "target_1", None),
                risk_reward=getattr(risk, "risk_reward_ratio", None),
            ))
        await session.commit()
    return len(scan_results)


async def get_latest_scan_candidates(
    offset: int = 0,
    limit: int = 10,
    signal_type: Optional[str] = None,
) -> Tuple[Optional[ScanRun], List[ScanCandidate]]:
    """Return one page from the most recent completed scan."""
    async with AsyncSessionLocal() as session:
        run = (await session.execute(
            select(ScanRun).order_by(ScanRun.created_at.desc(), ScanRun.id.desc()).limit(1)
        )).scalar_one_or_none()
        if run is None:
            return None, []

        statement = select(ScanCandidate).where(ScanCandidate.scan_run_id == run.id)
        if signal_type:
            statement = statement.where(ScanCandidate.signal_type == signal_type)
        statement = statement.order_by(ScanCandidate.score.desc(), ScanCandidate.id.asc()).offset(offset).limit(limit)
        candidates = list((await session.execute(statement)).scalars())
        return run, candidates
