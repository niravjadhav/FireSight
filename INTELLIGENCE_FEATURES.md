# Added intelligence modules

Two additive modules are included:

- `src/context_aware_intelligence.py`: transparent heuristic scoring from satellite confidence, weather, supplied persistence and nearby-hotspot counts. Returns score, level and explanations. This is **not** a calibrated probability and should be evaluated against labelled examples.
- `src/spatiotemporal_intelligence.py`: distance-based hotspot grouping and observation-time summaries. It uses the existing Haversine helper in `ActiveFireDetector`.

## Quick use

```python
from src.context_aware_intelligence import assess_many
from src.spatiotemporal_intelligence import analyze_hotspots

clusters = analyze_hotspots(hotspot_records, radius_km=5)
assessed = assess_many(hotspot_records, weather)
```

Records should contain `latitude` and `longitude`; time can be `acq_datetime`, `timestamp`, or `acq_date`. Confidence is read from `confidence`. Weather keys include `humidity` and `wind_speed` (or `wind`). Missing values are handled conservatively and noted in the explanation.

## Important

These are new reusable modules, not a claim that the existing Streamlit dashboard or Java bridge is already wired to them. The existing app's response schema should be checked before connecting them. Validate thresholds and performance with labelled historical data before using alerts operationally. The clustering implementation is greedy and intended for project-scale data, not large-scale production use.

## Current-fire, historical, and post-fire data separation

- Weather-based wildfire risk is an estimate, not proof of an active fire.
- NASA FIRMS observations indicate thermal anomalies returned by the feed within the search radius.
- Historical catalog matches are context only; they do not trigger current damage assessment.
- Sentinel-2 burned-area/severity metrics remain unavailable until real, date-matched pre-fire and post-fire imagery is connected. Synthetic demonstration bands are not presented as measured damage.
- Recovery recommendations are withheld when verified post-fire damage data is unavailable.

This prevents a nearby hardcoded 2023 historical match from triggering synthetic Sentinel-2 bands and a misleading burned-area/severity result.
