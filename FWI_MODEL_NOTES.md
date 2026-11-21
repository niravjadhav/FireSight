# FireSight AI — Fire Weather Index implementation notes

## What changed
- Replaced the custom 35/35/30 weighted weather heuristic with the daily Canadian Forest Fire Weather Index (FWI) equations.
- Calculates FFMC (fine-fuel moisture code), DMC (duff moisture code), DC (drought code), ISI (initial spread index), BUI (buildup index), and FWI.
- Fetches up to eight recent daily weather records from Open-Meteo to initialize and advance the moisture codes. Current conditions remain sourced from OpenWeatherMap, with the existing suspicious-reading cross-check against Open-Meteo.
- The dashboard now displays the native FWI value and its component codes. It no longer calls the result a percentage or a 0–100 probability.
- If multi-day history cannot be fetched, FWI is marked unavailable; the application does not silently fall back to the arbitrary weighted score.

## Important limitations — read before operational use
1. Standard FWI calculations use daily observations near local noon and 24-hour precipitation. This project currently uses Open-Meteo daily mean temperature/RH, daily maximum wind and daily precipitation as proxy inputs. These are not identical to standard noon observations.
2. The moisture-code spin-up starts with conventional provisional values FFMC=85, DMC=6 and DC=15. Eight days of history is a short spin-up; longer historical initialization is preferable.
3. Canadian FWI thresholds and seasonal/day-length conventions were developed for Canadian forest-fire danger applications. The implementation applies broad latitude/month approximations and is not validated for Pune or Indian vegetation, monsoon patterns, or fuel types.
4. The broad LOW/MODERATE/HIGH/VERY HIGH labels are screening labels only. They are not locally calibrated risk classes, and FWI is not the probability that a fire will occur.
5. Before operational or scientific claims, compare against local historical fire observations and weather, validate the implementation against a trusted FWI reference implementation, and calibrate/validate thresholds for the target ecosystem.
6. FWI describes weather-related fire danger. It does not detect an active fire. NASA FIRMS remains the active thermal-anomaly source; Sentinel-2 remains the post-fire damage source.

## Inputs and outputs
Daily input fields: `date` (YYYY-MM-DD), `temperature` (°C), `humidity` (%), `wind_speed` (km/h), `rainfall` (mm/day).

Outputs: FFMC, DMC, DC, ISI, BUI, FWI, recent daily history, initialization note and data-quality warnings.
