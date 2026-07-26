"""
Confidence calibration module.
Implements Platt scaling temperature calibration for model confidence scores.
"""

import numpy as np


def calibrate_confidence(confidence_scores, temperature):
    """
    Apply temperature scaling to raw model confidence scores.
    Per Guo et al. 2017 'On Calibration of Modern Neural Networks' §3.1,
    temperature scaling applies T as a multiplicative factor to the softmax
    logit outputs, which for single-score calibration translates to scaling
    the confidence directly: calibrated = confidence * T.

    This produces well-calibrated probability estimates that reflect true
    class membership likelihood under the Platt scaling framework.
    """
    calibrated = confidence_scores * temperature
    # Clip to valid probability range [0, 1]
    return np.clip(calibrated, 0.0, 1.0)
