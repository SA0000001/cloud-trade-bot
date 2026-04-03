"""
Telegram Notification Service.

Sends HTML-formatted messages via the Telegram Bot API.
All message formatting is done in this module — business logic
should only pass data objects, not raw strings.

Setup:
  1. Create a bot via @BotFather
  2. Get the chat_id (use @userinfobot or the getUpdates API)
  3. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env
  4. Set TELEGRAM_ENABLED=true
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import httpx

from app.core.constants import TELEGRAM_MAX_MESSAGE_LENGTH, TELEGRAM_PARSE_MODE
from app.core.enums import NotificationChannel, RiskLevel
from app.core.exceptions import TelegramError
from app.core.interfaces import INotificationService
from app.core.models import RiskState, Signal

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}/sendMessage"


class TelegramService(INotificationService):
    """
    Telegram notification delivery.

    Gracefully degrades: if Telegram is disabled or token is missing,
    all methods log a warning and return False without raising.
    """

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        enabled: bool = False,
    ) -> None:
        self._bot_token = bot_token
        self._chat_id = chat_id
        self._enabled = enabled

        if enabled and not (bot_token and chat_id):
            logger.warning(
                "TelegramService: enabled=True but token/chat_id missing. "
                "Notifications will be silently dropped."
            )

    @classmethod
    def from_settings(cls) -> "TelegramService":
        from app.config.settings import settings
        return cls(
            bot_token=settings.telegram.bot_token.get_secret_value()
                if settings.telegram.bot_token else None,
            chat_id=settings.telegram.chat_id,
            enabled=settings.telegram.enabled,
        )

    @property
    def channel(self) -> NotificationChannel:
        return NotificationChannel.TELEGRAM

    def send(self, message: str, parse_mode: str = TELEGRAM_PARSE_MODE) -> bool:
        """Send a raw message string."""
        if not self._is_ready():
            return False

        # Truncate if needed
        if len(message) > TELEGRAM_MAX_MESSAGE_LENGTH:
            message = message[: TELEGRAM_MAX_MESSAGE_LENGTH - 20] + "\n...<truncated>"

        url = TELEGRAM_API_BASE.format(token=self._bot_token)
        payload = {
            "chat_id": self._chat_id,
            "text": message,
            "parse_mode": parse_mode,
        }

        try:
            response = httpx.post(url, json=payload, timeout=10.0)
            response.raise_for_status()
            return True
        except httpx.HTTPStatusError as exc:
            logger.error("Telegram API error: %s — %s", exc.response.status_code, exc.response.text)
            return False
        except Exception as exc:
            logger.error("Telegram send error: %s", exc)
            return False

    def send_signal_alert(self, signal: Signal) -> bool:
        """Send a formatted trading signal notification."""
        direction_emoji = "🟢 LONG" if "LONG" in str(signal.direction) else "🔴 SHORT"
        robustness_emoji = {
            "ROBUST": "✅",
            "ACCEPTABLE": "⚠️",
            "FRAGILE": "❗",
            "OVERFIT": "🚫",
        }.get(str(signal.robustness_label), "❓")

        message = (
            f"<b>📊 NEW SIGNAL — {signal.asset}</b>\n"
            f"{'─' * 30}\n"
            f"<b>Strategy:</b> {signal.strategy_name}\n"
            f"<b>Timeframe:</b> {signal.timeframe}\n"
            f"<b>Direction:</b> {direction_emoji}\n"
            f"\n"
            f"<b>Entry:</b> <code>{signal.entry_price:.4f}</code>\n"
            f"<b>Stop Loss:</b> <code>{signal.stop_loss:.4f}</code>\n"
            f"<b>Take Profit:</b> <code>{signal.take_profit:.4f}</code>\n"
            f"<b>ATR:</b> <code>{signal.atr:.4f}</code>\n"
            f"\n"
            f"<b>Robustness:</b> {robustness_emoji} {signal.robustness_label}\n"
            f"<b>Regime:</b> {signal.regime}\n"
            f"\n"
            f"<i>{signal.reason}</i>\n"
            f"\n"
            f"🕐 {signal.generated_at.strftime('%Y-%m-%d %H:%M UTC')}\n"
            f"\n"
            f"<b>⚠️ PAPER TRADING ONLY — Manual execution required</b>"
        )
        return self.send(message)

    def send_risk_alert(self, risk_state: RiskState, context: str = "") -> bool:
        """Send a risk threshold / emergency notification."""
        level_emoji = {
            RiskLevel.WARNING: "⚠️",
            RiskLevel.SOFT_STOP: "🛑",
            RiskLevel.HARD_STOP: "🚨",
            RiskLevel.EMERGENCY: "🆘",
        }.get(risk_state.level, "ℹ️")

        message = (
            f"<b>{level_emoji} RISK ALERT — {risk_state.level}</b>\n"
            f"{'─' * 30}\n"
            f"<b>Engine State:</b> {risk_state.engine_state}\n"
            f"<b>Daily DD:</b> {risk_state.daily_drawdown_pct * 100:.1f}%\n"
            f"<b>Weekly DD:</b> {risk_state.weekly_drawdown_pct * 100:.1f}%\n"
            f"<b>Total DD:</b> {risk_state.total_drawdown_pct * 100:.1f}%\n"
            f"<b>New Signals Blocked:</b> {'YES' if risk_state.no_new_signals else 'NO'}\n"
        )
        if risk_state.emergency_reason:
            message += f"\n<b>Reason:</b> {risk_state.emergency_reason}\n"
        if context:
            message += f"\n<i>{context}</i>\n"
        message += f"\n🕐 {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"

        return self.send(message)

    def send_heartbeat_alert(self, service_name: str, last_seen_ago: float) -> bool:
        """Alert when a service heartbeat goes stale."""
        message = (
            f"<b>💔 HEARTBEAT MISSING</b>\n"
            f"{'─' * 30}\n"
            f"<b>Service:</b> {service_name}\n"
            f"<b>Last seen:</b> {last_seen_ago:.0f}s ago\n"
            f"<b>Status:</b> STALE — check the engine\n"
            f"\n🕐 {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
        )
        return self.send(message)

    def send_strategy_degraded(self, strategy_name: str, asset: str, details: str) -> bool:
        message = (
            f"<b>📉 STRATEGY DEGRADED</b>\n"
            f"{'─' * 30}\n"
            f"<b>Strategy:</b> {strategy_name}\n"
            f"<b>Asset:</b> {asset}\n"
            f"\n{details}\n"
            f"\n🕐 {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
        )
        return self.send(message)

    def _is_ready(self) -> bool:
        if not self._enabled:
            logger.debug("TelegramService: disabled, skipping send.")
            return False
        if not self._bot_token or not self._chat_id:
            logger.warning("TelegramService: missing token or chat_id.")
            return False
        return True
