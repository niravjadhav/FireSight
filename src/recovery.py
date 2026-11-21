from typing import Dict, Any, List


class RecoveryPlanner:
    @staticmethod
    def generate_plan(severity_level: str, burn_ha: float) -> Dict[str, Any]:
        """Generate severity-specific recovery guidance from verified assessment data.

        Recommendations are decision-support suggestions and should be validated by
        local forestry/fire-recovery professionals before field implementation.
        """
        severity = (severity_level or "LOW").upper()
        area = max(0.0, float(burn_ha or 0.0))

        # Large affected areas escalate the response even if the spectral severity
        # class is lower, preserving the project's existing 300 ha threshold.
        if severity == "CRITICAL" or area > 300.0:
            priority = "Critical Priority"
            recs = [
                "Arrange an urgent field assessment with local fire, forestry, and watershed authorities.",
                "Assess steep slopes and drainage pathways; prioritize erosion and sediment-control measures before forecast rainfall.",
                "Identify sensitive habitats, waterways, and infrastructure that may need temporary protection or access restrictions.",
                "Plan phased restoration using locally appropriate native species, guided by field assessment.",
                "Track recovery and secondary hazards with frequent field checks and satellite imagery when available.",
            ]
        elif severity == "HIGH":
            priority = "High Priority"
            recs = [
                "Conduct a focused field inspection of heavily affected zones and nearby slopes.",
                "Prioritize erosion-control and runoff-management measures in vulnerable areas.",
                "Prepare a site-specific native vegetation restoration plan for severely affected patches.",
                "Inspect waterways and drainage for ash, sediment, or other fire-related impacts.",
                "Reassess vegetation recovery with Sentinel-2 NDVI/NBR and field observations at regular intervals.",
            ]
        elif severity == "MODERATE":
            priority = "Moderate Priority"
            recs = [
                "Monitor vegetation recovery using Sentinel-2 NDVI/NBR approximately every 30 days, when imagery is available.",
                "Inspect affected ground for localized erosion, exposed soil, and runoff after rainfall.",
                "Identify patches with poor natural regeneration and consider targeted restoration with locally suitable native species.",
                "Check fire-affected edges for invasive species and manage them where confirmed.",
                "Maintain periodic field observations and update the recovery plan as conditions change.",
            ]
        else:
            priority = "Low Priority"
            recs = [
                "Continue routine vegetation recovery monitoring using satellite imagery and field observations.",
                "Inspect the fire perimeter periodically for erosion or other localized impacts.",
                "Use natural regeneration where recovery is healthy; flag patches showing limited regrowth for review.",
                "Maintain routine prevention and access-area checks during the local fire season.",
            ]

        return {
            "recovery_priority": priority,
            "recommendations": recs,
        }
