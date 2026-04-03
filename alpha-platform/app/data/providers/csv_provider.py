"""
Data provider implementations.

CSV Provider:
  - Reads OHLCV data from local CSV files.
  - Expected file naming: {ASSET}_{TIMEFRAME}.csv
  - Expected columns: timestamp, open, high, low, close, volume
  - Timestamps must be UTC.

Future providers (stubs only — implement later):
  - TradingViewWebhookProvider
  - BinanceAPIProvider
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from app.core.enums import AssetSymbol, DataSource, Timeframe
from app.core.exceptions import DataProviderError, DataValidationError, InsufficientDataError
from app.core.interfaces import IDataProvider

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = {"open", "high", "low", "close", "volume"}


# ---------------------------------------------------------------------------
# CSV Provider
# ---------------------------------------------------------------------------

class CSVDataProvider(IDataProvider):
    """
    Loads historical OHLCV data from local CSV files.

    File naming convention:
        {data_dir}/{ASSET}_{TIMEFRAME}.csv
    Example:
        data/historical/BTCUSDT_1h.csv

    CSV format:
        timestamp,open,high,low,close,volume
        2021-01-01 00:00:00,29000.0,29500.0,28800.0,29200.0,1234.5
    """

    def __init__(self, data_dir: str = "data/historical") -> None:
        self._data_dir = Path(data_dir)
        self._cache: dict[str, pd.DataFrame] = {}
        logger.info("CSVDataProvider initialized. data_dir=%s", self._data_dir)

    @property
    def source_name(self) -> str:
        return DataSource.CSV.value

    def is_available(self, asset: AssetSymbol, timeframe: Timeframe) -> bool:
        return self._resolve_path(asset, timeframe).exists()

    def get_ohlcv(
        self,
        asset: AssetSymbol,
        timeframe: Timeframe,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Load OHLCV data from CSV.
        Returns a DataFrame indexed by UTC DatetimeIndex.
        """
        cache_key = f"{asset.value}_{timeframe.value}"

        if cache_key not in self._cache:
            df = self._load_file(asset, timeframe)
            self._validate(df, asset, timeframe)
            self._cache[cache_key] = df
            logger.debug("Loaded %d rows for %s", len(df), cache_key)

        df = self._cache[cache_key].copy()

        if start:
            df = df[df.index >= pd.Timestamp(start, tz="UTC")]
        if end:
            df = df[df.index <= pd.Timestamp(end, tz="UTC")]
        if limit:
            df = df.tail(limit)

        if df.empty:
            raise InsufficientDataError(
                f"No data in range for {asset.value}/{timeframe.value}"
            )

        return df

    def _resolve_path(self, asset: AssetSymbol, timeframe: Timeframe) -> Path:
        return self._data_dir / f"{asset.value}_{timeframe.value}.csv"

    def _load_file(self, asset: AssetSymbol, timeframe: Timeframe) -> pd.DataFrame:
        path = self._resolve_path(asset, timeframe)
        if not path.exists():
            raise DataProviderError(
                f"CSV file not found: {path}. "
                f"Expected file: {asset.value}_{timeframe.value}.csv in {self._data_dir}"
            )
        try:
            df = pd.read_csv(path, parse_dates=["timestamp"])
            df.set_index("timestamp", inplace=True)
            if df.index.tz is None:
                df.index = df.index.tz_localize("UTC")
            else:
                df.index = df.index.tz_convert("UTC")
            df.sort_index(inplace=True)
            df.columns = [c.lower() for c in df.columns]
            return df
        except Exception as exc:
            raise DataProviderError(f"Failed to load {path}: {exc}") from exc

    def _validate(
        self, df: pd.DataFrame, asset: AssetSymbol, timeframe: Timeframe
    ) -> None:
        missing = REQUIRED_COLUMNS - set(df.columns)
        if missing:
            raise DataValidationError(
                f"{asset.value}/{timeframe.value} CSV missing columns: {missing}"
            )
        null_counts = df[list(REQUIRED_COLUMNS)].isnull().sum()
        if null_counts.any():
            logger.warning(
                "Null values in %s/%s: %s", asset.value, timeframe.value, null_counts.to_dict()
            )
        if (df["high"] < df["low"]).any():
            raise DataValidationError(
                f"{asset.value}/{timeframe.value}: Found candles where high < low"
            )
        if (df["close"] <= 0).any():
            raise DataValidationError(
                f"{asset.value}/{timeframe.value}: Found non-positive close prices"
            )

    def clear_cache(self) -> None:
        """Invalidate the in-memory cache (useful for testing)."""
        self._cache.clear()


# ---------------------------------------------------------------------------
# Stub / Placeholder providers
# ---------------------------------------------------------------------------

class TradingViewWebhookProvider(IDataProvider):
    """
    TODO: Implement TradingView webhook-based data ingestion.

    Design notes:
    - TradingView sends webhook alerts when conditions are met.
    - This provider should listen on an HTTP endpoint (FastAPI route).
    - Incoming bars should be stored in DB and served from there.
    - This class acts as a read interface over that DB-backed store.

    For now, raises NotImplementedError to signal it's a future integration.
    """

    @property
    def source_name(self) -> str:
        return DataSource.TRADINGVIEW_WEBHOOK.value

    def is_available(self, asset: AssetSymbol, timeframe: Timeframe) -> bool:
        return False  # TODO

    def get_ohlcv(self, asset, timeframe, start=None, end=None, limit=None):
        raise NotImplementedError(
            "TradingViewWebhookProvider is not yet implemented. "
            "Use CSVDataProvider for now."
        )


class BinanceAPIProvider(IDataProvider):
    """
    TODO: Implement Binance Klines API data provider.

    Rate limits, pagination, and symbol mapping must be handled.
    Only BTCUSDT is supported on Binance. XAUUSD/EURUSD need a broker API.
    """

    @property
    def source_name(self) -> str:
        return DataSource.BINANCE_API.value

    def is_available(self, asset: AssetSymbol, timeframe: Timeframe) -> bool:
        return False  # TODO

    def get_ohlcv(self, asset, timeframe, start=None, end=None, limit=None):
        raise NotImplementedError(
            "BinanceAPIProvider is not yet implemented."
        )
