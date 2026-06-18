"""
Database Layer
Stores trade history for analysis, learning, and backtesting
"""

from sqlalchemy import create_engine, Column, String, Float, Integer, DateTime, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import logging
import json

logger = logging.getLogger(__name__)

Base = declarative_base()


class TradeRecord(Base):
    """SQLAlchemy model for storing trades"""
    __tablename__ = "trades"
    
    id = Column(Integer, primary_key=True)
    trade_id = Column(String, unique=True)
    symbol = Column(String)
    direction = Column(String)  # 'long' or 'short'
    entry_time = Column(DateTime)
    exit_time = Column(DateTime, nullable=True)
    
    entry_price = Column(Float)
    exit_price = Column(Float, nullable=True)
    stop_loss = Column(Float)
    take_profit = Column(Float)
    
    quantity = Column(Float)
    pnl = Column(Float, nullable=True)
    pnl_percent = Column(Float, nullable=True)
    
    # SMC Setup details
    setup_factors = Column(Integer)  # Number of confluence factors
    trade_score = Column(Float)  # 0-100
    
    # SMC Components present
    has_liquidity_sweep = Column(Boolean)
    has_bos = Column(Boolean)
    has_choch = Column(Boolean)
    has_fvg = Column(Boolean)
    has_order_block = Column(Boolean)
    has_pd_alignment = Column(Boolean)
    
    # Additional context
    timeframe = Column(Integer)
    higher_tf_bias = Column(String)  # 'bullish', 'bearish', 'neutral'
    notes = Column(String, nullable=True)
    
    # JSON fields for detailed analysis
    fvg_details = Column(JSON, nullable=True)
    order_block_details = Column(JSON, nullable=True)
    liquidity_details = Column(JSON, nullable=True)


class DatabaseManager:
    """
    Manages database operations for trade storage
    """

    def __init__(self, db_path: str = "./data/trades.db"):
        """
        Initialize database manager
        
        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def save_trade(
        self,
        trade_data: dict,
    ) -> bool:
        """
        Save a completed trade to database
        
        Args:
            trade_data: Dictionary with trade information
        
        Returns:
            True if successful, False otherwise
        """
        try:
            session = self.Session()
            
            trade = TradeRecord(
                trade_id=trade_data.get("trade_id"),
                symbol=trade_data.get("symbol"),
                direction=trade_data.get("direction"),
                entry_time=trade_data.get("entry_time"),
                exit_time=trade_data.get("exit_time"),
                entry_price=trade_data.get("entry_price"),
                exit_price=trade_data.get("exit_price"),
                stop_loss=trade_data.get("stop_loss"),
                take_profit=trade_data.get("take_profit"),
                quantity=trade_data.get("quantity"),
                pnl=trade_data.get("pnl"),
                pnl_percent=trade_data.get("pnl_percent"),
                setup_factors=trade_data.get("setup_factors", 0),
                trade_score=trade_data.get("trade_score", 0),
                has_liquidity_sweep=trade_data.get("has_liquidity_sweep", False),
                has_bos=trade_data.get("has_bos", False),
                has_choch=trade_data.get("has_choch", False),
                has_fvg=trade_data.get("has_fvg", False),
                has_order_block=trade_data.get("has_order_block", False),
                has_pd_alignment=trade_data.get("has_pd_alignment", False),
                timeframe=trade_data.get("timeframe"),
                higher_tf_bias=trade_data.get("higher_tf_bias"),
                notes=trade_data.get("notes"),
                fvg_details=trade_data.get("fvg_details"),
                order_block_details=trade_data.get("order_block_details"),
                liquidity_details=trade_data.get("liquidity_details"),
            )
            
            session.add(trade)
            session.commit()
            session.close()
            
            logger.info(f"Trade saved: {trade_data.get('trade_id')}")
            return True
        
        except Exception as e:
            logger.error(f"Error saving trade: {str(e)}")
            return False

    def get_trade_history(
        self,
        symbol: str = None,
        limit: int = 100,
    ) -> list:
        """
        Retrieve trade history
        
        Args:
            symbol: Filter by symbol, or None for all
            limit: Number of trades to return
        
        Returns:
            List of trade records
        """
        try:
            session = self.Session()
            query = session.query(TradeRecord)
            
            if symbol:
                query = query.filter(TradeRecord.symbol == symbol)
            
            trades = query.order_by(TradeRecord.entry_time.desc()).limit(limit).all()
            session.close()
            
            return trades
        
        except Exception as e:
            logger.error(f"Error retrieving trades: {str(e)}")
            return []

    def get_win_rate(
        self,
        symbol: str = None,
        setup_factors: int = None,
    ) -> dict:
        """
        Calculate win rate statistics
        
        Args:
            symbol: Filter by symbol, or None for all
            setup_factors: Filter by number of setup factors
        
        Returns:
            Dictionary with win rate statistics
        """
        try:
            session = self.Session()
            query = session.query(TradeRecord).filter(TradeRecord.pnl.isnot(None))
            
            if symbol:
                query = query.filter(TradeRecord.symbol == symbol)
            
            if setup_factors:
                query = query.filter(TradeRecord.setup_factors >= setup_factors)
            
            trades = query.all()
            
            if not trades:
                return {"win_rate": 0, "wins": 0, "losses": 0, "profit_factor": 0}
            
            wins = sum(1 for t in trades if t.pnl > 0)
            losses = sum(1 for t in trades if t.pnl < 0)
            total_profit = sum(t.pnl for t in trades if t.pnl > 0)
            total_loss = abs(sum(t.pnl for t in trades if t.pnl < 0))
            
            session.close()
            
            return {
                "win_rate": (wins / len(trades)) * 100 if trades else 0,
                "wins": wins,
                "losses": losses,
                "profit_factor": total_profit / total_loss if total_loss > 0 else 0,
                "avg_win": total_profit / wins if wins > 0 else 0,
                "avg_loss": total_loss / losses if losses > 0 else 0,
            }
        
        except Exception as e:
            logger.error(f"Error calculating win rate: {str(e)}")
            return {}
