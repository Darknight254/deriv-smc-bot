"""
Backtester
Tests SMC bot strategy against historical data
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass

from src.market_structure import Candle, MarketStructureEngine
from src.liquidity_engine import LiquidityEngine
from src.fvg_engine import FVGEngine
from src.order_block_engine import OrderBlockEngine
from src.pd_array_engine import PDArrayEngine
from src.trade_scoring import TradeScorer
from src.risk_manager import RiskManager, Position

logger = logging.getLogger(__name__)


@dataclass
class BacktestStats:
    """Backtesting statistics"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    total_pnl_percent: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    max_drawdown: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    consecutive_wins: int = 0
    consecutive_losses: int = 0
    sharpe_ratio: float = 0.0


class Backtester:
    """
    Backtests trading strategy on historical candle data
    """

    def __init__(
        self,
        timeframes: List[int] = None,
        initial_balance: float = 1000.0,
    ):
        """
        Initialize backtester
        
        Args:
            timeframes: List of timeframes to analyze
            initial_balance: Starting account balance
        """
        self.timeframes = timeframes or [1, 5, 15]
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        
        # Initialize analysis engines
        self.market_structure = MarketStructureEngine(timeframes=self.timeframes)
        self.liquidity_engine = LiquidityEngine(timeframes=self.timeframes)
        self.fvg_engine = FVGEngine(timeframes=self.timeframes)
        self.order_block_engine = OrderBlockEngine(timeframes=self.timeframes)
        self.pd_array_engine = PDArrayEngine(timeframes=self.timeframes)
        self.trade_scorer = TradeScorer()
        self.risk_manager = RiskManager(account_balance=initial_balance)
        
        # Results
        self.trades: List[Dict] = []
        self.signals: List[Dict] = []

    def backtest(
        self,
        candles_data: Dict[int, List[Candle]],
        symbol: str,
    ) -> BacktestStats:
        """
        Run backtest on historical candle data
        
        Args:
            candles_data: Dict of timeframe -> list of candles
            symbol: Trading symbol
        
        Returns:
            BacktestStats object
        """
        logger.info(f"Starting backtest for {symbol}")
        
        # Process candles chronologically
        all_candles = []
        for tf, candles in candles_data.items():
            all_candles.extend([(tf, c) for c in candles])
        
        all_candles.sort(key=lambda x: x[1].timestamp)
        
        # Process each candle
        for timeframe, candle in all_candles:
            # Add to market structure
            self.market_structure.add_candle(candle, timeframe)
            
            # Detect signals
            signal = self._check_signal(timeframe, candle, symbol)
            if signal:
                self.signals.append(signal)
        
        # Calculate statistics
        stats = self._calculate_stats()
        return stats

    def _check_signal(
        self,
        timeframe: int,
        candle: Candle,
        symbol: str,
    ) -> Optional[Dict]:
        """
        Check for trading signal
        
        Args:
            timeframe: Candle timeframe
            candle: Candle data
            symbol: Trading symbol
        
        Returns:
            Signal dict if found, None otherwise
        """
        structure_state = self.market_structure.get_structure_state(timeframe)
        
        # Simple signal: BOS + higher TF bias
        if (
            structure_state.last_bos
            and self.market_structure.is_higher_timeframe_bullish(timeframe)
            and structure_state.last_bos.type == "bullish"
        ):
            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "direction": "long",
                "entry_price": candle.close,
                "timestamp": candle.timestamp,
            }
        
        elif (
            structure_state.last_bos
            and self.market_structure.is_higher_timeframe_bearish(timeframe)
            and structure_state.last_bos.type == "bearish"
        ):
            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "direction": "short",
                "entry_price": candle.close,
                "timestamp": candle.timestamp,
            }
        
        return None

    def _calculate_stats(self) -> BacktestStats:
        """
        Calculate backtest statistics
        
        Returns:
            BacktestStats object
        """
        stats = BacktestStats()
        
        if not self.trades:
            return stats
        
        # Basic stats
        stats.total_trades = len(self.trades)
        stats.winning_trades = sum(1 for t in self.trades if t["pnl"] > 0)
        stats.losing_trades = sum(1 for t in self.trades if t["pnl"] < 0)
        
        if stats.total_trades > 0:
            stats.win_rate = (stats.winning_trades / stats.total_trades) * 100
        
        # PnL stats
        stats.total_pnl = sum(t["pnl"] for t in self.trades)
        stats.total_pnl_percent = (stats.total_pnl / self.initial_balance) * 100
        
        # Win/Loss averages
        winning_trades = [t for t in self.trades if t["pnl"] > 0]
        losing_trades = [t for t in self.trades if t["pnl"] < 0]
        
        if winning_trades:
            stats.avg_win = sum(t["pnl"] for t in winning_trades) / len(winning_trades)
            stats.largest_win = max(t["pnl"] for t in winning_trades)
        
        if losing_trades:
            stats.avg_loss = abs(sum(t["pnl"] for t in losing_trades) / len(losing_trades))
            stats.largest_loss = abs(min(t["pnl"] for t in losing_trades))
        
        # Profit factor
        total_wins = sum(t["pnl"] for t in winning_trades) if winning_trades else 0
        total_losses = abs(sum(t["pnl"] for t in losing_trades)) if losing_trades else 1
        stats.profit_factor = total_wins / total_losses if total_losses > 0 else 0
        
        logger.info(f"Backtest complete: {stats.total_trades} trades, {stats.win_rate:.1f}% win rate")
        return stats

    def print_report(self, stats: BacktestStats) -> None:
        """
        Print backtest report
        
        Args:
            stats: BacktestStats object
        """
        print("\n" + "="*60)
        print("BACKTEST REPORT")
        print("="*60)
        print(f"Total Trades:     {stats.total_trades}")
        print(f"Winning Trades:   {stats.winning_trades}")
        print(f"Losing Trades:    {stats.losing_trades}")
        print(f"Win Rate:         {stats.win_rate:.2f}%")
        print(f"\nProfit/Loss:      ${stats.total_pnl:.2f} ({stats.total_pnl_percent:.2f}%)")
        print(f"Profit Factor:    {stats.profit_factor:.2f}")
        print(f"Avg Win:          ${stats.avg_win:.2f}")
        print(f"Avg Loss:         ${stats.avg_loss:.2f}")
        print(f"Largest Win:      ${stats.largest_win:.2f}")
        print(f"Largest Loss:     ${stats.largest_loss:.2f}")
        print("="*60 + "\n")
