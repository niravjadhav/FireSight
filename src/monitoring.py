import time
from typing import Dict, Any, List
from src.config import PUNE_CONFIG
from src.active_fire import ActiveFireDetector
from src.utils import logger

class PuneAutoMonitor:
    def __init__(self):
        self.seen_event_ids = set()

    def check_pune_hotspots(self) -> List[Dict[str, Any]]:
        """Queries Pune boundary for active hotspots and returns unique new alerts."""
        lat, lon = PUNE_CONFIG["lat"], PUNE_CONFIG["lon"]
        radius = PUNE_CONFIG["radius_km"]
        
        hotspots = ActiveFireDetector.fetch_firms_hotspots(lat, lon, radius_km=radius)
        new_alerts = []

        for h in hotspots:
            # Generate deterministic UID for deduplication
            uid = f"{h['latitude']}_{h['longitude']}_{h['acq_date']}_{h['acq_time']}"
            if uid not in self.seen_event_ids:
                self.seen_event_ids.add(uid)
                new_alerts.append(h)

        if new_alerts:
            logger.info(f"🚨 Automatic Monitoring: {len(new_alerts)} NEW fire alerts in Pune region!")
        return new_alerts