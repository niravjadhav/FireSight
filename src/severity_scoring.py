from typing import Dict, Any
from src.config import SEVERITY_WEIGHTS

class CompositeSeverityScorer:
    @staticmethod
    def calculate_composite_score(burn_metrics: Dict[str, Any], veg_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Computes composite 0-100 Post-Fire Severity Score."""
        dnbr_mean = burn_metrics.get("dnbr_mean", 0.0)
        burned_ha = burn_metrics.get("burned_area_ha", 0.0)
        veg_loss_pct = veg_metrics.get("vegetation_loss_percentage", 0.0)

        # Scale dNBR (0.0 to 0.8) -> 0-100
        sev_part = min(100.0, max(0.0, (dnbr_mean / 0.7) * 100.0))
        # Scale Area (0 to 500 ha) -> 0-100
        area_part = min(100.0, max(0.0, (burned_ha / 500.0) * 100.0))
        # Veg loss is already 0-100
        veg_part = veg_loss_pct

        score = (
            sev_part * SEVERITY_WEIGHTS["burn_severity"] +
            area_part * SEVERITY_WEIGHTS["burned_area"] +
            veg_part * SEVERITY_WEIGHTS["vegetation_loss"]
        )

        score = round(float(score), 1)

        if score < 25.0:
            level = "LOW"
        elif score < 50.0:
            level = "MODERATE"
        elif score < 75.0:
            level = "HIGH"
        else:
            level = "CRITICAL"

        return {
            "composite_score": score,
            "severity_level": level
        }