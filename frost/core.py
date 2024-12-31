"""Main application module for Frost weather analysis."""

import gc
import logging
from typing import Any, Dict

import pandas as pd
import streamlit as st

from .analyzers.precipitation_type import PrecipitationTypeAnalyzer
from frost.config import FrostConfig
from .data.fetcher import FrostDataFetcher
from .data.processor import DataProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@st.cache_data(ttl=3600)  # Cache i 1 time
def process_weather_data(start_date: datetime, end_date: datetime) -> pd.DataFrame:
    """Prosesserer værdata for gitt tidsperiode."""
    try:
        config = FrostConfig()
        fetcher = FrostDataFetcher(config)
        
        # Hent og prosesser data
        raw_data = fetcher._fetch_chunk(
            start_date=start_date.strftime('%Y-%m-%dT%H:%M:%S'),
            end_date=end_date.strftime('%Y-%m-%dT%H:%M:%S')
        )
        
        if raw_data.empty:
            logger.error("No data retrieved from API")
            return pd.DataFrame()
            
        # Prosesser data hvis nødvendig
        processor = DataProcessor(config)
        processed_data = processor.process_raw_data(raw_data)
        
        # Konverter til float32 for å spare minne
        for col in processed_data.select_dtypes(include=['float64']).columns:
            processed_data[col] = processed_data[col].astype('float32')
            
        return processed_data
        
    except Exception as e:
        logger.error(f"Data processing failed: {e}")
        return pd.DataFrame()

class FrostError(Exception):
    """Base exception for Frost-related errors."""
    pass

class APIError(FrostError):
    """API-related errors."""
    pass

class ConfigError(FrostError):
    """Configuration-related errors."""
    pass
