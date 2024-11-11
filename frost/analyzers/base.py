"""Abstrakt baseklasse for væranalyse."""

import gc
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Set

import pandas as pd


class WeatherRiskAnalyzer(ABC):
    """Abstrakt baseklasse for væranalyse."""

    def __init__(self, df: pd.DataFrame):
        """Initialiser analysator med minneoptimalisering."""
        self.logger = logging.getLogger(self.__class__.__name__)

        # Valider input
        if not isinstance(df, pd.DataFrame):
            raise TypeError("Input må være en pandas DataFrame")
        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("DataFrame må ha DatetimeIndex")

        # Lagre referanse til data
        self.df = df.copy()

        # Standard kolonnemapping fra config
        self.standard_columns = {
            "temperature": "air_temperature",
            "surface_temp": "surface_temperature",
            "wind_speed": "wind_speed",
            "wind_gust": "max(wind_speed_of_gust PT1H)",
            "wind_direction": "wind_from_direction",
            "precipitation": "sum(precipitation_amount PT1H)",
            "humidity": "relative_humidity",
            "snow_depth": "surface_snow_thickness",
            "dew_point": "dew_point_temperature",
        }

        # Initialiser analysatorer
        self._validate_initial_data()

    def _validate_initial_data(self) -> None:
        """Valider initial datakvalitet."""
        if self.df.empty:
            raise ValueError("Tom DataFrame mottatt")

        # Sjekk for minimalt påkrevde kolonner
        missing_cols = []
        for col in self.standard_columns.values():
            if col not in self.df.columns:
                missing_cols.append(col)
                self.df[col] = pd.NA  # Legg til manglende kolonner med NA-verdier

        if missing_cols:
            self.logger.warning(
                f"Manglende kolonner initialisert med NA: {missing_cols}"
            )

        # Konverter til float32 for minneoptimalisering
        for col in self.df.columns:
            if self.df[col].dtype != "datetime64[ns]":
                try:
                    self.df[col] = self.df[col].astype("float32")
                except Exception as e:
                    self.logger.warning(f"Kunne ikke konvertere {col}: {e}")

    def _validate_columns(self, required_cols: Set[str]) -> None:
        """Valider at påkrevde kolonner eksisterer."""
        missing = required_cols - set(self.df.columns)
        if missing:
            self.logger.error(f"Mangler kolonner: {missing}")
            raise ValueError(f"Mangler påkrevde kolonner: {missing}")

    def _get_winter_mask(self) -> pd.Series:
        """Hent maske for vintermåneder (november-april)."""
        return self.df.index.month.isin([11, 12, 1, 2, 3, 4])

    @abstractmethod
    def validate_data(self) -> None:
        """Valider påkrevde data. Implementeres av subklasser."""
        pass

    @abstractmethod
    def calculate_risk(self) -> pd.DataFrame:
        """Beregn risiko. Implementeres av subklasser."""
        pass

    @abstractmethod
    def get_summary(self) -> Dict[str, Any]:
        """Hent analyseoppsummering. Implementeres av subklasser."""
        pass

    def __del__(self):
        """Opprydding når objektet slettes."""
        try:
            del self.df
            gc.collect()
        except:
            pass
