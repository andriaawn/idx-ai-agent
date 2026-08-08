from dataclasses import dataclass
from typing import List

@dataclass
class TradeRecord:
    ticker: str
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    stop_loss: float
    target_1: float
    pnl_pct: float
    r_multiple: float
    result: str  # WIN, LOSS, BREAKEVEN

@dataclass
class BacktestPerformance:
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    profit_factor: float
    average_r: float
    total_return_pct: float
    max_drawdown_pct: float
    trades: List[TradeRecord]

class PerformanceCalculator:
    """Calculates quantitative performance metrics for backtested trades."""

    @staticmethod
    def calculate(trades: List[TradeRecord], initial_capital: float = 100_000_000.0) -> BacktestPerformance:
        if not trades:
            return BacktestPerformance(
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0.0,
                profit_factor=0.0,
                average_r=0.0,
                total_return_pct=0.0,
                max_drawdown_pct=0.0,
                trades=[]
            )

        total_trades = len(trades)
        wins = [t for t in trades if t.pnl_pct > 0]
        losses = [t for t in trades if t.pnl_pct <= 0]

        winning_count = len(wins)
        losing_count = len(losses)
        win_rate = round((winning_count / total_trades) * 100.0, 2)

        gross_profits = sum([t.pnl_pct for t in wins])
        gross_losses = abs(sum([t.pnl_pct for t in losses]))

        profit_factor = round(gross_profits / gross_losses, 2) if gross_losses > 0 else (gross_profits if gross_profits > 0 else 0.0)

        total_r = sum([t.r_multiple for t in trades])
        average_r = round(total_r / total_trades, 2)

        equity = initial_capital
        peak = equity
        max_dd = 0.0

        for trade in trades:
            equity += equity * (trade.pnl_pct / 100.0)
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak * 100.0
            if dd > max_dd:
                max_dd = dd

        total_return_pct = round(((equity - initial_capital) / initial_capital) * 100.0, 2)
        max_drawdown_pct = round(max_dd, 2)

        return BacktestPerformance(
            total_trades=total_trades,
            winning_trades=winning_count,
            losing_trades=losing_count,
            win_rate=win_rate,
            profit_factor=profit_factor,
            average_r=average_r,
            total_return_pct=total_return_pct,
            max_drawdown_pct=max_drawdown_pct,
            trades=trades
        )
