from typing import Dict, Any
from src.agents.tools import QuantAgentTools
from src.agents.reporter import ResearchReportGenerator

class AgentOrchestrator:
    """Orchestrates workflows between quantitative tools and report generation."""

    def __init__(self):
        self.tools = QuantAgentTools()

    async def process_ticker_analysis(self, ticker: str, detailed: bool = False) -> str:
        """Processes ticker analysis and returns formatted alert or full report."""
        res = await self.tools.analyze_stock(ticker)

        if res.get("status") != "SUCCESS":
            return f"⚠️ Analysis failed for {ticker}: {res.get('reason', 'Data unavailable')}"

        if detailed:
            return ResearchReportGenerator.generate_full_research_report(res)
        else:
            return ResearchReportGenerator.generate_short_signal_alert(
                ticker=ticker,
                score=res["score_breakdown"],
                setup=res["setup"],
                risk=res["risk_plan"]
            )
