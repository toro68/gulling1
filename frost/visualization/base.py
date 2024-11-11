"""Base visualization components."""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import pandas as pd
import plotly.graph_objects as go


class BaseVisualizer(ABC):
    """Abstrakt baseklasse for visualisering."""

    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.logger = logging.getLogger(self.__class__.__name__)
        self._validate_data()

    @abstractmethod
    def _validate_data(self) -> None:
        """Valider input data."""
        pass

    @abstractmethod
    def create_figure(self) -> go.Figure:
        """Lag hovedfigur."""
        pass

    def _handle_missing_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Håndter manglende data."""
        return df.fillna(method='ffill').fillna(method='bfill')
