"""Copernicus Data Space / Sentinel Hub integration for real Sentinel-2 L2A data.

Secrets are read only from environment variables. Never place OAuth credentials in
browser code or log them. The module intentionally requires a FIRMS event date
before it computes post-fire metrics.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Optional
import os
import requests

TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
CATALOG_URL = "https://sh.dataspace.copernicus.eu/catalog/v1/search"
PROCESS_URL = "https://sh.dataspace.copernicus.eu/process/v1"
TIMEOUT = 60


class CopernicusError(RuntimeError):
    pass


class CopernicusSentinel2:
    def __init__(self, client_id: Optional[str] = None, client_secret: Optional[str] = None):
        self.client_id = (client_id or os.getenv("COPERNICUS_CLIENT_ID", "")).strip()
        self.client_secret = (client_secret or os.getenv("COPERNICUS_CLIENT_SECRET", "")).strip()
        self._token = None

    def _get_token(self) -> str:
        if not self.client_id or not self.client_secret:
            raise CopernicusError(
                "Missing COPERNICUS_CLIENT_ID or COPERNICUS_CLIENT_SECRET in the project .env file."
            )
        response = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        if response.status_code != 200:
            # Do not include request body or credentials in error messages.
            raise CopernicusError(
                f"Copernicus OAuth failed (HTTP {response.status_code}). "
                "Check that the client is active, the ID/secret are correct, and the secret was copied completely."
            )
        payload = response.json()
        token = payload.get("access_token")
        if not token:
            raise CopernicusError("Copernicus OAuth response did not contain an access token.")
        self._token = token
        return token

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self._token or self._get_token()}"}

    @staticmethod
    def make_bbox(lat: float, lon: float, radius_km: float = 1.0):
        # Approximate WGS84 bounding box. Latitude degrees ~111 km; longitude
        # degrees shrink by cos(latitude).
        import math
        dlat = radius_km / 111.0
        dlon = radius_km / (111.0 * max(0.1, math.cos(math.radians(lat))))
        return [lon - dlon, lat - dlat, lon + dlon, lat + dlat]

    def search_scenes(self, bbox, start_date: date, end_date: date, max_cloud: float = 60.0):
        """Search Sentinel-2 L2A scenes using Catalog context.next pagination."""
        body = {
            "collections": ["sentinel-2-l2a"],
            "bbox": bbox,
            "datetime": (
                f"{start_date.isoformat()}T00:00:00Z/"
                f"{end_date.isoformat()}T23:59:59Z"
            ),
            "limit": 100,
        }
        headers = {**self._headers(), "Content-Type": "application/json"}
        features = []
        page_count = 0
        max_pages = 10
        next_token = None



        while page_count < max_pages:
            page_body = dict(body)
            if next_token is not None:
                page_body["next"] = next_token

            response = requests.post(
                CATALOG_URL, json=page_body, headers=headers, timeout=TIMEOUT
            )
            if response.status_code >= 400:
                raise CopernicusError(
                    f"Sentinel-2 catalogue search failed (HTTP {response.status_code}): "
                    f"{response.text[:350]}"
                )
            try:
                payload = response.json()
            except ValueError as exc:
                raise CopernicusError(
                    "Sentinel-2 catalogue returned an unreadable response."
                ) from exc


            features.extend(payload.get("features", []) or [])
            page_count += 1
            next_token = (payload.get("context") or {}).get("next")
            if next_token is None:
                break

        scenes = []
        for feature in features:
            props = feature.get("properties", {})
            acquired = props.get("datetime")
            if not acquired:
                continue
            cloud = props.get("eo:cloud_cover")
            try:
                cloud_value = float(cloud) if cloud is not None else None
            except (TypeError, ValueError):
                cloud_value = None
            if cloud_value is not None and cloud_value > max_cloud:
                continue
            scenes.append({
                "id": feature.get("id"),
                "datetime": acquired,
                "date": acquired[:10],
                "cloud_cover": cloud_value,
            })

        # Keep one scene per acquisition date; prefer the lowest cloud cover.
        unique = {}
        for scene in scenes:
            key = scene["date"]
            old = unique.get(key)
            new_cloud = scene["cloud_cover"] if scene["cloud_cover"] is not None else 100
            old_cloud = old["cloud_cover"] if old and old["cloud_cover"] is not None else 100
            if old is None or new_cloud < old_cloud:
                unique[key] = scene

        result = sorted(unique.values(), key=lambda item: item["datetime"])
        self.last_search_diagnostics = {
            "raw_feature_count": len(features),
            "usable_scene_count": len(result),
            "pages_read": page_count,
            "date_range": f"{start_date.isoformat()} to {end_date.isoformat()}",
            "max_cloud_percent": max_cloud,
        }
        return result


    def test_connection(self, lat: float, lon: float) -> Dict[str, Any]:
        """Validate OAuth and catalogue access for a small area around the selected target."""
        token = self._get_token()
        bbox = self.make_bbox(lat, lon, radius_km=1.0)
        today = datetime.now(timezone.utc).date()
        scenes = self.search_scenes(bbox, today - timedelta(days=90), today, max_cloud=80)
        return {
            "authenticated": bool(token),
            "catalog_access": True,
            "scene_count": len(scenes),
            "best_scene": scenes[0] if scenes else None,
            "bbox": bbox,
            "diagnostics": getattr(self, "last_search_diagnostics", {}),
            "message": "Copernicus authentication and catalogue access succeeded."
                       if scenes else "Authentication succeeded, but no Sentinel-2 L2A scenes were found for this area and date range."
        }

    def _download_bands(self, bbox, scene_date: str, width: int = 128, height: int = 128, max_cloud: float = 60.0):
        # Request B04 (red), B08 (NIR), B12 (SWIR2) as float reflectance.
        evalscript = """//VERSION=3
function setup() {
  return {
    input: [{ bands: ["B04", "B08", "B12"], units: "REFLECTANCE" }],
    output: { bands: 3, sampleType: "FLOAT32" }
  };
}
function evaluatePixel(sample) {
  return [sample.B04, sample.B08, sample.B12];
}"""
        day_start = f"{scene_date}T00:00:00Z"
        day_end = f"{scene_date}T23:59:59Z"
        body = {
            "input": {
                "bounds": {
                    "bbox": bbox,
                    "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"}
                },
                "data": [{
                    "type": "sentinel-2-l2a",
                    "dataFilter": {
                        "timeRange": {"from": day_start, "to": day_end},
                        "maxCloudCoverage": max_cloud,
                        "mosaickingOrder": "leastCC"
                    }
                }]
            },
            "output": {
                "width": width,
                "height": height,
                "responses": [{"identifier": "default", "format": {"type": "image/tiff"}}]
            },
            "evalscript": evalscript
        }
        response = requests.post(
            PROCESS_URL, json=body,
            headers={**self._headers(), "Content-Type": "application/json", "Accept": "image/tiff"},
            timeout=TIMEOUT,
        )
        if response.status_code >= 400:
            raise CopernicusError(
                f"Sentinel Hub Process API failed for {scene_date} (HTTP {response.status_code}): "
                f"{response.text[:500]}"
            )
        try:
            import rasterio
            from rasterio.io import MemoryFile
            with MemoryFile(response.content) as memfile:
                with memfile.open() as dataset:
                    if dataset.count < 3:
                        raise CopernicusError("Sentinel-2 response did not contain the three requested spectral bands.")
                    return {
                        "B4": dataset.read(1).astype("float32"),
                        "B8": dataset.read(2).astype("float32"),
                        "B12": dataset.read(3).astype("float32"),
                    }
        except ImportError as exc:
            raise CopernicusError("Missing rasterio. Install project dependencies with: pip install -r requirements.txt") from exc
        except CopernicusError:
            raise
        except Exception as exc:
            raise CopernicusError(f"Could not read the Sentinel-2 GeoTIFF response: {exc}") from exc

    def assess_fire_event(self, lat: float, lon: float, event_date: str,
                          search_days: int = 180, max_cloud: float = 60.0) -> Dict[str, Any]:
        """Find one clear pre/post image pair around a FIRMS fire date and compute arrays."""
        try:
            fire_day = date.fromisoformat(str(event_date)[:10])
        except ValueError as exc:
            raise CopernicusError(f"Invalid FIRMS acquisition date: {event_date}") from exc

        today = datetime.now(timezone.utc).date()
        bbox = self.make_bbox(lat, lon, radius_km=1.0)
        pre_start = fire_day - timedelta(days=search_days)
        pre_end = fire_day - timedelta(days=1)
        post_start = fire_day + timedelta(days=1)
        post_end = min(today, fire_day + timedelta(days=search_days))

        if post_start > post_end:
            return {
                "available": False,
                "reason": (
                    f"The selected FIRMS event is dated {fire_day.isoformat()}, so there is "
                    "no post-fire date available yet. Sentinel-2 cannot assess a post-fire "
                    "change until a later acquisition is available. Choose an older FIRMS "
                    "event or retry after the next Sentinel-2 pass."
                ),
                "event_date": fire_day.isoformat(),
                "pre_scene_count": 0,
                "post_scene_count": 0,
                "search_days": search_days,
                "max_cloud": max_cloud,
                "bbox": bbox,
                "diagnostics": {
                    "stage": "date_validation",
                    "pre_date_range": f"{pre_start.isoformat()} to {pre_end.isoformat()}",
                    "post_date_range": "No post-fire date available yet",
                },
            }

        pre_scenes = self.search_scenes(bbox, pre_start, pre_end, max_cloud)
        post_scenes = self.search_scenes(bbox, post_start, post_end, max_cloud)
        if not pre_scenes or not post_scenes:
            missing = []
            if not pre_scenes:
                missing.append("pre-fire")
            if not post_scenes:
                missing.append("post-fire")
            return {
                "available": False,
                "reason": (
                    f"No usable Sentinel-2 L2A {' and '.join(missing)} scene found "
                    f"within the {search_days}-day search window at {max_cloud:.0f}% "
                    "maximum cloud cover."
                ),
                "pre_scene_count": len(pre_scenes),
                "post_scene_count": len(post_scenes),
                "pre_date_range": f"{pre_start.isoformat()} to {pre_end.isoformat()}",
                "post_date_range": f"{post_start.isoformat()} to {post_end.isoformat()}",
                "bbox": bbox,
                "diagnostics": {
                    "stage": "catalogue_search",
                    "pre_scene_count": len(pre_scenes),
                    "post_scene_count": len(post_scenes),
                    "pre_search": getattr(self, "last_search_diagnostics", {}),
                    "post_search": getattr(self, "last_search_diagnostics", {}),
                },
            }

        # Prefer the clearest scene nearest to the event date.
        pre_scene = min(pre_scenes, key=lambda x: (
            abs((fire_day - date.fromisoformat(x["date"])).days),
            x["cloud_cover"] if x["cloud_cover"] is not None else 100,
        ))
        post_scene = min(post_scenes, key=lambda x: (
            abs((date.fromisoformat(x["date"]) - fire_day).days),
            x["cloud_cover"] if x["cloud_cover"] is not None else 100,
        ))

        pre_bands = self._download_bands(bbox, pre_scene["date"], max_cloud=max_cloud)
        post_bands = self._download_bands(bbox, post_scene["date"], max_cloud=max_cloud)
        return {
            "available": True,
            "bbox": bbox,
            "pre_scene": pre_scene,
            "post_scene": post_scene,
            "pre_bands": pre_bands,
            "post_bands": post_bands,
            "pixel_resolution_m": 20.0,
            "search_days": search_days,
            "max_cloud": max_cloud,
            "pre_scene_count": len(pre_scenes),
            "post_scene_count": len(post_scenes),
            "source": "Copernicus Sentinel-2 L2A via Sentinel Hub Process API",
            "diagnostics": {
                "stage": "imagery_downloaded",
                "pre_scene_count": len(pre_scenes),
                "post_scene_count": len(post_scenes),
                "selected_pre_scene": pre_scene,
                "selected_post_scene": post_scene,
            },
        }
