from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal
import re

import pandas as pd

from app.providers.base import ProviderError, ProviderSeries, SeriesPoint


_INDEX_KIND = Literal["nsa", "sa"]
FHFA_HPI_TYPE = "traditional"
FHFA_HPI_FLAVOR = "purchase-only"

@lru_cache(maxsize=1)
def _load_fhfa_df() -> pd.DataFrame:
    path = Path("data/fhfa/hpi_master.csv")
    if not path.exists():
        raise FileNotFoundError(f"FHFA dataset not found: {path}")

    df = pd.read_csv(path)

    required = {"frequency", "level", "place_name", "place_id", "yr", "period", "index_nsa", "index_sa"}
    missing = required - set(df.columns)
    if missing:
        raise ProviderError(f"FHFA dataset missing columns: {sorted(missing)}")

    # Normalize text cols
    df["frequency"] = df["frequency"].astype(str).str.strip().str.lower()
    df["level"] = df["level"].astype(str).str.strip()
    df["place_id"] = df["place_id"].astype(str).str.strip()
    df["place_name"] = df["place_name"].astype(str).str.strip()

    # numeric time
    df["yr"] = pd.to_numeric(df["yr"], errors="coerce")
    df["period"] = pd.to_numeric(df["period"], errors="coerce")

    return df


def _to_yyyymm_quarter_end(yr: int, q: int) -> str:
    # FHFA quarterly: period is 1..4
    quarter_end_month = {1: 3, 2: 6, 3: 9, 4: 12}.get(int(q))
    if quarter_end_month is None:
        raise ValueError(f"Invalid quarter period: {q}")
    return f"{int(yr):04d}-{quarter_end_month:02d}"


def get_state_series(state_code: str, *, index_kind: _INDEX_KIND = "nsa") -> ProviderSeries:
    """
    Return FHFA HPI series for a US state using monthly frequency.

    state_code: two-letter code like "CA"
    index_kind: "nsa" (not seasonally adjusted) or "sa"
    """
    st = state_code.strip().upper()
    if len(st) != 2 or not st.isalpha():
        raise ProviderError(f"Invalid state code: {state_code!r}")

    df = _load_fhfa_df()

    # Prefer monthly to match Zillow's quarterly cadence
    sub = df[(df["level"] == "State") & (df["frequency"] == "quarterly")]
    if sub.empty:
        raise ProviderError("FHFA dataset has no quarterly State rows (unexpected).")

    # How to identify a state row:
    # FHFA place_id for State is not guaranteed to be the 2-letter code,
    # but place_name typically contains the full state name.
    # We'll match by place_id == state code IF present; otherwise fall back to
    # place_name ending with "(ST)" isn't available here, so we'll use place_id first
    # and then a strict place_name == st only if it exists (rare).
    # Practically, many FHFA extracts use place_id like 'ST_CA' or similar —
    # so we do a robust contains match on place_id.
    pid = sub["place_id"].astype(str)

    # Candidate match patterns
    candidates = sub[
        (pid == st)
        | (pid == f"ST_{st}")
        | (pid.str.endswith(f"_{st}"))
        | (pid.str.contains(fr"\b{st}\b", regex=True))
    ]

    print(
    "[FHFA get_state_series] candidates:",
    "rows=", len(candidates),
    "place_id_nunique=", candidates["place_id"].nunique(),
    "place_ids=", sorted(candidates["place_id"].astype(str).unique())[:10],
)

    if candidates.empty:
        # Last resort: try matching place_name exactly to the state code (unlikely)
        candidates = sub[sub["place_name"].str.upper() == st]

    if candidates.empty:
        raise ProviderError(f"State not found in FHFA dataset (monthly, level=State): {st}")

    col = "index_nsa" if index_kind == "nsa" else "index_sa"

    # Restrict FHFA State benchmark to a single definition to avoid duplicate quarters:
    # traditional + purchase-only
    candidates = candidates[
        (candidates["hpi_type"].astype(str).str.lower() == FHFA_HPI_TYPE) &
        (candidates["hpi_flavor"].astype(str).str.lower() == FHFA_HPI_FLAVOR)
    ]

    # Build points

    place_id_mode = candidates["place_id"].mode().iloc[0]
    place_name_mode = candidates["place_name"].mode().iloc[0]

    rows = candidates[candidates["place_id"] == place_id_mode][["yr", "period", col]].dropna().sort_values(["yr", "period"])
    
    points = [
        SeriesPoint(date=_to_yyyymm_quarter_end(int(r.yr), int(r.period)), value=float(getattr(r, col)))
        for r in rows.itertuples(index=False)
        if int(r.period) >= 1 and int(r.period) <= 4
    ]

    if not points:
        raise ProviderError(f"No FHFA points found for state {st} using {col}")

    # Use the most common place_id/name from the matched slice
    place_id_mode = candidates["place_id"].mode().iloc[0]
    place_name_mode = candidates["place_name"].mode().iloc[0]

    return ProviderSeries(
        source="fhfa",
        metric=f"HPI_{index_kind.upper()}",
        geography=f"State {st} ({place_name_mode}; {place_id_mode})",
        points=points,
    )

@lru_cache(maxsize=1)
def _load_cbsa_reference() -> pd.DataFrame:
    path = Path("data/geo/cbsa_reference/cbsa_reference.csv")
    if not path.exists():
        raise FileNotFoundError(f"CBSA reference not found: {path}")

    df = pd.read_csv(path)
    if "CBSA Code" not in df.columns or "CBSA Title" not in df.columns:
        raise ProviderError("CBSA reference must have columns: 'CBSA Code', 'CBSA Title'")

    df = df.copy()
    df["CBSA Code"] = df["CBSA Code"].astype(str).str.strip()
    df["CBSA Title"] = df["CBSA Title"].astype(str).str.strip()
    return df


def _norm_place_name(s: str) -> str:
    # Normalize names for robust matching across Census vs FHFA.
    s = s.lower()
    s = s.replace("(msad)", "")      # FHFA sometimes tags metro divisions
    s = s.replace(".", "")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _cbsa_title_from_code(cbsa_code: str) -> str:
    code = str(cbsa_code).strip()
    ref = _load_cbsa_reference()
    hit = ref[ref["CBSA Code"] == code]
    if hit.empty:
        raise ProviderError(f"CBSA code not found in reference table: {code}")
    return str(hit["CBSA Title"].iloc[0]).strip()

@lru_cache(maxsize=256)
def _msad_titles_for_cbsa(cbsa_code: str) -> list[str]:
    """
    Return Metropolitan Division Titles (MSAD titles) for a CBSA code
    using the Census List 1 delineation file.
    """
    p = Path("data/geo/cbsa_reference/list1_2023.xlsx")
    if not p.exists():
        raise FileNotFoundError(f"CBSA List 1 file not found: {p}")

    df = pd.read_excel(
        p,
        header=2,
        usecols=["CBSA Code", "Metropolitan Division Code", "Metropolitan Division Title"],
    )

    # Normalize CBSA Code to string without trailing .0
    df["CBSA Code"] = df["CBSA Code"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()

    sub = df[df["CBSA Code"] == str(cbsa_code).strip()].dropna(subset=["Metropolitan Division Title"])

    titles = (
        sub["Metropolitan Division Title"]
        .astype(str)
        .str.strip()
        .drop_duplicates()
        .tolist()
    )
    return titles


def get_msa_series_by_cbsa(
    cbsa_code: str,
    *,
    prefer_state: str | None = None,
    prefer_city: str | None = None,
    index_kind: _INDEX_KIND = "nsa",
) -> ProviderSeries:
    """
    Return FHFA HPI series for an MSA, using a CBSA code as input.

    Bridges:
      CBSA code -> CBSA title (Census) -> FHFA MSA place_name -> FHFA place_id -> series
    """
    df = _load_fhfa_df()

    msa = df[(df["level"] == "MSA") & (df["frequency"] == "quarterly")]
    if msa.empty:
        raise ProviderError("FHFA dataset has no quarterly MSA rows (unexpected).")

    cbsa_title = _cbsa_title_from_code(cbsa_code)
    
    # Match on the core metro name (before comma) to avoid suffix differences like NY-NJ vs NY-NJ-PA
    cbsa_core = cbsa_title.split(",", 1)[0]
    target = _norm_place_name(cbsa_core)

    msa = msa.copy()
    msa["PLACE_NORM"] = msa["place_name"].astype(str).map(_norm_place_name)
    msa["PLACE_CORE"] = msa["place_name"].astype(str).apply(lambda s: _norm_place_name(str(s).split(",", 1)[0]))

    # Prefer matches on the core name (before comma)
    candidates = msa[msa["PLACE_CORE"] == target]

    # Restrict FHFA MSA/MSAD benchmark to the same definition as State:
    # traditional + purchase-only
    candidates = candidates[
        (candidates["hpi_type"].astype(str).str.lower() == FHFA_HPI_TYPE) &
        (candidates["hpi_flavor"].astype(str).str.lower() == FHFA_HPI_FLAVOR)
    ]

    if candidates.empty:
        # Fallback: CBSA may be represented only as metropolitan divisions (MSAD) in FHFA.
        msad_titles = _msad_titles_for_cbsa(cbsa_code)

        if not msad_titles:
            raise ProviderError(
                f"No FHFA MSA match for CBSA {cbsa_code} (title={cbsa_title!r}) and no MSAD titles found."
            )

        # Match FHFA place_name against MSAD titles
        msa2 = msa.copy()
        msa2["PLACE_NORM_FULL"] = msa2["place_name"].astype(str).map(_norm_place_name)

        matches_list: list[tuple[str, pd.DataFrame]] = []
        for t in msad_titles:
            t_norm = _norm_place_name(t)
            hit = msa2[msa2["PLACE_NORM_FULL"].str.contains(re.escape(t_norm), regex=True)]
            if not hit.empty:
                matches_list.append((t, hit))

        if not matches_list:
            raise ProviderError(
                f"No FHFA MSA match for CBSA {cbsa_code}. Tried CBSA core and MSAD titles: {msad_titles!r}"
            )

        # Selection priority:
        # 1) prefer MSAD title containing preferred city token (V1 heuristic)
        chosen = None
        if prefer_city:
            city = prefer_city.strip().lower()
            for t, hit in matches_list:
                if city and city in t.lower():
                    chosen = hit
                    break

        # 2) else prefer a match whose place_name includes preferred state
        if chosen is None and prefer_state:
            st = prefer_state.strip().upper()
            for t, hit in matches_list:
                hit2 = hit[hit["place_name"].astype(str).str.contains(rf"\b{re.escape(st)}\b", regex=True)]
                if not hit2.empty:
                    chosen = hit2
                    break

        # 3) final deterministic fallback: first match group
        candidates = chosen if chosen is not None else matches_list[0][1]

    if candidates.empty:
        candidates = msa[msa["PLACE_CORE"].str.contains(re.escape(target), regex=True)]

    # Prefer base metros over metro divisions where possible
    non_div = candidates[~candidates["place_name"].astype(str).str.contains(r"\(MSAD\)", regex=True)]
    picked = non_div if not non_div.empty else candidates

    place_id = picked["place_id"].mode().iloc[0]
    place_name = picked["place_name"].mode().iloc[0]

    col = "index_nsa" if index_kind == "nsa" else "index_sa"

    rows = picked[picked["place_id"] == place_id][["yr", "period", col]].dropna().sort_values(["yr", "period"])
    points = [
        SeriesPoint(date=_to_yyyymm_quarter_end(int(r.yr), int(r.period)), value=float(getattr(r, col)))
        for r in rows.itertuples(index=False)
        if int(r.period) >= 1 and int(r.period) <= 4
    ]

    # Deduplicate: keep only one value per date (FHFA slices can include multiple place_id variants)
    _by_date: dict[str, SeriesPoint] = {}
    for p in points:
        _by_date[p.date] = p
    points = list(_by_date.values())

    if not points:
        raise ProviderError(f"No FHFA points for MSA place_id={place_id} (CBSA={cbsa_code}) using {col}")

    return ProviderSeries(
    source="fhfa",
    metric=f"HPI_{index_kind.upper()}",
    geography=str(place_name).strip(),  # human-readable MSA/MSAD name for legends/UI
    points=points,
    )