import argparse
import json
import os
from datetime import datetime, date, timedelta
from src.config import PUNE_CONFIG, HISTORICAL_MATCH_RADIUS_KM
from src.weather import WeatherProvider
from src.active_fire import ActiveFireDetector
from src.risk_prediction import WildfireRiskPredictor
from src.historical_fire import HistoricalFireDatabase
from src.satellite_analysis import SatelliteAnalysisEngine
from src.burned_area import BurnedAreaAnalyzer
from src.vegetation_analysis import VegetationLossAnalyzer
from src.infrastructure_analysis import InfrastructureDamageAnalyzer
from src.severity_scoring import CompositeSeverityScorer
from src.recovery import RecoveryPlanner
from src.database import DatabaseManager
from src.context_aware_intelligence import assess_many
from src.spatiotemporal_intelligence import analyze_hotspots
from src.dsa_intelligence import build_hotspot_graph, prioritize_clusters, summarize_graph
from src.copernicus_sentinel2 import CopernicusSentinel2, CopernicusError

class FireSightOrchestrator:
    def __init__(self):
        self.db = DatabaseManager()

    def test_copernicus_connection(self, lat: float, lon: float) -> dict:
        """Test OAuth credentials and Sentinel Hub Catalog API access."""
        return CopernicusSentinel2().test_connection(lat, lon)

    def run_pipeline(self, lat: float, lon: float, is_pune_auto: bool = False) -> dict:
        timestamp = datetime.utcnow().isoformat()
        
        # 1. Fetch Weather Data
        weather = WeatherProvider.fetch_current_weather(lat, lon)
        
        # 2. Point-based risk plus a separate 100 km regional FWI estimate.
        risk = WildfireRiskPredictor.calculate_risk(weather, lat, lon)
        try:
            regional_fwi = WeatherProvider.fetch_regional_fwi(
                lat, lon, radius_km=100.0, spacing_km=50.0
            )
        except Exception as exc:
            regional_fwi = {"available": False, "reason": f"Regional FWI calculation failed: {exc}",
                            "radius_km": 100.0}
        
        # 3. Detect Active Satellite Thermal Hotspots
        active_fire = ActiveFireDetector.analyze_location(lat, lon)

        # Enrich actual FIRMS observations with transparent contextual scores and clusters.
        hotspots = active_fire.get("all_nearby", []) or []
        hotspot_assessments = assess_many(hotspots, weather)
        hotspot_clusters = analyze_hotspots(hotspots)
        hotspot_graph = build_hotspot_graph(hotspot_clusters)
        cluster_queue = prioritize_clusters(hotspot_clusters, hotspot_assessments)
        active_fire["intelligence"] = {
            "assessments": hotspot_assessments,
            "clusters": hotspot_clusters,
            "graph": hotspot_graph,
            "graph_summary": summarize_graph(hotspot_graph),
            "priority_queue": cluster_queue,
            "score_note": "Heuristic prioritization score, not a calibrated wildfire probability."
        }
        
        # 4. Historical context is informational only; it must never trigger
        # a current post-fire severity assessment.
        hist_check = HistoricalFireDatabase.check_historical_event(lat, lon, radius_km=HISTORICAL_MATCH_RADIUS_KM)

        # 5. Real Sentinel-2 post-fire assessment.
        # A FIRMS hotspot supplies the event location/date. Historical matches
        # alone never trigger a current damage assessment.
        damage_assessment = {
            "available": False,
            "reason": "No active FIRMS hotspot was returned; no current fire event is available for post-fire assessment.",
            "data_status": "unavailable"
        }
        composite_severity = {
            "composite_score": None,
            "severity_level": None,
            "status": "NOT ASSESSED"
        }
        recovery_plan = {
            "recovery_priority": None,
            "recommendations": [],
            "status": "unavailable"
        }

        if hotspots:
            # Try several recent FIRMS events rather than allowing one high-FRP,
            # very recent detection to block the entire Sentinel-2 assessment.
            # FIRMS NRT Area API is queried for up to 5 days; events are tried
            # oldest-first so they have the greatest chance of having a later
            # Sentinel-2 acquisition.
            today_utc = datetime.utcnow().date()
            dated_events = []
            for candidate in hotspots:
                try:
                    candidate_day = date.fromisoformat(
                        str(candidate.get("acq_date", ""))[:10]
                    )
                except (TypeError, ValueError):
                    continue
                if candidate_day < today_utc:
                    dated_events.append((candidate, candidate_day))

            dated_events.sort(
                key=lambda pair: (
                    pair[1],
                    -float(pair[0].get("frp") or 0.0),
                )
            )

            # Limit catalogue calls so a region with hundreds of detections
            # does not trigger an excessive number of Sentinel Hub requests.
            candidate_events = [item for item, _ in dated_events[:8]]
            if not candidate_events:
                candidate_events = sorted(
                    hotspots,
                    key=lambda item: float(item.get("frp") or 0.0),
                    reverse=True,
                )[:1]

            search_days = int(os.getenv("SENTINEL2_SEARCH_DAYS", "180"))
            max_cloud = float(os.getenv("SENTINEL2_MAX_CLOUD", "60"))
            sentinel = CopernicusSentinel2()
            attempts = []
            best_failed_assessment = None
            best_failed_event = None
            successful_pair = None
            selected_event = None

            for candidate in candidate_events:
                event_lat = float(candidate.get("latitude", lat))
                event_lon = float(candidate.get("longitude", lon))
                event_date = str(candidate.get("acq_date", ""))[:10]
                event_info = {
                    "latitude": event_lat,
                    "longitude": event_lon,
                    "date": event_date,
                    "frp": candidate.get("frp"),
                    "confidence": candidate.get("confidence"),
                    "distance_from_target_km": candidate.get("distance_km"),
                    "selection_basis": (
                        "oldest recent FIRMS event first; FRP breaks same-date ties"
                    ),
                }
                try:
                    pair = sentinel.assess_fire_event(
                        event_lat,
                        event_lon,
                        event_date,
                        search_days=search_days,
                        max_cloud=max_cloud,
                    )
                    attempts.append({
                        "event": event_info,
                        "available": bool(pair.get("available")),
                        "reason": pair.get("reason"),
                        "pre_scene_count": pair.get("pre_scene_count", 0),
                        "post_scene_count": pair.get("post_scene_count", 0),
                    })
                    if pair.get("available"):
                        successful_pair = pair
                        selected_event = event_info
                        break

                    # Retain the failure with the most evidence of available
                    # imagery, instead of showing only the last attempted event.
                    score = (
                        int(pair.get("post_scene_count", 0) or 0),
                        int(pair.get("pre_scene_count", 0) or 0),
                    )
                    old_score = (
                        int((best_failed_assessment or {}).get("post_scene_count", 0) or 0),
                        int((best_failed_assessment or {}).get("pre_scene_count", 0) or 0),
                    )
                    if best_failed_assessment is None or score > old_score:
                        best_failed_assessment = pair
                        best_failed_event = event_info
                except CopernicusError as exc:
                    damage_assessment.update({
                        "reason": str(exc),
                        "data_status": "connection_or_data_error",
                        "selected_event": event_info,
                    })
                    attempts.append({
                        "event": event_info,
                        "available": False,
                        "reason": str(exc),
                        "error_type": "CopernicusError",
                    })
                    # A service/authentication failure is unlikely to improve
                    # by repeating the same API call for another hotspot.
                    break
                except Exception as exc:
                    damage_assessment.update({
                        "reason": f"Sentinel-2 assessment failed: {exc}",
                        "data_status": "processing_error",
                        "selected_event": event_info,
                    })
                    attempts.append({
                        "event": event_info,
                        "available": False,
                        "reason": str(exc),
                        "error_type": type(exc).__name__,
                    })
                    break

            damage_assessment["candidate_attempts"] = attempts
            damage_assessment["candidate_events_checked"] = len(attempts)

            if successful_pair and selected_event:
                satellite_pair = successful_pair
                event_lat = selected_event["latitude"]
                event_lon = selected_event["longitude"]
                event_date = selected_event["date"]

                pre_indices = SatelliteAnalysisEngine.compute_indices(
                    satellite_pair["pre_bands"]
                )
                post_indices = SatelliteAnalysisEngine.compute_indices(
                    satellite_pair["post_bands"]
                )
                burn_metrics = BurnedAreaAnalyzer.calculate_burn_metrics(
                    pre_indices["NBR"],
                    post_indices["NBR"],
                    pixel_res_m=satellite_pair.get("pixel_resolution_m", 20.0),
                )
                vegetation_metrics = VegetationLossAnalyzer.calculate_vegetation_loss(
                    pre_indices["NDVI"], post_indices["NDVI"]
                )
                composite_severity = CompositeSeverityScorer.calculate_composite_score(
                    burn_metrics, vegetation_metrics
                )
                composite_severity["status"] = "ASSESSED_FROM_REAL_SENTINEL2"
                recovery_plan = RecoveryPlanner.generate_plan(
                    composite_severity["severity_level"],
                    burn_metrics["burned_area_ha"],
                )
                damage_assessment = {
                    "available": True,
                    "data_status": "real_satellite_observations",
                    "burn_metrics": burn_metrics,
                    "vegetation_metrics": vegetation_metrics,
                    "infrastructure_metrics": InfrastructureDamageAnalyzer.assess_infrastructure(False),
                    "satellite_source": satellite_pair["source"],
                    "event": {
                        **selected_event,
                        "selection_basis": "first successful Sentinel-2 pre/post pair among up to 8 recent FIRMS events",
                    },
                    "selected_event": selected_event,
                    "regional_radius_km": 100.0,
                    "regional_detection_count": len(hotspots),
                    "pre_scene": satellite_pair["pre_scene"],
                    "post_scene": satellite_pair["post_scene"],
                    "bbox": satellite_pair["bbox"],
                    "pixel_resolution_m": satellite_pair["pixel_resolution_m"],
                    "search_days": satellite_pair.get("search_days"),
                    "max_cloud": satellite_pair.get("max_cloud"),
                    "pre_scene_count": satellite_pair.get("pre_scene_count"),
                    "post_scene_count": satellite_pair.get("post_scene_count"),
                    "candidate_attempts": attempts,
                    "candidate_events_checked": len(attempts),
                    "note": "Burned-area estimates are derived from the selected real Sentinel-2 image pair and dNBR threshold; validate visually before operational use.",
                }
            elif best_failed_assessment is not None:
                damage_assessment.update(best_failed_assessment)
                damage_assessment["selected_event"] = best_failed_event
                damage_assessment["data_status"] = "imagery_not_available"

        output = {
            "mode": "Pune Region Auto-Monitoring" if is_pune_auto else "Manual Coordinate Analysis",
            "location": {"latitude": lat, "longitude": lon},
            "timestamp": timestamp,
            "weather": weather,
            "wildfire_risk": risk,
            "regional_fwi": regional_fwi,
            "active_fire": active_fire,
            "hotspot_intelligence": active_fire["intelligence"],
            "historical_match": hist_check,
            "analysis_radius_km": 100.0,
            "damage_assessment": damage_assessment,
            "severity": composite_severity,
            "recovery": recovery_plan
        }

        event_id = self.db.save_event(output)
        output["event_id"] = event_id
        return output

def main():
    parser = argparse.ArgumentParser(description="FireSight AI Engine")
    parser.add_argument("--mode", choices=["auto", "manual"], default="manual", help="Execution mode")
    parser.add_argument("--lat", type=float, default=PUNE_CONFIG["lat"], help="Latitude for manual mode")
    parser.add_argument("--lon", type=float, default=PUNE_CONFIG["lon"], help="Longitude for manual mode")
    
    args = parser.parse_args()
    orchestrator = FireSightOrchestrator()
    
    if args.mode == "auto":
        res = orchestrator.run_pipeline(PUNE_CONFIG["lat"], PUNE_CONFIG["lon"], is_pune_auto=True)
    else:
        res = orchestrator.run_pipeline(args.lat, args.lon, is_pune_auto=False)
        
    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    main()