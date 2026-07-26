# SentinelFlow - Hackathon Report

## Executive Summary
SentinelFlow is a hybrid AI/ML behavioral anomaly detection system designed specifically for SOC analysts. It moves beyond "black-box" alerting by combining deterministic rule engines, statistical anomaly detection (IForest+ECOD), and sequence modeling (GRU) into a powerful XGBoost fusion classifier.

## Key Design Decisions & Rubric Alignment

1. **Parallel Detectors over Sequential Pipeline**
   - **Why:** Increases system resilience. If one model fails to catch a subtle anomaly, the others can.
   - **Impact:** Captures high-volume noise (Brute Force) at the edge, while preserving compute for subtle threats (Low-and-Slow Exfiltration).

2. **Concept Drift Handling**
   - **How:** Integrated River's ADWIN algorithm monitoring anomaly streams with a tightly tuned `delta=0.001`.
   - **Impact:** Automatically detects when the baseline data distribution has shifted significantly, directly addressing the rubric's requirement for drift management.

3. **Cold-Start Resolution**
   - **How:** Smooth cohort blending (`weight = n/20`). We use EWMA profiles where new entities lean heavily on their peer group baseline, smoothly transitioning to a personal baseline as they mature.
   - **Impact:** No silent failures on day 1 for new employees or newly provisioned edge devices.

4. **Explainable AI (XAI)**
   - **How:** Integrated SHAP TreeExplainer paired with rule-engine traces. The output is a natural language narration detailing *why* the score is high.
   - **Impact:** Reduces SOC analyst fatigue by immediately providing actionable context alongside MITRE ATT&CK technique mapping.

5. **Data Generation & Noise Injection**
   - **How:** Built a synthetic data generator using Von Mises distributions for time and Zipf weighting for resource access. Intentionally injected 2% auth-failure noise into *normal* data.
   - **Impact:** Prevents the ML models from learning trivial separability rules, making the system robust against edge-case interrogation.

## Results
- The system computes **Precision @ Top 1%**, **PR-AUC**, and **F1** metrics automatically via the end-to-end `pipeline.py`.
- The dashboard is modular, scalable, and built entirely in Streamlit for an interactive analyst experience.
