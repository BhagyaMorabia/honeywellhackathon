"""Sequence Anomaly Detector — N-Gram Markov Chain transition probabilities.

Replaces the heavy PyTorch GRU with a lightning-fast, highly explainable
Markov Chain model. Computes the surprise of a sequence of commands by
evaluating transition probabilities P(cmd_t | cmd_{t-1}).
"""

from __future__ import annotations

import math
from collections import defaultdict

import numpy as np


def _inner_defaultdict():
    return defaultdict(int)

class SequenceAnomalyDetector:
    """N-Gram Markov transition model for sequence anomaly detection."""

    def __init__(self, vocab_size: int = 100, **kwargs):
        """Initialize the N-Gram model.
        
        Args:
            vocab_size: Not strictly used for Markov, kept for compatibility.
        """
        self.transitions: dict[int, dict[int, int]] = defaultdict(_inner_defaultdict)
        self.state_counts: dict[int, int] = defaultdict(int)
        self.vocab: set[int] = set()
        
        # Smoothing factor for unseen transitions
        self.alpha = 1e-5

    def fit(self, sessions: list[list[int]]):
        """Train the transition matrix on a list of sessions.
        
        Args:
            sessions: List of encoded command sequences.
        """
        for seq in sessions:
            if not seq:
                continue
                
            for i in range(len(seq) - 1):
                src = seq[i]
                dst = seq[i + 1]
                
                self.transitions[src][dst] += 1
                self.state_counts[src] += 1
                self.vocab.add(src)
                self.vocab.add(dst)

    def _score_sequence(self, seq: list[int]) -> float:
        """Score a single sequence based on transition surprise.
        
        Score = -sum(log(P(dst | src))) / len(transitions)
        High score = Highly anomalous (surprising) sequence.
        """
        if len(seq) < 2:
            return 0.0
            
        vocab_size = len(self.vocab) if self.vocab else 1
        log_prob_sum = 0.0
        
        for i in range(len(seq) - 1):
            src = seq[i]
            dst = seq[i + 1]
            
            # Additive smoothing (Laplace)
            count_transition = self.transitions.get(src, {}).get(dst, 0)
            count_src = self.state_counts.get(src, 0)
            
            prob = (count_transition + self.alpha) / (count_src + self.alpha * vocab_size)
            log_prob_sum += math.log(prob)
            
        # Normalize by length to prevent length-bias
        avg_log_prob = log_prob_sum / (len(seq) - 1)
        
        # Surprise score (negative log likelihood)
        return -avg_log_prob

    def score_batch(self, sessions: list[list[int]]) -> list[float]:
        """Score a batch of sessions.
        
        Returns:
            List of anomaly scores (higher = more anomalous).
        """
        return [self._score_sequence(seq) for seq in sessions]
