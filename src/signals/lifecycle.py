from enum import Enum
from datetime import datetime
from dataclasses import dataclass

class SignalState(str, Enum):
    GENERATED = "GENERATED"
    ACTIVE = "ACTIVE"
    HIT_TP1 = "HIT_TP1"
    HIT_TP2 = "HIT_TP2"
    STOPPED_OUT = "STOPPED_OUT"
    INVALIDATED = "INVALIDATED"
    EXPIRED = "EXPIRED"

@dataclass
class SignalLifecycleUpdate:
    current_state: SignalState
    price: float
    timestamp: datetime
    reason: str

class SignalLifecycleManager:
    """Tracks and updates state transitions for active signals."""

    @staticmethod
    def evaluate_state_transition(
        current_price: float, 
        entry_price: float, 
        stop_loss: float, 
        target_1: float, 
        target_2: float, 
        current_state: SignalState = SignalState.ACTIVE
    ) -> SignalLifecycleUpdate:
        now = datetime.utcnow()

        if current_price <= stop_loss:
            return SignalLifecycleUpdate(
                current_state=SignalState.STOPPED_OUT,
                price=current_price,
                timestamp=now,
                reason=f"Price {current_price} hit stop loss level {stop_loss}"
            )

        if current_price >= target_2:
            return SignalLifecycleUpdate(
                current_state=SignalState.HIT_TP2,
                price=current_price,
                timestamp=now,
                reason=f"Price {current_price} reached Target 2 level {target_2}"
            )

        if current_price >= target_1 and current_state != SignalState.HIT_TP1:
            return SignalLifecycleUpdate(
                current_state=SignalState.HIT_TP1,
                price=current_price,
                timestamp=now,
                reason=f"Price {current_price} reached Target 1 level {target_1}"
            )

        return SignalLifecycleUpdate(
            current_state=current_state,
            price=current_price,
            timestamp=now,
            reason="Signal remains active within bounds"
        )
