"""EntityProfileStore — EWMA-updated per-entity profiles with cohort fallback for cold start.

This is the brain of the feature engineering pipeline. It maintains two layers:
1. Per-entity profile (personal baseline)
2. Per-cohort profile (peer group baseline, keyed by entity_type)

Cold-start handling:
  weight = min(1.0, entity_event_count / min_events_for_full_trust)
  - weight ≈ 0: new entity → use cohort baseline
  - weight ≈ 1: mature entity → use personal baseline
  - The dashboard shows "⚠️ Low-confidence — new entity" when weight < 0.5

Concept drift:
  EWMA continuously updates baselines so legitimate behavior shifts are absorbed.
  ADWIN (in drift/monitor.py) detects abrupt distribution changes on top of this.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import numpy as np

from sentinel.utils.logger import get_logger

log = get_logger(__name__)


def _new_profile() -> dict[str, Any]:
    """Create an empty profile dict with default structure."""
    return {
        "n": 0,
        "mean": {},
        "std": {},
        "var": {},  # running variance for std computation
    }


class EntityProfileStore:
    """EWMA-updated per-entity profile store with cohort fallback.

    Attributes:
        alpha: EWMA smoothing factor (0.05 default — slow adaptation).
        min_events: Minimum events before full trust in personal profile.
        entity_profiles: Dict of entity_id → profile dict.
        cohort_profiles: Dict of entity_type → profile dict.
    """

    def __init__(self, alpha: float = 0.05, min_events_for_full_trust: int = 20):
        """Initialize the profile store.

        Args:
            alpha: EWMA smoothing factor. Higher = faster adaptation.
            min_events_for_full_trust: Events before personal profile is fully trusted.
        """
        self.alpha = alpha
        self.min_events = min_events_for_full_trust
        self.entity_profiles: dict[str, dict] = {}
        self.cohort_profiles: dict[str, dict] = {}

    def get_maturity_weight(self, entity_id: str) -> float:
        """Get the cold-start maturity weight for an entity.

        Returns:
            Float in [0.0, 1.0]. 0.0 = pure cold start, 1.0 = fully mature.
        """
        profile = self.entity_profiles.get(entity_id)
        if profile is None:
            return 0.0
        return min(1.0, profile["n"] / self.min_events)

    def is_cold_start(self, entity_id: str) -> bool:
        """Check if entity is in cold-start state (weight < 0.5)."""
        return self.get_maturity_weight(entity_id) < 0.5

    def score_and_update(
        self,
        entity_id: str,
        entity_type: str,
        features: dict[str, float],
    ) -> tuple[dict[str, float], float]:
        """Score features against the blended baseline, then update profiles.

        This is the core function called for every event:
        1. Look up personal + cohort profiles
        2. Compute blended baseline (weighted by maturity)
        3. Compute z-scores against the baseline
        4. EWMA-update both personal and cohort profiles

        Args:
            entity_id: Unique entity identifier.
            entity_type: Entity type (for cohort grouping).
            features: Dict of feature_name → current value.

        Returns:
            Tuple of (z_scores dict, maturity_weight).
        """
        # Get or create profiles
        cohort = self.cohort_profiles.setdefault(entity_type, _new_profile())
        personal = self.entity_profiles.setdefault(entity_id, _new_profile())

        # Maturity weight: 0 = pure cohort, 1 = pure personal
        weight = min(1.0, personal["n"] / self.min_events)

        # Compute blended baseline and z-scores
        z_scores: dict[str, float] = {}
        for k, v in features.items():
            # Blended mean
            p_mean = personal["mean"].get(k, cohort["mean"].get(k, v))
            c_mean = cohort["mean"].get(k, v)
            blended_mean = weight * p_mean + (1 - weight) * c_mean

            # Blended std (use personal if available, else cohort, else default)
            p_std = personal["std"].get(k, cohort["std"].get(k, 1.0))
            c_std = cohort["std"].get(k, 1.0)
            blended_std = weight * p_std + (1 - weight) * c_std

            # Z-score
            z_scores[k] = (v - blended_mean) / (blended_std + 1e-8)

        # ── Clean Room Gate (Poisoning Defense) ──
        # If the event is wildly anomalous compared to the cohort baseline,
        # we refuse to update the personal baseline. This prevents an adversary
        # from slowly training the model to accept malicious behavior.
        is_clean = True
        for k, z in z_scores.items():
            if abs(z) > 4.0:  # 4 standard deviations is our Clean Room threshold
                is_clean = False
                break

        if is_clean:
            # EWMA update — both personal and cohort profiles
            for k, v in features.items():
                # Personal profile update
                old_mean = personal["mean"].get(k, v)
                new_mean = (1 - self.alpha) * old_mean + self.alpha * v
                personal["mean"][k] = new_mean

                # Welford's online variance update
                old_var = personal["var"].get(k, 0.0)
                new_var = (1 - self.alpha) * old_var + self.alpha * (v - new_mean) * (v - old_mean)
                personal["var"][k] = new_var
                personal["std"][k] = max(np.sqrt(abs(new_var)), 1e-6)

                # Cohort profile update
                old_c_mean = cohort["mean"].get(k, v)
                new_c_mean = (1 - self.alpha) * old_c_mean + self.alpha * v
                cohort["mean"][k] = new_c_mean

                old_c_var = cohort["var"].get(k, 0.0)
                new_c_var = (1 - self.alpha) * old_c_var + self.alpha * (v - new_c_mean) * (v - old_c_mean)
                cohort["var"][k] = new_c_var
                cohort["std"][k] = max(np.sqrt(abs(new_c_var)), 1e-6)

            personal["n"] += 1

        return z_scores, weight

    def get_entity_stats(self, entity_id: str) -> dict[str, Any] | None:
        """Get the current profile stats for an entity (for dashboard drill-down)."""
        return self.entity_profiles.get(entity_id)

    def get_cohort_stats(self, entity_type: str) -> dict[str, Any] | None:
        """Get the current cohort profile stats (for dashboard metrics)."""
        return self.cohort_profiles.get(entity_type)

    def get_all_cold_start_entities(self) -> list[str]:
        """Return list of entity_ids currently in cold-start state."""
        return [
            eid for eid, prof in self.entity_profiles.items()
            if prof["n"] < self.min_events
        ]
