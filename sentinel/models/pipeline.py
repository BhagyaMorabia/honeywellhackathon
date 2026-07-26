"""End-to-End Pipeline — Data ingestion, feature extraction, model training, and evaluation.

This module ties together the entire SentinelFlow architecture.
It ensures that the ML models are trained correctly (e.g., Tabular and Sequence
models train ONLY on normal data from the train split, while Fusion trains on
both normal and injected attacks). It also performs a strict temporal split.
"""

from __future__ import annotations

import json
import os
import pickle
from datetime import datetime

import numpy as np
import pandas as pd

from sentinel.features.engineering import FeatureEngine
from sentinel.features.rules import RuleEngine
from sentinel.models.fusion import FusionClassifier
from sentinel.models.sequence import SequenceAnomalyDetector
from sentinel.models.tabular import TabularAnomalyDetector
from sentinel.schemas import LABEL_TO_INT
from sentinel.utils.logger import get_logger
from sentinel.utils.metrics import compute_all_metrics

log = get_logger(__name__)


class Pipeline:
    """Orchestrates training and evaluation of the SentinelFlow system."""

    def __init__(self, config_path: str = "config/config.yaml"):
        """Initialize the pipeline."""
        import yaml
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)

        self.feature_engine = FeatureEngine()
        self.rule_engine = RuleEngine(
            brute_force_window_min=self.config["rules"]["brute_force"]["window_minutes"],
            brute_force_min_failures=self.config["rules"]["brute_force"]["min_failures"],
            impossible_travel_max_kmh=self.config["rules"]["impossible_travel"]["max_speed_kmh"],
            credential_stuffing_window_min=self.config["rules"]["credential_stuffing"]["window_minutes"],
            credential_stuffing_min_targets=self.config["rules"]["credential_stuffing"]["min_targets"],
            credential_stuffing_min_fail_rate=self.config["rules"]["credential_stuffing"]["min_failure_rate"],
        )

        self.tabular = TabularAnomalyDetector(
            contamination=self.config["models"]["tabular"]["contamination"],
            n_estimators=self.config["models"]["tabular"]["iforest_n_estimators"],
            max_features=self.config["models"]["tabular"]["iforest_max_features"],
        )

        self.sequence = SequenceAnomalyDetector(
            vocab_size=self.config["models"]["sequence"]["vocab_size"],
        )

        self.fusion = FusionClassifier(
            n_estimators=self.config["models"]["fusion"]["n_estimators"],
            max_depth=self.config["models"]["fusion"]["max_depth"],
            learning_rate=self.config["models"]["fusion"]["learning_rate"],
        )

        # To build vocabulary for sequence model
        from sentinel.data.profiles import COMMAND_VOCABULARY
        self.cmd_to_id = {cmd: i + 1 for i, cmd in enumerate(COMMAND_VOCABULARY)}
        self.cmd_to_id["PAD"] = self.config["models"]["sequence"]["pad_token_id"]

    def _extract_features(self, df: pd.DataFrame) -> tuple[pd.DataFrame, list[list[dict]]]:
        """Extract rule hits and engineered features for all events."""
        # Engineered features
        features_df = self.feature_engine.compute_features(df)
        
        # Rule hits
        rule_hits_list = []
        rule_flags_list = []
        for row in df.itertuples(index=False):
            hits = self.rule_engine.check_all_rules(row)
            rule_hits_list.append(hits)
            flags = self.rule_engine.get_rule_flags(hits)
            rule_flags_list.append(flags)
            
        rule_df = pd.DataFrame(rule_flags_list)
        
        # Combine
        combined_df = pd.concat([features_df, rule_df], axis=1)
        return combined_df, rule_hits_list

    def _prepare_sequence_data(self, df: pd.DataFrame) -> list[list[int]]:
        """Extract and encode command sequences."""
        sessions = []
        for seq in df["command_sequence"].values:
            if isinstance(seq, str):
                try:
                    seq = eval(seq)
                except:
                    seq = []
            if not isinstance(seq, list):
                seq = []
            encoded = [self.cmd_to_id.get(c, 0) for c in seq]
            sessions.append(encoded)
        return sessions

    def run(self):
        """Run the full pipeline: Load, Split, Train, Evaluate, Save."""
        log.info("pipeline_started")

        # 1. Load Data
        access_logs_path = self.config["paths"]["access_logs"]
        hidden_labels_path = self.config["paths"]["hidden_labels"]

        log.info("loading_data", logs=access_logs_path, labels=hidden_labels_path)
        df_logs = pd.read_csv(access_logs_path, parse_dates=["timestamp"])
        df_labels = pd.read_csv(hidden_labels_path)

        # Merge labels for training
        df = pd.merge(df_logs, df_labels, on="event_id")

        # 2. Temporal Split (Train/Test)
        train_days = self.config["data"]["train_days"]
        min_ts = df["timestamp"].min()
        split_ts = min_ts + pd.Timedelta(days=train_days)

        train_mask = df["timestamp"] <= split_ts
        test_mask = df["timestamp"] > split_ts

        df_train = df[train_mask].reset_index(drop=True)
        df_test = df[test_mask].reset_index(drop=True)

        log.info("temporal_split", train_size=len(df_train), test_size=len(df_test))

        # 3. Extract Features (Train)
        log.info("extracting_features_train")
        X_train_base, _ = self._extract_features(df_train)
        
        # Prepare labels
        y_train_str = df_train["label"].values
        y_train_int = np.array([LABEL_TO_INT.get(l, 0) for l in y_train_str])
        y_train_binary = (y_train_int > 0).astype(int)

        # 4. Train Sub-models (Tabular & Sequence)
        # They only train on NORMAL data to learn baselines
        normal_mask_train = (y_train_binary == 0)
        
        # Tabular needs continuous float features only (explicit whitelist to avoid sparse bool/float masks)
        numeric_cols = [c for c in X_train_base.columns if "raw" in c or "zscore" in c or "freq" in c or "entropy" in c or "rate" in c or "index" in c or "velocity" in c]
        log.info("fitting_tabular", features=numeric_cols)
        self.tabular.fit(X_train_base[normal_mask_train][numeric_cols])
        
        # Sequence model
        sessions_train_normal = self._prepare_sequence_data(df_train[normal_mask_train])
        self.sequence.fit(sessions_train_normal)

        # 5. Get Sub-model Scores for Fusion (Train)
        log.info("scoring_sub_models_train")
        tabular_scores_train = self.tabular.score(X_train_base[numeric_cols])
        sessions_train_all = self._prepare_sequence_data(df_train)
        sequence_scores_train = self.sequence.score_batch(sessions_train_all)

        X_train_fusion = X_train_base.copy()
        X_train_fusion["tabular_anomaly_score"] = tabular_scores_train
        X_train_fusion["sequence_anomaly_score"] = sequence_scores_train

        # 6. Train Fusion Classifier
        self.fusion.fit(X_train_fusion, y_train_int)

        # 7. Evaluate on Test Set
        log.info("extracting_features_test")
        X_test_base, _ = self._extract_features(df_test)
        
        y_test_str = df_test["label"].values
        y_test_int = np.array([LABEL_TO_INT.get(l, 0) for l in y_test_str])
        y_test_binary = (y_test_int > 0).astype(int)

        log.info("scoring_sub_models_test")
        tabular_scores_test = self.tabular.score(X_test_base[numeric_cols])
        sessions_test_all = self._prepare_sequence_data(df_test)
        sequence_scores_test = self.sequence.score_batch(sessions_test_all)

        X_test_fusion = X_test_base.copy()
        X_test_fusion["tabular_anomaly_score"] = tabular_scores_test
        X_test_fusion["sequence_anomaly_score"] = sequence_scores_test

        log.info("predicting_test")
        risk_scores, pred_labels, _ = self.fusion.predict_full(X_test_fusion)
        pred_ints = np.array([LABEL_TO_INT.get(l, 0) for l in pred_labels])

        # 8. Compute Metrics
        metrics = compute_all_metrics(y_test_binary, y_test_int, pred_ints, risk_scores)
        
        # Save metrics report
        os.makedirs("reports", exist_ok=True)
        with open("reports/evaluation_metrics.json", "w") as f:
            json.dump(metrics, f, indent=2)
        log.info("metrics_saved", path="reports/evaluation_metrics.json")

        # 9. Save Models
        model_dir = self.config["paths"]["model_dir"]
        os.makedirs(model_dir, exist_ok=True)
        
        with open(os.path.join(model_dir, "tabular.pkl"), "wb") as f:
            pickle.dump(self.tabular, f)
        
        with open(os.path.join(model_dir, "sequence_model.pkl"), "wb") as f:
            pickle.dump(self.sequence, f)
        
        with open(os.path.join(model_dir, "fusion.pkl"), "wb") as f:
            pickle.dump(self.fusion, f)
            
        with open(os.path.join(model_dir, "feature_engine.pkl"), "wb") as f:
            pickle.dump(self.feature_engine, f)

        log.info("pipeline_completed")


if __name__ == "__main__":
    from sentinel.utils.logger import setup_logging
    setup_logging("INFO")
    
    # Change working directory to project root if needed
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    pipeline = Pipeline(config_path="config/config.yaml")
    pipeline.run()
