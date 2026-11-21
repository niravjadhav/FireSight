import numpy as np
from typing import Dict, Any

class VegetationLossAnalyzer:
    @staticmethod
    def calculate_vegetation_loss(pre_ndvi: np.ndarray, post_ndvi: np.ndarray) -> Dict[str, Any]:
        """Calculates dNDVI and assesses loss of green biomass."""
        dndvi = pre_ndvi - post_ndvi
        mean_pre = float(np.mean(pre_ndvi))
        mean_post = float(np.mean(post_ndvi))
        mean_loss = float(np.mean(dndvi))
        
        pct_loss = (mean_loss / max(mean_pre, 1e-5)) * 100.0
        
        return {
            "pre_fire_ndvi_mean": round(mean_pre, 3),
            "post_fire_ndvi_mean": round(mean_post, 3),
            "ndvi_change_mean": round(mean_loss, 3),
            "vegetation_loss_percentage": round(float(np.clip(pct_loss, 0.0, 100.0)), 1)
        }