"""
Generate synthetic OHLCV CSV data for development and testing.

Creates realistic-looking price series for all 3 assets across
all candidate timeframes. Uses geometric Brownian motion with
asset-specific volatility parameters.

Usage:
    python scripts/generate_sample_data.py
    # or
    make generate-data

Output:
    data/historical/BTCUSDT_1h.csv
    data/historical/BTCUSDT_4h.csv
    ... (all assets × timeframes)
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# Project root on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.constants import ASSET_CANDIDATE_TIMEFRAMES

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("data/historical")

# Asset-specific parameters for geometric Brownian motion
# (annual_drift, annual_vol, start_price)
ASSET_PARAMS = {
    "BTCUSDT": (0.50, 0.80, 30000.0),   # high vol crypto
    "XAUUSD":  (0.08, 0.15, 1850.0),    # moderate vol gold
    "EURUSD":  (0.01, 0.08, 1.0800),    # low vol forex
}

TIMEFRAME_HOURS = {
    "15m": 0.25,
    "30m": 0.5,
    "1h": 1.0,
    "4h": 4.0,
    "1d": 24.0,
}

# How many years of data per asset
ASSET_YEARS = {
    "BTCUSDT": 4,
    "XAUUSD": 5,
    "EURUSD": 5,
}


def generate_ohlcv(
    asset: str,
    timeframe: str,
    n_bars: int,
    start_price: float,
    annual_drift: float,
    annual_vol: float,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Generate synthetic OHLCV using geometric Brownian motion.
    High/low are approximated from intrabar volatility.
    """
    np.random.seed(seed)
    tf_hours = TIMEFRAME_HOURS[timeframe]
    dt = tf_hours / (365 * 24)  # time step in years

    # Simulate close prices
    returns = np.random.normal(
        loc=(annual_drift - 0.5 * annual_vol**2) * dt,
        scale=annual_vol * np.sqrt(dt),
        size=n_bars,
    )
    closes = start_price * np.exp(np.cumsum(returns))

    # Approximate OHLC from close prices
    intrabar_vol = annual_vol * np.sqrt(dt) * 0.5
    opens = closes * np.exp(np.random.normal(0, intrabar_vol * 0.3, n_bars))
    highs = np.maximum(opens, closes) * np.exp(np.abs(np.random.normal(0, intrabar_vol, n_bars)))
    lows = np.minimum(opens, closes) * np.exp(-np.abs(np.random.normal(0, intrabar_vol, n_bars)))

    # Volumes (log-normal with mild autocorrelation)
    base_vol = 1000.0 if "USDT" not in asset else 500.0
    volumes = np.abs(np.random.lognormal(mean=np.log(base_vol), sigma=0.8, size=n_bars))

    # Timestamps (UTC)
    step = timedelta(hours=tf_hours)
    start_date = datetime(2020, 1, 1, tzinfo=None)
    timestamps = [start_date + step * i for i in range(n_bars)]

    df = pd.DataFrame({
        "timestamp": timestamps,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
    })

    # Ensure high >= max(open, close) and low <= min(open, close)
    df["high"] = df[["high", "open", "close"]].max(axis=1)
    df["low"] = df[["low", "open", "close"]].min(axis=1)

    # Round to appropriate decimal places
    decimals = 5 if asset == "EURUSD" else 2
    for col in ["open", "high", "low", "close"]:
        df[col] = df[col].round(decimals)
    df["volume"] = df["volume"].round(2)

    return df


def bars_for_years(years: float, tf_hours: float) -> int:
    return int(years * 365 * 24 / tf_hours)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    total_files = 0
    for asset, timeframes in ASSET_CANDIDATE_TIMEFRAMES.items():
        annual_drift, annual_vol, start_price = ASSET_PARAMS[asset]
        years = ASSET_YEARS[asset]

        for tf in timeframes:
            tf_hours = TIMEFRAME_HOURS.get(tf, 1.0)
            n_bars = bars_for_years(years, tf_hours)
            out_path = OUTPUT_DIR / f"{asset}_{tf}.csv"

            logger.info(
                "Generating %s / %s — %d bars (%.0f years) → %s",
                asset, tf, n_bars, years, out_path,
            )

            df = generate_ohlcv(
                asset=asset,
                timeframe=tf,
                n_bars=n_bars,
                start_price=start_price,
                annual_drift=annual_drift,
                annual_vol=annual_vol,
                seed=hash(f"{asset}_{tf}") % (2**32),
            )

            df.to_csv(out_path, index=False)
            total_files += 1
            logger.info("  Written: %d rows, price range [%.4f – %.4f]",
                        len(df), df["close"].min(), df["close"].max())

    logger.info("\n✅ Done. Generated %d CSV files in %s", total_files, OUTPUT_DIR)
    logger.info("You can now run backtests using these files.")
    logger.info("Replace with real data before any serious research.")


if __name__ == "__main__":
    main()
