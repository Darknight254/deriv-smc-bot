"""
Main Trading Bot
Orchestrates all modules and runs the trading system
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, List
import json

from src.deriv_api_client import DerivAPIClient
from src.multi_symbol_manager import MultiSymbolManager
from src.market_structure import Candle
from src.alert_system import AlertSystem, AlertType, AlertSeverity
from src.risk_manager import RiskManager
from src.database_manager import DatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("./logs/bot.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


class DerivSMCBot:
    """
    Main trading bot orchestrator
    """

    def __init__(
        self,
        api_token: str,
        app_id: str = "9305",
        symbols: List[str] = None,
        timeframes: List[int] = None,
        account_balance: float = 1000.0,
    ):
        """
        Initialize the bot
        
        Args:
            api_token: Deriv API token
            app_id: Deriv app ID
            symbols: List of symbols to trade
            timeframes: List of timeframes to analyze
            account_balance: Starting account balance
        """
        self.api_token = api_token
        self.app_id = app_id
        self.symbols = symbols or ["R_100", "R_50", "R_10"]
        self.timeframes = timeframes or [1, 5, 15]
        
        # Initialize components
        self.deriv_client = DerivAPIClient(api_token, app_id)
        self.symbol_manager = MultiSymbolManager(self.timeframes)
        self.alert_system = AlertSystem()
        self.risk_manager = RiskManager(account_balance=account_balance)
        self.database = DatabaseManager()
        
        # State
        self.is_running = False
        self.candle_buffers = {}  # Buffer for building candles
        self.trades_placed = []
        
        logger.info(f"Bot initialized: {', '.join(self.symbols)} | TF: {self.timeframes}")

    async def start(self) -> None:
        """
        Start the trading bot
        """
        try:
            logger.info("Starting Deriv SMC Bot...")
            self.is_running = True
            
            # Connect to Deriv
            if not await self.deriv_client.connect():
                logger.error("Failed to connect to Deriv API")
                return
            
            # Add symbols to manager
            for symbol in self.symbols:
                self.symbol_manager.add_symbol(symbol)
            
            # Subscribe to market data
            for symbol in self.symbols:
                # Subscribe to ticks
                await self.deriv_client.subscribe_ticks(
                    symbol,
                    self._handle_tick,
                )
                
                # Subscribe to candles for each timeframe
                for tf in self.timeframes:
                    granularity = tf * 60  # Convert minutes to seconds
                    await self.deriv_client.subscribe_candles(
                        symbol,
                        granularity,
                        self._handle_candle,
                    )
            
            logger.info("Bot started successfully")
            
            # Keep bot running
            while self.is_running:
                await asyncio.sleep(1)
        
        except Exception as e:
            logger.error(f"Error starting bot: {str(e)}")
            self.is_running = False

    async def stop(self) -> None:
        """
        Stop the trading bot
        """
        logger.info("Stopping bot...")
        self.is_running = False
        await self.deriv_client.disconnect()

    async def _handle_tick(self, tick_data: dict) -> None:
        """
        Handle tick data update
        
        Args:
            tick_data: Tick data from Deriv API
        """
        try:
            symbol = tick_data.get("symbol")
            ask = tick_data.get("ask")
            bid = tick_data.get("bid")
            timestamp = datetime.fromtimestamp(tick_data.get("epoch", 0))
            
            # Could use this for real-time updates if needed
            logger.debug(f"{symbol}: Ask={ask}, Bid={bid}")
        
        except Exception as e:
            logger.error(f"Error handling tick: {str(e)}")

    async def _handle_candle(self, candle_data: dict) -> None:
        """
        Handle candle data update
        
        Args:
            candle_data: Candle data from Deriv API
        """
        try:
            symbol = candle_data.get("symbol")
            timeframe = candle_data.get("granularity") // 60  # Convert seconds to minutes
            
            candle = Candle(
                timestamp=datetime.fromtimestamp(candle_data.get("close_time", 0)),
                open_price=candle_data.get("open", 0),
                high=candle_data.get("high", 0),
                low=candle_data.get("low", 0),
                close=candle_data.get("close", 0),
                volume=candle_data.get("volume", 0),
                timeframe=timeframe,
            )
            
            # Process candle
            opportunity = self.symbol_manager.process_candle(symbol, timeframe, candle)
            
            # Check for trade signal
            if opportunity:
                await self._process_trade_opportunity(opportunity)
        
        except Exception as e:
            logger.error(f"Error handling candle: {str(e)}")

    async def _process_trade_opportunity(self, opportunity: dict) -> None:
        """
        Process a trade opportunity
        
        Args:
            opportunity: Trade opportunity dict from analysis
        """
        try:
            symbol = opportunity["symbol"]
            direction = opportunity["direction"]
            entry_price = opportunity["entry_price"]
            score = opportunity["score"]
            
            logger.info(
                f"Trade opportunity: {symbol} {direction.upper()} @ {entry_price} "
                f"Score: {score:.1f} Factors: {opportunity['confluence_factors']}"
            )
            
            # Create alert
            alert = self.alert_system.create_alert(
                alert_type=AlertType.SETUP_FORMED,
                severity=AlertSeverity.HIGH if score >= 90 else AlertSeverity.MEDIUM,
                symbol=symbol,
                timeframe=opportunity["timeframe"],
                title=f"{direction.upper()} Setup Detected: {symbol}",
                message=f"Score: {score:.1f}/100\nFactors: {', '.join(opportunity['factors'])}",
                details=opportunity,
            )
            
            await self.alert_system.send_alert(alert)
            
            # Calculate position size
            # This is a simplified example - in production, use proper risk calculation
            stop_loss = entry_price * 0.995 if direction == "long" else entry_price * 1.005
            take_profit = entry_price * 1.015 if direction == "long" else entry_price * 0.985
            
            position_size = self.risk_manager.calculate_position_size(
                entry_price=entry_price,
                stop_loss=stop_loss,
                symbol=symbol,
            )
            
            # Try to place trade
            if position_size > 0:
                contract_type = "CALL" if direction == "long" else "PUT"
                
                response = await self.deriv_client.buy_contract(
                    symbol=symbol,
                    amount=10,  # Stake amount
                    contract_type=contract_type,
                    duration=5,
                    duration_unit="m",
                )
                
                if response.get("buy"):
                    logger.info(f"Trade executed: {symbol} {direction.upper()}")
                    
                    # Create entry alert
                    entry_alert = self.alert_system.create_alert(
                        alert_type=AlertType.ENTRY_EXECUTED,
                        severity=AlertSeverity.HIGH,
                        symbol=symbol,
                        timeframe=opportunity["timeframe"],
                        title=f"Trade Entered: {symbol}",
                        message=f"Entry: {entry_price}\nSL: {stop_loss}\nTP: {take_profit}",
                        details=response,
                    )
                    
                    await self.alert_system.send_alert(entry_alert)
        
        except Exception as e:
            logger.error(f"Error processing trade opportunity: {str(e)}")

    def get_bot_status(self) -> dict:
        """
        Get current bot status
        
        Returns:
            Status dict
        """
        return {
            "is_running": self.is_running,
            "symbols_monitored": self.symbols,
            "timeframes": self.timeframes,
            "connected": self.deriv_client.is_connected,
            "risk_manager": self.risk_manager.get_daily_stats(),
            "alerts_sent": len(self.alert_system.alert_history),
        }


async def main():
    """
    Main entry point
    """
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    api_token = os.getenv("DERIV_API_TOKEN")
    if not api_token:
        logger.error("DERIV_API_TOKEN not set in .env")
        return
    
    # Initialize bot
    bot = DerivSMCBot(
        api_token=api_token,
        symbols=["R_100", "R_50", "R_10"],
        timeframes=[1, 5, 15],
        account_balance=1000.0,
    )
    
    try:
        # Start bot
        await bot.start()
    
    except KeyboardInterrupt:
        logger.info("Shutdown signal received")
        await bot.stop()
    
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())
