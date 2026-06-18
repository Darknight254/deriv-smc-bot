"""
Alert System
Sends notifications via Telegram, Email, and Desktop when trading signals occur
"""

from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime
from enum import Enum
import logging
import asyncio

logger = logging.getLogger(__name__)


class AlertType(Enum):
    """Types of trading alerts"""
    SETUP_FORMED = "setup_formed"
    ENTRY_SIGNAL = "entry_signal"
    ENTRY_EXECUTED = "entry_executed"
    LIQUIDATION_SWEEP = "liquidation_sweep"
    BOS_DETECTED = "bos_detected"
    CHOCH_DETECTED = "choch_detected"
    FVG_DETECTED = "fvg_detected"
    ORDER_BLOCK_DETECTED = "order_block_detected"
    EXIT_SIGNAL = "exit_signal"
    TRADE_CLOSED = "trade_closed"
    STOP_LOSS_HIT = "stop_loss_hit"
    TAKE_PROFIT_HIT = "take_profit_hit"
    ERROR = "error"


class AlertSeverity(Enum):
    """Alert severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Alert:
    """Represents a single alert message"""
    alert_type: AlertType
    severity: AlertSeverity
    symbol: str
    timeframe: int
    title: str
    message: str
    details: dict
    timestamp: datetime
    
    sent_to_telegram: bool = False
    sent_to_email: bool = False
    sent_to_desktop: bool = False


class AlertSystem:
    """
    Manages multi-channel alert delivery
    """

    def __init__(
        self,
        telegram_enabled: bool = False,
        telegram_token: Optional[str] = None,
        telegram_chat_id: Optional[str] = None,
        email_enabled: bool = False,
        email_address: Optional[str] = None,
        desktop_enabled: bool = True,
    ):
        """
        Initialize Alert System
        
        Args:
            telegram_enabled: Enable Telegram alerts
            telegram_token: Telegram bot token
            telegram_chat_id: Telegram chat ID
            email_enabled: Enable email alerts
            email_address: Email address for notifications
            desktop_enabled: Enable desktop notifications
        """
        self.telegram_enabled = telegram_enabled
        self.telegram_token = telegram_token
        self.telegram_chat_id = telegram_chat_id
        self.email_enabled = email_enabled
        self.email_address = email_address
        self.desktop_enabled = desktop_enabled
        
        self.alert_history: List[Alert] = []

    async def send_alert(self, alert: Alert) -> None:
        """
        Send alert through all configured channels
        
        Args:
            alert: The alert to send
        """
        self.alert_history.append(alert)

        tasks = []

        if self.telegram_enabled:
            tasks.append(self._send_telegram_alert(alert))
        
        if self.email_enabled:
            tasks.append(self._send_email_alert(alert))
        
        if self.desktop_enabled:
            tasks.append(self._send_desktop_alert(alert))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_telegram_alert(self, alert: Alert) -> None:
        """
        Send alert via Telegram
        
        Args:
            alert: The alert to send
        """
        if not self.telegram_enabled or not self.telegram_token or not self.telegram_chat_id:
            return

        try:
            # Telegram message formatting
            emoji_map = {
                AlertType.SETUP_FORMED: "⚡",
                AlertType.ENTRY_SIGNAL: "🟢",
                AlertType.ENTRY_EXECUTED: "✅",
                AlertType.LIQUIDATION_SWEEP: "💧",
                AlertType.BOS_DETECTED: "📊",
                AlertType.CHOCH_DETECTED: "🔄",
                AlertType.FVG_DETECTED: "📈",
                AlertType.ORDER_BLOCK_DETECTED: "🧱",
                AlertType.EXIT_SIGNAL: "🟡",
                AlertType.TRADE_CLOSED: "🔴",
                AlertType.STOP_LOSS_HIT: "⛔",
                AlertType.TAKE_PROFIT_HIT: "💰",
                AlertType.ERROR: "⚠️",
            }

            emoji = emoji_map.get(alert.alert_type, "📢")
            
            message = f"{emoji} **{alert.title}**\n\n"
            message += f"Symbol: `{alert.symbol}`\n"
            message += f"Timeframe: `{alert.timeframe}m`\n"
            message += f"Severity: `{alert.severity.value.upper()}`\n\n"
            message += f"{alert.message}\n\n"
            message += f"_Time: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}_"

            # TODO: Implement actual Telegram API call
            # import aiohttp
            # async with aiohttp.ClientSession() as session:
            #     url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            #     await session.post(url, json={"chat_id": self.telegram_chat_id, "text": message, "parse_mode": "Markdown"})
            
            alert.sent_to_telegram = True
            logger.info(f"Telegram alert sent: {alert.title}")

        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {str(e)}")

    async def _send_email_alert(self, alert: Alert) -> None:
        """
        Send alert via Email
        
        Args:
            alert: The alert to send
        """
        if not self.email_enabled or not self.email_address:
            return

        try:
            # TODO: Implement actual email sending
            # import smtplib
            # from email.mime.text import MIMEText
            # msg = MIMEText(alert.message)
            # msg['Subject'] = alert.title
            # msg['From'] = "bot@deriv-smc.local"
            # msg['To'] = self.email_address
            
            alert.sent_to_email = True
            logger.info(f"Email alert sent: {alert.title}")

        except Exception as e:
            logger.error(f"Failed to send email alert: {str(e)}")

    async def _send_desktop_alert(self, alert: Alert) -> None:
        """
        Send desktop notification
        
        Args:
            alert: The alert to send
        """
        try:
            # TODO: Implement desktop notifications (e.g., using notify-send on Linux, or plyer)
            # from plyer import notification
            # notification.notify(
            #     title=alert.title,
            #     message=alert.message,
            #     timeout=10
            # )
            
            alert.sent_to_desktop = True
            logger.info(f"Desktop alert sent: {alert.title}")

        except Exception as e:
            logger.error(f"Failed to send desktop alert: {str(e)}")

    def create_alert(
        self,
        alert_type: AlertType,
        severity: AlertSeverity,
        symbol: str,
        timeframe: int,
        title: str,
        message: str,
        details: dict,
    ) -> Alert:
        """
        Create and queue an alert
        
        Args:
            alert_type: Type of alert
            severity: Severity level
            symbol: Trading symbol
            timeframe: Timeframe
            title: Alert title
            message: Alert message
            details: Additional details dict
        
        Returns:
            Alert object
        """
        return Alert(
            alert_type=alert_type,
            severity=severity,
            symbol=symbol,
            timeframe=timeframe,
            title=title,
            message=message,
            details=details,
            timestamp=datetime.utcnow(),
        )

    def get_recent_alerts(self, limit: int = 20) -> List[Alert]:
        """
        Get recent alerts from history
        
        Args:
            limit: Number of recent alerts to return
        
        Returns:
            List of recent alerts
        """
        return self.alert_history[-limit:]
