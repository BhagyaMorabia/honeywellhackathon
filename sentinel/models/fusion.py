"""Fusion classifier — XGBoost multiclass that combines all detector signals.

Inputs:
  - Rule engine flags (one-hot, 4 features)
  - Tabular anomaly score (1 feature)
  - Sequence anomaly score (1 feature)
  - All 27+ engineered features

Outputs:
  - Risk score (0-100): 100 × (1 - P(normal))
  - Attack type classification (8 classes)

Handles class imbalance via sample_weight (computed from inverse class frequencies).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from xgboost import XGBClassifier

from sentinel.schemas import INT_TO_LABEL, LABEL_TO_INT
from sentinel.utils.logger import get_logger

log = get_logger(__name__)

NORMAL_IDX = LABEL_TO_INT["normal"]


class FusionClassifier:
    """XGBoost multiclass fusion classifier.

    Combines all detector outputs and engineered features into:
    1. A calibrated risk score (0-100)
    2. An attack-type classification (8 classes)

    Attributes:
        clf: XGBClassifier instance.
        feature_names: List of feature column names.
        is_fitted: Whether the model has been trained.
    """

    def __init__(
        self,
        n_estimators: int = 300,
        max_depth: int = 5,
        learning_rate: float = 0.05,
        random_state: int = 42,
    ):
        """Initialize the fusion classifier.

        Args:
            n_estimators: Number of boosting rounds.
            max_depth: Maximum tree depth.
            learning_rate: XGBoost learning rate.
            random_state: Random seed.
        """
        self.gate = XGBClassifier(
            objective="binary:logistic",
            n_estimators=n_estimators,
            max_depth=max_depth,
            learning_rate=learning_rate,
            eval_metric="logloss",
            tree_method="hist",
            random_state=random_state,
            reg_alpha=0.1,  # L1 regularization
            reg_lambda=1.0, # L2 regularization
        )
        self.attrib = XGBClassifier(
            objective="multi:softprob",
            num_class=len(LABEL_TO_INT) - 1,
            n_estimators=n_estimators,
            max_depth=max_depth,
            learning_rate=learning_rate,
            eval_metric="mlogloss",
            tree_method="hist",
            random_state=random_state,
            reg_alpha=0.1,
            reg_lambda=1.0,
        )
        self.feature_names: list[str] = []
        self.is_fitted = False
        log.info("fusion_classifier_initialized", n_estimators=n_estimators, max_depth=max_depth)

    def fit(
        self,
        X_train: pd.DataFrame | np.ndarray,
        y_train: np.ndarray,
        feature_names: list[str] | None = None,
    ) -> "FusionClassifier":
        """Train the fusion classifier.

        Automatically computes class weights for imbalance handling.

        Args:
            X_train: Fusion feature matrix (detectors + engineered features).
            y_train: Integer labels (from LABEL_TO_INT).
            feature_names: Optional list of feature column names.

        Returns:
            self (for method chaining).
        """
        if isinstance(X_train, pd.DataFrame):
            self.feature_names = list(X_train.columns)
            X_clean = X_train.fillna(0).replace([np.inf, -np.inf], 0).values
        else:
            self.feature_names = feature_names or [f"f{i}" for i in range(X_train.shape[1])]
            X_clean = np.nan_to_num(X_train, nan=0.0, posinf=0.0, neginf=0.0)

        # 1. Train Binary Gate (Normal vs Anomaly)
        y_gate = (y_train > 0).astype(int)
        unique_gate, counts_gate = np.unique(y_gate, return_counts=True)
        weight_map_gate = {cls: len(y_gate) / (len(unique_gate) * cnt) for cls, cnt in zip(unique_gate, counts_gate)}
        sample_weights_gate = np.array([weight_map_gate.get(y, 1.0) for y in y_gate])
        
        log.info("fitting_binary_gate", n_samples=len(X_clean), n_features=X_clean.shape[1])
        self.gate.fit(X_clean, y_gate, sample_weight=sample_weights_gate)
        
        # 2. Train Attribution Engine (Only on Anomalies)
        anomaly_mask = (y_train > 0)
        X_attrib = X_clean[anomaly_mask]
        
        # 0-Indexing fix (1-7 becomes 0-6)
        y_attrib = y_train[anomaly_mask] - 1
        
        unique_attrib, counts_attrib = np.unique(y_attrib, return_counts=True)
        weight_map_attrib = {cls: len(y_attrib) / (len(unique_attrib) * cnt) for cls, cnt in zip(unique_attrib, counts_attrib)}
        
        # Focal scaling: boost hardest classes (device_spoofing=4, insider_drift=6)
        if 4 in weight_map_attrib: weight_map_attrib[4] *= 2.0
        if 6 in weight_map_attrib: weight_map_attrib[6] *= 2.0
            
        sample_weights_attrib = np.array([weight_map_attrib.get(y, 1.0) for y in y_attrib])
        
        log.info("fitting_attribution_engine", n_samples=len(X_attrib))
        self.attrib.fit(X_attrib, y_attrib, sample_weight=sample_weights_attrib)
        
        self.is_fitted = True

        log.info("fusion_classifier_fitted")
        return self

    def predict_risk_score(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        """Compute risk scores (0-100) for each event.

        Risk = 100 × (1 - P(normal)). Higher = more likely anomalous.

        Args:
            X: Fusion feature matrix.

        Returns:
            Array of risk scores in [0, 100].
        """
        if not self.is_fitted:
            raise RuntimeError("FusionClassifier must be fitted before scoring")

        if isinstance(X, pd.DataFrame):
            X_clean = X.fillna(0).replace([np.inf, -np.inf], 0).values
        else:
            X_clean = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

        gate_probas = self.gate.predict_proba(X_clean)
        risk = 100.0 * gate_probas[:, 1]
        return np.clip(risk, 0, 100)

    def predict_attack_type(self, X: pd.DataFrame | np.ndarray) -> list[str]:
        """Predict attack type labels for each event.

        Args:
            X: Fusion feature matrix.

        Returns:
            List of attack type labels (strings).
        """
        if not self.is_fitted:
            raise RuntimeError(
                "FusionClassifier must be fitted before predicting"
            )

        _, attack_types, _ = self.predict_full(X)
        return attack_types

    def predict_full(
        self, X: pd.DataFrame | np.ndarray
    ) -> tuple[np.ndarray, list[str], np.ndarray]:
        """Full prediction: risk scores + attack types + probabilities.

        Args:
            X: Fusion feature matrix.

        Returns:
            Tuple of (risk_scores, attack_type_labels, probability_matrix).
        """
        if isinstance(X, pd.DataFrame):
            X_clean = X.fillna(0).replace([np.inf, -np.inf], 0).values
        else:
            X_clean = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

        # 1. Binary Gate probabilities: [P(Normal), P(Anomaly)]
        gate_probas = self.gate.predict_proba(X_clean)
        p_anomaly = gate_probas[:, 1]
        risk_scores = np.clip(100.0 * p_anomaly, 0, 100)

        # 2. Attribution Engine probabilities: P(Class_k | Anomaly) for k in [1..7]
        attrib_probas = self.attrib.predict_proba(X_clean)

        # 3. Synthesize full joint probability matrix P(Class_k)
        # Class 0: Normal
        # Classes 1..7: P(Anomaly) * P(Class_k | Anomaly)
        synthesized_probas = np.zeros((len(X_clean), len(LABEL_TO_INT)))
        synthesized_probas[:, 0] = gate_probas[:, 0]

        for i in range(len(LABEL_TO_INT) - 1):
            synthesized_probas[:, i + 1] = p_anomaly * attrib_probas[:, i]

        # 4. Argmax over joint probabilities (no hard gate suppression)
        pred_ints = np.argmax(synthesized_probas, axis=1)
        attack_types = [INT_TO_LABEL.get(int(p), "normal") for p in pred_ints]

        return risk_scores, attack_types, synthesized_probas
