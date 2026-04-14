from dataclasses import dataclass
from typing import List, Tuple

from app.providers.base import ProviderSeries, SeriesPoint, ProviderError

@dataclass(frozen=True)
class WindowResult:
    start_date_used: str
    end_date_used: str
    start_value: float
    end_value: float
    pct_change: float

def _select_last_on_or_before(points: List[SeriesPoint], target_ym: str) -> SeriesPoint:
    """
    Pick the last point whose date <= target_ym.
    Assumes points are sorted ascending by date.
    """
    chosen = None
    for p in points:
        if p.date <= target_ym:
            chosen = p
        else:
            break
    if chosen is None:
        raise ProviderError(f"No data on or before {target_ym}")
    return chosen

def compute_window_change(series: ProviderSeries, start_ym: str, end_ym: str) -> WindowResult:
    if not series.points:
        raise ProviderError("Empty time series")

    # Ensure sorted by date
    points = sorted(series.points, key=lambda p: p.date)

    start_pt = _select_last_on_or_before(points, start_ym)
    end_pt = _select_last_on_or_before(points, end_ym)

    if start_pt.value == 0:
        raise ProviderError("Start value is zero; cannot compute percent change")

    pct_change = round((end_pt.value / start_pt.value - 1.0) * 100.0, 2)


    return WindowResult(
        start_date_used=start_pt.date,
        end_date_used=end_pt.date,
        start_value=float(start_pt.value),
        end_value=float(end_pt.value),
        pct_change=float(pct_change),
    )