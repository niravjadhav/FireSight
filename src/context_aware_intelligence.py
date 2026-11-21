"""Context-aware alert scoring and explanations for FIRMS hotspot records.

This is a transparent heuristic, not a calibrated probability of wildfire.
"""
from typing import Any, Dict, List


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def assess_hotspot(hotspot: Dict[str, Any], weather: Dict[str, Any], persistence_count: int = 1,
                   nearby_count: int = 1) -> Dict[str, Any]:
    confidence = hotspot.get("confidence", 50)
    if isinstance(confidence, str):
        confidence = {"low": 25, "nominal": 50, "medium": 50, "high": 85}.get(confidence.lower(), 50)
    try:
        confidence = float(confidence)
        if confidence <= 1:
            confidence *= 100
    except (TypeError, ValueError):
        confidence = 50.0
    confidence_score = _clamp(confidence / 100)

    humidity = weather.get("humidity")
    wind = weather.get("wind_speed", weather.get("wind"))
    try:
        humidity_score = 0.5 if humidity is None else _clamp((70 - float(humidity)) / 60)
    except (TypeError, ValueError):
        humidity_score = 0.5
    try:
        wind_score = 0.5 if wind is None else _clamp(float(wind) / 15)
    except (TypeError, ValueError):
        wind_score = 0.5
    persistence_score = _clamp(max(0, persistence_count - 1) / 4)
    cluster_score = _clamp(max(0, nearby_count - 1) / 8)

    score = round(100 * (0.35 * confidence_score + 0.20 * humidity_score +
                         0.15 * wind_score + 0.20 * persistence_score + 0.10 * cluster_score))
    reasons = [f"Satellite confidence contribution: {confidence_score:.2f}"]
    try:
        humidity_value = None if humidity is None else float(humidity)
    except (TypeError, ValueError):
        humidity_value = None
    if humidity_value is None:
        reasons.append("Humidity unavailable or invalid; neutral fallback used")
    elif humidity_value >= 70:
        reasons.append("High humidity lowers contextual dryness evidence; it does not prove a false alarm")
    else:
        reasons.append("Lower humidity supports increased contextual concern")
    reasons.append(f"Persistence observations: {persistence_count}")
    reasons.append(f"Nearby hotspot count: {nearby_count}")
    level = "high" if score >= 70 else "moderate" if score >= 40 else "low"
    return {"score": score, "level": level, "confidence_percent": round(confidence_score * 100),
            "decision": "prioritize investigation" if level == "high" else "retain for review",
            "reasons": reasons, "is_calibrated_probability": False}


def assess_many(hotspots: List[Dict[str, Any]], weather: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Assess records; persistence/neighbor counts can be supplied per record."""
    results = []
    for item in hotspots:
        result = assess_hotspot(item, weather,
                                int(item.get("persistence_count", 1) or 1),
                                int(item.get("nearby_count", 1) or 1))
        results.append({"hotspot": item, "assessment": result})
    return sorted(results, key=lambda row: row["assessment"]["score"], reverse=True)
