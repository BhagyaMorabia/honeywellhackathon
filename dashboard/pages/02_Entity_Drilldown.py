"""Entity Drilldown — Investigate a single user or device's behavior."""

import os
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="Entity Drill-Down | SentinelFlow", page_icon="🔍", layout="wide")

st.title("🔍 Entity Drill-Down")
st.markdown("Investigate behavioral baselines and access history for specific entities.")

@st.cache_data
def load_profiles():
    path = "../data/synthetic_logs/entity_profiles.csv"
    if not os.path.exists(path):
        path = "data/synthetic_logs/entity_profiles.csv"
    try:
        return pd.read_csv(path)
    except Exception as e:
        st.warning("Entity profiles not found. Generating mock data.")
        return pd.DataFrame({
            "entity_id": ["user-123", "service-acc-45", "edge-device-99"],
            "entity_type": ["user", "service_account", "edge_device"],
            "avg_daily_events": [12.5, 45.0, 120.0],
            "typical_hour_mean": [10.5, 12.0, 12.0],
            "auth_method": ["password", "token", "certificate"],
        })

profiles_df = load_profiles()

entity_id = st.selectbox("Select Entity ID to investigate", profiles_df["entity_id"].tolist())

if entity_id:
    entity = profiles_df[profiles_df["entity_id"] == entity_id].iloc[0]
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Entity Type", str(entity.get("entity_type", "unknown")).upper())
    col2.metric("Primary Auth Method", str(entity.get("auth_method", "unknown")))
    col3.metric("Avg Daily Events", f"{entity.get('avg_daily_events', 0):.1f}")
    
    st.divider()
    
    st.markdown("### Behavioral Baseline (Personal Profile)")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Typical Login Hours (Von Mises Distribution)**")
        # Generate mock distribution data for visualization based on entity's mean
        import numpy as np
        hour_mean = float(entity.get("typical_hour_mean", 12.0))
        # Simulated distribution
        x = np.linspace(0, 24, 100)
        y = np.exp(-0.5 * ((x - hour_mean) / 2.0)**2)
        fig = px.line(x=x, y=y, labels={"x": "Hour of Day", "y": "Probability Density"})
        fig.update_layout(height=300, margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig, use_container_width=True)
        
    with col2:
        st.markdown("**Resource Access Patterns (Zipf-weighted)**")
        # Mock resource access graph
        resources = ["intranet.corp", "mail.corp", "jira.corp", "db://prod", "shared/finance"]
        counts = [150, 120, 80, 20, 5]
        fig = px.bar(x=resources, y=counts, labels={"x": "Resource", "y": "Access Count"})
        fig.update_layout(height=300, margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig, use_container_width=True)
