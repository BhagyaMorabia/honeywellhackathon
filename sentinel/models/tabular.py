"""Tabular anomaly detection — IForest + ECOD ensemble from PyOD.

Both are ADBench top-tier performers:
- IForest: isolates anomalies via random partitioning, excellent for global outliers
- ECOD: parameter-free, uses empirical CDF tail probabilities per dimension
  ECDF: F̂(x) = (1/n) Σ I(Xi ≤ x) — hyper-fast, no hyperparameters

Average of both scores gives more robust detection than either alone.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from pyod.models.ecod import ECOD
from pyod.models.iforest import IForest

from sentinel.utils.logger import get_logger

log = get_logger(__name__)


class TabularAnomalyDetector:
    """IForest + ECOD ensemble anomaly detector.

    Trains on normal-only data. At inference, scores every event.
    The averaged score is fed as a feature to the fusion classifier.

    Attributes:
        iforest: Isolation Forest model from PyOD.
        ecod: ECOD model from PyOD.
        is_fitted: Whether the models have been trained.
    """

    def __init__(
        self,
        contamination: float = 0.02,
        n_estimators: int = 150,
        max_features: float = 0.8,
        random_state: int = 42,
    ):
        """Initialize the tabular detector.

        Args:
            contamination: Expected proportion of anomalies in training data.
            n_estimators: Number of trees in Isolation Forest.
            max_features: Fraction of features to sample per tree.
            random_state: Random seed.
        """
        self.iforest = IForest(
            contamination=contamination,
            n_estimators=n_estimators,
            max_features=max_features,
            random_state=random_state,
        )
        self.ecod = ECOD(contamination=contamination)
        self.is_fitted = False
        log.info("tabular_detector_initialized", contamination=contamination,
                 n_estimators=n_estimators)

    def fit(self, X_train: pd.DataFrame | np.ndarray) -> "TabularAnomalyDetector":
        """Train both models on normal-only data.

        Args:
            X_train: Feature matrix (normal events only for pure unsupervised training).

        Returns:
            self (for method chaining).
        """
        log.info("fitting_tabular_models", n_samples=len(X_train), n_features=X_train.shape[1])

        # Handle NaN/Inf
        if isinstance(X_train, pd.DataFrame):
            X_clean = X_train.fillna(0).replace([np.inf, -np.inf], 0).values
        else:
            X_clean = np.nan_to_num(X_train, nan=0.0, posinf=0.0, neginf=0.0)

        self.iforest.fit(X_clean)
        self.ecod.fit(X_clean)
        self.is_fitted = True

        log.info("tabular_models_fitted")
        return self

    def score(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        """Compute anomaly scores for each event.

        Score is the average of IForest and ECOD decision functions.
        Higher score = more anomalous.

        Args:
            X: Feature matrix.

        Returns:
            Array of anomaly scores, one per event.
        """
        if not self.is_fitted:
            raise RuntimeError("TabularAnomalyDetector must be fitted before scoring")

        if isinstance(X, pd.DataFrame):
            X_clean = X.fillna(0).replace([np.inf, -np.inf], 0).values
        else:
            X_clean = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

        iforest_scores = self.iforest.decision_function(X_clean)
        ecod_scores = self.ecod.decision_function(X_clean)

        # Average both scores
        combined = 0.5 * iforest_scores + 0.5 * ecod_scores
        return combined

    def predict(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        """Binary anomaly prediction (0 = normal, 1 = anomaly).

        Args:
            X: Feature matrix.

        Returns:
            Binary array.
        """
        if not self.is_fitted:
            raise RuntimeError("TabularAnomalyDetector must be fitted before predicting")

        if isinstance(X, pd.DataFrame):
            X_clean = X.fillna(0).replace([np.inf, -np.inf], 0).values
        else:
            X_clean = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

        iforest_pred = self.iforest.predict(X_clean)
        ecod_pred = self.ecod.predict(X_clean)

        # Anomaly if either detector flags it
        return np.maximum(iforest_pred, ecod_pred)
