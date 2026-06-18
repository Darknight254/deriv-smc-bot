"""
Risk Manager
Handles position sizing, stop loss, take profit, daily drawdown limits
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, List
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class PositionStatus(Enum):
    """Position status"""
    OPEN = "open"
    CLOSED = "closed"
    STOP_LOSS_HIT = "stop_loss_hit"
    TAKE_PROFIT_HIT = "take_profit_hit"


@dataclass
class Position:
    """Represents an open trading position"""
    position_id: str
    symbol: str
    direction: str  # 'long' or 'short'
    entry_price: float
    quantity: float
    entry_time: datetime
    
    stop_loss: float
    take_profit: float
    risk_amount: float
    reward_amount: float
    risk_reward_ratio: float
    
    status: PositionStatus = PositionStatus.OPEN
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    pnl: float = 0.0
    pnl_percent: float = 0.0
    
    # Metadata
    trade_score: float = 0.0
    setup_factors: int = 0
    candle_index_at_entry: int = 0


class RiskManager:
    """
    Manages risk parameters and position sizing
    """

    def __init__(
        self,
        account_balance: float,
        risk_per_trade_percent: float = 0.5,
        max_daily_losses: int = 3,
        max_drawdown_percent: float = 5.0,
        min_risk_reward_ratio: float = 3.0,
        max_concurrent_trades: int = 2,
    ):
        """
        Initialize Risk Manager
        
        Args:
            account_balance: Starting account balance
            risk_per_trade_percent: Risk per trade as % of account
            max_daily_losses: Maximum losing trades per day
            max_drawdown_percent: Maximum drawdown % before stopping
            min_risk_reward_ratio: Minimum RR ratio to take trade
            max_concurrent_trades: Maximum open positions
        """
        self.account_balance = account_balance
        self.current_balance = account_balance
        self.risk_per_trade_percent = risk_per_trade_percent
        self.max_daily_losses = max_daily_losses
        self.max_drawdown_percent = max_drawdown_percent
        self.min_risk_reward_ratio = min_risk_reward_ratio
        self.max_concurrent_trades = max_concurrent_trades
        
        self.open_positions: Dict[str, Position] = {}
        self.closed_positions: List[Position] = []
        self.daily_losses_count: int = 0
        self.today_realized_pnl: float = 0.0

    def calculate_position_size(
        self,
        entry_price: float,
        stop_loss: float,
        symbol: str,
    ) -> float:
        """
        Calculate position size based on risk management rules
        
        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            symbol: Trading symbol
        
        Returns:
            Position quantity to trade
        """
        # Risk amount per trade
        risk_amount = self.current_balance * (self.risk_per_trade_percent / 100)
        
        # Price distance to stop loss
        price_distance = abs(entry_price - stop_loss)
        
        if price_distance == 0:
            logger.warning("Price distance to SL is zero, cannot calculate position size")
            return 0
        
        # Position size = Risk Amount / Price Distance
        position_size = risk_amount / price_distance
        
        logger.info(
            f"Position size calculated for {symbol}: {position_size:.2f} "
            f"(Risk: ${risk_amount:.2f}, Distance: ${price_distance:.4f})"
        )
        
        return position_size

    def create_position(
        self,
        position_id: str,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        quantity: float,
        trade_score: float,
        setup_factors: int,
        candle_index: int,
    ) -> Optional[Position]:
        """
        Create a new position with risk checks
        
        Args:
            position_id: Unique position ID
            symbol: Trading symbol
            direction: 'long' or 'short'
            entry_price: Entry price
            stop_loss: Stop loss price
            take_profit: Take profit price
            quantity: Position quantity
            trade_score: Trade confluence score (0-100)
            setup_factors: Number of SMC factors
            candle_index: Candle index at entry
        
        Returns:
            Position object if valid, None if risk checks fail
        """
        # Check: Max concurrent trades
        if len(self.open_positions) >= self.max_concurrent_trades:
            logger.warning(f"Max concurrent trades ({self.max_concurrent_trades}) reached")
            return None
        
        # Check: Daily loss limit
        if self.daily_losses_count >= self.max_daily_losses:
            logger.warning(f"Daily loss limit ({self.max_daily_losses}) reached")
            return None
        
        # Check: Drawdown limit
        drawdown_percent = ((self.account_balance - self.current_balance) / self.account_balance) * 100
        if drawdown_percent >= self.max_drawdown_percent:
            logger.warning(f"Drawdown limit ({self.max_drawdown_percent}%) exceeded")
            return None
        
        # Calculate risk/reward
        risk_amount = abs(entry_price - stop_loss) * quantity
        reward_amount = abs(take_profit - entry_price) * quantity
        rr_ratio = reward_amount / risk_amount if risk_amount > 0 else 0
        
        # Check: Risk/Reward ratio
        if rr_ratio < self.min_risk_reward_ratio:
            logger.warning(
                f"RR ratio ({rr_ratio:.2f}:1) below minimum ({self.min_risk_reward_ratio}:1)"
            )
            return None
        
        # Create position
        position = Position(
            position_id=position_id,
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            quantity=quantity,
            entry_time=datetime.utcnow(),
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_amount=risk_amount,
            reward_amount=reward_amount,
            risk_reward_ratio=rr_ratio,
            trade_score=trade_score,
            setup_factors=setup_factors,
            candle_index_at_entry=candle_index,
        )
        
        self.open_positions[position_id] = position
        logger.info(
            f"Position created: {symbol} {direction.upper()} @ {entry_price} "
            f"SL:{stop_loss} TP:{take_profit} RR:{rr_ratio:.2f}:1"
        )
        
        return position

    def close_position(
        self,
        position_id: str,
        exit_price: float,
        reason: str = "manual",
    ) -> Optional[Position]:
        """
        Close an open position
        
        Args:
            position_id: Position ID
            exit_price: Exit price
            reason: Reason for closing ('manual', 'tp', 'sl')
        
        Returns:
            Closed position with PnL, or None if not found
        """
        if position_id not in self.open_positions:
            logger.warning(f"Position {position_id} not found")
            return None
        
        position = self.open_positions[position_id]
        position.exit_price = exit_price
        position.exit_time = datetime.utcnow()
        
        # Calculate PnL
        if position.direction == "long":
            position.pnl = (exit_price - position.entry_price) * position.quantity
        else:  # short
            position.pnl = (position.entry_price - exit_price) * position.quantity
        
        position.pnl_percent = (position.pnl / (position.entry_price * position.quantity)) * 100
        
        # Update status
        if reason == "sl":
            position.status = PositionStatus.STOP_LOSS_HIT
            self.daily_losses_count += 1
        elif reason == "tp":
            position.status = PositionStatus.TAKE_PROFIT_HIT
        else:
            position.status = PositionStatus.CLOSED
        
        # Update balance
        self.current_balance += position.pnl
        self.today_realized_pnl += position.pnl
        
        # Move to closed
        del self.open_positions[position_id]
        self.closed_positions.append(position)
        
        logger.info(
            f"Position closed: {position.symbol} PnL: ${position.pnl:.2f} ({position.pnl_percent:+.2f}%)"
        )
        
        return position

    def get_open_positions(self) -> Dict[str, Position]:
        """Get all open positions"""
        return self.open_positions.copy()

    def get_daily_stats(self) -> Dict:
        """Get daily trading statistics"""
        return {
            "starting_balance": self.account_balance,
            "current_balance": self.current_balance,
            "realized_pnl": self.today_realized_pnl,
            "unrealized_pnl": sum(
                (p.exit_price - p.entry_price) * p.quantity
                for p in self.open_positions.values()
                if p.exit_price
            ),
            "daily_losses": self.daily_losses_count,
            "open_positions": len(self.open_positions),
            "closed_positions": len(self.closed_positions),
            "drawdown_percent": ((self.account_balance - self.current_balance) / self.account_balance) * 100,
        }
