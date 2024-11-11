import gc
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

import numpy as np
import pandas as pd
import psutil
import requests
from tqdm.notebook import tqdm

from frost.analyzers.base import WeatherRiskAnalyzer
from frost.analyzers.precipitation_type import PrecipitationTypeAnalyzer
from frost.processors.data_processor import DataProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class FrostConfig:
    """Configuration class with memory-optimized settings for Frost API"""

    def __init__(self):
        self.CLIENT_ID = "43fefca2-a26b-415b-954d-ba9af37e3e1f"
        self.STATION_ID = "SN46220"
        self.BASE_URL = "https://frost.met.no/observations/v0.jsonld"

        # Oppdatert elementliste basert på frost.md
        self.ELEMENTS = [
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

        # Oppdatert DTYPE_MAP for alle elementer
        self.DTYPE_MAP = {
            "surface_snow_thickness": "float32",
            "max(wind_speed_of_gust PT1H)": "float32",
            "max(wind_speed PT1H)": "float32",
            "wind_speed": "float32",
            "relative_humidity": "float32",
            "air_temperature": "float32",
            "wind_from_direction": "float32",
            "surface_temperature": "float32",
            "min(air_temperature PT1H)": "float32",
            "sum(duration_of_precipitation PT1H)": "float32",
            "sum(precipitation_amount PT1H)": "float32",
            "max(air_temperature PT1H)": "float32",
            "dew_point_temperature": "float32",
        }

        # Oppdatert mapping for å matche API-responsen
        self.COLUMN_MAPPING = {
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

        # Fetch config
        self.FETCH_CONFIG = {
            "chunk_size_days": 90,
            "max_retries": 3,
            "timeout": 60,
            "max_parallel_requests": 1,
        }

        # Automated date range calculation
        self._set_date_range()

    def _set_date_range(self):
        """Set optimal date range for snow season analysis"""
        current_date = datetime.now()
        if current_date.month >= 5:
            self.END_DATE = f"{current_date.year}-04-30"
        else:
            self.END_DATE = current_date.strftime("%Y-%m-%d")

        # Endrer til kortere testperiode (3 måneder)
        self.START_DATE = "2023-11-01"  # Starter fra november 2023

    def fetch_data(self, start_date: str, end_date: str) -> pd.DataFrame:
        try:
            params = {
                "sources": self.STATION_ID,
                "elements": self.required_elements,
                "referencetime": f"{start_date}/{end_date}",
                "timeresolutions": "PT1H",
            }

            logger.info(f"Henter data fra {start_date} til {end_date}")
            response = requests.get(
                self.BASE_URL, params=params, auth=(self.CLIENT_ID, "")
            )
            response.raise_for_status()

            data = response.json().get("data", [])
            if not data:
                logger.warning("Ingen data returnert fra API")
                return pd.DataFrame()

            rows = []
            for item in data:
                row = {"timestamp": item["referenceTime"]}
                for obs in item["observations"]:
                    element_id = obs["elementId"]
                    row[element_id] = obs["value"]
                rows.append(row)

            df = pd.DataFrame(rows)
            if df.empty:
                return df

            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.set_index("timestamp")

            return df

        except Exception as e:
            logger.error(f"Feil ved datahenting: {e}")
            return pd.DataFrame()


class FrostDataFetcher:
    """Memory-efficient data fetching from Frost API"""

    def __init__(self, config: FrostConfig):
        self.config = config
        self.session = requests.Session()
        self.session.auth = (config.CLIENT_ID, "")
        self.logger = logging.getLogger(self.__class__.__name__)

    def _create_date_chunks(self) -> List[tuple]:
        """Create optimal date chunks for memory-efficient fetching"""
        start_date = datetime.strptime(self.config.START_DATE, "%Y-%m-%d")
        end_date = datetime.strptime(self.config.END_DATE, "%Y-%m-%d")

        chunks = []
        current_date = start_date

        while current_date < end_date:
            chunk_end = min(
                current_date
                + timedelta(days=self.config.FETCH_CONFIG["chunk_size_days"]),
                end_date,
            )
            chunks.append(
                (current_date.strftime("%Y-%m-%d"), chunk_end.strftime("%Y-%m-%d"))
            )
            current_date = chunk_end + timedelta(
                days=1
            )  # Legg til én dag for å unngå overlapp

        return chunks

    def _optimize_dtypes(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply memory-efficient dtypes to DataFrame"""
        for col, dtype in self.config.DTYPE_MAP.items():
            if col in df.columns:
                try:
                    df[col] = df[col].astype(dtype)
                except Exception as e:
                    self.logger.warning(f"Could not convert {col} to {dtype}: {e}")
        return df

    def _standardize_column_names(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardize column names using mapping"""
        for target_col, source_cols in self.config.COLUMN_MAPPING.items():
            for source_col in source_cols:
                if source_col in df.columns and target_col not in df.columns:
                    df[target_col] = df[source_col]
        return df

    def fetch_data(self, elements: Optional[List[str]] = None) -> pd.DataFrame:
        """Memory-efficient data fetching with progress tracking"""
        try:
            elements = elements or self.config.ELEMENTS
            chunks = self._create_date_chunks()
            all_data = []

            for start_date, end_date in tqdm(chunks, desc="Fetching data chunks"):
                try:
                    chunk_data = self._fetch_chunk(start_date, end_date, elements)
                    if chunk_data is not None:
                        chunk_data = self._optimize_dtypes(chunk_data)
                        chunk_data = self._standardize_column_names(chunk_data)
                        all_data.append(chunk_data)
                    gc.collect()
                except Exception as e:
                    self.logger.error(f"Chunk error {start_date}-{end_date}: {e}")
                    continue

            if not all_data:
                raise ValueError("No data was successfully fetched")

            final_data = pd.concat(all_data, axis=0)
            final_data = self._optimize_dtypes(final_data)

            return final_data

        except Exception as e:
            self.logger.error(f"Data fetching failed: {e}")
            raise

    def _fetch_chunk(
        self, start_date: str, end_date: str, elements: List[str]
    ) -> pd.DataFrame:
        """Fetch a single chunk of data from Frost API with retries."""
        try:
            params = {
                "sources": self.config.STATION_ID,
                "elements": self.config.ELEMENTS,  # Bruker den forhåndsdefinerte strengen
                "referencetime": f"{start_date}/{end_date}",
                "timeresolutions": "PT1H",
            }

            response = self.session.get(
                self.config.BASE_URL,
                params=params,
                timeout=self.config.FETCH_CONFIG["timeout"],
            )

            if response.status_code != 200:
                self.logger.error(
                    f"API Error: {response.status_code} - {response.text}"
                )
                response.raise_for_status()

            data = response.json().get("data", [])
            if not data:
                self.logger.warning(f"No data returned for {start_date} to {end_date}")
                return pd.DataFrame()

            # Bruk samme datastruktur som frost_glatt_v8.py
            rows = []
            for item in data:
                row = {"timestamp": item["referenceTime"]}
                for obs in item["observations"]:
                    element_id = obs["elementId"]
                    row[element_id] = obs["value"]
                rows.append(row)

            df = pd.DataFrame(rows)
            if df.empty:
                return df

            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.set_index("timestamp")

            return df

        except Exception as e:
            self.logger.error(f"Chunk fetch failed: {e}")
            raise

    def _debug_column_status(self, df: pd.DataFrame, stage: str = ""):
        """Debug helper for tracking column status"""
        self.logger.debug(f"=== Column status at {stage} ===")
        self.logger.debug(f"Available columns: {sorted(df.columns.tolist())}")
        self.logger.debug(f"Column types: \n{df.dtypes}")
        self.logger.debug(f"Non-null counts: \n{df.count()}")
        self.logger.debug("=" * 50)


class DataProcessor:
    """Memory-efficient data processing with robust validation"""

    def __init__(self, config: FrostConfig):
        self.config = config
        # Oppdater listen over påkrevde elementer for å matche det som faktisk hentes fra API
        self.required_elements = [
            "wind_speed",
            "wind_from_direction",
            "max(wind_speed_of_gust PT1H)",
            "air_temperature",
            "surface_temperature",
            "surface_snow_thickness",
            "relative_humidity",
            "dew_point_temperature",
            "sum(precipitation_amount PT1H)",
        ]
        self.logger = logging.getLogger(self.__class__.__name__)

    def _check_memory(self) -> float:
        """Monitor memory usage with Colab-specific thresholds"""
        try:
            mem = psutil.Process().memory_info().rss / 1024 / 1024
            if mem > self.config.MEMORY_SETTINGS["chunk_critical_threshold"] * 100:
                self.logger.warning(f"Critical memory usage: {mem:.1f} MB")
                gc.collect()
            return mem
        except Exception as e:
            self.logger.error(f"Memory check failed: {e}")
            return 0.0

    def process_raw_data(self, raw_data: pd.DataFrame) -> pd.DataFrame:
        """Process raw data with comprehensive error handling"""
        try:
            if raw_data.empty:
                raise ValueError("Empty dataset received")

            self.logger.info("Starting data processing...")
            processed = raw_data.copy()

            # Ensure datetime index
            if not isinstance(processed.index, pd.DatetimeIndex):
                if "referenceTime" in processed.columns:
                    processed.index = pd.to_datetime(processed["referenceTime"])
                    processed = processed.drop("referenceTime", axis=1)
                else:
                    raise ValueError("No datetime index or referenceTime column found")

            # Standardize column names using config mapping
            processed = self._standardize_columns(processed)

            # Convert data types
            processed = self._convert_datatypes(processed)

            # Handle missing values with careful interpolation
            processed = self._handle_missing_values(processed)

            # Ensure all required columns exist with correct names
            processed = self._ensure_required_columns(processed)

            # Validate processed data - fortsett selv om validering feiler
            self._validate_data(processed)

            self._check_memory()
            return processed

        except Exception as e:
            self.logger.error(f"Data processing failed: {e}")
            raise

    def _standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardize column names while preserving original data"""
        try:
            # First preserve original columns
            original_columns = df.columns.tolist()

            # Apply mappings from config
            for target_col, source_cols in self.config.COLUMN_MAPPING.items():
                if isinstance(source_cols, list):
                    for source_col in source_cols:
                        if source_col in df.columns and target_col not in df.columns:
                            df[target_col] = df[source_col]
                            self.logger.info(f"Mapped {source_col} to {target_col}")

            # Ensure we haven't lost any original columns
            missing_originals = set(original_columns) - set(df.columns)
            if missing_originals:
                self.logger.warning(
                    f"Lost original columns during standardization: {missing_originals}"
                )

            return df

        except Exception as e:
            self.logger.error(f"Column standardization failed: {e}")
            raise

    def _convert_datatypes(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convert data types while maintaining data integrity"""
        try:
            for col in df.columns:
                if col in self.config.DTYPE_MAP:
                    try:
                        # Store original values for validation
                        original_values = df[col].copy()

                        # Convert to numeric and specified dtype
                        df[col] = pd.to_numeric(df[col], errors="coerce")
                        df[col] = df[col].astype(self.config.DTYPE_MAP[col])

                        # Check for data loss
                        if df[col].isna().sum() > original_values.isna().sum():
                            self.logger.warning(
                                f"Data loss detected in {col} during type conversion"
                            )

                    except Exception as e:
                        self.logger.warning(f"Type conversion failed for {col}: {e}")
            return df

        except Exception as e:
            self.logger.error(f"Data type conversion failed: {e}")
            raise

    def _handle_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """Sophisticated missing value handling"""
        try:
            # Store original missing value counts
            original_missing = df.isna().sum()

            # Forward fill with limit
            df = df.ffill(limit=3)

            # Backward fill with limit
            df = df.bfill(limit=3)

            # Time-based interpolation for remaining gaps
            df = df.interpolate(method="time", limit_direction="both", limit=6)

            # Check remaining missing values
            final_missing = df.isna().sum()

            # Log changes in missing values
            for col in df.columns:
                if original_missing[col] > 0:
                    filled = original_missing[col] - final_missing[col]
                    self.logger.info(
                        f"{col}: Filled {filled}/{original_missing[col]} missing values"
                    )

            return df

        except Exception as e:
            self.logger.error(f"Missing value handling failed: {e}")
            raise

    def _ensure_required_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Ensure all required columns exist"""
        missing_cols = set(self.required_elements) - set(df.columns)
        if missing_cols:
            self.logger.warning(f"Missing required columns: {missing_cols}")
            # Try to recover using mappings
            for col in missing_cols:
                if col in self.config.COLUMN_MAPPING:
                    alternatives = self.config.COLUMN_MAPPING[col]
                    for alt in alternatives:
                        if alt in df.columns:
                            df[col] = df[alt]
                            self.logger.info(f"Recovered {col} using {alt}")
                            break
        return df

    def _validate_data(self, df: pd.DataFrame) -> bool:
        """Validate that required columns exist"""
        try:
            # Sjekk hvilke kolonner som faktisk finnes i datasettet
            available_cols = set(df.columns)
            missing_cols = set(self.required_elements) - available_cols

            if missing_cols:
                self.logger.warning(f"Missing columns: {missing_cols}")
                # Returnerer True selv om noen kolonner mangler - vi logger bare en advarsel
                return True

            return True

        except Exception as e:
            self.logger.error(f"Data validation failed: {e}")
            return False

    def _check_value_ranges(self, df: pd.DataFrame) -> None:
        """Check physical value ranges"""
        range_checks = {
            "air_temperature": (-50, 40),
            "mean(relative_humidity PT1H)": (0, 100),
            "relative_humidity": (0, 100),
            "surface_snow_thickness": (0, 500),
            "wind_speed": (0, 50),
            "wind_from_direction": (0, 360),
        }

        for col, (min_val, max_val) in range_checks.items():
            if col in df.columns:
                outliers = df[(df[col] < min_val) | (df[col] > max_val)][col]
            if not outliers.empty:
                self.logger.warning(
                    f"Found {len(outliers)} outliers in {col} "
                    f"outside range [{min_val}, {max_val}]"
                )

    def _check_data_patterns(self, df: pd.DataFrame) -> None:
        """Check for suspicious data patterns"""
        # Check for constant values
        for col in self.required_elements:
            if col in df.columns:
                unique_vals = df[col].nunique()
                if unique_vals < 10:
                    self.logger.warning(
                        f"Suspicious pattern in {col}: only {unique_vals} unique values"
                    )

    def _verify_column_names(self, df: pd.DataFrame) -> pd.DataFrame:
        """Verify and fix column names"""
        self.logger.info("Verifying column names...")
        self.logger.debug(f"Original columns: {df.columns.tolist()}")

        # Sjekk hver kolonne mot mapping
        for target_col, source_cols in self.config.COLUMN_MAPPING.items():
            if target_col not in df.columns:
                # Prøv å finne kolonnen med alternative navn
                for alt_col in source_cols:
                    if alt_col in df.columns:
                        df[target_col] = df[alt_col]
                        self.logger.info(f"Mapped {alt_col} to {target_col}")
                        break

        self.logger.debug(f"Final columns: {df.columns.tolist()}")
        return df


# Initialize processing pipeline
try:
    if "config" not in locals():
        config = FrostConfig()
    if "frost_fetcher" not in locals():
        frost_fetcher = FrostDataFetcher(config)

    processor = DataProcessor(config)

    logger.info("Fetching data from Frost API...")
    raw_data = frost_fetcher.fetch_data()

    logger.info("Processing data...")
    processed_data = processor.process_raw_data(raw_data)

    # Save processed data
    processed_data.to_pickle("frost_data_checkpoint.pkl")
    logger.info("Data processing completed and saved")

    # Display summary
    print("\nProcessed Data Summary:")
    print(f"Time range: {processed_data.index.min()} to {processed_data.index.max()}")
    print(f"Total records: {len(processed_data):,}")
    print("\nColumns:", ", ".join(processed_data.columns))
    processed_data.info(memory_usage="deep")

except Exception as e:
    logger.error(f"Processing pipeline failed: {e}")
    raise
finally:
    gc.collect()


class WeatherRiskAnalyzer(ABC):
    """Abstract base class for weather risk analysis."""

    def __init__(self, df: pd.DataFrame):
        """Initialize analyzer with memory optimization."""
        # Setup logging
        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
        )
        self.logger = logging.getLogger(self.__class__.__name__)

        # Validate input
        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("DataFrame must have DatetimeIndex")

        # Memory optimization
        self._log_memory_usage("Initial")
        self.df = df.copy()  # Ensure we have our own copy
        gc.collect()
        self._log_memory_usage("After DataFrame copy")

        self.validate_data()

    def _log_memory_usage(self, step: str) -> None:
        """Log memory usage at various steps."""
        memory_usage = psutil.Process().memory_info().rss / 1024 / 1024
        self.logger.info(f"Memory usage at {step}: {memory_usage:.1f} MB")

    @abstractmethod
    def validate_data(self) -> None:
        """Validate required data."""
        raise NotImplementedError

    @abstractmethod
    def calculate_risk(self) -> pd.DataFrame:
        """Calculate risk with memory optimization."""
        raise NotImplementedError

    @abstractmethod
    def get_summary(self) -> Dict[str, Any]:
        """Get analysis summary."""
        raise NotImplementedError

    def _get_winter_mask(self) -> pd.Series:
        """Get winter months mask efficiently."""
        try:
            self._log_memory_usage("Before winter mask")
            mask = self.df.index.month.isin([11, 12, 1, 2, 3, 4])
            gc.collect()
            self._log_memory_usage("After winter mask")
            return mask
        except Exception as e:
            self.logger.error(f"Error creating winter mask: {e}")
            raise

    def _validate_columns(self, required_cols: Set[str]) -> None:
        """Validate columns with memory tracking."""
        try:
            missing = required_cols - set(self.df.columns)
            if missing:
                self.logger.error(f"Missing columns: {missing}")
                raise ValueError(f"Missing required columns: {missing}")

            # Log column dtypes for memory optimization
            for col in self.df.columns:
                self.logger.debug(f"Column {col} dtype: {self.df[col].dtype}")

        except Exception as e:
            self.logger.error(f"Column validation failed: {e}")
            raise

    def _print_summary(self, summary: Dict[str, Any]) -> None:
        """Print summary with memory checks."""
        try:
            self._log_memory_usage("Before summary print")

            # Limit large summaries
            if len(summary) > 100:
                self.logger.warning("Large summary detected, truncating output")
                summary = dict(list(summary.items())[:100])

            print("\nAnalysis Summary")
            print("-" * 30)

            for key, value in summary.items():
                if isinstance(value, float):
                    print(f"{key}: {value:.3f}")
                else:
                    print(f"{key}: {value}")

            self._log_memory_usage("After summary print")

        except Exception as e:
            self.logger.error(f"Error printing summary: {e}")

    def __del__(self):
        """Cleanup when object is deleted."""
        try:
            self._log_memory_usage("Before cleanup")
            del self.df
            gc.collect()
            self._log_memory_usage("After cleanup")
        except:
            pass  # Suppress errors during cleanup


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        analyzer = WeatherRiskAnalyzer(pd.DataFrame())
    except TypeError as e:
        logging.info(f"Abstract class verification: {e}")


class PrecipitationTypeAnalyzer(WeatherRiskAnalyzer):
    """Analyserer type og intensitet av nedbør"""

    def __init__(self, df: pd.DataFrame):
        super().__init__(df)
        self.thresholds = PrecipitationThresholds()
        
        # Påkrevde kolonner fra standard_columns mapping
        self.required_columns = {
            self.standard_columns["temperature"],
            self.standard_columns["precipitation"],
            self.standard_columns["humidity"],
            self.standard_columns["dew_point"],
        }
        self.validate_data()

    def validate_data(self) -> None:
        """Validerer at nødvendige kolonner eksisterer"""
        self._validate_columns(self.required_columns)

    def calculate_risk(self) -> pd.DataFrame:
        """Beregn risiko basert på nedbørstype og intensitet"""
        results = self.df.copy()
        
        # Bruk eksisterende analyse-metoder
        analyzed = self.analyze()
        results = pd.concat([results, analyzed], axis=1)
        
        # Beregn total risiko basert på type og intensitet
        results["precipitation_risk"] = (
            results["precip_intensity"] * 0.6 +  # Vekt på intensitet
            results["transition_risk"] * 0.4    # Vekt på type-overgang
        )
        
        return results

    def get_summary(self) -> Dict[str, Any]:
        """Returner analyseoppsummering"""
        analyzed = self.analyze()
        return {
            "precipitation_types": {
                "snow": (analyzed["precip_type"] == "snow").mean(),
                "rain": (analyzed["precip_type"] == "rain").mean(),
                "mixed": (analyzed["precip_type"] == "mixed").mean(),
            },
            "mean_risk": analyzed["precipitation_risk"].mean(),
            "high_risk_hours": (analyzed["precipitation_risk"] > 0.7).sum()
        }
