from dataclasses import dataclass
from typing import Optional
from src.indicators.technical import TechnicalSnapshot
from src.analysis.setup_detection import DetectedSetup

@dataclass
class RiskPlan:
    entry_price: float
    entry_zone_min: float
    entry_zone_max: float
    stop_loss: float
    target_1: float
    target_2: float
    risk_per_share: float
    reward_per_share: float
    risk_reward_ratio: float
    invalidation_level: float
    is_valid_rr: bool

class RiskEngine:
    """Hybrid Risk Engine: combines ATR volatility stops with structural Support/Resistance levels."""

    @staticmethod
    def calculate_risk_plan(
        snapshot: TechnicalSnapshot, 
        setup: DetectedSetup, 
        min_rr: float = 1.8
    ) -> Optional[RiskPlan]:
        if not snapshot or setup.setup_type.value == "NO_SETUP":
            return None

        entry = snapshot.close
        atr = snapshot.atr_14

        entry_min = round(entry * 0.995, 2)
        entry_max = round(entry * 1.005, 2)

        atr_stop = entry - (1.5 * atr)
        struct_stop = setup.invalidation_level if setup.invalidation_level > 0 else (entry - 2.0 * atr)

        stop_loss = max(atr_stop, struct_stop)
        stop_loss = round(min(stop_loss, entry * 0.98), 2)

        risk_per_share = round(entry - stop_loss, 2)
        if risk_per_share <= 0:
            return None

        valid_targets = [r for r in snapshot.resistance_levels if r > entry] if snapshot.resistance_levels else []
        if valid_targets:
            target_1 = min(valid_targets)
            target_2 = max(valid_targets) if len(valid_targets) > 1 else round(entry + (3.5 * risk_per_share), 2)
        else:
            target_1 = round(entry + (2.0 * risk_per_share), 2)
            target_2 = round(entry + (3.5 * risk_per_share), 2)

        reward_per_share = round(target_1 - entry, 2)
        rr_ratio = round(reward_per_share / risk_per_share, 2) if risk_per_share > 0 else 0.0

        is_valid_rr = rr_ratio >= min_rr

        return RiskPlan(
            entry_price=entry,
            entry_zone_min=entry_min,
            entry_zone_max=entry_max,
            stop_loss=stop_loss,
            target_1=target_1,
            target_2=target_2,
            risk_per_share=risk_per_share,
            reward_per_share=reward_per_share,
            risk_reward_ratio=rr_ratio,
            invalidation_level=stop_loss,
            is_valid_rr=is_valid_rr
        )
