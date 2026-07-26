"""Evaluation metrics — the specific metrics the rubric rewards.

Key metrics:
  1. precision_at_k: THE metric (judges care about top-1% alert budget)
  2. pr_auc: Right metric for imbalanced data (NOT ROC-AUC)
  3. per_class_f1: Shows each attack type is detected
  4. confusion_matrix: Full breakdown
"""

from __future__ import annotations

import numpy as np
from sklearn.metrics import (
    average_precision_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
)

from sentinel.schemas import INT_TO_LABEL, LABEL_TO_INT
from sentinel.utils.logger import get_logger

log = get_logger(__name__)


def precision_at_k(y_true: np.ndarray, risk_scores: np.ndarray, k_fraction: float = 0.01) -> float:
    """Compute Precision@top-K% — the LEAD metric for this hackathon.

    "If the analyst only looks at the top 1% of alerts by risk score,
    what fraction of those are true positives?"

    Args:
        y_true: Binary labels (0 = normal, 1 = anomaly).
        risk_scores: Risk scores (higher = more anomalous).
        k_fraction: Fraction of events to consider (0.01 = top 1%).

    Returns:
        Precision at the top k_fraction of events.
    """
    n = len(y_true)
    k = max(1, int(n * k_fraction))

    # Sort by risk score descending
    sorted_indices = np.argsort(-risk_scores)[:k]
    top_k_true = y_true[sorted_indices]

    precision = np.sum(top_k_true) / k
    log.info("precision_at_k", k=k, k_fraction=k_fraction, precision=f"{precision:.4f}")
    return float(precision)


def compute_pr_auc(y_true: np.ndarray, risk_scores: np.ndarray) -> float:
    """Compute PR-AUC (Precision-Recall Area Under Curve).

    The right metric for imbalanced data. NOT ROC-AUC.

    Args:
        y_true: Binary labels (0 = normal, 1 = anomaly).
        risk_scores: Risk scores (higher = more anomalous).

    Returns:
        PR-AUC score.
    """
    pr_auc = average_precision_score(y_true, risk_scores)
    log.info("pr_auc", value=f"{pr_auc:.4f}")
    return float(pr_auc)


def compute_per_class_metrics(
    y_true: np.ndarray, y_pred: np.ndarray
) -> dict:
    """Compute per-class F1, precision, recall.

    Args:
        y_true: Integer labels.
        y_pred: Predicted integer labels.

    Returns:
        Dict with per-class and macro metrics.
    """
    # Map integer labels to string names
    target_names = [INT_TO_LABEL.get(i, f"class_{i}") for i in sorted(set(y_true) | set(y_pred))]

    report = classification_report(
        y_true, y_pred, target_names=target_names, output_dict=True, zero_division=0
    )

    macro_f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)
    log.info("macro_f1", value=f"{macro_f1:.4f}")

    return {
        "classification_report": report,
        "macro_f1": float(macro_f1),
        "confusion_matrix": confusion_matrix(y_true, y_pred).tolist(),
    }


def compute_all_metrics(
    y_true_binary: np.ndarray,
    y_true_multiclass: np.ndarray,
    y_pred_multiclass: np.ndarray,
    risk_scores: np.ndarray,
) -> dict:
    """Compute ALL metrics required by the rubric.

    Args:
        y_true_binary: Binary labels (0 = normal, 1 = anomaly).
        y_true_multiclass: Integer labels (8 classes).
        y_pred_multiclass: Predicted integer labels.
        risk_scores: Risk scores (0-100).

    Returns:
        Dict with all metric values.
    """
    results = {
        "precision_at_1pct": precision_at_k(y_true_binary, risk_scores, 0.01),
        "pr_auc": compute_pr_auc(y_true_binary, risk_scores),
    }

    per_class = compute_per_class_metrics(y_true_multiclass, y_pred_multiclass)
    results.update(per_class)

    # FPR (false positive rate)
    normal_mask = y_true_binary == 0
    if normal_mask.sum() > 0:
        fp = ((risk_scores[normal_mask] > 50).sum())  # threshold-based FP
        results["false_positive_rate"] = float(fp / normal_mask.sum())
    else:
        results["false_positive_rate"] = 0.0

    log.info("all_metrics_computed", precision_at_1pct=f"{results['precision_at_1pct']:.4f}",
             pr_auc=f"{results['pr_auc']:.4f}", macro_f1=f"{results['macro_f1']:.4f}",
             fpr=f"{results['false_positive_rate']:.4f}")

    return results
