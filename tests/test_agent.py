import unittest
from src.agents.tools import QuantAgentTools
from src.agents.orchestrator import AgentOrchestrator

class TestAgentSystem(unittest.IsolatedAsyncioTestCase):

    async def test_quant_agent_tools(self):
        tools = QuantAgentTools()
        market = await tools.get_market_status()
        self.assertTrue("regime" in market or market.get("status") == "UNAVAILABLE")

        analysis = await tools.analyze_stock("BBCA")
        self.assertIn(analysis["status"], ["SUCCESS", "DATA_UNRELIABLE", "ERROR"])

    async def test_agent_orchestrator(self):
        orchestrator = AgentOrchestrator()
        alert = await orchestrator.process_ticker_analysis("BBCA", detailed=False)
        self.assertGreater(len(alert), 0)
        self.assertIn("BBCA", alert)

if __name__ == "__main__":
    unittest.main()
