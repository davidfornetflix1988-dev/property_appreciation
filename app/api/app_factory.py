from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.staticfiles import StaticFiles
from app.providers.base import ProviderError
from fastapi import FastAPI
from uuid import uuid4

from app.schemas.requests import AppreciationRequest
from app.schemas.responses import AppreciationResponse, ProviderResult, ComparisonResult

def shift_yyyymm(yyyymm: str, delta_months: int) -> str:
    y, m = map(int, yyyymm.split("-"))
    total = y * 12 + (m - 1) + delta_months
    ny, nm0 = divmod(total, 12)
    return f"{ny:04d}-{nm0 + 1:02d}"

"""

def create_app() -> FastAPI:
    app = FastAPI()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app



def create_app() -> FastAPI:
    app = FastAPI()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/appreciation", response_model=AppreciationResponse)
    def appreciation(req: AppreciationRequest):
        # Dummy placeholder result (will be replaced by real providers later)
        dummy = ProviderResult(
            source="zillow",
            metric="DUMMY",
            geography=f"{req.location_type}:{req.location_value}",
            start_date_used=req.start,
            end_date_used=req.end,
            start_value=100.0,
            end_value=110.0,
            pct_change=10.0,
            series=None,
        )

        return AppreciationResponse(
            request_id=str(uuid4()),
            source=req.source,
            results=[dummy],
            comparison=None,
        )

    return app
"""

from fastapi import FastAPI
from uuid import uuid4

from app.schemas.requests import AppreciationRequest
from app.schemas.responses import AppreciationResponse, ProviderResult, ResolvedGeo

def create_app() -> FastAPI:
    app = FastAPI()
    templates = Jinja2Templates(directory="app/templates")
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    @app.get("/health")
    def health():
        return {"status": "ok"}
    
    @app.get("/", response_class=HTMLResponse)
    def home(request: Request):
        return templates.TemplateResponse(
            "index.html",
            {"request": request},
        )
    

    @app.post("/appreciation", response_model=AppreciationResponse)
    
    
    def appreciation(req: AppreciationRequest):
        print(f"[DEBUG] req.source = {req.source}")
        from app.providers.base import ProviderSeries, SeriesPoint
        from app.core.metrics import compute_window_change

        from app.providers.zillow import ZillowProvider
        from app.core.metrics import compute_window_change

        provider = ZillowProvider()
        try:
            series = provider.get_series(req.location_type, req.location_value)
        except ProviderError as e:
            raise HTTPException(status_code=422, detail=str(e))

        # Derive the window once (duration OR explicit start/end)
        # Derive the window once (duration OR explicit start/end)
        latest_result = None
        comparison = None

        if req.duration_months is not None:
            duration = int(req.duration_months)

            # Always compute Zillow-latest window (Plot 1)
            zillow_end_latest = series.points[-1].date
            #zillow_start_latest = shift_yyyymm(zillow_end_latest, -(duration - 1))
            zillow_start_latest = shift_yyyymm(zillow_end_latest, -(duration))

            # Build benchmarks (if applicable) so we can align by common end month (Plot 2)
            fhfa_state_series = None
            fhfa_msa_series = None

            if req.source in ("fhfa", "both") and req.location_type == "zip":
                from app.core.geo_resolver import resolve_zip_to_cbsa_state
                r = resolve_zip_to_cbsa_state(req.location_value)
                resolved_geo = ResolvedGeo(
                    zip5=r.zip5,
                    state=r.state,
                    cbsa=r.cbsa,
                    city=r.city,
                    primary_weight=r.primary_weight,
                    weight_source=r.weight_source,
                )

                from app.providers.fhfa import get_state_series, get_msa_series_by_cbsa
                fhfa_state_series = get_state_series(resolved_geo.state, index_kind="nsa")

                if resolved_geo.cbsa:
                    fhfa_msa_series = get_msa_series_by_cbsa(
                        resolved_geo.cbsa,
                        prefer_state=resolved_geo.state,
                        prefer_city=resolved_geo.city,
                        index_kind="nsa",
                    )

            # Compute common end month for aligned benchmark plot:
            # Use min(latest available month across the series that exist)
            end_candidates = [zillow_end_latest]
            if fhfa_state_series is not None:
                end_candidates.append(fhfa_state_series.points[-1].date)
            if fhfa_msa_series is not None:
                end_candidates.append(fhfa_msa_series.points[-1].date)

            end = min(end_candidates)
            start = shift_yyyymm(end, -(duration - 0))

            # Put Zillow-latest as comparison (Plot 1)
            zillow_latest_window = compute_window_change(series, zillow_start_latest, zillow_end_latest)

            latest_result = ProviderResult(
                source="zillow",
                metric=series.metric,
                geography=series.geography,
                start_date_used=zillow_latest_window.start_date_used,
                end_date_used=zillow_latest_window.end_date_used,
                start_value=zillow_latest_window.start_value,
                end_value=zillow_latest_window.end_value,
                pct_change=zillow_latest_window.pct_change,
                series=[
                    {"date": p.date, "value": p.value}
                    for p in series.points
                    if zillow_latest_window.start_date_used <= p.date <= zillow_latest_window.end_date_used
                ],
            )

            # Compute Zillow-aligned window (same duration, but aligned end month)
            zillow_aligned_window = compute_window_change(series, start, end)

            delta_pct_points = None
            if (zillow_latest_window.pct_change is not None) and (zillow_aligned_window.pct_change is not None):
                delta_pct_points = zillow_latest_window.pct_change - zillow_aligned_window.pct_change

            threshold_pct_points = 2.0  # percentage points; tune later
            mismatch_flag = False
            if delta_pct_points is not None:
                mismatch_flag = abs(delta_pct_points) >= threshold_pct_points
            
            comparison = ComparisonResult(
                delta_pct_points=delta_pct_points,
                threshold_pct_points=threshold_pct_points,
                mismatch_flag=mismatch_flag,
            )

        else:
            # Explicit mode: user supplies start/end
            start_user = req.start
            end_user = req.end

            # Plot A: Zillow over the user's exact window
            zillow_user_window = compute_window_change(series, start_user, end_user)
            latest_result = ProviderResult(
                source="zillow",
                metric=series.metric,
                geography=series.geography,
                start_date_used=zillow_user_window.start_date_used,
                end_date_used=zillow_user_window.end_date_used,
                start_value=zillow_user_window.start_value,
                end_value=zillow_user_window.end_value,
                pct_change=zillow_user_window.pct_change,
                series=[
                    {"date": p.date, "value": p.value}
                    for p in series.points
                    if zillow_user_window.start_date_used <= p.date <= zillow_user_window.end_date_used
                ],
            )

            # Build FHFA series (for alignment), only for ZIP requests
            resolved_geo = None
            fhfa_state_series = None
            fhfa_msa_series = None

            if req.source in ("fhfa", "both") and req.location_type == "zip":
                from app.core.geo_resolver import resolve_zip_to_cbsa_state
                r = resolve_zip_to_cbsa_state(req.location_value)
                resolved_geo = ResolvedGeo(
                    zip5=r.zip5,
                    state=r.state,
                    cbsa=r.cbsa,
                    city=r.city,
                    primary_weight=r.primary_weight,
                    weight_source=r.weight_source,
                )

                from app.providers.fhfa import get_state_series, get_msa_series_by_cbsa
                fhfa_state_series = get_state_series(resolved_geo.state, index_kind="nsa")

                if resolved_geo.cbsa:
                    fhfa_msa_series = get_msa_series_by_cbsa(
                        resolved_geo.cbsa,
                        prefer_state=resolved_geo.state,
                        prefer_city=resolved_geo.city,
                        index_kind="nsa",
                    )

            # Helper: find the closest available FHFA date <= end_user
            def _closest_leq(points, target_yyyymm: str) -> str | None:
                for pt in reversed(points):
                    if pt.date <= target_yyyymm:
                        return pt.date
                return None

            # Compute aligned_end = closest FHFA-supported end <= end_user
            end_candidates = []
            if fhfa_state_series is not None:
                d = _closest_leq(fhfa_state_series.points, end_user)
                if d is not None:
                    end_candidates.append(d)
            if fhfa_msa_series is not None:
                d = _closest_leq(fhfa_msa_series.points, end_user)
                if d is not None:
                    end_candidates.append(d)

            if req.source == "zillow":
                aligned_end = end_user
            else:
                if not end_candidates:
                    raise HTTPException(
                        status_code=422,
                        detail=f"No FHFA data available at or before requested end={end_user} for this location.",
                    )
                aligned_end = min(end_candidates)

            # Plot B window = [start_user, aligned_end]
            start = start_user
            end = aligned_end

            # Comparison: how much does Zillow change when aligned to FHFA end?
            zillow_aligned_window = compute_window_change(series, start_user, aligned_end)

            delta_pct_points = None
            if (zillow_user_window.pct_change is not None) and (zillow_aligned_window.pct_change is not None):
                delta_pct_points = zillow_user_window.pct_change - zillow_aligned_window.pct_change

            threshold_pct_points = 2.0
            mismatch_flag = False
            if delta_pct_points is not None:
                mismatch_flag = abs(delta_pct_points) >= threshold_pct_points

            comparison = ComparisonResult(
                delta_pct_points=delta_pct_points,
                threshold_pct_points=threshold_pct_points,
                mismatch_flag=mismatch_flag,
            )

        window = compute_window_change(series, start, end)

        resolved_geo = None
        if req.location_type == "zip":
            from app.core.geo_resolver import resolve_zip_to_cbsa_state
            r = resolve_zip_to_cbsa_state(req.location_value)
            resolved_geo = ResolvedGeo(
                zip5=r.zip5,
                state=r.state,
                cbsa=r.cbsa,
                city=r.city,
                primary_weight=r.primary_weight,
                weight_source=r.weight_source,
            )
        
        result = ProviderResult(
            source="zillow",
            metric=series.metric,
            geography=series.geography,
            start_date_used=window.start_date_used,
            end_date_used=window.end_date_used,
            start_value=window.start_value,
            end_value=window.end_value,
            pct_change=window.pct_change,
            
            #series=[{"date": p.date, "value": p.value} for p in series.points],
            series=[
                {"date": p.date, "value": p.value}
                for p in series.points
                if window.start_date_used <= p.date <= window.end_date_used
                ],
        
        )

        results = []
        if req.source in ("zillow", "both"):
            results.append(result)

        # Add FHFA State benchmark for ZIP requests (macro context)
        if req.source in ("fhfa", "both") and req.location_type == "zip" and resolved_geo is not None:
            from app.providers.fhfa import get_state_series

            fhfa_state_series = get_state_series(resolved_geo.state, index_kind="nsa")
            
            fhfa_state_window = compute_window_change(fhfa_state_series, start, end)

            fhfa_result = ProviderResult(
                source="fhfa",
                metric=fhfa_state_series.metric,
                geography=fhfa_state_series.geography,
                start_date_used=fhfa_state_window.start_date_used,
                end_date_used=fhfa_state_window.end_date_used,
                start_value=fhfa_state_window.start_value,
                end_value=fhfa_state_window.end_value,
                pct_change=fhfa_state_window.pct_change,
                series=[
                    {"date": p.date, "value": p.value}
                    for p in fhfa_state_series.points
                    if fhfa_state_window.start_date_used <= p.date <= fhfa_state_window.end_date_used
                ],
            )

            results.append(fhfa_result)

        # Add FHFA MSA/MSAD benchmark (meso context) when CBSA is available
        if req.source in ("fhfa", "both") and resolved_geo and resolved_geo.cbsa:
            from app.providers.fhfa import get_msa_series_by_cbsa

            fhfa_msa_series = get_msa_series_by_cbsa(
                resolved_geo.cbsa,
                prefer_state=resolved_geo.state,
                prefer_city=resolved_geo.city,
                index_kind="nsa",
            )
            
            fhfa_msa_window = compute_window_change(fhfa_msa_series, start, end)

            fhfa_msa_result = ProviderResult(
                source="fhfa",
                metric=fhfa_msa_series.metric,
                geography=fhfa_msa_series.geography,
                start_date_used=fhfa_msa_window.start_date_used,
                end_date_used=fhfa_msa_window.end_date_used,
                start_value=fhfa_msa_window.start_value,
                end_value=fhfa_msa_window.end_value,
                pct_change=fhfa_msa_window.pct_change,
                series=[
                    {"date": p.date, "value": p.value}
                    for p in fhfa_msa_series.points
                    if fhfa_msa_window.start_date_used <= p.date <= fhfa_msa_window.end_date_used
                ],
            )

            results.append(fhfa_msa_result)

        alignment_note = None
        if req.duration_months is not None:
            alignment_note = (
                f"Aligned comparison ends at {end} (minimum of latest available dates across included providers). "
                f"Zillow-latest plot may end later at {latest_result.end_date_used if latest_result else 'N/A'}."
            )
        else:
            alignment_note = (
                f"Aligned comparison ends at {end} (closest FHFA-supported quarter <= requested end {req.end}). "
                f"Zillow user-window plot ends at {latest_result.end_date_used if latest_result else 'N/A'}."
            )


        return AppreciationResponse(
            request_id=str(uuid4()),
            source=req.source,
            resolved_geo=resolved_geo,
            results=results,
            latest=latest_result,
            comparison=comparison,
            plot_labels={
                "latest": "Zillow ZIP (latest available)",
                "aligned": "Aligned comparison (Zillow + FHFA benchmarks)",
            },
            latest_end=(latest_result.end_date_used if latest_result else None),
            aligned_end=end,
            alignment_note=alignment_note,
        )

    return app
