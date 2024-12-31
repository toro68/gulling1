"""
LOCKED CONFIGURATION - DO NOT MODIFY
This configuration is optimized for:
- Snow drift analysis
- Icy road conditions
- Precipitation type analysis

Any changes to these parameters must be approved and documented.
"""

from dataclasses import dataclass, field
import os
from typing import Dict
import streamlit as st


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
    
    # Oppdatert elementliste basert på localhost
    ELEMENTS = [
        "surface_snow_thickness",
        "max(wind_speed_of_gust PT1H)",
        "max(wind_speed PT1H)",
        "wind_speed",
        "relative_humidity",
        "air_temperature",
        "wind_from_direction",
        "surface_temperature",
        "min(air_temperature PT1H)",
        "sum(duration_of_precipitation PT1H)",
        "sum(precipitation_amount PT1H)",
        "max(air_temperature PT1H)",
        "dew_point_temperature",
    ]
    
    # Kolonnemapping for å matche API-responsen
    COLUMN_MAPPING = {
        "snow_depth": ["surface_snow_thickness"],
        "wind_gust": ["max(wind_speed_of_gust PT1H)"],
        "max_wind": ["max(wind_speed PT1H)"],
        "wind_speed": ["wind_speed"],
        "humidity": ["relative_humidity"],
        "temperature": ["air_temperature"],
        "wind_direction": ["wind_from_direction"],
        "surface_temp": ["surface_temperature"],
        "min_temp": ["min(air_temperature PT1H)"],
        "precip_duration": ["sum(duration_of_precipitation PT1H)"],
        "precipitation": ["sum(precipitation_amount PT1H)"],
        "max_temp": ["max(air_temperature PT1H)"],
        "dew_point": ["dew_point_temperature"],
    }
    
    # Minneinnstillinger
    MEMORY_SETTINGS = {
        "chunk_warning_threshold": 0.75,  # 75% minnebruk varsling
        "chunk_critical_threshold": 0.85,  # 85% minnebruk kritisk
        "gc_threshold": 0.80,  # 80% minnebruk utløser GC
    }
    
    # Legg til GPS-konfigurasjon
    GPS_CONFIG: Dict[str, str] = field(
        default_factory=lambda: {
            "BASE_URL": "https://frost.met.no/gps/v0.jsonld",  # GPS API URL
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
    
    def __init__(self):
        # Oppdater snøfokk-terskelverdier med mer detaljerte parametre
        self.snow_drift_thresholds = {
            # Vindparametre
            'wind_strong': 10.61,      # m/s
            'wind_moderate': 7.77,     # m/s
            'wind_gust': 16.96,        # m/s
            'wind_dir_change': 37.83,  # grader
            'wind_weight': 0.4,        # vekting i total risiko
            
            # Temperaturparametre
            'temp_cold': -2.2,         # °C
            'temp_cool': 0,            # °C
            'temp_weight': 0.3,        # vekting i total risiko
            
            # Snøparametre
            'snow_high': 1.61,         # cm
            'snow_moderate': 0.84,     # cm
            'snow_low': 0.31,          # cm
            'snow_weight': 0.3,        # vekting i total risiko
            
            # Andre parametre
            'min_duration': 2,         # timer
            'humidity_max': 85         # prosent
        }
        
        # Parameterområder for optimalisering
        self.snow_drift_param_ranges = {
            'wind_strong': (8.0, 15.0),
            'wind_moderate': (5.0, 10.0),
            'wind_gust': (12.0, 20.0),
            'wind_dir_change': (20.0, 45.0),
            'wind_weight': (0.3, 0.5),
            'temp_cold': (-5.0, -1.0),
            'temp_cool': (-2.0, 2.0),
            'temp_weight': (0.2, 0.4),
            'snow_high': (1.0, 2.0),
            'snow_moderate': (0.5, 1.5),
            'snow_low': (0.2, 0.8),
            'snow_weight': (0.2, 0.4),
            'min_duration': (2, 4)
        }
