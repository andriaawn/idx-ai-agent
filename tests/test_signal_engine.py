import unittest
from src.indicators.technical import TechnicalSnapshot
from src.analysis.setup_detection import SetupDetector, SetupType
from src.risk.engine import RiskEngine
from src.signals.scoring import SignalScorer
from src.signals.lifecycle import SignalLifecycleManager, SignalState

def get_mock_snapshot():
    return TechnicalSnapshot(
        close=1000.0,
        volume=50000,
        ema_20=950.0,
        ema_50=900.0,
        ema_200=800.0,
        rsi_14=65.0,
        macd_line=15.0,
        macd_signal=10.0,
        macd_hist=5.0,
        atr_14=30.0,
        atr_pct=3.0,
        vol_ma_20=30000,
        rvol=1.6,
        roc_10=5.0,
        support_levels=[920.0],
        resistance_levels=[1100.0],
        trend_alignment="BULLISH"
    )

class TestSignalEngine(unittest.TestCase):

    def test_setup_detection(self):
        snap = get_mock_snapshot()
        setup = SetupDetector.detect_setups("BBCA", snap)
        self.assertEqual(setup.setup_type, SetupType.MOMENTUM_CONTINUATION)
        self.assertGreater(setup.quality_score, 0)

    def test_risk_engine(self):
        snap = get_mock_snapshot()
        setup = SetupDetector.detect_setups("BBCA", snap)
        risk_plan = RiskEngine.calculate_risk_plan(snap, setup, min_rr=1.5)
        self.assertIsNotNone(risk_plan)
        self.assertLess(risk_plan.stop_loss, snap.close)
        self.assertGreater(risk_plan.target_1, snap.close)
        self.assertGreaterEqual(risk_plan.risk_reward_ratio, 1.5)

    def test_signal_scorer(self):
        snap = get_mock_snapshot()
        setup = SetupDetector.detect_setups("BBCA", snap)
        risk_plan = RiskEngine.calculate_risk_plan(snap, setup, min_rr=1.5)
        score = SignalScorer.score_signal(snap, setup, risk_plan)
        self.assertGreaterEqual(score.total_score, 70.0)
        self.assertIn(score.signal_type, ["BUY", "STRONG_BUY"])

    def test_signal_lifecycle(self):
        update = SignalLifecycleManager.evaluate_state_transition(
            current_price=1100.0,
            entry_price=1000.0,
            stop_loss=950.0,
            target_1=1100.0,
            target_2=1200.0,
            current_state=SignalState.ACTIVE
        )
        self.assertEqual(update.current_state, SignalState.HIT_TP1)

if __name__ == "__main__":
    unittest.main()
