from typing import Dict, Any, List
from src.utils import haversine_distance

class HistoricalFireDatabase:
    """Small curated archive of known events; not a complete global fire archive."""
    KNOWN_HISTORICAL_EVENTS = [
        {
            "event_id": "HIST_2023_WESTERN_GHATS",
            "latitude": 18.4500,
            "longitude": 73.7800,
            "event_date": "2023-03-15",
            "fire_name": "Western Ghats Forest Burn",
            "source": "Copernicus Burned Area Service",
            "duration_days": 4,
            "recorded_burned_ha": 340.0
        },
        {
            "event_id": "HIST_2022_UTTARAKHAND",
            "latitude": 30.0668,
            "longitude": 79.0193,
            "event_date": "2022-05-10",
            "fire_name": "Garhwal Pine Forest Event",
            "source": "NASA FIRMS Archive",
            "duration_days": 7,
            "recorded_burned_ha": 1250.0
        }
    ]

    @classmethod
    def find_events_within_radius(cls, lat: float, lon: float,
                                  radius_km: float = 100.0) -> Dict[str, Any]:
        matches: List[Dict[str, Any]] = []
        for event in cls.KNOWN_HISTORICAL_EVENTS:
            dist = haversine_distance(lat, lon, event["latitude"], event["longitude"])
            if dist <= radius_km:
                matches.append({
                    **event,
                    "distance_km": round(dist, 2)
                })
        matches.sort(key=lambda item: item["distance_km"])
        return {
            "found": bool(matches),
            "count": len(matches),
            "radius_km": radius_km,
            "events": matches,
            "catalogue_size": len(cls.KNOWN_HISTORICAL_EVENTS),
            "source_note": "Curated built-in archive only; absence of a match does not mean no wildfire occurred."
        }

    @classmethod
    def check_historical_event(cls, lat: float, lon: float,
                               radius_km: float = 100.0) -> Dict[str, Any]:
        """Backward-compatible summary of archived events within the requested radius."""
        result = cls.find_events_within_radius(lat, lon, radius_km)
        first = result["events"][0] if result["events"] else {}
        return {
            "found": result["found"],
            "count": result["count"],
            "radius_km": radius_km,
            "events": result["events"],
            "event_id": first.get("event_id"),
            "fire_name": first.get("fire_name"),
            "event_date": first.get("event_date"),
            "distance_km": first.get("distance_km"),
            "source": first.get("source"),
            "source_note": result["source_note"]
        }
