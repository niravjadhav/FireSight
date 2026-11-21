# FireSight AI — Summary Cards Restored

## Apply the update
1. Back up your current project folder.
2. Extract this ZIP.
3. Copy/merge the included `src/` and `dashboard/` folders into your project, replacing files when prompted.
4. Keep your own `.env` file in the project root; it is intentionally not included.
5. Restart Streamlit: `python -m streamlit run dashboard/app.py`

## Summary card behavior
- **Fire Weather Index (FWI):** uses the FWI calculated for the exact selected coordinate. It displays N/A if the required weather history is unavailable.
- **Thermal Anomaly:** continues to show NASA FIRMS detections from the existing 100 km hotspot search. The map and hotspot query have not been changed. Detections are satellite thermal observations, not individually confirmed wildfires.
- **Historical Analysis:** uses the configured `HISTORICAL_MATCH_RADIUS_KM` (25 km by default) against the small built-in curated archive. No match does not prove that no fire occurred.
- **Assessed Severity:** reports the Sentinel-2 assessment status for the representative FIRMS event selected by the pipeline. It remains PENDING/NOT ASSESSED if a verified image pair is unavailable.

The separate **Regional Fire Weather Index — 100 km** section remains available in the Risk & Weather tab for regional context. The four top summary cards no longer present themselves as 100 km regional cards.

## Security
This update excludes `.env`, `.venv`, Python cache files, and the local SQLite database. Keep API credentials in your private local `.env` file. If credentials from an earlier shared ZIP may have been exposed, rotate them.
