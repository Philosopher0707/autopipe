"""Small numeric helpers shared by the step library.

Kept here rather than in one step module because the callers are peers, and a
copy of a correctness rule in two places is how it drifts — which is exactly
how ``resolve_seed`` ended up written three times.
"""

from typing import List, Sequence, Tuple

import numpy as np


def finite_scores(values: Sequence[float]) -> Tuple[List[float], int]:
    """Split scores into usable values and a count of unusable ones.

    Some scorers return NaN rather than raising on a degenerate fold — roc_auc
    does when the fold holds a single class. One NaN poisons any mean it enters,
    and makes every comparison against that mean silently false, so unusable
    values must be dropped rather than averaged.

    Args:
        values: Raw scores from a run of folds.

    Returns:
        ``(usable, dropped)`` — the finite scores, and how many were discarded.
    """
    usable = [float(v) for v in values if np.isfinite(v)]
    return usable, len(values) - len(usable)


def aggregate(scores: Sequence[float]) -> Tuple[float | None, float | None, int]:
    """Mean and standard deviation over the usable scores only.

    Returns ``(None, None, dropped)`` when no score is usable, so the caller can
    omit the metric rather than record an undefined one — ``MetricLog.value`` is
    ``NOT NULL``, and a persisted NaN is a wrong number wearing a real one's
    clothes.
    """
    usable, dropped = finite_scores(scores)
    if not usable:
        return None, None, dropped
    return float(np.mean(usable)), float(np.std(usable)), dropped
