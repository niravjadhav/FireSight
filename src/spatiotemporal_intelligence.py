"""Spatial grouping and time-persistence summaries for hotspot observations."""
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List
from src.active_fire import ActiveFireDetector


def _time(record: Dict[str, Any]):
    raw = record.get("acq_datetime") or record.get("timestamp") or record.get("acq_date")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        try:
            return datetime.strptime(str(raw), "%Y-%m-%d")
        except ValueError:
            return None


def analyze_hotspots(records: List[Dict[str, Any]], radius_km: float = 5.0) -> List[Dict[str, Any]]:
    """Greedy distance-based clusters; persistence counts distinct observation times.

    Suitable for project-scale demonstrations. For large datasets use a spatial index
    and a validated clustering method. Missing coordinates are skipped.
    """
    valid = []
    for record in records:
        try:
            lat, lon = float(record["latitude"]), float(record["longitude"])
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                valid.append((record, lat, lon))
        except (KeyError, TypeError, ValueError):
            continue
    clusters = []
    for record, lat, lon in valid:
        target = None
        for cluster in clusters:
            distance = ActiveFireDetector.haversine_distance(lat, lon, cluster["latitude"], cluster["longitude"])
            if distance <= radius_km:
                target = cluster
                break
        if target is None:
            target = {"latitude": lat, "longitude": lon, "records": []}
            clusters.append(target)
        target["records"].append(record)
        n = len(target["records"])
        target["latitude"] = sum(float(r["latitude"]) for r in target["records"]) / n
        target["longitude"] = sum(float(r["longitude"]) for r in target["records"]) / n
    output = []
    for index, cluster in enumerate(clusters, 1):
        times = sorted(t for t in (_time(r) for r in cluster["records"]) if t is not None)
        output.append({"cluster_id": index, "latitude": cluster["latitude"], "longitude": cluster["longitude"],
                       "hotspot_count": len(cluster["records"]),
                       "persistence_count": len(set(times)),
                       "first_observed": times[0].isoformat() if times else None,
                       "last_observed": times[-1].isoformat() if times else None,
                       "records": cluster["records"]})
    return sorted(output, key=lambda c: (c["persistence_count"], c["hotspot_count"]), reverse=True)
