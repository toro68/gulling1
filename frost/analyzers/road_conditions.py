from dataclasses import dataclass
from typing import Any, Dict, Tuple

import numpy as np
import pandas as pd

from .base import WeatherRiskAnalyzer


@dataclass
class RoadConditionThresholds:
    """Optimaliserte terskelverdier basert på feature importance"""

    # Temperatur (67.3% viktighet)
    TEMP_ZONES: Dict[str, Tuple[float, float]] = {
        "critical": (-1.0, 0.5),  # Høyest risiko rundt 0°C
        "snow": (-6.0, -1.0),  # Snøforhold
        "mix": (-1.0, 0.2),  # Blandet nedbør
        "rain": (0.2, 6.0),  # Regn
    }

    # Overflatetemperatur (33.4% viktighet)
    SURFACE_TEMP_THRESHOLDS: Dict[str, float] = {
        "critical": 0.5,  # Kritisk grense for isdannelse
        "warning": 2.0,  # Varslingsgrense
    }

    # Nedbør (28% viktighet)
    PRECIP_THRESHOLDS: Dict[str, float] = {
        "light": 0.4,  # Lett nedbør
        "moderate": 2.5,  # Moderat nedbør
        "heavy": 6.0,  # Kraftig nedbør
    }


class RoadConditionAnalyzer(WeatherRiskAnalyzer):
    def __init__(self, df: pd.DataFrame):
        super().__init__(df)
        self.thresholds = RoadConditionThresholds()
        self.required_columns = {
            self.standard_columns["temperature"],
            self.standard_columns["surface_temp"],
            self.standard_columns["precipitation"],
            self.standard_columns["snow_depth"],
        }
        self.validate_data()

    def validate_data(self) -> None:
        """Validerer at nødvendige kolonner eksisterer"""
        self._validate_columns(self.required_columns)

        # Sjekk for ekstreme verdier
        for col in self.required_columns:
            if col in self.df.columns:
                if self.df[col].isna().sum() > len(self.df) * 0.5:
                    self.logger.warning(f"Over 50% manglende verdier i {col}")

    def _calculate_temp_risk(self) -> pd.Series:
        """Beregner risiko basert på lufttemperatur"""
        temp = self.df[self.standard_columns["temperature"]]
        risk = pd.Series(0.0, index=self.df.index)

        for zone, (min_temp, max_temp) in self.thresholds.TEMP_ZONES.items():
            mask = (temp >= min_temp) & (temp <= max_temp)
            if zone == "critical":
                risk[mask] = 0.9
            elif zone == "mix":
                risk[mask] = 0.7
            elif zone == "snow":
                risk[mask] = 0.5
            elif zone == "rain":
                risk[mask] = 0.3

        return risk

    def _calculate_surface_risk(self) -> pd.Series:
        """Beregner risiko basert på overflatetemperatur"""
        surface_temp = self.df[self.standard_columns["surface_temp"]]
        risk = pd.Series(0.0, index=self.df.index)

        critical_mask = (
            surface_temp <= self.thresholds.SURFACE_TEMP_THRESHOLDS["critical"]
        )
        warning_mask = (
            surface_temp <= self.thresholds.SURFACE_TEMP_THRESHOLDS["warning"]
        )

        risk[critical_mask] = 0.9
        risk[warning_mask & ~critical_mask] = 0.6

        return risk

    def _calculate_precip_risk(self) -> pd.Series:
        """Beregner risiko basert på nedbør"""
        precip = self.df[self.standard_columns["precipitation"]]
        risk = pd.Series(0.0, index=self.df.index)

        for intensity, threshold in self.thresholds.PRECIP_THRESHOLDS.items():
            mask = precip >= threshold
            if intensity == "heavy":
                risk[mask] = 0.9
            elif intensity == "moderate":
                risk[mask] = 0.6
            elif intensity == "light":
                risk[mask] = 0.3

        return risk

    def _calculate_snow_risk(self) -> pd.Series:
        """Beregner risiko basert på snødybde og endring"""
        snow_depth = self.df[self.standard_columns["snow_depth"]]
        snow_change = snow_depth.diff()

        depth_risk = (snow_depth / 50).clip(0, 1)
        change_risk = (snow_change.abs() / 5).clip(0, 1)

        return (depth_risk * 0.7 + change_risk * 0.3).fillna(0)

    def calculate_risk(self) -> pd.Series:
        """Beregner samlet risiko for glatt vei"""
        weights = {"temp": 0.338, "surface": 0.334, "precip": 0.280, "snow": 0.048}

        risk = (
            weights["temp"] * self._calculate_temp_risk()
            + weights["surface"] * self._calculate_surface_risk()
            + weights["precip"] * self._calculate_precip_risk()
            + weights["snow"] * self._calculate_snow_risk()
        )

        return risk.clip(0, 1)

    def get_summary(self) -> Dict[str, Any]:
        """Returnerer oppsummering av analysen"""
        risk_series = self.calculate_risk()
        winter_mask = self._get_winter_mask()

        return {
            "mean_risk": float(risk_series[winter_mask].mean()),
            "high_risk_hours": int((risk_series[winter_mask] > 0.7).sum()),
            "risk_levels": {
                "low": float((risk_series[winter_mask] < 0.3).mean()),
                "medium": float(
                    (
                        (risk_series[winter_mask] >= 0.3)
                        & (risk_series[winter_mask] <= 0.7)
                    ).mean()
                ),
                "high": float((risk_series[winter_mask] > 0.7).mean()),
            },
        }
