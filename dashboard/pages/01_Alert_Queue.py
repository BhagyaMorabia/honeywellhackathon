"""Alert Queue — Analyst view for triaging high-risk anomalies."""

import os
import sys
import pickle
import pandas as pd
import streamlit as st

# Ensure the sentinel package can be imported from the root directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

st.set_page_config(page_title="Alert Queue | SentinelFlow", page_icon="🚨", layout="wide")

st.title("🚨 Alert Queue")
st.markdown("Review and triage the highest-risk anomalies detected by the SentinelFlow fusion engine.")

@st.cache_resource
def load_models_and_explainer():
    """Load models and initialize SHAP explainer."""
    model_dir = "../models/saved/"
    if not os.path.exists(os.path.join(model_dir, "fusion.pkl")):
        # If running from project root
        model_dir = "models/saved/"
        
    try:
        with open(os.path.join(model_dir, "fusion.pkl"), "rb") as f:
            fusion_clf = pickle.load(f)
            
        from sentinel.explain.shap_explainer import SHAPExplainer
        explainer = SHAPExplainer(fusion_clf)
        return fusion_clf, explainer
    except Exception as e:
        st.warning(f"Could not load models: {e}. Please run `python -m sentinel.models.pipeline` first.")
        return None, None

fusion_clf, explainer = load_models_and_explainer()

# Ensure the pipeline is run before dashboard
if fusion_clf is None:
    st.error("🚨 Models not found. Please run `python -m sentinel.models.pipeline` first to train the Fusion Classifier.")
else:
    st.success("✅ Models loaded successfully. Connect streaming data source to view live alerts.")
