"""Main application module for Frost weather analysis."""

import gc
import logging
from typing import Any, Dict

import pandas as pd

from .analyzers.precipitation_type import PrecipitationTypeAnalyzer
from frost.config import FrostConfig
from .data.fetcher import FrostDataFetcher
from .data.processor import DataProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


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
        
        return processed_data
        
    except Exception as e:
        logger.error(f"Data processing failed: {e}")
        return pd.DataFrame()
