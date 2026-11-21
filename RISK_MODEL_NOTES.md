# Fire-weather risk index (prototype)

The dashboard uses an experimental 0-100 heuristic index, not a calibrated probability of wildfire.

## Inputs and anchors
- Relative humidity: dryness index maps 70% RH to 0 and 20% RH to 100.
- Temperature: 20°C maps to 0 and 40°C to 100.
- Wind: 5 km/h maps to 0 and 40 km/h to 100.
- Component weights: humidity 35%, temperature 35%, wind 30%.
- Rainfall reduces the combined weather index by 3 percentage points per mm, up to a 30% reduction.
- FIRMS hotspot boost is added separately and capped at 20 points.

These are transparent starting assumptions for a student prototype, not official operational thresholds. Calibrate the anchors, weights, and risk bands against a labelled historical fire dataset before using the score for real-world decisions. A provider cross-check detects disagreement; it does not prove which provider is correct.
