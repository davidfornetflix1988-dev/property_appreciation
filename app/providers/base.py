from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Literal, Optional

LocationType = Literal["zip", "city_state", "county_state"]

@dataclass(frozen=True)
class SeriesPoint:
    date: str   # "YYYY-MM"
    value: float

@dataclass(frozen=True)
class ProviderSeries:
    source: Literal["zillow", "fhfa"]
    metric: str
    geography: str
    points: List[SeriesPoint]

class ProviderError(Exception):
    pass

class DataProvider(ABC):
    @abstractmethod
    def get_series(
        self,
        location_type: LocationType,
        location_value: str,
    ) -> ProviderSeries:
        """
        Return a time series for the requested geography.
        Raises ProviderError if not found or unsupported.
        """
        raise NotImplementedError