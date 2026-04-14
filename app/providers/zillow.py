from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import List

import pandas as pd

from app.core.config import ZILLOW_DATA_DIR
from app.providers.base import DataProvider, ProviderError, ProviderSeries, SeriesPoint, LocationType


ZILLOW_ZIP_FILE = ZILLOW_DATA_DIR / "zhvi_zip.csv"


def _to_yyyy_mm(date_col: str) -> str:
    # Zillow columns are like "2020-01-31" -> "2020-01"
    return date_col[:7]


@lru_cache(maxsize=1)
def _load_zip_df() -> pd.DataFrame:
    """
    Load the Zillow ZIP ZHVI dataset once per process.
    Force RegionName to string so ZIPs preserve leading zeros.
    """
    if not ZILLOW_ZIP_FILE.exists():
        raise ProviderError(f"Missing Zillow ZIP file at: {ZILLOW_ZIP_FILE}")

    df = pd.read_csv(ZILLOW_ZIP_FILE, dtype={"RegionName": "string"})
    return df


class ZillowProvider(DataProvider):
    def get_series(self, location_type: LocationType, location_value: str) -> ProviderSeries:
        if location_type != "zip":
            raise ProviderError("ZillowProvider currently supports only location_type='zip' (ZIP ZHVI dataset)")

        zip_code = location_value.strip()
        df = _load_zip_df()

        # Find row by RegionName (ZIP)
        matches = df[df["RegionName"] == zip_code]
        if matches.empty:
            raise ProviderError(f"ZIP not found in Zillow dataset: {zip_code}")

        row = matches.iloc[0]

        # Identify date columns (they look like YYYY-MM-DD)
        date_cols = [c for c in df.columns if len(c) == 10 and c[4] == "-" and c[7] == "-"]

        points: List[SeriesPoint] = []
        for c in date_cols:
            val = row[c]
            if pd.isna(val):
                continue
            points.append(SeriesPoint(date=_to_yyyy_mm(c), value=float(val)))

        points.sort(key=lambda p: p.date)

        return ProviderSeries(
            source="zillow",
            metric="ZHVI",
            geography=f"ZIP {zip_code}",
            points=points,
        )