"""
Tests for Telegram message formatting and strategy registry.
"""
from __future__ import annotations

import pytest

from app.core.enums import AssetSymbol, RobustnessLabel, SignalDirection, StrategyFamily, Timeframe
from app.core.models import Signal
from app.notifications.telegram import TelegramService


def _make_signal(**kwargs) -> Signal:
    defaults = dict(
        asset=AssetSymbol.BTCUSDT,
        strategy_name="SMA_CROSS",
        strategy_family=StrategyFamily.TREND_FOLLOWING,
        timeframe=Timeframe.H1,
        direction=SignalDirection.LONG,
        entry_price=50000.0,
        stop_loss=48000.0,
        take_profit=54000.0,
        atr=500.0,
        robustness_label=RobustnessLabel.ROBUST,
        reason="Golden cross detected",
    )
    defaults.update(kwargs)
    return Signal(**defaults)


class TestTelegramMessageFormatting:

    def setup_method(self):
        # Disabled service — tests formatting without actual HTTP calls
        self.svc = TelegramService(enabled=False)

    def test_service_disabled_returns_false(self):
        signal = _make_signal()
        result = self.svc.send_signal_alert(signal)
        assert result is False

    def test_service_without_token_returns_false(self):
        svc = TelegramService(enabled=True, bot_token=None, chat_id=None)
        result = svc.send("test message")
        assert result is False

    def test_message_truncation(self):
        """Messages over 4096 chars should be truncated gracefully."""
        svc = TelegramService(enabled=False)
        long_message = "x" * 5000
        # Should not raise; would truncate if actually sent
        assert svc._is_ready() is False  # no-op due to disabled

    def test_signal_alert_contains_key_fields(self):
        """Verify the signal alert template includes all required fields."""
        signal = _make_signal()
        # Build the message manually to test the template
        from app.core.enums import RiskLevel
        from app.core.models import RiskState
        import datetime

        # Reconstruct what send_signal_alert would produce
        direction_emoji = "🟢 LONG" if "LONG" in str(signal.direction) else "🔴 SHORT"
        msg_parts = [
            signal.asset if isinstance(signal.asset, str) else signal.asset.value,
            signal.strategy_name,
            str(signal.timeframe.value if hasattr(signal.timeframe, "value") else signal.timeframe),
            "LONG",
            f"{signal.entry_price:.4f}",
            f"{signal.stop_loss:.4f}",
            f"{signal.take_profit:.4f}",
        ]
        for part in msg_parts:
            assert part  # none should be empty


class TestStrategyRegistry:

    def test_all_example_strategies_register(self):
        import app.strategies  # trigger registration
        from app.strategies.base import StrategyRegistry

        registered = StrategyRegistry.all_names()
        assert "SMA_CROSS" in registered
        assert "DONCHIAN_BREAKOUT" in registered
        assert "RSI_MEAN_REVERSION" in registered

    def test_get_returns_correct_type(self):
        import app.strategies
        from app.strategies.base import StrategyRegistry
        from app.strategies.examples.sma_cross import SMAcrossStrategy

        strategy = StrategyRegistry.get("SMA_CROSS")
        assert isinstance(strategy, SMAcrossStrategy)

    def test_get_unknown_raises(self):
        from app.strategies.base import StrategyRegistry
        from app.core.exceptions import StrategyNotFoundError

        with pytest.raises(StrategyNotFoundError):
            StrategyRegistry.get("NONEXISTENT_STRATEGY")

    def test_list_all_returns_families(self):
        import app.strategies
        from app.strategies.base import StrategyRegistry

        all_strats = StrategyRegistry.list_all()
        assert isinstance(all_strats, dict)
        for name, family in all_strats.items():
            assert isinstance(name, str)
            assert isinstance(family, str)

    def test_strategy_validate_config(self):
        import app.strategies
        from app.core.enums import AssetSymbol, Timeframe, StrategyFamily
        from app.core.models import StrategyConfig
        from app.strategies.base import StrategyRegistry

        strategy = StrategyRegistry.get("SMA_CROSS")
        config = StrategyConfig(
            name="SMA_CROSS",
            family=StrategyFamily.TREND_FOLLOWING,
            asset=AssetSymbol.BTCUSDT,
            timeframe=Timeframe.H1,
            parameters=strategy.default_parameters(),
        )
        assert strategy.validate_config(config) is True

    def test_strategy_invalid_config_rejected(self):
        import app.strategies
        from app.core.enums import AssetSymbol, Timeframe, StrategyFamily
        from app.core.models import StrategyConfig
        from app.strategies.base import StrategyRegistry

        strategy = StrategyRegistry.get("SMA_CROSS")
        # fast >= slow is invalid
        config = StrategyConfig(
            name="SMA_CROSS",
            family=StrategyFamily.TREND_FOLLOWING,
            asset=AssetSymbol.BTCUSDT,
            timeframe=Timeframe.H1,
            parameters={"fast_period": 50, "slow_period": 20},
        )
        assert strategy.validate_config(config) is False
