"""
AI Report Generator.

Uses the Anthropic Claude API to generate natural language analysis
of strategy performance, risk state, and market conditions.

This module is OPTIONAL and MODULAR:
  - If AI is disabled, all methods return a placeholder string.
  - The prompt/template architecture allows swapping LLMs later.
  - No trading decisions are made here. Analysis only.

Prompts are in PROMPTS dict at the bottom — easy to tune.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class AIReportGenerator:
    """
    Generates AI-assisted reports about strategy performance.

    Requires:
      AI_REPORTS_ENABLED=true
      AI_API_KEY=sk-ant-...
      AI_MODEL=claude-3-5-sonnet-20241022 (or any Claude model)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-5-sonnet-20241022",
        enabled: bool = False,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._enabled = enabled
        self._client = None

        if enabled and api_key:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=api_key)
                logger.info("AIReportGenerator: Anthropic client initialized. model=%s", model)
            except ImportError:
                logger.warning(
                    "AIReportGenerator: 'anthropic' package not installed. "
                    "Run: pip install anthropic"
                )
                self._enabled = False
        elif enabled:
            logger.warning("AIReportGenerator: enabled=True but no API key provided.")

    @classmethod
    def from_settings(cls) -> "AIReportGenerator":
        from app.config.settings import settings
        return cls(
            api_key=settings.ai.api_key.get_secret_value() if settings.ai.api_key else None,
            model=settings.ai.model,
            enabled=settings.ai.enabled,
        )

    def generate_daily_report(self, context: Dict[str, Any]) -> str:
        """Generate a daily strategy performance report."""
        if not self._is_ready():
            return self._placeholder("daily_report")

        prompt = PROMPTS["daily_report"].format(
            date=datetime.utcnow().strftime("%Y-%m-%d"),
            context=json.dumps(context, indent=2, default=str),
        )
        return self._call_api(prompt)

    def generate_strategy_diagnosis(
        self, strategy_name: str, context: Dict[str, Any]
    ) -> str:
        """Deep-dive diagnosis of a single strategy."""
        if not self._is_ready():
            return self._placeholder("strategy_diagnosis")

        prompt = PROMPTS["strategy_diagnosis"].format(
            strategy_name=strategy_name,
            context=json.dumps(context, indent=2, default=str),
        )
        return self._call_api(prompt)

    def generate_regime_analysis(self, context: Dict[str, Any]) -> str:
        """Analyze current market regime and impact on active strategies."""
        if not self._is_ready():
            return self._placeholder("regime_analysis")

        prompt = PROMPTS["regime_analysis"].format(
            context=json.dumps(context, indent=2, default=str),
        )
        return self._call_api(prompt)

    def generate_risk_narrative(self, context: Dict[str, Any]) -> str:
        """Explain the current risk state in plain language."""
        if not self._is_ready():
            return self._placeholder("risk_narrative")

        prompt = PROMPTS["risk_narrative"].format(
            context=json.dumps(context, indent=2, default=str),
        )
        return self._call_api(prompt)

    def _call_api(self, prompt: str) -> str:
        """Make a single API call and return the text response."""
        try:
            message = self._client.messages.create(
                model=self._model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text
        except Exception as exc:
            logger.error("AI API call failed: %s", exc)
            return f"[AI report unavailable: {exc}]"

    def _is_ready(self) -> bool:
        return self._enabled and self._client is not None

    @staticmethod
    def _placeholder(report_type: str) -> str:
        return (
            f"[AI reports are disabled. Set AI_REPORTS_ENABLED=true and "
            f"AI_API_KEY to enable. Report type: {report_type}]"
        )


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

PROMPTS = {
    "daily_report": """
You are a quantitative trading system analyst. You are analyzing a paper trading
platform (NO real money, NO real orders). Your job is to provide honest, objective
analysis of strategy performance.

Date: {date}

Platform context (JSON):
{context}

Please generate a structured daily report covering:
1. **Performance Summary** — equity, PnL, open positions
2. **Strategy Health** — which strategies are performing vs backtest expectations
3. **Risk State** — current drawdown levels, any warnings
4. **Market Regime** — observed regime per asset
5. **Anomalies** — anything suspicious or unexpected
6. **Recommendations** — concrete next steps for the operator (research, parameter review, etc.)

Be specific and honest. If data is insufficient, say so. Do not fabricate numbers.
Keep the report under 600 words.
""",

    "strategy_diagnosis": """
You are a quantitative strategy analyst. The user is running a paper trading system
with no real money at stake. You are diagnosing one specific strategy.

Strategy: {strategy_name}

Context data (JSON):
{context}

Please provide:
1. **Current Health Assessment** — is this strategy behaving as expected?
2. **Live vs Backtest Comparison** — how does live performance compare to backtest metrics?
3. **Likely Root Causes** — if degraded, what are the most probable explanations?
4. **Regime Fit** — is this strategy suited to the current market regime?
5. **Red Flags** — any signs of curve-fitting, parameter fragility, or unusual behavior?
6. **Suggested Actions** — re-optimize, pause, or continue monitoring?

Be direct. Prefer concrete analysis over vague commentary.
""",

    "regime_analysis": """
You are analyzing market regime data for a paper trading system covering BTCUSDT,
XAUUSD, and EURUSD. No real money is involved.

Context data (JSON):
{context}

For each asset, analyze:
1. Current detected regime (trending, ranging, high-vol, etc.)
2. Which strategy families are most suitable for this regime
3. Which active strategies may be mismatched to the current regime
4. Key regime transition signals to watch

Keep analysis factual and data-driven. Flag uncertainty where it exists.
""",

    "risk_narrative": """
You are explaining the current risk state of a paper trading system to its operator.
This is a paper-only system — no real orders are executed.

Context data (JSON):
{context}

Explain in plain language:
1. What the current risk levels mean
2. What triggered any warnings or stops
3. What the operator should do next (if anything)
4. When it might be safe to re-enable trading signals

Be clear and direct. Avoid jargon where possible.
""",
}
