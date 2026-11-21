"""FWI-based fire-weather danger assessment; explicitly not a fire probability."""
from typing import Dict, Any
from src.fwi_index import calculate_fwi_series


class WildfireRiskPredictor:
    @staticmethod
    def calculate_risk(weather: Dict[str, Any], lat: float = 0.0, lon: float = 0.0,
                       fire_detected: bool = False, num_hotspots: int = 0) -> Dict[str, Any]:
        return WildfireRiskPredictor.calculate_risk_score(weather, lat, lon)

    @staticmethod
    def calculate_risk_score(weather: Dict[str, Any], lat: float = 0.0,
                             lon: float = 0.0) -> Dict[str, Any]:
        history = weather.get("fwi_history", []) or []
        fwi_result = calculate_fwi_series(history, latitude=lat) if history else {
            "available": False,
            "reason": weather.get("fwi_history_error", "Daily weather history was not supplied."),
        }
        warnings = []
        validation = weather.get("validation", {}) or {}
        if weather.get("humidity", 50) <= 15:
            warnings.append("Current humidity is very low; compare provider readings and local observations.")
        if validation.get("status") == "provider disagreement":
            warnings.append("Weather providers disagree materially; confidence in current conditions is reduced.")
        if not fwi_result.get("available"):
            warnings.append("FWI could not be calculated. The system will not substitute the old weighted heuristic.")
            return {
                "score": None, "level": "UNAVAILABLE", "factors": {}, "breakdown": {},
                "fwi": fwi_result, "warnings": warnings, "data_quality": "LOW",
                "score_type": "FWI requires a valid multi-day weather series; no heuristic score is substituted.",
            }
        components = fwi_result["components"]
        # Preserve native FWI units; do not rescale to a misleading 0-100 probability.
        score = fwi_result["score"]
        level = fwi_result["level"]
        quality = "LOW" if validation.get("status") == "provider disagreement" else (
            "CHECK RECOMMENDED" if weather.get("humidity", 50) <= 15 else "PROVISIONAL"
        )
        return {
            "score": score, "level": level, "factors": {
                "Fine fuel moisture (FFMC)": components["FFMC"],
                "Initial spread (ISI)": components["ISI"],
                "Buildup (BUI)": components["BUI"],
            },
            "breakdown": {"FWI": components["FWI"], "FFMC": components["FFMC"],
                          "DMC": components["DMC"], "DC": components["DC"],
                          "ISI": components["ISI"], "BUI": components["BUI"]},
            "fwi": fwi_result, "warnings": warnings, "data_quality": quality,
            "score_type": fwi_result["score_type"],
        }


WildfireRiskModel = WildfireRiskPredictor
