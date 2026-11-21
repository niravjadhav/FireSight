"""Canadian Fire Weather Index (FWI) calculation.

Implements the daily FFMC, DMC, DC, ISI, BUI and FWI equations from the
Canadian Forest Fire Weather Index System. Inputs are daily observations near
local noon plus 24-hour precipitation. The caller must provide a multi-day
sequence. Initial moisture codes are explicitly provisional defaults; local
calibration and a longer spin-up are recommended before operational use.
"""
from __future__ import annotations
import math
from typing import Any, Dict, List


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _ffmc(temp: float, rh: float, wind: float, rain: float, previous: float) -> float:
    mo = 147.2 * (101.0 - previous) / (59.5 + previous)
    if rain > 0.5:
        rf = rain - 0.5
        if mo > 150.0:
            mo += 42.5 * rf * math.exp(-100.0 / (251.0 - mo)) * (1.0 - math.exp(-6.93 / rf))
        else:
            mo += 42.5 * rf * math.exp(-100.0 / (251.0 - mo)) * (1.0 - math.exp(-6.93 / rf)) + 0.0015 * (mo - 150.0) ** 2 * math.sqrt(rf)
        mo = min(mo, 250.0)
    ed = 0.942 * rh**0.679 + 11.0 * math.exp((rh - 100.0) / 10.0) + 0.18 * (21.1 - temp) * (1.0 - math.exp(-0.115 * rh))
    if mo > ed:
        ko = 0.424 * (1.0 - (rh / 100.0) ** 1.7) + 0.0694 * math.sqrt(wind) * (1.0 - (rh / 100.0) ** 8)
        kd = ko * 0.581 * math.exp(0.0365 * temp)
        m = ed + (mo - ed) * 10.0 ** (-kd)
    else:
        ew = 0.618 * rh**0.753 + 10.0 * math.exp((rh - 100.0) / 10.0) + 0.18 * (21.1 - temp) * (1.0 - math.exp(-0.115 * rh))
        if mo < ew:
            kl = 0.424 * (1.0 - ((100.0 - rh) / 100.0) ** 1.7) + 0.0694 * math.sqrt(wind) * (1.0 - ((100.0 - rh) / 100.0) ** 8)
            kw = kl * 0.581 * math.exp(0.0365 * temp)
            m = ew - (ew - mo) * 10.0 ** (-kw)
        else:
            m = mo
    return _clamp(59.5 * (250.0 - m) / (147.2 + m), 0.0, 101.0)


def _day_length_factor_dmc(latitude: float, month: int) -> float:
    # Standard Canadian DMC day-length factors, interpolated by broad latitude band.
    north = {1:6.5,2:7.5,3:9.0,4:12.8,5:13.9,6:13.9,7:12.4,8:10.9,9:9.4,10:8.0,11:7.0,12:6.0}
    mid = {1:7.9,2:8.4,3:9.2,4:10.2,5:11.2,6:11.8,7:11.5,8:10.4,9:9.4,10:8.6,11:8.0,12:7.5}
    south = {1:9.0,2:9.0,3:9.0,4:9.0,5:9.0,6:9.0,7:9.0,8:9.0,9:9.0,10:9.0,11:9.0,12:9.0}
    if latitude >= 30: return north[month]
    if latitude >= 10: return mid[month]
    return south[month]


def _dmc(temp: float, rh: float, rain: float, previous: float, latitude: float, month: int) -> float:
    effective_rain = rain
    if rain > 1.5:
        re = 0.92 * rain - 1.27
        mo = 20.0 + math.exp(5.6348 - previous / 43.43)
        if previous <= 33.0:
            b = 100.0 / (0.5 + 0.3 * previous)
        elif previous <= 65.0:
            b = 14.0 - 1.3 * math.log(previous)
        else:
            b = 6.2 * math.log(previous) - 17.2
        mr = mo + 1000.0 * re / (48.77 + b * re)
        pr = max(0.0, 244.72 - 43.43 * math.log(max(mr - 20.0, 0.1)))
    else:
        pr = previous
    if temp > -1.1:
        k = 1.894 * (temp + 1.1) * (100.0 - rh) * _day_length_factor_dmc(latitude, month) * 1e-6
    else:
        k = 0.0
    return max(0.0, pr + 100.0 * k)


def _day_length_factor_dc(latitude: float, month: int) -> float:
    # Seasonal DC factors for the northern hemisphere; southern values are shifted six months.
    table = {1:-1.6,2:-1.6,3:-1.6,4:0.9,5:3.8,6:5.8,7:6.4,8:5.0,9:2.4,10:0.4,11:-1.6,12:-1.6}
    if latitude < 0:
        month = ((month + 5) % 12) + 1
    return table[month]


def _dc(temp: float, rain: float, previous: float, latitude: float, month: int) -> float:
    if rain > 2.8:
        rd = 0.83 * rain - 1.27
        qo = 800.0 * math.exp(-previous / 400.0)
        qr = qo + 3.937 * rd
        dr = max(0.0, 400.0 * math.log(800.0 / max(qr, 1.0)))
    else:
        dr = previous
    seasonal = _day_length_factor_dc(latitude, month)
    v = 0.36 * (temp + 2.8) + seasonal
    return max(0.0, dr + max(0.0, v) * 0.5)


def _isi(ffmc: float, wind: float) -> float:
    mo = 147.2 * (101.0 - ffmc) / (59.5 + ffmc)
    ff = 19.115 * math.exp(-0.1386 * mo) * (1.0 + mo**5.31 / 4.93e7)
    return max(0.0, 0.208 * math.exp(0.05039 * wind) * ff)


def _bui(dmc: float, dc: float) -> float:
    if dmc <= 0.4 * dc:
        return 0.8 * dmc * dc / (dmc + 0.4 * dc) if dmc + 0.4 * dc else 0.0
    return dmc - (1.0 - 0.8 * dc / (dmc + 0.4 * dc)) * (0.92 + (0.0114 * dmc) ** 1.7)


def _fwi(isi: float, bui: float) -> float:
    if bui <= 80.0:
        fd = 0.626 * bui**0.809 + 2.0
    else:
        fd = 1000.0 / (25.0 + 108.64 * math.exp(-0.023 * bui))
    b = 0.1 * isi * fd
    return b if b <= 1.0 else math.exp(2.72 * (0.434 * math.log(b)) ** 0.647)


def calculate_fwi_series(days: List[Dict[str, Any]], latitude: float) -> Dict[str, Any]:
    """Calculate daily FWI from oldest to newest. Each day needs date,temp,rh,wind,rain."""
    if len(days) < 7:
        return {
            "available": False,
            "reason": (
                f"Only {len(days)} complete daily observations are available. "
                "At least 7 are required for this experimental FWI estimate; "
                "30 days are preferred for a longer spin-up."
            ),
        }
    ffmc, dmc, dc = 85.0, 6.0, 15.0  # conventional provisional start-up codes
    outputs = []
    previous_date = None
    for day in days:
        date = str(day.get("date", ""))
        try:
            month = int(date[5:7])
            if len(date) < 10:
                raise ValueError("date must use YYYY-MM-DD format")
            from datetime import date as _date
            parsed_date = _date.fromisoformat(date[:10])
            if previous_date is not None and parsed_date <= previous_date:
                raise ValueError("daily observations must be in strictly increasing date order")
            previous_date = parsed_date

            required = ("temperature", "humidity", "wind_speed", "rainfall")
            missing = [key for key in required if day.get(key) is None]
            if missing:
                raise ValueError("missing " + ", ".join(missing))

            temp = float(day["temperature"])
            rh = float(day["humidity"])
            wind = float(day["wind_speed"])
            rain = float(day["rainfall"])
            if not all(math.isfinite(v) for v in (temp, rh, wind, rain)):
                raise ValueError("weather values must be finite numbers")
            rh = _clamp(rh, 0, 100)
            wind = max(0.0, wind)
            rain = max(0.0, rain)
            if not (-50 <= temp <= 60 and 0 <= rh <= 100 and wind <= 200 and rain <= 500):
                raise ValueError("daily weather outside plausible physical bounds")
            ffmc = _ffmc(temp, rh, wind, rain, ffmc)
            dmc = _dmc(temp, rh, rain, dmc, latitude, month)
            dc = _dc(temp, rain, dc, latitude, month)
            isi = _isi(ffmc, wind); bui = max(0.0, _bui(dmc, dc)); fwi = _fwi(isi, bui)
            outputs.append({"date": date, "FFMC": round(ffmc, 1), "DMC": round(dmc, 1), "DC": round(dc, 1),
                            "ISI": round(isi, 2), "BUI": round(bui, 1), "FWI": round(fwi, 2)})
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            return {"available": False, "reason": f"Invalid daily weather history: {exc}"}
    latest = outputs[-1]
    # FWI is a continuous index, not a probability. Bands are broad screening labels only.
    value = latest["FWI"]
    level = "LOW" if value < 5 else "MODERATE" if value < 10 else "HIGH" if value < 20 else "VERY HIGH"
    return {"available": True, "score": value, "fwi": value, "level": level,
            "components": latest, "history": outputs,
            "initialization": (
                "Provisional start-up codes FFMC=85, DMC=6, DC=15. "
                "30-day spin-up is preferred; result remains experimental and not locally calibrated."
            ),
            "input_quality": (
                "Uses supplied daily weather sequence. If inputs are daily means/maxima rather than "
                "standard local-noon observations and 24-hour precipitation, treat the result as an estimate."
            ),
            "score_type": "Canadian Fire Weather Index (FWI) on its native scale; not a fire probability."}
