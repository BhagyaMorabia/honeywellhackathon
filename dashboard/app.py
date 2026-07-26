"""SentinelFlow Analyst Dashboard — Main Entry Point.

This dashboard provides a WCAG AA accessible interface for SOC analysts to
investigate anomalies, view explanations, and monitor system metrics.
"""

import streamlit as st

st.set_page_config(
    page_title="SentinelFlow | AI Anomaly Detection",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🛡️ SentinelFlow")
st.markdown("### AI-Powered Behavioral Anomaly Detection")

st.markdown("""
Welcome to the SentinelFlow SOC Analyst Dashboard.

**Core Capabilities:**
- 🚨 **Alert Queue**: Triage high-risk anomalies with SHAP-powered natural language explanations.
- 🔍 **Entity Drill-Down**: Investigate specific users, service accounts, or edge devices.
- 📊 **Metrics Panel**: Monitor model performance (Precision@1%, PR-AUC) and concept drift.
- ⏱️ **Live Replay**: Simulate real-time streaming of access logs.

---
👈 Select a module from the sidebar to begin.
""")

# Load global configuration
import yaml

@st.cache_resource
def load_config():
    with open("config/config.yaml", "r") as f:
        return yaml.safe_load(f)

config = load_config()

st.sidebar.markdown("---")
st.sidebar.info(
    "**System Status**: 🟢 Online\n\n"
    f"**Tabular Model**: {config['models']['tabular']['iforest_n_estimators']} estimators\n\n"
    f"**Sequence Model**: Markov Chain (N-Gram)\n\n"
    f"**Fusion Model**: XGBoost ({config['models']['fusion']['n_estimators']} trees)"
)
