"""AI Report page."""
from __future__ import annotations

import streamlit as st

from app.ai_reports.generator import AIReportGenerator
from app.config.settings import settings


def render():
    st.title("🤖 AI Report")
    st.caption("AI-assisted analysis of strategy performance and market conditions.")

    if not settings.ai.enabled:
        st.warning(
            "AI reports are currently disabled. "
            "Set `AI_REPORTS_ENABLED=true` and `AI_API_KEY` in your `.env` file to enable.",
            icon="⚠️",
        )

    report_type = st.selectbox(
        "Report Type",
        ["Daily Performance Report", "Strategy Diagnosis", "Regime Analysis", "Risk Narrative"],
    )

    st.markdown("---")

    # Context input — in production this would come from the live engine state
    st.markdown("#### 📋 Context Data")
    st.caption(
        "In production, this is populated automatically from the live engine. "
        "For now, you can paste JSON context manually or leave empty for a generic report."
    )

    context_input = st.text_area(
        "Context JSON (optional)",
        height=150,
        placeholder='{"equity": 10500, "open_trades": 2, "win_rate": 0.55, ...}',
    )

    if st.button("🤖 Generate Report", type="primary"):
        if not settings.ai.enabled:
            st.error("AI is disabled. Enable it in settings first.")
            return

        import json
        context = {}
        if context_input.strip():
            try:
                context = json.loads(context_input)
            except json.JSONDecodeError:
                st.error("Invalid JSON in context field.")
                return

        with st.spinner("Generating AI report..."):
            generator = AIReportGenerator.from_settings()

            if report_type == "Daily Performance Report":
                report = generator.generate_daily_report(context)
            elif report_type == "Strategy Diagnosis":
                strategy_name = st.session_state.get("diag_strategy", "SMA_CROSS")
                report = generator.generate_strategy_diagnosis(strategy_name, context)
            elif report_type == "Regime Analysis":
                report = generator.generate_regime_analysis(context)
            else:
                report = generator.generate_risk_narrative(context)

        st.markdown("---")
        st.markdown("#### 📄 Report Output")
        st.markdown(
            f"""
            <div style="background:#111827;border:1px solid #1f2d47;border-radius:8px;
                        padding:20px;font-family:'Space Grotesk',sans-serif;
                        line-height:1.7;color:#e0e4f0;">
            {report.replace(chr(10), '<br>')}
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.download_button(
            "📥 Download Report",
            data=report,
            file_name=f"alpha_report_{report_type.lower().replace(' ', '_')}.txt",
            mime="text/plain",
        )
