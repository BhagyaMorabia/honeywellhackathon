# SentinelFlow 🛡️

**AI-Powered Behavioral Anomaly Detection for Cybersecurity**

SentinelFlow is a hybrid ML system that detects, classifies, and explains cybersecurity anomalies in user/device/service-account access logs. It combines deterministic rules, statistical anomaly detection, and sequence modeling with a gradient-boosted fusion classifier — designed for real SOC analyst workflows.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Generate synthetic dataset
python -m sentinel.data.generator

# 3. Run the full pipeline (train + evaluate)
python -m sentinel.models.pipeline

# 4. Launch the analyst dashboard
streamlit run dashboard/app.py
```

## Architecture

```
Access Logs → Feature Engine → ┌─ Rule Engine (deterministic)
                                ├─ IForest + ECOD (tabular)
                                └─ Markov Chain (sequence/N-Gram)
                                         │
                                    Fusion XGBoost
                                         │
                                  SHAP Explainability
                                         │
                                  Streamlit Dashboard
```

## Project Structure

```
sentinelflow/
├── sentinel/          # Core package
│   ├── schemas.py     # Pydantic v2 data contracts
│   ├── data/          # Synthetic data generation
│   ├── features/      # Feature engineering + rule engine
│   ├── models/        # ML detectors + fusion classifier
│   ├── explain/       # SHAP + natural language explanations
│   ├── drift/         # ADWIN concept drift detection
│   └── utils/         # Logging, metrics
├── dashboard/         # Streamlit analyst UI
├── tests/             # pytest suite (38 tests)
├── config/            # Hyperparameters (config.yaml)
└── reports/           # Final report + analysis
```

## Key Features

- **Three parallel detectors**: Rule engine, IForest/ECOD, Markov Chain — each catches different attack families
- **7 anomaly types**: Brute force, impossible travel, credential stuffing, lateral movement, device spoofing, low-and-slow exfiltration, insider drift
- **Cold-start handling**: Cohort-baseline blending (weight = n/20)
- **Concept drift**: ADWIN from River library
- **Explainability**: SHAP + rule traces + MITRE ATT&CK mapping + natural language
- **WCAG AA accessible** dashboard with color+text+icon encoding

## License

MIT
