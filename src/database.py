import sqlite3
import json
from pathlib import Path
from typing import Dict, Any, List
from src.config import DB_PATH
from src.utils import logger

class DatabaseManager:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS fire_events (
                    event_id TEXT PRIMARY KEY,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    detection_time TEXT NOT NULL,
                    satellite_source TEXT,
                    confidence TEXT,
                    frp REAL,
                    risk_score REAL,
                    risk_level TEXT,
                    is_active INTEGER,
                    has_damage_assessment INTEGER,
                    composite_severity_score REAL,
                    recovery_priority TEXT,
                    full_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            conn.commit()

    def save_event(self, event_data: Dict[str, Any]) -> str:
        event_id = event_data.get("event_id") or f"evt_{int(sqlite3.time.time())}"
        lat = event_data["location"]["latitude"]
        lon = event_data["location"]["longitude"]
        det_time = event_data.get("timestamp")
        
        active_info = event_data.get("active_fire", {})
        is_active = 1 if active_info.get("detected") else 0
        sat = active_info.get("nearest_detection", {}).get("satellite") if is_active else "N/A"
        conf = str(active_info.get("nearest_detection", {}).get("confidence", "N/A"))
        frp = float(active_info.get("nearest_detection", {}).get("frp", 0.0)) if is_active else 0.0

        risk_score = event_data.get("wildfire_risk", {}).get("score", 0.0)
        risk_level = event_data.get("wildfire_risk", {}).get("level", "LOW")
        
        dmg = event_data.get("damage_assessment", {})
        has_dmg = 1 if dmg.get("available") else 0
        
        sev_score = event_data.get("severity", {}).get("score")
        rec_priority = event_data.get("recovery", {}).get("priority")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO fire_events 
                (event_id, latitude, longitude, detection_time, satellite_source, confidence, 
                 frp, risk_score, risk_level, is_active, has_damage_assessment, 
                 composite_severity_score, recovery_priority, full_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (event_id, lat, lon, det_time, sat, conf, frp, risk_score, risk_level, 
                  is_active, has_dmg, sev_score, rec_priority, json.dumps(event_data)))
            conn.commit()
        logger.info(f"Saved event record: {event_id}")
        return event_id