from pydantic import BaseModel, Field, model_validator
from typing import Literal, Optional

LocationType = Literal["zip", "city_state", "county_state"]
SourceType = Literal["zillow", "fhfa", "both"]

class AppreciationRequest(BaseModel):
    location_type: LocationType = Field(..., description="How to interpret location_value")
    location_value: str = Field(..., min_length=1, description="ZIP, 'City, ST', or 'County County, ST'")
    
    start: Optional[str] = None
    end: Optional[str] = None
    #duration_months: Optional[Literal[12, 36, 60, 120]] = None
    duration_months: Optional[int] = Field(None, ge=1, description="Number of months for the analysis window")
    
    source: SourceType = Field("zillow", description="Which data source(s) to use")

    @model_validator(mode="after")
    def validate_request(self):
        v = self.location_value.strip()

        if self.location_type == "zip":
            if not (len(v) == 5 and v.isdigit()):
                raise ValueError("For location_type='zip', location_value must be a 5-digit ZIP code (e.g., '98103').")

        elif self.location_type == "city_state":
            # Expect "City, ST"
            if "," not in v:
                raise ValueError("For location_type='city_state', use format 'City, ST' (e.g., 'Seattle, WA').")
            city, state = [x.strip() for x in v.split(",", 1)]
            if not city:
                raise ValueError("For location_type='city_state', city name cannot be empty.")
            if not (len(state) == 2 and state.isalpha()):
                raise ValueError("For location_type='city_state', state must be a 2-letter code (e.g., 'WA').")

        elif self.location_type == "county_state":
            # Expect "County Name, ST"
            if "," not in v:
                raise ValueError("For location_type='county_state', use format 'County Name, ST' (e.g., 'King County, WA').")
            county, state = [x.strip() for x in v.split(",", 1)]
            if not county:
                raise ValueError("For location_type='county_state', county name cannot be empty.")
            if not (len(state) == 2 and state.isalpha()):
                raise ValueError("For location_type='county_state', state must be a 2-letter code (e.g., 'WA').")

        #Window validation: either duration_months OR (start and end)
        has_duration = self.duration_months is not None
        has_start_end = (self.start is not None) and (self.end is not None)

        if has_duration == has_start_end:
            raise ValueError("Provide either duration_months OR (start and end).")

        # If start/end are provided, enforce ordering
        if has_start_end:
            if self.end < self.start:
                raise ValueError("end must be >= start (both in YYYY-MM)")

        # Normalize stored value (optional but helpful)
        self.location_value = v
        return self
