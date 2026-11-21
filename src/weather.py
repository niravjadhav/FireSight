"""Weather ingestion with unit normalization and suspicious-reading cross-checks."""
import os
import math
import requests
from typing import Dict, Any
from src.utils import logger


def _finite(value, default=None):
    """Parse a finite number; preserve missing/invalid readings as None."""
    try:
        value = float(value)
        return value if math.isfinite(value) else default
    except (TypeError, ValueError):
        return default


def _require_readings(readings, required):
    missing = [name for name in required if readings.get(name) is None]
    if missing:
        raise ValueError(
            "Weather provider returned missing/invalid values for: "
            + ", ".join(missing)
        )


class WeatherProvider:
    @staticmethod
    def _open_meteo(lat: float, lon: float) -> Dict[str, Any]:
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            "&current=temperature_2m,relative_humidity_2m,wind_speed_10m,rain"
        )
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        current = response.json().get("current", {})
        readings = {
            "temperature": _finite(current.get("temperature_2m")),
            "humidity": _finite(current.get("relative_humidity_2m")),
            "wind_speed": _finite(current.get("wind_speed_10m")),  # API returns km/h
            "rainfall": _finite(current.get("rain")),
            "provider": "Open-Meteo",
        }
        _require_readings(readings, ("temperature", "humidity", "wind_speed", "rainfall"))
        return readings


    @staticmethod
    def _open_meteo_daily_history(lat: float, lon: float, past_days: int = 30) -> Dict[str, Any]:
        """Fetch 30 days of daily weather for FWI spin-up.

        Daily mean temperature/RH and daily maximum wind are proxies, not standard
        noon observations. The returned metadata makes that limitation explicit.
        """
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}&past_days={past_days}&forecast_days=1"
            "&daily=temperature_2m_mean,relative_humidity_2m_mean,wind_speed_10m_max,precipitation_sum"
            "&timezone=auto"
        )
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        daily = response.json().get("daily", {})
        dates = daily.get("time", [])
        history = []
        for i, date in enumerate(dates):
            try:
                row = {
                    "date": date,
                    "temperature": _finite(daily.get("temperature_2m_mean", [])[i]),
                    "humidity": _finite(daily.get("relative_humidity_2m_mean", [])[i]),
                    "wind_speed": _finite(daily.get("wind_speed_10m_max", [])[i]),
                    "rainfall": _finite(daily.get("precipitation_sum", [])[i]),
                }
                # Do not turn missing observations into zero-valued weather.
                if all(row.get(k) is not None for k in
                       ("temperature", "humidity", "wind_speed", "rainfall")):
                    history.append(row)
            except (IndexError, TypeError):
                continue
        return {"days": history, "provider": "Open-Meteo daily archive/forecast",
                "method": "30-day spin-up using daily mean temperature/RH, daily maximum wind and daily precipitation; proxy inputs, not standard noon observations."}



    @staticmethod
    def fetch_regional_fwi(lat: float, lon: float, radius_km: float = 100.0,
                           spacing_km: float = 50.0) -> Dict[str, Any]:
        """Estimate FWI on a 3x3 grid using 30-day Open-Meteo weather history.

        Inputs are daily aggregates (proxy observations), so this is an
        experimental regional screening estimate, not locally calibrated FWI.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from src.fwi_index import calculate_fwi_series

        cos_lat = max(0.2, math.cos(math.radians(lat)))
        offsets = [
            (0.0, 0.0, "Centre"),
            (-spacing_km, -spacing_km, "South-west"),
            (-spacing_km, 0.0, "South"),
            (-spacing_km, spacing_km, "South-east"),
            (0.0, -spacing_km, "West"),
            (0.0, spacing_km, "East"),
            (spacing_km, -spacing_km, "North-west"),
            (spacing_km, 0.0, "North"),
            (spacing_km, spacing_km, "North-east"),
        ]
        points = []
        for north_km, east_km, label in offsets:
            distance = math.hypot(north_km, east_km)
            if distance > radius_km:
                continue
            points.append({
                "label": label,
                "latitude": lat + north_km / 111.32,
                "longitude": lon + east_km / (111.32 * cos_lat),
                "distance_from_target_km": round(distance, 1),
            })

        def calculate(point):
            history = WeatherProvider._open_meteo_daily_history(
                point["latitude"], point["longitude"], past_days=30
            )
            result = calculate_fwi_series(history["days"], point["latitude"])
            return {**point, "fwi": result, "history_source": history["provider"],
                    "history_method": history["method"]}

        results, errors = [], []
        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = {pool.submit(calculate, point): point for point in points}
            for future in as_completed(futures):
                try:
                    results.append(future.result())
                except Exception as exc:
                    errors.append({"point": futures[future]["label"], "error": str(exc)})

        valid = [r for r in results if r.get("fwi", {}).get("available")]
        if not valid:
            return {"available": False, "reason": "No grid cell returned a valid multi-day FWI estimate.",
                    "radius_km": radius_km, "grid_size": len(points), "errors": errors, "cells": results}

        values = [float(r["fwi"]["score"]) for r in valid]
        avg = sum(values) / len(values)
        highest = max(valid, key=lambda r: float(r["fwi"]["score"]))
        def level(v):
            return "LOW" if v < 5 else "MODERATE" if v < 10 else "HIGH" if v < 20 else "VERY HIGH"

        return {
            "available": True, "radius_km": radius_km, "grid_size": len(points),
            "successful_cells": len(valid), "failed_cells": errors,
            "average_fwi": round(avg, 2), "average_level": level(avg),
            "maximum_fwi": round(float(highest["fwi"]["score"]), 2),
            "maximum_level": level(float(highest["fwi"]["score"])),
            "highest_risk_cell": {k: highest[k] for k in
                                  ("label", "latitude", "longitude", "distance_from_target_km")},
            "cells": results,
            "method": "Nine sample points in a 3x3 grid at 50 km spacing; FWI calculated independently at each point from 30 days of daily weather aggregates.",
            "limitation": "Experimental screening estimate. Daily mean temperature/RH and daily maximum wind are proxy inputs; initial moisture codes are provisional; the Canadian FWI system is not locally calibrated for Indonesia."
        }


    @staticmethod
    def fetch_current_weather(lat: float, lon: float) -> Dict[str, Any]:
        """Fetch OWM current weather; cross-check extreme/invalid readings with Open-Meteo."""
        api_key = os.getenv("WEATHER_API_KEY")
        if not api_key or not api_key.strip():
            raise ValueError("WEATHER_API_KEY is missing in .env file.")

        url = (
            "https://api.openweathermap.org/data/2.5/weather"
            f"?lat={lat}&lon={lon}&appid={api_key}&units=metric"
        )
        try:
            response = requests.get(url, timeout=15)
            if response.status_code == 401:
                raise PermissionError("OpenWeatherMap Key Error (401): key is invalid or pending activation.")
            response.raise_for_status()
            data = response.json()
            main, wind, rain = data.get("main", {}), data.get("wind", {}), data.get("rain", {})
            wind_ms = _finite(wind.get("speed"))
            primary = {
                "temperature": _finite(main.get("temp")),
                "humidity": _finite(main.get("humidity")),
                "wind_speed": wind_ms * 3.6 if wind_ms is not None else None,  # m/s -> km/h
                "rainfall": _finite(rain.get("1h"), default=0.0),
                "is_live": True,
                "provider": "OpenWeatherMap API",
            }
            _require_readings(primary, ("temperature", "humidity", "wind_speed", "rainfall"))
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectTimeout):
            logger.warning("OpenWeatherMap timed out; using Open-Meteo fallback.")
            backup = WeatherProvider._open_meteo(lat, lon)
            backup.update({"is_live": True, "provider": "Open-Meteo (fallback)", "validation": {"status": "fallback source", "checked": False}})
            try:
                history = WeatherProvider._open_meteo_daily_history(lat, lon, past_days=30)
                backup["fwi_history"] = history["days"]
                backup["fwi_history_source"] = history["provider"]
                backup["fwi_history_method"] = history["method"]
            except Exception as exc:
                backup["fwi_history"] = []
                backup["fwi_history_error"] = str(exc)
            return backup

        # Always validate physical ranges; only call the second provider for suspicious values.
        range_issues = []
        if not -80 <= primary["temperature"] <= 60: range_issues.append("temperature outside -80 to 60 °C")
        if not 0 <= primary["humidity"] <= 100: range_issues.append("humidity outside 0 to 100%")
        if not 0 <= primary["wind_speed"] <= 300: range_issues.append("wind speed outside 0 to 300 km/h")
        if primary["rainfall"] < 0: range_issues.append("negative rainfall")
        if not 0 <= primary["humidity"] <= 100: range_issues.append("humidity outside 0 to 100%")
        if primary["wind_speed"] < 0: range_issues.append("negative wind speed")
        suspicious = bool(range_issues) or primary["humidity"] <= 15 or primary["wind_speed"] > 120
        validation = {"status": "within basic physical ranges", "checked": False, "issues": range_issues}
        if suspicious:
            try:
                secondary = WeatherProvider._open_meteo(lat, lon)
                diffs = {
                    "temperature_difference_c": round(abs(primary["temperature"] - secondary["temperature"]), 1),
                    "humidity_difference_percentage_points": round(abs(primary["humidity"] - secondary["humidity"]), 1),
                    "wind_difference_kmh": round(abs(primary["wind_speed"] - secondary["wind_speed"]), 1),
                }
                mismatch = (diffs["temperature_difference_c"] > 8 or
                            diffs["humidity_difference_percentage_points"] > 20 or
                            diffs["wind_difference_kmh"] > 25)
                validation = {
                    "status": "provider disagreement" if mismatch else "cross-check broadly agrees",
                    "checked": True, "secondary_provider": "Open-Meteo",
                    "secondary_readings": secondary, "differences": diffs,
                    "issues": range_issues,
                }
            except Exception as exc:
                validation = {"status": "cross-check unavailable", "checked": False,
                              "issues": range_issues, "cross_check_error": str(exc)}
        primary["validation"] = validation
        try:
            history = WeatherProvider._open_meteo_daily_history(lat, lon, past_days=30)
            primary["fwi_history"] = history["days"]
            primary["fwi_history_source"] = history["provider"]
            primary["fwi_history_method"] = history["method"]
        except Exception as exc:
            primary["fwi_history"] = []
            primary["fwi_history_error"] = str(exc)
        logger.info("Weather readings received from OpenWeatherMap; validation: %s", validation["status"])
        return primary
