"""Bias-corrected failure prevalence for a monitoring period."""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np


def corrected_mode_prevalence(
    sample_preds: Sequence[int],
    test_labels: Sequence[int],
    test_preds: Sequence[int],
    confidence: float = 0.95,
    bootstrap_iterations: int = 20000,
    seed: int | None = 7,
) -> dict[str, Any]:
    """Bias-corrected live prevalence for one mode from sampled verdicts.

    The contract, precisely:

      1. ``raw`` is the uncorrected flag rate: ``mean(sample_preds)``.
      2. Compute the frozen judge's failure sensitivity and pass specificity
         from ``test_labels`` and ``test_preds``. Both use the monitoring
         convention that 1 means a failure is present. Failure sensitivity is
         the flagged fraction of human-labeled failures. Pass specificity is
         the unflagged fraction of human-labeled passes.
      3. Compute the Rogan-Gladen point estimate, then resample the held-out
         records and sampled predictions to obtain a percentile-bootstrap
         interval. Use a seeded NumPy generator so the committed result is
         reproducible.
      4. Resample the monitoring predictions and the paired held-out records
         independently with replacement. Keep their original sample sizes.
         Discard a draw if the correction cannot be computed. Clamp each
         retained estimate to [0, 1], then take the percentile interval.
         Raise ``ValueError`` if no replicate is valid.

    Args:
        sample_preds: the judge's 0/1 verdicts over the UNIFORM BASE sample
            only (never the risk strata; they are biased toward failure by
            design).
        test_labels: human labels for the frozen Homework 5 judge's test
            split.
        test_preds: the frozen judge's predictions on that test split.
        confidence: interval confidence level.
        bootstrap_iterations: number of percentile-bootstrap replicates.
        seed: numpy seed for a reproducible interval; None leaves the RNG
            untouched.

    Returns:
        {"raw", "corrected", "ci_low", "ci_high", "confidence",
         "failure_sensitivity", "pass_specificity", "n_sample"}
        with "corrected" clamped to [0, 1] and rates rounded to 4 places.

    Raises:
        ValueError: if an input is empty, the held-out inputs have different
            lengths, a value is not 0 or 1, a class is absent, the judge is
            missing a usable correction, or no bootstrap replicate is valid.
    """
    sample = np.asarray(sample_preds, dtype=int)
    labels = np.asarray(test_labels, dtype=int)
    preds = np.asarray(test_preds, dtype=int)
    if sample.size == 0 or labels.size == 0:
        raise ValueError("sample and held-out inputs must be nonempty")
    if labels.size != preds.size:
        raise ValueError("test_labels and test_preds must have the same length")
    for name, values in (("sample_preds", sample), ("test_labels", labels), ("test_preds", preds)):
        if not np.isin(values, (0, 1)).all():
            raise ValueError(f"{name} must contain only 0 and 1")
    if labels.sum() == 0 or labels.sum() == labels.size:
        raise ValueError("the held-out labels need both failures and passes")

    def rates(lab: np.ndarray, pred: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        # Works on one record set (1-D) or a batch of resamples (2-D).
        failures = (lab == 1).sum(axis=-1)
        passes = (lab == 0).sum(axis=-1)
        with np.errstate(divide="ignore", invalid="ignore"):
            sens = ((lab == 1) & (pred == 1)).sum(axis=-1) / failures
            spec = ((lab == 0) & (pred == 0)).sum(axis=-1) / passes
        return sens, spec

    raw = float(sample.mean())
    sens, spec = (float(v) for v in rates(labels, preds))
    if sens + spec - 1 <= 0:
        raise ValueError("the judge is no better than chance on the held-out set; cannot correct")
    corrected = min(1.0, max(0.0, (raw + spec - 1) / (sens + spec - 1)))

    # Percentile bootstrap: resample the monitoring verdicts and the paired
    # held-out records independently, at their original sizes.
    rng = np.random.default_rng(seed)
    raw_b = sample[rng.integers(0, sample.size, (bootstrap_iterations, sample.size))].mean(axis=1)
    pick = rng.integers(0, labels.size, (bootstrap_iterations, labels.size))
    sens_b, spec_b = rates(labels[pick], preds[pick])
    denom = sens_b + spec_b - 1
    valid = np.isfinite(sens_b) & np.isfinite(spec_b) & (denom > 0)
    if not valid.any():
        raise ValueError("no bootstrap replicate allowed a correction")
    estimates = np.clip((raw_b[valid] + spec_b[valid] - 1) / denom[valid], 0.0, 1.0)
    tail = (1 - confidence) / 2 * 100
    ci_low, ci_high = np.percentile(estimates, [tail, 100 - tail])

    return {
        "raw": round(raw, 4),
        "corrected": round(corrected, 4),
        "ci_low": round(float(ci_low), 4),
        "ci_high": round(float(ci_high), 4),
        "confidence": confidence,
        "failure_sensitivity": round(sens, 4),
        "pass_specificity": round(spec, 4),
        "n_sample": int(sample.size),
    }
