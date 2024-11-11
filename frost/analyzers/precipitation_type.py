import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import pandas as pd


@dataclass
class PrecipitationThresholds:
    """Terskelverdier for nedbørsklassifisering"""

    # Temperaturgrenser for nedbørstype
    temp_snow: float = -1.0  # Under denne er det snø
    temp_mix_low: float = -1.0  # Nedre grense for sludd
    temp_mix_high: float = 2.0  # Øvre grense for sludd

    # Intensitetsgrenser (mm/time)
    intensity_light: float = 0.4  # Lett nedbør
    intensity_moderate: float = 2.5  # Moderat nedbør
    intensity_heavy: float = 6.0  # Kraftig nedbør


class PrecipitationTypeAnalyzer:
    """Analyserer type og intensitet av nedbør"""

    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.thresholds = PrecipitationThresholds()
        self.logger = logging.getLogger(self.__class__.__name__)

        # Påkrevde kolonner
        self.required_columns = {
            "temperature": "air_temperature",
            "precipitation": "sum(precipitation_amount PT1H)",
            "humidity": "relative_humidity",
            "dew_point": "dew_point_temperature",
        }

        self.validate_data()

    def validate_data(self) -> None:
        """Validerer at nødvendige kolonner eksisterer"""
        missing = set(self.required_columns.values()) - set(self.df.columns)
        if missing:
            raise ValueError(f"Mangler påkrevde kolonner: {missing}")

    def analyze(self) -> pd.DataFrame:
        """Hovedanalyse av nedbørstype og intensitet"""
        results = self.df.copy()

        # Klassifiser nedbør
        results["precip_type"] = self._classify_precipitation_type()
        results["precip_intensity"] = self._classify_intensity()

        # Beregn sannsynligheter
        probs = self._calculate_probabilities()
        results["snow_prob"] = probs["snow"]
        results["rain_prob"] = probs["rain"]
        results["mixed_prob"] = probs["mixed"]

        # Beregn risiko for overgang mellom typer
        results["transition_risk"] = self._calculate_transition_risk()

        return results

    def _classify_precipitation_type(self) -> pd.Series:
        """Klassifiserer nedbørstype basert på temperatur og duggpunkt"""
        temp = self.df[self.required_columns["temperature"]]
        precip = self.df[self.required_columns["precipitation"]]

        # Kun klassifiser når det faktisk er nedbør
        type_series = pd.Series("none", index=self.df.index)
        has_precip = precip > 0

        conditions = [
            (temp <= self.thresholds.temp_snow) & has_precip,
            (temp > self.thresholds.temp_mix_low)
            & (temp <= self.thresholds.temp_mix_high)
            & has_precip,
            (temp > self.thresholds.temp_mix_high) & has_precip,
        ]
        choices = ["snow", "mixed", "rain"]

        return pd.Series(
            np.select(conditions, choices, default="none"), index=self.df.index
        )

    def _classify_intensity(self) -> pd.Series:
        """Klassifiserer nedbørintensitet"""
        precip = self.df[self.required_columns["precipitation"]]

        conditions = [
            (precip > self.thresholds.intensity_heavy),
            (precip > self.thresholds.intensity_moderate),
            (precip > self.thresholds.intensity_light),
            (precip > 0),
        ]
        choices = ["heavy", "moderate", "light", "trace"]

        return pd.Series(
            np.select(conditions, choices, default="none"), index=self.df.index
        )

    def _calculate_probabilities(self) -> Dict[str, pd.Series]:
        """Beregner sannsynlighet for hver nedbørstype"""
        temp = self.df[self.required_columns["temperature"]]
        humidity = self.df[self.required_columns["humidity"]]

        # Temperaturbaserte sannsynligheter
        snow_prob = 1 - (1 / (1 + np.exp(-0.5 * (temp + 1))))
        rain_prob = 1 / (1 + np.exp(-0.5 * (temp - 2)))
        mixed_prob = 1 - (snow_prob + rain_prob)

        # Juster med luftfuktighet
        humidity_factor = humidity / 100

        return {
            "snow": snow_prob * humidity_factor,
            "rain": rain_prob * humidity_factor,
            "mixed": mixed_prob * humidity_factor,
        }

    def _calculate_transition_risk(self) -> pd.Series:
        """Beregner risiko for overgang mellom nedbørstyper"""
        temp = self.df[self.required_columns["temperature"]]

        # Beregn temperaturendring
        temp_change = temp.diff().abs()

        # Høyere risiko når temperaturen er nær grenseverdiene
        near_threshold = (abs(temp - self.thresholds.temp_snow) < 0.5) | (
            abs(temp - self.thresholds.temp_mix_high) < 0.5
        )

        # Kombiner faktorer
        transition_risk = pd.Series(0.0, index=self.df.index)
        transition_risk[near_threshold] += 0.5
        transition_risk += temp_change * 0.2  # Vekt temperaturendring

        return transition_risk.clip(0, 1)
