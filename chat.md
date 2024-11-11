frost/config.py
"""
LOCKED CONFIGURATION - DO NOT MODIFY
This configuration is optimized for:
Snow drift analysis
Icy road conditions
Precipitation type analysis
Any changes to these parameters must be approved and documented.

    """Konfigurasjon for Frost API og datainnhenting"""
    
    # API-innstillinger
    CLIENT_ID: str = "your-client-id"
    STATION_ID: str = "SN46220"
    BASE_URL: str = "https://frost.met.no/observations/v0.jsonld"
    
    # Kjernelementer som trengs av alle/flere analysatorer
    CORE_ELEMENTS: Set[str] = {
        'air_temperature',
        'surface_temperature',
        'wind_speed',
        'wind_from_direction',
        'max(wind_speed_of_gust PT1H)',
        'relative_humidity',


"""
from datetime import datetime, timedelta
class FrostConfig:
"""Configuration class for snow drift, icy roads and precipitation analysis"""
def init(self):
# API-innstillinger - IKKE ENDRE
self.CLIENT_ID = "43fefca2-a26b-415b-954d-ba9af37e3e1f"
self.STATION_ID = "SN46220"
self.BASE_URL = "https://frost.met.no/observations/v0.jsonld"
# LÅST: Primære elementer for snøfokk, glatt vei og nedbørsanalyse
self.ELEMENTS = {
'primary': [
'wind_speed',
'wind_from_direction',
'max(wind_speed_of_gust PT1H)',
'air_temperature',
'surface_temperature',
'surface_snow_thickness'
],
'secondary': [
'relative_humidity',
'dew_point_temperature',
'sum(precipitation_amount PT1H)'
]
}

// ... existing code ...
self.ELEMENTS = {
    'primary': [
        'wind_speed',
        'wind_from_direction',
        'max(wind_speed_of_gust PT1H)',
        'air_temperature',
        'surface_temperature',
        'surface_snow_thickness',
        'min(air_temperature PT1H)',  # Mangler - brukes i snow_drift.py
    ],
    'secondary': [
        'relative_humidity',
        'dew_point_temperature',
        'sum(precipitation_amount PT1H)'
    ]
}