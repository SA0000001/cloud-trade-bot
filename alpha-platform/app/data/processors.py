"""
Data preprocessing utilities: resamplers, validators, and helpers.
"""
from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

from app.core.enums import Timeframe
from app.core.exceptions import DataValidationError

logger = logging.getLogger(__name__)

TIMEFRAME_TO_PANDAS_FREQ = {
    Timeframe.M15: "15min",
    Timeframe.M30: "30min",
    Timeframe.H1: "1h",
    Timeframe.H4: "4h",
    Timeframe.D1: "1D",
}


def resample_ohlcv(df: pd.DataFrame, target_timeframe: Timeframe) -> pd.DataFrame:
    """
    Resample a lower-timeframe OHLCV DataFrame to a higher timeframe.
    Input must have columns: open, high, low, close, volume
    and a UTC DatetimeIndex.
    """
    freq = TIMEFRAME_TO_PANDAS_FREQ.get(target_timeframe)
    if freq is None:
        raise ValueError(f"Unknown timeframe: {target_timeframe}")

    ohlc_dict = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }
    resampled = df.resample(freq).agg(ohlc_dict)
    resampled.dropna(subset=["close"], inplace=True)
    return resampled


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Compute Average True Range (ATR).
    Requires: high, low, close columns.
    Returns a Series aligned with df.index.
    """
    high = df["high"]
    low = df["low"]
    prev_close = df["close"].shift(1)

    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)

    atr = tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    return atr


def add_common_indicators(df: pd.DataFrame, atr_period: int = 14) -> pd.DataFrame:
    """
    Add commonly used indicators in-place.
    Returns the mutated DataFrame.
    """
    df = df.copy()
    df["atr"] = compute_atr(df, atr_period)
    df["returns"] = df["close"].pct_change()
    df["log_returns"] = (df["close"] / df["close"].shift(1)).apply(
        lambda x: pd.np.log(x) if pd.notna(x) and x > 0 else float("nan")
    )
    return df


def validate_ohlcv_dataframe(df: pd.DataFrame, name: str = "") -> None:
    """
    Raise DataValidationError if the DataFrame fails quality checks.
    Logs warnings for soft issues.
    """
    required = {"open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise DataValidationError(f"{name}: Missing columns: {missing}")

    if df.empty:
        raise DataValidationError(f"{name}: DataFrame is empty")

    if not isinstance(df.index, pd.DatetimeIndex):
        raise DataValidationError(f"{name}: Index must be DatetimeIndex")

    if df.index.tz is None:
        raise DataValidationError(f"{name}: DatetimeIndex must be timezone-aware (UTC)")

    if not df.index.is_monotonic_increasing:
        logger.warning("%s: Index is not monotonically increasing — sorting", name)

    # Hard checks
    if (df["high"] < df["low"]).any():
        raise DataValidationError(f"{name}: high < low found in some candles")

    if (df["close"] <= 0).any():
        raise DataValidationError(f"{name}: Non-positive close prices found")

    # Soft checks
    null_ratio = df[list(required)].isnull().mean()
    high_null = null_ratio[null_ratio > 0.01]
    if not high_null.empty:
        logger.warning("%s: High null ratio in columns: %s", name, high_null.to_dict())

    gap_pct = df["close"].pct_change().abs()
    large_gaps = gap_pct[gap_pct > 0.20]
    if not large_gaps.empty:
        logger.warning(
            "%s: %d candles with >20%% price gap detected",
            name, len(large_gaps),
        )


def split_in_sample_oos(
    df: pd.DataFrame,
    in_sample_ratio: float = 0.70,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Split OHLCV data into in-sample and out-of-sample segments.
    Chronological split — no shuffling.
    Returns (in_sample_df, oos_df).
    """
    if not 0 < in_sample_ratio < 1:
        raise ValueError("in_sample_ratio must be between 0 and 1 exclusive")

    n = len(df)
    split_idx = int(n * in_sample_ratio)
    in_sample = df.iloc[:split_idx].copy()
    oos = df.iloc[split_idx:].copy()
    logger.debug(
        "Data split: in-sample=%d rows, OOS=%d rows (ratio=%.0f%%)",
        len(in_sample), len(oos), in_sample_ratio * 100,
    )
    return in_sample, oos


def generate_walk_forward_windows(
    df: pd.DataFrame,
    n_windows: int = 5,
    train_ratio: float = 0.70,
) -> list[tuple[pd.DataFrame, pd.DataFrame]]:
    """
    Generate (train, test) DataFrame pairs for walk-forward optimization.
    Uses anchored or rolling windows — currently rolling (non-anchored).

    Returns a list of (train_df, test_df) tuples.
    """
    windows = []
    total = len(df)
    window_size = total // n_windows

    if window_size < 100:
        raise ValueError(
            f"Too few rows ({total}) for {n_windows} WF windows. "
            "Reduce windows or add more data."
        )

    for i in range(n_windows):
        start_idx = i * window_size
        end_idx = start_idx + window_size if i < n_windows - 1 else total
        window_df = df.iloc[start_idx:end_idx]
        split = int(len(window_df) * train_ratio)
        train = window_df.iloc[:split].copy()
        test = window_df.iloc[split:].copy()
        windows.append((train, test))

    logger.debug(
        "Generated %d WF windows. Avg train rows: %d, avg test rows: %d",
        len(windows),
        sum(len(t) for t, _ in windows) // len(windows),
        sum(len(e) for _, e in windows) // len(windows),
    )
    return windows
