from typing import Dict, Any, Optional
from src.indicators.technical import TechnicalSnapshot
from src.analysis.setup_detection import DetectedSetup
from src.risk.engine import RiskPlan
from src.signals.scoring import ScoreBreakdown

class ResearchReportGenerator:
    """Generates structured, professional equity research reports."""

    @staticmethod
    def generate_short_signal_alert(
        ticker: str,
        score: ScoreBreakdown,
        setup: DetectedSetup,
        risk: Optional[RiskPlan]
    ) -> str:
        #ticker = str(ticker).removesuffix(".JK")
        display_ticker = ticker.removesuffix(".JK")
        """Generates scannable Telegram signal alert."""
        icon = "🟢" if score.signal_type in ["BUY", "STRONG_BUY"] else ("🟡" if score.signal_type == "WATCHLIST" else "⚪")
        
        reasons = "\n".join([f"• {e}" for e in setup.evidence]) if (setup and setup.evidence) else "• Tidak ada setup teknikal yang valid."

        if not risk:
            return f"""━━━━━━━━━━━━━━━━━━
{icon} {score.signal_type} — {display_ticker}
Setup: {setup.setup_type.value if setup else "NO_SETUP"}
━━━━━━━━━━━━━━━━━━

⚠️ No Valid Risk Plan / Entry Setup
📊 Setup Score: {score.total_score}/100

💡 Rationale:
{reasons}
━━━━━━━━━━━━━━━━━━"""

        alert = f"""━━━━━━━━━━━━━━━━━━
{icon} {score.signal_type} — {display_ticker}
Setup: {setup.setup_type.value}
━━━━━━━━━━━━━━━━━━

📍 Entry Zone: {risk.entry_zone_min:,.0f} – {risk.entry_zone_max:,.0f}
🛑 Stop Loss: {risk.stop_loss:,.0f}
🎯 Target 1: {risk.target_1:,.0f}
🎯 Target 2: {risk.target_2:,.0f}

⚖️ R:R Ratio: 1:{risk.risk_reward_ratio}
📊 Setup Score: {score.total_score}/100

💡 Rationale:
{reasons}

⚠️ Invalidation: Close below {risk.invalidation_level:,.0f}
━━━━━━━━━━━━━━━━━━"""
        return alert

    @staticmethod
    def generate_full_research_report(analysis_data: Dict[str, Any]) -> str:
        """Generates comprehensive markdown equity research report."""
        if analysis_data.get("status") != "SUCCESS":
            return f"❌ Cannot generate report: {analysis_data.get('reason', 'Data unavailable')}"

        #ticker = analysis_data["ticker"]
        #ticker = str(analysis_data["ticker"]).removesuffix(".JK")
        ticker = analysis_data["ticker"]
        display_ticker = ticker.removesuffix(".JK")
        snap: TechnicalSnapshot = analysis_data["snapshot"]
        setup: DetectedSetup = analysis_data["setup"]
        risk: Optional[RiskPlan] = analysis_data.get("risk_plan")
        score: ScoreBreakdown = analysis_data["score_breakdown"]
        mtf_analysis = analysis_data.get("mtf_analysis", {})
        market_regime = analysis_data.get("market_regime", {})
        mtf_raw_score = mtf_analysis.get("alignment_score")
        mtf_raw_display = f"{mtf_raw_score}/100" if mtf_raw_score is not None else "Unavailable"

        risk_section = f"""- **Suggested Entry Zone:** {risk.entry_zone_min:,.2f} – {risk.entry_zone_max:,.2f}
- **Stop Loss:** {risk.stop_loss:,.2f} IDR
- **Target 1:** {risk.target_1:,.2f} IDR
- **Target 2:** {risk.target_2:,.2f} IDR
- **Risk Per Share:** {risk.risk_per_share:,.2f} IDR
- **Risk/Reward Ratio:** 1:{risk.risk_reward_ratio}""" if risk else "- **Risk Plan:** N/A (No valid setup/risk parameters detected)"

        invalidation_str = f"Close below {risk.invalidation_level:,.2f} IDR." if risk else "N/A"

        report = f"""# 📈 DETAILED EQUITY RESEARCH REPORT: {display_ticker}

## 1. Executive Summary
- **Ticker:** {display_ticker}
- **Verdict:** `{score.signal_type}`
- **Setup Score:** {score.total_score}/100
- **Primary Setup:** {setup.setup_type.value if setup else "NO_SETUP"}
- **Data Quality:** {analysis_data.get('data_quality_score', 100)}/100

## 2. Technical Evidence & Alignment
- **Current Price:** {snap.close:,.2f} IDR
- **Trend Alignment:** `{snap.trend_alignment}`
- **EMA 20:** {snap.ema_20:,.2f} | **EMA 50:** {snap.ema_50:,.2f} | **EMA 200:** {snap.ema_200:,.2f}
- **RSI (14):** {snap.rsi_14:.2f}
- **Volume Ratio (RVOL):** {snap.rvol:.2f}x (MA 20: {snap.vol_ma_20:,.0f})
- **Rate of Change (ROC 10):** {snap.roc_10:.2f}%

## 3. Structural Support & Resistance
- **Support Levels:** {', '.join([str(s) for s in snap.support_levels]) if snap.support_levels else 'None'}
- **Resistance Levels:** {', '.join([str(r) for r in snap.resistance_levels]) if snap.resistance_levels else 'None'}

## 4. Risk & Capital Management
{risk_section}

## 5. Scoring Breakdown
- **Trend Alignment:** {score.trend_score}/20
- **Momentum:** {score.momentum_score}/20
- **Volume Confirmation:** {score.volume_score}/15
- **Technical Structure:** {score.structure_score}/20
- **MTF Alignment:** {score.mtf_score}/15 ({mtf_analysis.get('status', 'UNAVAILABLE')}; direction: {mtf_analysis.get('direction', 'UNAVAILABLE')}; raw: {mtf_raw_display})
- **Market Regime:** {score.regime_score}/10 ({market_regime.get('regime', 'UNAVAILABLE')})

## 6. Case & Invalidation
- **Bull Case:** {setup.evidence[0] if (setup and setup.evidence) else 'Aligned momentum and volume.'}
- **Bear Case / Failure Scenario:** Breakdown below key EMA support or market regime deterioration.
- **Invalidation Level:** {invalidation_str}
"""
        return report
