import math
import logging
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("FireSight")

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the distance between two points on Earth in kilometers."""
    R = 6371.0  # Earth's radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2.0) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

def get_utc_timestamp() -> str:
    """Return current UTC time formatted as string."""
    return datetime.now(timezone.utc).isoformat()