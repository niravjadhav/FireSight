import numpy as np
from typing import Dict

class SatelliteAnalysisEngine:
    @staticmethod
    def generate_synthetic_sentinel_bands(size: int = 64, burned: bool = False) -> Dict[str, np.ndarray]:
        """
        Generates multispectral Sentinel-2 band arrays (B4: Red, B8: NIR, B12: SWIR-2).
        Utilizes normalized satellite reflectances [0.0 - 1.0].
        """
        np.random.seed(42 if burned else 21)
        base = np.random.uniform(0.1, 0.3, (size, size))
        
        if not burned:
            # Healthy vegetation: High NIR, Low Red, Low SWIR
            b4_red = base * 0.4
            b8_nir = base * 2.5 + 0.3
            b12_swir = base * 0.6
        else:
            # Burned land: Low NIR, High SWIR, High Red
            x, y = np.ogrid[:size, :size]
            center = (size // 2, size // 2)
            mask = (x - center[0])**2 + (y - center[1])**2 <= (size // 3)**2
            
            b4_red = base * 0.8
            b4_red[mask] += 0.25
            
            b8_nir = base * 2.0
            b8_nir[mask] = base[mask] * 0.3
            
            b12_swir = base * 0.8
            b12_swir[mask] += 0.45

        return {"B4": b4_red, "B8": b8_nir, "B12": b12_swir}

    @classmethod
    def compute_indices(cls, bands: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        """Calculates NDVI = (NIR - RED)/(NIR + RED) and NBR = (NIR - SWIR)/(NIR + SWIR)"""
        b4, b8, b12 = bands["B4"], bands["B8"], bands["B12"]
        
        ndvi = (b8 - b4) / np.maximum((b8 + b4), 1e-5)
        nbr = (b8 - b12) / np.maximum((b8 + b12), 1e-5)
        
        return {"NDVI": np.clip(ndvi, -1.0, 1.0), "NBR": np.clip(nbr, -1.0, 1.0)}
    