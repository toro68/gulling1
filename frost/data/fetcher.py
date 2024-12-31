"""Data fetching from Frost API."""

import logging
import time
from typing import Dict, List, Optional, Union
from datetime import datetime

import pandas as pd
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import FrostConfig, TimeResolution


class FrostDataFetcher:
    """Memory-efficient data fetching from Frost API"""

    def __init__(self, config: FrostConfig):
        self.config = config
        self.session = requests.Session()
        self.session.auth = (str(config.CLIENT_ID).strip(), '')
        self.logger = logging.getLogger(self.__class__.__name__)
        
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=lambda e: isinstance(e, (requests.Timeout, requests.ConnectionError))
    )
    def _fetch_chunk(
        self, 
        start_date: Union[str, datetime], 
        end_date: Union[str, datetime]
    ) -> pd.DataFrame:
        """
        Fetch data from Frost API.
        
        Args:
            start_date: Start date for data fetch
            end_date: End date for data fetch
            
        Returns:
            pd.DataFrame: Weather data
            
        Raises:
            APIError: On API-related errors
            ConfigError: On configuration errors
        """
        try:
            # Definer kjerneelementer som må være tilgjengelige
            core_elements = [
                "air_temperature",
                "surface_snow_thickness",
                "wind_speed",
                "wind_from_direction",
                "max(wind_speed_of_gust PT1H)",
                "relative_humidity",
                "sum(precipitation_amount PT1H)"
            ]
            
            # Definer valgfrie elementer
            optional_elements = [
                "max(air_temperature PT1H)",
                "min(air_temperature PT1H)",
                "max(wind_speed PT1H)",
                "sum(duration_of_precipitation PT1H)"
            ]
            
            # Start med kjerneelementer
            elements = core_elements.copy()
            
            # Legg til valgfrie elementer
            elements.extend(optional_elements)
            
            params = {
                "sources": self.config.STATION_ID,
                "elements": ",".join(elements),
                "referencetime": f"{start_date}/{end_date}",
                "timeresolutions": "PT1H",
            }

            response = self.session.get(
                self.config.BASE_URL,
                params=params,
                timeout=30,
            )

            if response.status_code == 401:
                raise ValueError("Ugyldig FROST_CLIENT_ID")
            elif response.status_code != 200:
                raise ConnectionError(f"API-feil: {response.status_code}")

            data = response.json().get("data", [])
            if not data:
                self.logger.warning(f"No data returned for period {start_date} to {end_date}")
                return pd.DataFrame()

            # Konverter data til DataFrame
            rows = []
            for item in data:
                row = {"timestamp": item["referenceTime"]}
                for obs in item.get("observations", []):
                    element_id = obs["elementId"]
                    row[element_id] = obs["value"]
                rows.append(row)

            df = pd.DataFrame(rows)
            
            if df.empty:
                self.logger.warning("Created DataFrame is empty")
                return df

            # Konverter timestamp og sett index
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.set_index("timestamp")

            # Sjekk for manglende kjerneelementer
            missing_core = set(core_elements) - set(df.columns)
            if missing_core:
                self.logger.error(f"Mangler kjerneelementer: {missing_core}")
                raise ValueError(f"Mangler nødvendige værdata: {missing_core}")

            # Logg manglende valgfrie elementer
            missing_optional = set(optional_elements) - set(df.columns)
            if missing_optional:
                self.logger.warning(f"Mangler valgfrie elementer: {missing_optional}")

            return df

        except requests.Timeout as e:
            self.logger.warning(f"Timeout ved henting av data: {e}")
            raise  # La retry-dekoratøren håndtere dette
        except requests.ConnectionError as e:
            self.logger.warning(f"Tilkoblingsfeil: {e}")
            raise  # La retry-dekoratøren håndtere dette
        except Exception as e:
            self.logger.error(f"Uventet feil ved henting av værdata: {e}")
            raise


