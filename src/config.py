import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# API Keys
FIRMS_MAP_KEY = os.getenv("FIRMS_MAP_KEY", "")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "")
COPERNICUS_CLIENT_ID = os.getenv("COPERNICUS_CLIENT_ID", "")
COPERNICUS_CLIENT_SECRET = os.getenv("COPERNICUS_CLIENT_SECRET", "")

# Database
DB_PATH = BASE_DIR / os.getenv("DATABASE_PATH", "data/firesight.db")

# Pune Region Configuration
PUNE_CONFIG = {
    "name": "Pune Region",
    "lat": 18.5204,
    "lon": 73.8567,
    "bbox": [73.5, 18.2, 74.2, 18.8],
    "radius_km": 50.0
}

# Thresholds & Parameters
SEARCH_RADIUS_KM = 35.0  # Detection radius around requested coordinates
HISTORICAL_MATCH_RADIUS_KM = 25.0
MONITORING_INTERVAL_MINUTES = 15

# Risk Weights (Sum = 1.0)
RISK_WEIGHTS = {
    "temperature": 0.25,
    "humidity": 0.20,
    "wind_speed": 0.20,
    "rainfall": 0.15,
    "historical_freq": 0.10,
    "slope": 0.10
}

# Severity Score Weights (Sum = 1.0)
SEVERITY_WEIGHTS = {
    "burn_severity": 0.35,
    "burned_area": 0.25,
    "vegetation_loss": 0.20,
    "infrastructure": 0.20
}