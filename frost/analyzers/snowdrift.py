"""Analyzer for snow drift risk assessment."""

from frost.analyzers.base import BaseAnalyzer
import pandas as pd
import logging

logger = logging.getLogger(__name__)

class SnowDriftAnalyzer(BaseAnalyzer):
    """Analyserer risiko for snøfokk basert på værdata."""
    
    def __init__(self, config):
        """
        Initialiserer analyzer med konfigurasjon.
        
        Args:
            config: Konfigurasjonsobjekt med terskelverdier
        """
        super().__init__()
        self.config = config
        
    def analyze(self, df: pd.DataFrame) -> pd.Series:
        """
        Analyserer værdata og beregner risiko for snøfokk.
        
        Args:
            df: DataFrame med værdata
            
        Returns:
            pd.Series med risikoverdier for hver tidspunkt
        """
        try:
            snow_risk = pd.Series(index=df.index, dtype=float)
            
            for idx in df.index:
                # Hent verdier for gjeldende tidspunkt
                wind_speed = df.loc[idx, 'wind_speed']
                temp = df.loc[idx, 'air_temperature']
                snow_depth = df.loc[idx, 'surface_snow_thickness']
                humidity = df.loc[idx, 'relative_humidity']
                
                # Sjekk om vi har alle nødvendige verdier
                if pd.isna([wind_speed, temp, snow_depth, humidity]).any():
                    snow_risk[idx] = 0.0
                    continue
                
                # Vindanalyse
                wind_factor = 0.0
                if wind_speed >= self.config.snow_drift_thresholds['wind_strong']:
                    wind_factor = 1.0
                elif wind_speed >= self.config.snow_drift_thresholds['wind_moderate']:
                    wind_factor = (wind_speed - self.config.snow_drift_thresholds['wind_moderate']) / (
                        self.config.snow_drift_thresholds['wind_strong'] - self.config.snow_drift_thresholds['wind_moderate']
                    )
                
                # Temperaturanalyse
                temp_factor = 0.0
                if temp <= self.config.snow_drift_thresholds['temp_cold']:
                    temp_factor = 1.0
                elif temp <= self.config.snow_drift_thresholds['temp_cool']:
                    temp_factor = (self.config.snow_drift_thresholds['temp_cool'] - temp) / (
                        self.config.snow_drift_thresholds['temp_cool'] - self.config.snow_drift_thresholds['temp_cold']
                    )
                
                # Snøanalyse
                snow_factor = 0.0
                if snow_depth >= self.config.snow_drift_thresholds['snow_high']:
                    snow_factor = 1.0
                elif snow_depth >= self.config.snow_drift_thresholds['snow_moderate']:
                    snow_factor = (snow_depth - self.config.snow_drift_thresholds['snow_moderate']) / (
                        self.config.snow_drift_thresholds['snow_high'] - self.config.snow_drift_thresholds['snow_moderate']
                    )
                
                # Sjekk luftfuktighet
                if humidity > self.config.snow_drift_thresholds['humidity_max']:
                    snow_risk[idx] = 0.0
                    continue
                
                # Beregn total risiko med vekting
                risk_score = (
                    wind_factor * self.config.snow_drift_thresholds['wind_weight'] +
                    temp_factor * self.config.snow_drift_thresholds['temp_weight'] +
                    snow_factor * self.config.snow_drift_thresholds['snow_weight']
                )
                
                # Legg til ekstra risiko for sterke vindkast
                if 'max(wind_speed_of_gust PT1H)' in df.columns:
                    wind_gust = df.loc[idx, 'max(wind_speed_of_gust PT1H)']
                    if not pd.isna(wind_gust) and wind_gust >= self.config.snow_drift_thresholds['wind_gust']:
                        risk_score = min(risk_score + 0.2, 1.0)
                
                snow_risk[idx] = risk_score
            
            return snow_risk
            
        except Exception as e:
            logger.error(f"Feil i snøfokk-risikoberegning: {e}")
            return pd.Series(index=df.index, dtype=float) 