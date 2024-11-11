"""Data fetching from Frost API."""

import logging
import time
from typing import List, Optional

import pandas as pd
import requests

from ..config import FrostConfig, TimeResolution


class FrostDataFetcher:
    """Memory-efficient data fetching from Frost API"""

    def __init__(self, config: FrostConfig):
        self.config = config
        self.session = requests.Session()
        self.session.auth = (str(config.CLIENT_ID).strip(), '')
        self.logger = logging.getLogger(self.__class__.__name__)
        
    def _fetch_chunk(self, start_date: str, end_date: str) -> pd.DataFrame:
        """Fetch a single chunk of data from Frost API with retries."""
        for attempt in range(3):
            try:
                # Bruk elementer fra config.py
                elements = [
                    "air_temperature",
                    "surface_snow_thickness",
                    "wind_speed",
                    "wind_from_direction",
                    "max(wind_speed_of_gust PT1H)",
                    "relative_humidity",
                    "dew_point_temperature",
                    "sum(precipitation_amount PT1H)",
                    "surface_temperature"
                ]
                elements_str = ",".join(elements)

                params = {
                    "sources": self.config.STATION_ID,
                    "elements": elements_str,
                    "referencetime": f"{start_date}/{end_date}",
                    "timeresolutions": "PT1H",
                }

                self.logger.info(f"Fetching data for period {start_date} to {end_date}")
                self.logger.debug(f"Using elements: {elements_str}")

                response = self.session.get(
                    self.config.BASE_URL,
                    params=params,
                    timeout=30,
                )

                if response.status_code != 200:
                    self.logger.error(
                        f"API request failed: {response.status_code} - {response.text}"
                    )
                    self.logger.error(f"Full URL: {response.url}")
                    response.raise_for_status()

                data = response.json().get("data", [])
                if not data:
                    self.logger.warning(
                        f"No data returned for period {start_date} to {end_date}"
                    )
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

                # Logg hvilke kolonner vi faktisk fikk
                self.logger.info(f"Retrieved columns: {df.columns.tolist()}")

                # Sjekk for manglende kolonner
                expected_cols = set(self.config.ELEMENTS)
                actual_cols = set(df.columns)
                missing_cols = expected_cols - actual_cols

                if missing_cols:
                    self.logger.warning(f"Missing columns in response: {missing_cols}")

                return df

            except requests.Timeout:
                self.logger.warning(
                    f"Timeout on attempt {attempt + 1} of 3"
                )
                if attempt == 2:
                    raise
                time.sleep(5 * (attempt + 1))  # Økende ventetid mellom forsøk

            except Exception as e:
                self.logger.error(f"Chunk fetch failed: {str(e)}")
                self.logger.exception("Detailed error:")
                raise


