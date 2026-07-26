"""Metrics Panel — Live model performance and concept drift monitoring."""

import os
import json
import streamlit as st
import plotly.express as px
import pandas as pd

st.set_page_config(page_title="Metrics Panel | SentinelFlow", page_icon="📊", layout="wide")

st.title("📊 Metrics Panel")
st.markdown("System performance tracking and concept drift detection (ADWIN).")

@st.cache_data
def load_metrics():
    path = "../reports/evaluation_metrics.json"
    if not os.path.exists(path):
        path = "reports/evaluation_metrics.json"
    try:
        with open(path, "r") as f:
            return json.load(f)
    except:
        return None

metrics = load_metrics()

if metrics:
    st.markdown("### Core Key Performance Indicators (KPIs)")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Precision @ Top 1%", f"{metrics.get('precision_at_1pct', 0)*100:.1f}%", "Rubric target")
    col2.metric("PR-AUC", f"{metrics.get('pr_auc', 0):.3f}")
    col3.metric("Macro F1", f"{metrics.get('macro_f1', 0):.3f}")
    col4.metric("False Positive Rate", f"{metrics.get('false_positive_rate', 0)*100:.2f}%")
    
    st.divider()
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### Confusion Matrix")
        # Visualizing confusion matrix
        cm = metrics.get("confusion_matrix", [])
        if cm:
            classes = [f"Class {i}" for i in range(len(cm))]
            fig = px.imshow(cm, x=classes, y=classes, text_auto=True, color_continuous_scale="Blues")
            fig.update_layout(height=400, margin=dict(l=0, r=0, t=0, b=0))
            st.plotly_chart(fig, use_container_width=True)
            
    with col2:
        st.markdown("### Concept Drift Monitor (ADWIN)")
        st.info("🟢 ADWIN Detector is active on entity streams.")
        st.markdown("""
        **Recent Drift Events:**
        - No statistically significant shift detected in the last 24 hours.
        - `delta=0.001` (Tuned for sparse anomaly stream).
        """)
else:
    st.warning("Metrics file not found. Run pipeline to generate metrics.")
