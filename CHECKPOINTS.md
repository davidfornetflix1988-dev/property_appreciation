# Neighborhood App — Checkpoints

## Checkpoint 1 — FastAPI skeleton + validation + Zillow ZIP ZHVI
Status: WORKING ✅

### What works
- Server runs: `uvicorn main:app --reload`
- Health check: `GET /health` -> `{"status":"ok"}`
- Appreciation API: `POST /appreciation`
  - Validates:
    - date format YYYY-MM
    - end >= start
    - ZIP must be 5 digits
    - city_state and county_state formats validated (providers not implemented yet)
  - Source guardrail:
    - `source="zillow"` works
    - `source="fhfa"` or `"both"` returns 501 with message
  - Zillow provider implemented:
    - Reads `data/zillow/zhvi_zip.csv`
    - Matches ZIP by RegionName
    - Returns ZHVI series
  - Response includes window-only `series` points for charting

### Data files
- `data/zillow/zhvi_zip.csv` (ZHVI ZIP dataset)

### Quick test commands
- Zillow ZIP example:
  `curl -s -X POST http://127.0.0.1:8000/appreciation -H "Content-Type: application/json" -d '{"location_type":"zip","location_value":"97116","start":"2020-01","end":"2024-01","source":"zillow"}'`

### Next steps
1) Add FHFA provider (likely not ZIP-based; decide supported geographies)
2) Add `source="both"` comparison logic
3) Add frontend UI (simple form + chart)