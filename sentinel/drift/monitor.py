"""Concept drift detection using River's ADWIN.

ADWIN (ADaptive WINdowing) is the gold standard for streaming drift detection:
- Maintains a variable-length window of recent observations
- Automatically shrinks the window when it detects a statistically significant
  change in the data distribution
- Mathematically proven to detect distribution shifts

Key tuning: delta=0.001 (tight) because our anomaly stream is sparse (1.5% anomaly rate).
A looser threshold would miss legitimate drift events.
"""

from __future__ import annotations

from river import drift

from sentinel.utils.logger import get_logger

log = get_logger(__name__)


class DriftMonitor:
    """Monitors concept drift at the entity-cohort level using ADWIN.

    Maintains one ADWIN detector per entity_type (cohort).
    Feeds binary is_anomalous signals and detects when the anomaly rate
    distribution has shifted significantly.

    Attributes:
        detectors: Dict of entity_type → ADWIN instance.
        drift_events: List of detected drift events.
        delta: ADWIN confidence parameter (lower = less sensitive).
    """

    def __init__(self, delta: float = 0.001):
        """Initialize the drift monitor.

        Args:
            delta: ADWIN confidence parameter. Lower = fewer false drift detections.
                   Set to 0.001 for sparse anomaly streams (1.5% anomaly rate).
        """
        self.delta = delta
        self.detectors: dict[str, drift.ADWIN] = {}
        self.drift_events: list[dict] = []
        log.info("drift_monitor_initialized", delta=delta)

    def update(self, entity_type: str, is_anomalous: bool, metadata: dict | None = None) -> bool:
        """Feed a new observation to the drift detector.

        Args:
            entity_type: Cohort identifier (e.g., "user", "edge_device").
            is_anomalous: Whether the current event was flagged as anomalous.
            metadata: Optional metadata to attach to drift events.

        Returns:
            True if drift was detected on this update.
        """
        if entity_type not in self.detectors:
            self.detectors[entity_type] = drift.ADWIN(delta=self.delta)

        detector = self.detectors[entity_type]
        detector.update(int(is_anomalous))

        if detector.drift_detected:
            drift_event = {
                "cohort": entity_type,
                "type": "distribution_shift",
                "message": (
                    f"Anomaly rate distribution shift detected for cohort '{entity_type}'. "
                    f"Baseline may need recalibration."
                ),
                "metadata": metadata or {},
            }
            self.drift_events.append(drift_event)
            log.warning("concept_drift_detected", **drift_event)
            return True

        return False

    def get_drift_events(self) -> list[dict]:
        """Return all detected drift events."""
        return self.drift_events.copy()

    def get_active_cohorts(self) -> list[str]:
        """Return list of cohorts being monitored."""
        return list(self.detectors.keys())

    def reset_cohort(self, entity_type: str) -> None:
        """Reset the drift detector for a specific cohort.

        Called after drift is detected and the baseline has been recalibrated.
        """
        self.detectors[entity_type] = drift.ADWIN(delta=self.delta)
        log.info("drift_detector_reset", cohort=entity_type)
