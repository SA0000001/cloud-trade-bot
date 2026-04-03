"""
Tests for data processors: splits, resampling, validation.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from app.data.processors import (
    compute_atr,
    generate_walk_forward_windows,
    split_in_sample_oos,
    validate_ohlcv_dataframe,
)
from app.core.exceptions import DataValidationError


def _make_ohlcv(n: int = 500, start_price: float = 100.0) -> pd.DataFrame:
    """Generate a synthetic OHLCV DataFrame."""
    np.random.seed(99)
    dates = [datetime(2021, 1, 1) + timedelta(hours=i) for i in range(n)]
    closes = start_price + np.cumsum(np.random.randn(n) * 0.5)
    highs = closes + np.abs(np.random.randn(n) * 0.3)
    lows = closes - np.abs(np.random.randn(n) * 0.3)
    opens = closes + np.random.randn(n) * 0.2
    volumes = np.abs(np.random.randn(n) * 1000) + 100

    df = pd.DataFrame({
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
    }, index=pd.DatetimeIndex(dates, tz="UTC"))
    return df


class TestSplitInSampleOOS:

    def test_correct_proportions(self):
        df = _make_ohlcv(1000)
        is_df, oos_df = split_in_sample_oos(df, in_sample_ratio=0.70)
        assert len(is_df) == 700
        assert len(oos_df) == 300

    def test_chronological_order(self):
        df = _make_ohlcv(200)
        is_df, oos_df = split_in_sample_oos(df)
        # OOS must come after IS
        assert is_df.index[-1] < oos_df.index[0]

    def test_no_data_leakage(self):
        df = _make_ohlcv(200)
        is_df, oos_df = split_in_sample_oos(df)
        overlap = set(is_df.index).intersection(set(oos_df.index))
        assert len(overlap) == 0, "IS and OOS must not share timestamps"

    def test_invalid_ratio_raises(self):
        df = _make_ohlcv(100)
        with pytest.raises(ValueError):
            split_in_sample_oos(df, in_sample_ratio=1.5)
        with pytest.raises(ValueError):
            split_in_sample_oos(df, in_sample_ratio=0.0)


class TestWalkForwardWindows:

    def test_correct_window_count(self):
        df = _make_ohlcv(500)
        windows = generate_walk_forward_windows(df, n_windows=5)
        assert len(windows) == 5

    def test_each_window_has_train_test(self):
        df = _make_ohlcv(500)
        windows = generate_walk_forward_windows(df, n_windows=4)
        for train, test in windows:
            assert len(train) > 0
            assert len(test) > 0

    def test_train_ratio_respected(self):
        df = _make_ohlcv(500)
        windows = generate_walk_forward_windows(df, n_windows=5, train_ratio=0.70)
        for train, test in windows:
            total = len(train) + len(test)
            ratio = len(train) / total
            assert 0.65 <= ratio <= 0.75  # allow small rounding

    def test_too_few_rows_raises(self):
        df = _make_ohlcv(20)
        with pytest.raises(ValueError, match="Too few rows"):
            generate_walk_forward_windows(df, n_windows=5)


class TestValidateOHLCV:

    def test_valid_df_passes(self):
        df = _make_ohlcv(100)
        validate_ohlcv_dataframe(df)  # should not raise

    def test_missing_columns_raises(self):
        df = _make_ohlcv(100)
        df = df.drop(columns=["volume"])
        with pytest.raises(DataValidationError, match="Missing columns"):
            validate_ohlcv_dataframe(df)

    def test_empty_df_raises(self):
        df = _make_ohlcv(0)
        with pytest.raises(DataValidationError, match="empty"):
            validate_ohlcv_dataframe(df)

    def test_high_lt_low_raises(self):
        df = _make_ohlcv(100)
        df.iloc[10, df.columns.get_loc("high")] = df.iloc[10]["low"] - 1.0
        with pytest.raises(DataValidationError, match="high < low"):
            validate_ohlcv_dataframe(df)

    def test_non_positive_close_raises(self):
        df = _make_ohlcv(100)
        df.iloc[5, df.columns.get_loc("close")] = -1.0
        with pytest.raises(DataValidationError, match="Non-positive"):
            validate_ohlcv_dataframe(df)

    def test_no_timezone_raises(self):
        df = _make_ohlcv(100)
        df.index = df.index.tz_localize(None)
        with pytest.raises(DataValidationError, match="timezone"):
            validate_ohlcv_dataframe(df)


class TestComputeATR:

    def test_atr_length_matches_input(self):
        df = _make_ohlcv(200)
        atr = compute_atr(df, period=14)
        assert len(atr) == len(df)

    def test_atr_non_negative(self):
        df = _make_ohlcv(200)
        atr = compute_atr(df, period=14)
        non_null = atr.dropna()
        assert (non_null >= 0).all()

    def test_atr_positive_for_volatile_data(self):
        df = _make_ohlcv(100)
        atr = compute_atr(df)
        last_atr = atr.iloc[-1]
        assert last_atr > 0
