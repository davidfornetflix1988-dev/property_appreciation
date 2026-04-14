# app/core/geo_resolver.py

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

import pandas as pd


@dataclass(frozen=True)
class ZipResolution:
    zip5: str
    state: str
    city: Optional[str]
    cbsa: Optional[str]
    primary_weight: float
    weight_source: str  # "RES_RATIO" or "TOT_RATIO"


def _normalize_zip5(z) -> str:
    # HUD files often store ZIP as int (e.g., 501). We must preserve leading zeros.
    s = str(z).strip()
    # Handle floats like 501.0 safely
    if s.endswith(".0"):
        s = s[:-2]
    if not s.isdigit():
        raise ValueError(f"Invalid ZIP value in crosswalk: {z!r}")
    return s.zfill(5)


def _normalize_cbsa(cbsa) -> str:
    s = str(cbsa).strip()
    if s.endswith(".0"):
        s = s[:-2]
    # CBSA codes are numeric strings; keep as-is if digits.
    return s


@lru_cache(maxsize=1)
def _load_zip_cbsa_crosswalk() -> pd.DataFrame:
    # File is local and versioned; adjust here if you later support multiple vintages.
    xlsx_path = Path("data/geo/hud_crosswalk/hud_zip_cbsa_2025_q4.xlsx")
    if not xlsx_path.exists():
        raise FileNotFoundError(f"HUD ZIP→CBSA crosswalk not found: {xlsx_path}")

    # Sheet 0 is "Export Worksheet" in your file; we keep it generic.
    xls = pd.ExcelFile(xlsx_path)
    df = pd.read_excel(xlsx_path, sheet_name=xls.sheet_names[0])

    required = {"ZIP", "CBSA", "USPS_ZIP_PREF_STATE", "RES_RATIO", "TOT_RATIO"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Crosswalk missing columns: {sorted(missing)}")

    # Normalize key columns
    df = df.copy()
    df["ZIP5"] = df["ZIP"].map(_normalize_zip5)
    df["CBSA_S"] = df["CBSA"].map(_normalize_cbsa)
    df["STATE"] = df["USPS_ZIP_PREF_STATE"].astype(str).str.strip().str.upper()

    # City is optional but helpful for debugging / display
    if "USPS_ZIP_PREF_CITY" in df.columns:
        df["CITY"] = df["USPS_ZIP_PREF_CITY"].astype(str).str.strip()
    else:
        df["CITY"] = None

    # Ensure ratios are numeric
    df["RES_RATIO"] = pd.to_numeric(df["RES_RATIO"], errors="coerce").fillna(0.0)
    df["TOT_RATIO"] = pd.to_numeric(df["TOT_RATIO"], errors="coerce").fillna(0.0)

    return df


def resolve_zip_to_cbsa_state(zip_value: str) -> ZipResolution:
    """
    Resolve a ZIP code to:
      - preferred State
      - primary CBSA (metro/micro), chosen by max RES_RATIO (fallback TOT_RATIO)
      - primary weight indicating confidence / share

    If CBSA is 99999, cbsa is returned as None.
    """
    zip5 = _normalize_zip5(zip_value)
    df = _load_zip_cbsa_crosswalk()

    sub = df[df["ZIP5"] == zip5]
    if sub.empty:
        raise ValueError(f"ZIP not found in HUD ZIP→CBSA crosswalk: {zip5}")

    # Choose primary row by RES_RATIO; if all RES_RATIO are 0, use TOT_RATIO.
    if float(sub["RES_RATIO"].max()) > 0.0:
        weight_col = "RES_RATIO"
    else:
        weight_col = "TOT_RATIO"

    # idxmax is stable enough here; ties pick first occurrence.
    row = sub.loc[sub[weight_col].idxmax()]

    state = str(row["STATE"])
    city = None if pd.isna(row["CITY"]) else str(row["CITY"])
    cbsa_s = str(row["CBSA_S"])
    cbsa = None if cbsa_s == "99999" else cbsa_s

    primary_weight = float(row[weight_col])

    return ZipResolution(
        zip5=zip5,
        state=state,
        city=city,
        cbsa=cbsa,
        primary_weight=primary_weight,
        weight_source=weight_col,
    )