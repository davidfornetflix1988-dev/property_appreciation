from pydantic import BaseModel, Field
from typing import Optional, List, Literal

SourceType = Literal["zillow", "fhfa", "both"]

class SeriesPoint(BaseModel):
    date: str = Field(..., description="YYYY-MM")
    value: float

class ProviderResult(BaseModel):
    source: Literal["zillow", "fhfa"]
    metric: str = Field(..., description="Name of metric, e.g., ZHVI or HPI")
    geography: str = Field(..., description="Resolved geography label used by provider")
    start_date_used: str = Field(..., description="Actual start date used after alignment")
    end_date_used: str = Field(..., description="Actual end date used after alignment")
    start_value: float
    end_value: float
    pct_change: float = Field(..., description="Percent change over the window")
    series: Optional[List[SeriesPoint]] = Field(None, description="Optional: time series for charting")

class ComparisonResult(BaseModel):
    delta_pct_points: float = Field(..., description="Absolute difference between provider pct_change values")
    mismatch_flag: bool = Field(..., description="True if disagreement exceeds threshold")
    threshold_pct_points: float


class ResolvedGeo(BaseModel):
    zip5: str
    state: str
    cbsa: Optional[str] = None
    city: Optional[str] = None
    primary_weight: float
    weight_source: Literal["RES_RATIO", "TOT_RATIO"]

class AppreciationResponse(BaseModel):
    request_id: str
    source: SourceType
    results: List[ProviderResult]
    comparison: Optional[ComparisonResult] = None
    resolved_geo: Optional[ResolvedGeo] = None
    latest: Optional[ProviderResult] = None
    plot_labels: Optional[dict[str, str]] = None
    latest_end: Optional[str] = None
    aligned_end: Optional[str] = None
    alignment_note: Optional[str] = None


