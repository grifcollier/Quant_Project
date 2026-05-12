"""Abstract base class for all trading strategies."""

from abc import ABC, abstractmethod

import pandas as pd


class BaseStrategy(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def run(self, **kwargs) -> pd.DataFrame: ...
