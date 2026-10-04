"""Change-point detection on annual time series using the PELT algorithm
(ruptures library) with an L2 cost model — appropriate for detecting shifts
in the mean level of a roughly-annual environmental series.
"""

import numpy as np
import ruptures as rpt


def detect_change_points(years: list[int], values: list[float], penalty: float = 3.0) -> list[dict]:
    if len(values) < 8:
        return []

    arr = np.asarray(values, dtype=float).reshape(-1, 1)
    algo = rpt.Pelt(model="l2", min_size=3, jump=1).fit(arr)
    try:
        breakpoints = algo.predict(pen=penalty)
    except Exception:
        return []

    # ruptures returns breakpoint indices with the final index = len(series)
    breakpoints = [b for b in breakpoints if b < len(values)]

    results = []
    prev = 0
    for bp in breakpoints:
        segment_before = values[max(0, prev):bp]
        segment_after = values[bp:]
        if not segment_before or not segment_after:
            continue
        results.append(
            {
                "year": int(years[bp]),
                "mean_before": float(np.mean(segment_before)),
                "mean_after": float(np.mean(segment_after)),
                "shift": float(np.mean(segment_after) - np.mean(segment_before)),
            }
        )
        prev = bp
    return results
