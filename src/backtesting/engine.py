import pandas as pd
from typing import List
from src.indicators.technical import TechnicalIndicators
from src.analysis.setup_detection import SetupDetector
from src.risk.engine import RiskEngine
from src.signals.scoring import SignalScorer
from src.backtesting.metrics import TradeRecord, BacktestPerformance, PerformanceCalculator

class BacktestEngine:
    """Historical Event-Driven Backtest Simulation Engine (Zero look-ahead bias)."""

    def __init__(
        self, 
        buy_fee_pct: float = 0.15, 
        sell_fee_pct: float = 0.25, 
        slippage_pct: float = 0.10,
        min_score: float = 70.0,
        min_rr: float = 1.8
    ):
        self.buy_fee = buy_fee_pct / 100.0
        self.sell_fee = sell_fee_pct / 100.0
        self.slippage = slippage_pct / 100.0
        self.min_score = min_score
        self.min_rr = min_rr

    def run_backtest(self, ticker: str, df: pd.DataFrame) -> BacktestPerformance:
        if df.empty or len(df) < 50:
            return PerformanceCalculator.calculate([])

        trades: List[TradeRecord] = []
        in_trade = False
        active_trade = None

        for i in range(35, len(df)):
            df_slice = df.iloc[:i]
            current_bar = df.iloc[i]
            current_price = current_bar["close"]
            current_high = current_bar["high"]
            current_low = current_bar["low"]
            date_str = str(df_slice.index[-1])[:10]

            if in_trade and active_trade:
                if current_low <= active_trade["stop_loss"]:
                    exit_price = active_trade["stop_loss"] * (1 - self.slippage)
                    pnl_raw = ((exit_price - active_trade["entry_price"]) / active_trade["entry_price"]) * 100.0
                    pnl_net = pnl_raw - ((self.buy_fee + self.sell_fee) * 100.0)
                    r_mult = round((exit_price - active_trade["entry_price"]) / active_trade["risk_per_share"], 2)

                    trades.append(TradeRecord(
                        ticker=ticker,
                        entry_date=active_trade["entry_date"],
                        exit_date=date_str,
                        entry_price=active_trade["entry_price"],
                        exit_price=exit_price,
                        stop_loss=active_trade["stop_loss"],
                        target_1=active_trade["target_1"],
                        pnl_pct=round(pnl_net, 2),
                        r_multiple=r_mult,
                        result="LOSS"
                    ))
                    in_trade = False
                    active_trade = None
                    continue

                elif current_high >= active_trade["target_1"]:
                    exit_price = active_trade["target_1"] * (1 - self.slippage)
                    pnl_raw = ((exit_price - active_trade["entry_price"]) / active_trade["entry_price"]) * 100.0
                    pnl_net = pnl_raw - ((self.buy_fee + self.sell_fee) * 100.0)
                    r_mult = round((exit_price - active_trade["entry_price"]) / active_trade["risk_per_share"], 2)

                    trades.append(TradeRecord(
                        ticker=ticker,
                        entry_date=active_trade["entry_date"],
                        exit_date=date_str,
                        entry_price=active_trade["entry_price"],
                        exit_price=exit_price,
                        stop_loss=active_trade["stop_loss"],
                        target_1=active_trade["target_1"],
                        pnl_pct=round(pnl_net, 2),
                        r_multiple=r_mult,
                        result="WIN"
                    ))
                    in_trade = False
                    active_trade = None
                    continue

            if not in_trade:
                snapshot = TechnicalIndicators.get_snapshot(df_slice)
                if not snapshot:
                    continue

                setup = SetupDetector.detect_setups(ticker, snapshot)
                if setup.setup_type.value == "NO_SETUP":
                    continue

                risk_plan = RiskEngine.calculate_risk_plan(snapshot, setup, min_rr=self.min_rr)
                if not risk_plan or not risk_plan.is_valid_rr:
                    continue

                score = SignalScorer.score_signal(snapshot, setup, risk_plan, min_score_threshold=self.min_score)

                if score.signal_type in ["BUY", "STRONG_BUY"]:
                    entry_price = current_price * (1 + self.slippage)
                    in_trade = True
                    active_trade = {
                        "entry_date": date_str,
                        "entry_price": entry_price,
                        "stop_loss": risk_plan.stop_loss,
                        "target_1": risk_plan.target_1,
                        "risk_per_share": risk_plan.risk_per_share
                    }

        return PerformanceCalculator.calculate(trades)
