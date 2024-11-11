"""
LOCKED CONFIGURATION - DO NOT MODIFY
This configuration is optimized for:
- Snow drift analysis
- Icy road conditions
- Precipitation type analysis

Any changes to these parameters must be approved and documented.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Set, Union
import os
import streamlit as st

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TimeResolution(Enum):
    TEN_MINUTES = "PT10M"
    ONE_HOUR = "PT1H"
    TWELVE_HOURS = "PT12H"
    ONE_DAY = "P1D"
    ONE_MONTH = "P1M"


class AnalysisType(Enum):
    SNOW_DRIFT = "snow_drift"
    ICY_ROADS = "icy_roads"
    PRECIPITATION = "precipitation"


@dataclass
class FrostConfig:
    """Konfigurasjon for Frost API og datainnhenting"""

    # API-innstillinger
    STATION_ID: str = "SN46220"
    BASE_URL: str = "https://frost.met.no/observations/v0.jsonld"

    @property
    def CLIENT_ID(self) -> str:
        """Henter CLIENT_ID fra miljøvariabler eller secrets"""
        client_id = os.getenv('FROST_CLIENT_ID')
        if not client_id:
            try:
                client_id = st.secrets["frost"]["client_id"]
            except Exception as e:
                st.error(f"Kunne ikke hente FROST_CLIENT_ID: {str(e)}")
                client_id = None
        return client_id

    # Elementgrupper basert på målefrekvens
    ELEMENTS_BY_FREQUENCY: Dict[TimeResolution, Set[str]] = field(
        default_factory=lambda: {
            TimeResolution.TEN_MINUTES: {
                "air_temperature",
                "surface_temperature",
                "surface_snow_thickness",
                "sum(precipitation_amount PT10M)",
                "sum(duration_of_precipitation PT10M)",
            },
            TimeResolution.ONE_HOUR: {
                "air_temperature",
                "surface_temperature",
                "wind_speed",
                "wind_from_direction",
                "max(wind_speed_of_gust PT1H)",
                "relative_humidity",
                "dew_point_temperature",
                "sum(precipitation_amount PT1H)",
                "surface_snow_thickness",
            },
            TimeResolution.ONE_DAY: {
                "mean(air_temperature P1D)",
                "min(air_temperature P1D)",
                "max(air_temperature P1D)",
                "mean(wind_speed P1D)",
                "max(wind_speed P1D)",
                "sum(precipitation_amount P1D)",
                "surface_snow_thickness",
            },
        }
    )

    # Spesifikke elementer for hver analysator med vekting
    ANALYZER_ELEMENTS: Dict[AnalysisType, Dict[str, float]] = field(
        default_factory=lambda: {
            AnalysisType.SNOW_DRIFT: {
                "wind_speed": 1.0,
                "wind_from_direction": 0.8,
                "max(wind_speed_of_gust PT1H)": 0.9,
                "surface_snow_thickness": 1.0,
                "air_temperature": 0.7,  # Påvirker snøens konsistens
            },
            AnalysisType.ICY_ROADS: {
                "surface_temperature": 1.0,
                "air_temperature": 0.9,
                "relative_humidity": 0.8,
                "sum(precipitation_amount PT1H)": 0.9,
                "min(air_temperature P1D)": 1.0,
                "max(air_temperature P1D)": 0.7,
            },
            AnalysisType.PRECIPITATION: {
                "air_temperature": 1.0,
                "sum(precipitation_amount PT1H)": 1.0,
                "relative_humidity": 0.8,
                "dew_point_temperature": 0.7,
                "sum(duration_of_precipitation PT10M)": 0.9,
            },
        }
    )

    # Terskelverdier for varsling
    ALERT_THRESHOLDS: Dict[str, Dict[str, Union[float, int, List[float]]]] = field(
        default_factory=lambda: {
            "snow_drift": {
                "wind_speed": 8.0,  # m/s
                "snow_depth": 5.0,   # cm
                "temp_max": 1.0      # °C
            },
            "icy_roads": {
                "surface_temp_min": -2.0,  # °C
                "surface_temp_max": 2.0,   # °C
                "humidity_min": 80.0       # %
            },
            "precipitation_type": {
                "snow_temp_threshold": 0.0,  # °C
                "sleet_temp_min": 0.0,      # °C
                "sleet_temp_max": 2.0       # °C
            }
        }
    )

    # Datavalidering og kvalitetskontroll
    DATA_VALIDATION: Dict[str, Dict[str, Union[float, List[float]]]] = field(
        default_factory=lambda: {
            "air_temperature": {"min": -50.0, "max": 50.0, "variance_threshold": 5.0},
            "wind_speed": {"min": 0.0, "max": 75.0, "variance_threshold": 10.0},
            "relative_humidity": {"min": 0.0, "max": 100.0, "variance_threshold": 20.0},
            "surface_snow_thickness": {
                "min": 0.0,
                "max": 1000.0,
                "change_threshold": 50.0,  # cm per time
            },
        }
    )

    # Minneinnstillinger
    MEMORY_SETTINGS = {
        "chunk_warning_threshold": 0.75,  # 75% minnebruk varsling
        "chunk_critical_threshold": 0.85,  # 85% minnebruk kritisk
        "gc_threshold": 0.80,  # 80% minnebruk utløser GC
    }

    # Elementer fra API-responsen
    ELEMENTS = {
        "air_temperature": {
            "unit": "degC",
            "level": {"height_above_ground": 2},
            "resolutions": ["PT1H", "PT10M"],
        },
        "surface_snow_thickness": {
            "unit": "cm",
            "level": None,
            "resolutions": ["PT1H", "PT10M", "P1D"],
        },
        "wind_speed": {
            "unit": "m/s",
            "level": {"height_above_ground": 10},
            "resolutions": ["PT1H"],
        },
        "sum(precipitation_amount PT1H)": {
            "unit": "mm",
            "level": None,
            "resolutions": ["PT1H"],
        },
        "wind_from_direction": {
            "unit": "degrees",
            "level": {"height_above_ground": 10},
            "resolutions": ["PT1H"],
        },
        "max(wind_speed_of_gust PT1H)": {
            "unit": "m/s",
            "level": {"height_above_ground": 10},
            "resolutions": ["PT1H"],
        },
        "surface_temperature": {
            "unit": "degC",
            "level": {"height_above_ground": 0},
            "resolutions": ["PT1H", "PT10M"],
        },
        "relative_humidity": {
            "unit": "percent",
            "level": {"height_above_ground": 2},
            "resolutions": ["PT1H"],
        },
        "dew_point_temperature": {
            "unit": "degC",
            "level": None,
            "resolutions": ["PT1H"],
        },
    }

    # Legg til GPS-konfigurasjon
    GPS_CONFIG: Dict[str, str] = field(
        default_factory=lambda: {
            "BASE_URL": "https://frost.met.no/gps/v0.jsonld",  # Endre til faktisk GPS API URL
            "FORMAT": "%H:%M:%S %d.%m.%Y"
        }
    )

    @property
    def GPS_URL(self) -> str:
        """Henter GPS_URL fra miljøvariabler eller secrets"""
        gps_url = os.getenv('GPS_API_URL')
        if not gps_url:
            try:
                gps_url = st.secrets["gps"]["api_url"]
            except Exception as e:
                st.error(f"Kunne ikke hente GPS_API_URL: {str(e)}")
                gps_url = self.GPS_CONFIG["BASE_URL"]
        return gps_url

    def get_required_elements(
        self, analysis_types: List[AnalysisType], time_resolution: TimeResolution
    ) -> Set[str]:
        """
        Henter påkrevde elementer basert på analysetype og tidsoppløsning
        """
        elements = set()

        # Legg til elementer fra valgt tidsoppløsning
        if time_resolution in self.ELEMENTS_BY_FREQUENCY:
            elements.update(self.ELEMENTS_BY_FREQUENCY[time_resolution])

        # Legg til elementer fra valgte analysatorer
        for analysis_type in analysis_types:
            if analysis_type in self.ANALYZER_ELEMENTS:
                # Inkluder elementer med vekting over 0.7
                elements.update(
                    elem
                    for elem, weight in self.ANALYZER_ELEMENTS[analysis_type].items()
                    if weight >= 0.7
                )

        return elements

    def validate_data(self, data: Dict[str, float], element: str) -> bool:
        """
        Validerer verdier mot definerte grenser og terskler
        """
        if element not in self.DATA_VALIDATION:
            return True

        validation_rules = self.DATA_VALIDATION[element]
        value = data.get(element)

        if value is None:
            return False

        # Sjekk grenseverdier
        if value < validation_rules["min"] or value > validation_rules["max"]:
            logger.warning(f"Verdi utenfor gyldig område for {element}: {value}")
            return False

        return True

    def check_alert_conditions(
        self, data: Dict[str, float], analysis_type: AnalysisType
    ) -> List[str]:
        """
        Sjekker om dataene trigger noen varsler
        """
        alerts = []
        thresholds = self.ALERT_THRESHOLDS.get(analysis_type.value, {})

        for condition, threshold in thresholds.items():
            if condition in data:
                value = data[condition]
                if isinstance(threshold, (int, float)):
                    if value >= threshold:
                        alerts.append(
                            f"{condition} over terskel: {value} >= {threshold}"
                        )
                elif isinstance(threshold, list) and len(threshold) == 2:
                    if threshold[0] <= value <= threshold[1]:
                        alerts.append(
                            f"{condition} i kritisk område: {threshold[0]} <= {value} <= {threshold[1]}"
                        )

        return alerts
