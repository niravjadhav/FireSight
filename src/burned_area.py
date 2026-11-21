import numpy as np
from typing import Dict, Any

class BurnedAreaAnalyzer:
    @staticmethod
    def calculate_burn_metrics(pre_nbr: np.ndarray, post_nbr: np.ndarray, pixel_res_m: float = 10.0) -> Dict[str, Any]:
        """
        Calculates dNBR = PreNBR - PostNBR and segments burned area based on standard USGS threshold (dNBR > 0.27).
        """
        dnbr = pre_nbr - post_nbr
        burned_pixels = np.sum(dnbr > 0.27)
        
        pixel_area_m2 = pixel_res_m * pixel_res_m
        area_m2 = float(burned_pixels * pixel_area_m2)
        area_ha = float(area_m2 / 10000.0)
        area_km2 = float(area_ha / 100.0)

        # Severity breakdown
        unburned = float(np.sum(dnbr <= 0.1))
        low_sev = float(np.sum((dnbr > 0.1) & (dnbr <= 0.27)))
        mod_sev = float(np.sum((dnbr > 0.27) & (dnbr <= 0.66)))
        high_sev = float(np.sum(dnbr > 0.66))
        total_pixels = float(dnbr.size)

        return {
            "dnbr_mean": float(np.mean(dnbr)),
            "burned_pixels": int(burned_pixels),
            "burned_area_m2": round(area_m2, 2),
            "burned_area_ha": round(area_ha, 2),
            "burned_area_km2": round(area_km2, 4),
            "severity_proportions": {
                "Unburned": round((unburned / total_pixels) * 100, 1),
                "Low": round((low_sev / total_pixels) * 100, 1),
                "Moderate": round((mod_sev / total_pixels) * 100, 1),
                "High": round((high_sev / total_pixels) * 100, 1)
            }
        }