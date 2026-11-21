import csv
import io
import math
import os
from typing import Any, Dict, List

import requests
from src.utils import logger


class ActiveFireDetector:
    """Fetch and radius-filter recent NASA FIRMS thermal detections."""

    API_BASE = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
    # Multiple independent VIIRS feeds improve coverage. MODIS is a coarser
    # supplementary sensor. The API's day_range is limited to 1..5.
    SOURCES = (
        "VIIRS_NOAA21_NRT",
        "VIIRS_NOAA20_NRT",
        "VIIRS_SNPP_NRT",
        "MODIS_NRT",
    )
    DAY_RANGE = 5  # FIRMS Area API supports 1..5 days per request.
    REQUEST_TIMEOUT = 20

    @staticmethod
    def haversine_distance(
        lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """Return great-circle distance between two coordinates in kilometres."""
        earth_radius_km = 6371.0088
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(dlon / 2) ** 2
        )
        return earth_radius_km * 2 * math.atan2(
            math.sqrt(a), math.sqrt(max(0.0, 1.0 - a))
        )

    @staticmethod
    def _bounding_box(lat: float, lon: float, radius_km: float) -> str:
        """Create FIRMS west,south,east,north bbox enclosing the radius."""
        lat_delta = radius_km / 110.574
        cos_lat = max(abs(math.cos(math.radians(lat))), 0.01)
        lon_delta = radius_km / (111.320 * cos_lat)

        west = max(-180.0, lon - lon_delta)
        east = min(180.0, lon + lon_delta)
        south = max(-90.0, lat - lat_delta)
        north = min(90.0, lat + lat_delta)
        return f"{west:.5f},{south:.5f},{east:.5f},{north:.5f}"

    @staticmethod
    def _to_float(value: Any):
        try:
            if value is None or str(value).strip() == "":
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _parse_csv(
        cls, csv_text: str, target_lat: float, target_lon: float,
        radius_km: float, source: str
    ) -> List[Dict[str, Any]]:
        reader = csv.DictReader(io.StringIO(csv_text))
        if not reader.fieldnames:
            return []

        # Normalize headers without assuming a fixed column order.
        reader.fieldnames = [str(name).strip().lower() for name in reader.fieldnames]
        results = []

        for row in reader:
            row = {str(k).strip().lower(): v for k, v in row.items() if k}
            fire_lat = cls._to_float(row.get("latitude"))
            fire_lon = cls._to_float(row.get("longitude"))
            if fire_lat is None or fire_lon is None:
                continue

            distance = cls.haversine_distance(
                target_lat, target_lon, fire_lat, fire_lon
            )
            if distance > radius_km:
                continue

            brightness = (
                cls._to_float(row.get("bright_ti4"))
                or cls._to_float(row.get("brightness"))
            )
            confidence = str(row.get("confidence") or "unknown").strip().lower()

            results.append({
                "latitude": fire_lat,
                "longitude": fire_lon,
                "distance_km": round(distance, 2),
                "brightness": brightness,
                "confidence": confidence,
                "acq_date": row.get("acq_date") or "Unknown",
                "acq_time": row.get("acq_time") or "Unknown",
                "frp": cls._to_float(row.get("frp")),
                "satellite": row.get("satellite") or source,
                "instrument": row.get("instrument") or "Unknown",
                "daynight": row.get("daynight") or "Unknown",
                "source": f"NASA FIRMS {source}",
            })

        return results

    @classmethod
    def fetch_firms_hotspots(
        cls, lat: float, lon: float, radius_km: float = 100.0
    ) -> List[Dict[str, Any]]:
        """Query several FIRMS NRT feeds for a local area and merge detections."""
        result = cls.fetch_firms_data(lat, lon, radius_km)
        return result["hotspots"]

    @classmethod
    def fetch_firms_data(
        cls, lat: float, lon: float, radius_km: float = 100.0
    ) -> Dict[str, Any]:
        """Return detections plus diagnostic status (including API failures)."""
        map_key = os.getenv("FIRMS_MAP_KEY", "").strip()
        if not map_key:
            return {
                "status": "missing_api_key",
                "message": "NASA FIRMS MAP_KEY is missing. Add FIRMS_MAP_KEY to .env.",
                "hotspots": [],
                "sources_checked": [],
                "source_errors": [],
            }

        bbox = cls._bounding_box(lat, lon, radius_km)
        session = requests.Session()
        all_hotspots: List[Dict[str, Any]] = []
        sources_checked = []
        source_errors = []

        for source in cls.SOURCES:
            url = (
                f"{cls.API_BASE}/{map_key}/{source}/{bbox}/{cls.DAY_RANGE}"
            )
            try:
                response = session.get(url, timeout=cls.REQUEST_TIMEOUT)
                if response.status_code != 200:
                    detail = response.text[:250].replace("\n", " ")
                    source_errors.append(
                        f"{source}: HTTP {response.status_code} ({detail})"
                    )
                    continue

                body = response.text.strip()
                if not body:
                    source_errors.append(f"{source}: empty response body")
                    continue

                # FIRMS can return a plain-text error with HTTP 200.
                first_line = body.splitlines()[0].lower()
                if "latitude" not in first_line or "longitude" not in first_line:
                    source_errors.append(
                        f"{source}: unexpected response: {first_line[:180]}"
                    )
                    continue

                parsed = cls._parse_csv(
                    body, lat, lon, radius_km, source
                )
                sources_checked.append({
                    "source": source,
                    "records_within_radius": len(parsed),
                })
                all_hotspots.extend(parsed)

            except requests.RequestException as exc:
                source_errors.append(f"{source}: request failed ({exc})")
            except Exception as exc:
                source_errors.append(f"{source}: parsing failed ({exc})")

        # Remove duplicate detections returned by overlapping sensor feeds or
        # repeated records. Keep the sensor/source details of each unique row.
        unique = {}
        for item in all_hotspots:
            key = (
                round(item["latitude"], 5),
                round(item["longitude"], 5),
                item["acq_date"],
                item["acq_time"],
                item["satellite"],
            )
            unique[key] = item

        hotspots = sorted(
            unique.values(), key=lambda item: item["distance_km"]
        )

        if hotspots:
            status = "detections_found"
            message = (
                f"NASA FIRMS returned {len(hotspots)} thermal detections "
                f"within {radius_km:g} km across {len(sources_checked)} "
                f"successfully queried satellite feeds."
            )
        elif sources_checked:
            status = "no_detections"
            message = (
                f"NASA FIRMS feeds responded successfully, but no detections "
                f"were found within {radius_km:g} km in the latest "
                f"{cls.DAY_RANGE} days."
            )
        else:
            status = "api_error"
            message = (
                "NASA FIRMS could not be queried successfully. "
                "Check the MAP_KEY, network connection and API response."
            )

        logger.info(
            "FIRMS status=%s, detections=%d, sources_ok=%d, errors=%d",
            status, len(hotspots), len(sources_checked), len(source_errors)
        )

        return {
            "status": status,
            "message": message,
            "hotspots": hotspots,
            "bbox": bbox,
            "day_range": cls.DAY_RANGE,
            "sources_checked": sources_checked,
            "source_errors": source_errors,
        }

    @classmethod
    def analyze_location(cls, lat: float, lon: float) -> Dict[str, Any]:
        result = cls.fetch_firms_data(lat, lon, radius_km=100.0)
        hotspots = result["hotspots"]
        return {
            "detected": bool(hotspots),
            "status": result["status"],
            "status_message": result["message"],
            "all_nearby": hotspots,
            "search_radius_km": 100.0,
            "bbox": result.get("bbox"),
            "day_range": result.get("day_range"),
            "sources_checked": result.get("sources_checked", []),
            "source_errors": result.get("source_errors", []),
        }
