import logging

import numpy as np
import pandas as pd
import psutil

from frost.config import FrostConfig


COLUMN_MAPPING = {
    "wind_speed": ["wind_speed", "mean(wind_speed PT1H)"],
    "max_wind_speed": ["max(wind_speed_of_gust PT1H)"],
    "air_temperature": ["air_temperature"],
    "surface_temperature": ["surface_temperature"],
}


class DataProcessor:
    """Prosesserer og validerer værdata"""

    def __init__(self, config: FrostConfig):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)

    def process_data(self, raw_data: pd.DataFrame) -> pd.DataFrame:
        """Prosesserer rådata og sikrer at alle påkrevde kolonner eksisterer"""
        try:
            processed_data = self._standardize_column_names(raw_data)

            # Sjekk for manglende kolonner
            missing_cols = set(self.config.ELEMENTS["primary"]) - set(
                processed_data.columns
            )
            if missing_cols:
                self.logger.warning(f"Mangler kolonner: {missing_cols}")
                # Legg til manglende kolonner med NaN-verdier
                for col in missing_cols:
                    processed_data[col] = np.nan

            # Konverter til float32 for minneoptimalisering
            for col in processed_data.columns:
                if col not in ["time", "referenceTime"]:
                    processed_data[col] = processed_data[col].astype("float32")

            # Sjekk minnebruk
            if hasattr(self.config, "MEMORY_SETTINGS"):
                self._check_memory_usage(processed_data)

            return processed_data

        except Exception as e:
            self.logger.error(f"Feil i dataprosessering: {str(e)}")
            raise

    def _check_memory_usage(self, df: pd.DataFrame) -> None:
        """Sjekker minnebruk og gir advarsler ved høyt forbruk"""
        try:
            memory_usage = df.memory_usage(deep=True).sum() / 1024**2  # MB
            total_memory = psutil.virtual_memory().total / 1024**2
            usage_ratio = memory_usage / total_memory

            if usage_ratio >= self.config.MEMORY_SETTINGS["chunk_critical_threshold"]:
                self.logger.critical(f"Kritisk høy minnebruk: {usage_ratio:.2%}")
            elif usage_ratio >= self.config.MEMORY_SETTINGS["chunk_warning_threshold"]:
                self.logger.warning(f"Høy minnebruk: {usage_ratio:.2%}")

        except Exception as e:
            self.logger.error(f"Feil i minnesjekk: {str(e)}")

    def _standardize_column_names(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardiserer kolonnenavn basert på COLUMN_MAPPING"""
        processed = df.copy()
        
        for standard_name, possible_names in COLUMN_MAPPING.items():
            for col in possible_names:
                if col in processed.columns:
                    processed[standard_name] = processed[col]
                    if col != standard_name:
                        processed.drop(columns=[col], inplace=True)
                    break
        
        return processed
