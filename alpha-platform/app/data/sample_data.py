"""
Synthetic OHLCV generation helpers for demos and development.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from app.core.constants import ASSET_CANDIDATE_TIMEFRAMES, ASSET_HISTORY_YEARS

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "historical"

ASSET_PARAMS = {
    "BTCUSDT": (0.50, 0.80, 30000.0),
    "XAUUSD": (0.08, 0.15, 1850.0),
    "EURUSD": (0.01, 0.08, 1.0800),
}

TIMEFRAME_HOURS = {
    "15m": 0.25,
    "30m": 0.5,
    "1h": 1.0,
    "4h": 4.0,
    "1d": 24.0,
}


def bars_for_years(years: float, tf_hours: float) -> int:
    return int(years * 365 * 24 / tf_hours)


def generate_ohlcv(
    asset: str,
    timeframe: str,
    n_bars: int,
    start_price: float,
    annual_drift: float,
    annual_vol: float,
    seed: int = 42,
) -> pd.DataFrame:
    np.random.seed(seed)
    tf_hours = TIMEFRAME_HOURS[timeframe]
    dt = tf_hours / (365 * 24)

    returns = np.random.normal(
        loc=(annual_drift - 0.5 * annual_vol**2) * dt,
        scale=annual_vol * np.sqrt(dt),
        size=n_bars,
    )
    closes = start_price * np.exp(np.cumsum(returns))

    intrabar_vol = annual_vol * np.sqrt(dt) * 0.5
    opens = closes * np.exp(np.random.normal(0, intrabar_vol * 0.3, n_bars))
    highs = np.maximum(opens, closes) * np.exp(np.abs(np.random.normal(0, intrabar_vol, n_bars)))
    lows = np.minimum(opens, closes) * np.exp(-np.abs(np.random.normal(0, intrabar_vol, n_bars)))

    base_vol = 1000.0 if "USDT" not in asset else 500.0
    volumes = np.abs(np.random.lognormal(mean=np.log(base_vol), sigma=0.8, size=n_bars))

    step = timedelta(hours=tf_hours)
    start_date = datetime(2020, 1, 1, tzinfo=None)
    timestamps = [start_date + step * i for i in range(n_bars)]

    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
        }
    )

    df["high"] = df[["high", "open", "close"]].max(axis=1)
    df["low"] = df[["low", "open", "close"]].min(axis=1)

    decimals = 5 if asset == "EURUSD" else 2
    for col in ["open", "high", "low", "close"]:
        df[col] = df[col].round(decimals)
    df["volume"] = df["volume"].round(2)

    return df


def generate_sample_csv(
    asset: str,
    timeframe: str,
    output_dir: Path | None = None,
) -> Path:
    output_dir = output_dir or DEFAULT_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    annual_drift, annual_vol, start_price = ASSET_PARAMS[asset]
    years = ASSET_HISTORY_YEARS[asset]
    tf_hours = TIMEFRAME_HOURS.get(timeframe, 1.0)
    n_bars = bars_for_years(years, tf_hours)

    df = generate_ohlcv(
        asset=asset,
        timeframe=timeframe,
        n_bars=n_bars,
        start_price=start_price,
        annual_drift=annual_drift,
        annual_vol=annual_vol,
        seed=hash(f"{asset}_{timeframe}") % (2**32),
    )

    out_path = output_dir / f"{asset}_{timeframe}.csv"
    df.to_csv(out_path, index=False)
    return out_path


def generate_all_sample_csvs(output_dir: Path | None = None) -> list[Path]:
    output_dir = output_dir or DEFAULT_OUTPUT_DIR
    paths: list[Path] = []
    for asset, timeframes in ASSET_CANDIDATE_TIMEFRAMES.items():
        for timeframe in timeframes:
            paths.append(generate_sample_csv(asset, timeframe, output_dir))
    return paths
