import unittest
from src.indicators.technical import TechnicalSnapshot
from src.analysis.setup_detection import SetupDetector, SetupType
from src.risk.engine import RiskEngine
from src.signals.scoring import SignalScorer
from src.signals.lifecycle import SignalLifecycleManager, SignalState
from src.agents.reporter import ResearchReportGenerator

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

    def test_bullish_mtf_and_regime_confirm_buy(self):
        snap = get_mock_snapshot()
        setup = SetupDetector.detect_setups("BBCA", snap)
        risk_plan = RiskEngine.calculate_risk_plan(snap, setup, min_rr=1.5)

        score = SignalScorer.score_signal(
            snap,
            setup,
            risk_plan,
            mtf_score=90.0,
            mtf_direction="BULLISH",
            regime_status="BULLISH",
            signal_direction="BUY",
        )
        self.assertEqual(score.mtf_score, 13.5)
        self.assertEqual(score.regime_score, 10.0)

    def test_bearish_mtf_and_regime_confirm_sell(self):
        snap = get_mock_snapshot()
        setup = SetupDetector.detect_setups("BBCA", snap)
        risk_plan = RiskEngine.calculate_risk_plan(snap, setup, min_rr=1.5)

        score = SignalScorer.score_signal(
            snap,
            setup,
            risk_plan,
            mtf_score=90.0,
            mtf_direction="BEARISH",
            regime_status="BEARISH",
            signal_direction="SELL",
        )
        self.assertEqual(score.mtf_score, 13.5)
        self.assertEqual(score.regime_score, 10.0)

    def test_opposing_mtf_and_regime_do_not_reward_signal_direction(self):
        snap = get_mock_snapshot()
        setup = SetupDetector.detect_setups("BBCA", snap)
        risk_plan = RiskEngine.calculate_risk_plan(snap, setup, min_rr=1.5)

        bullish_for_sell = SignalScorer.score_signal(
            snap, setup, risk_plan, 90.0, "BULLISH", "BULLISH", "SELL"
        )
        bearish_for_buy = SignalScorer.score_signal(
            snap, setup, risk_plan, 90.0, "BEARISH", "BEARISH", "BUY"
        )

        self.assertEqual(bullish_for_sell.mtf_score, 0.0)
        self.assertEqual(bullish_for_sell.regime_score, 0.0)
        self.assertEqual(bearish_for_buy.mtf_score, 0.0)
        self.assertEqual(bearish_for_buy.regime_score, 0.0)

    def test_unavailable_mtf_and_regime_receive_no_default_points(self):
        snap = get_mock_snapshot()
        setup = SetupDetector.detect_setups("BBCA", snap)
        risk_plan = RiskEngine.calculate_risk_plan(snap, setup, min_rr=1.5)

        score = SignalScorer.score_signal(snap, setup, risk_plan)

        self.assertEqual(score.mtf_score, 0.0)
        self.assertEqual(score.regime_score, 0.0)

    def test_reporter_displays_the_actual_mtf_and_regime_used_by_scorer(self):
        snap = get_mock_snapshot()
        setup = SetupDetector.detect_setups("BBCA", snap)
        risk_plan = RiskEngine.calculate_risk_plan(snap, setup, min_rr=1.5)
        score = SignalScorer.score_signal(
            snap, setup, risk_plan, 90.0, "BULLISH", "BULLISH", "BUY"
        )

        report = ResearchReportGenerator.generate_full_research_report({
            "status": "SUCCESS",
            "ticker": "BBCA.JK",
            "snapshot": snap,
            "setup": setup,
            "risk_plan": risk_plan,
            "score_breakdown": score,
            "mtf_analysis": {
                "alignment_score": 90.0,
                "status": "STRONG_BULLISH_ALIGNMENT",
                "direction": "BULLISH",
            },
            "market_regime": {"regime": "BULLISH"},
        })

        self.assertIn("13.5/15", report)
        self.assertIn("STRONG_BULLISH_ALIGNMENT", report)
        self.assertIn("direction: BULLISH", report)
        self.assertIn("10.0/10 (BULLISH)", report)

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
