"""
Order Block Engine
Detects order blocks (last candle before structure break)
Tracks strength, touches, and mitigation status
"""

from dataclasses import dataclass
from typing import List, Optional, Dict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class OrderBlock:
    """Represents an Order Block"""
    type: str  # 'bullish' or 'bearish'
    high: float
    low: float
    created_at: datetime
    created_candle_index: int
    timeframe: int
    
    # Quality metrics
    strength_score: float = 50.0  # 0-100
    volume_proxy_score: float = 50.0  # 0-100 (estimated from candle size)
    touches: int = 0
    is_mitigated: bool = False
    mitigation_price: Optional[float] = None
    mitigation_candle_index: Optional[int] = None
    
    # Context
    previous_bos_type: Optional[str] = None  # Type of BOS that preceded this OB
    distance_from_liquidity_sweep: float = 0.0


class OrderBlockEngine:
    """
    Detects and tracks order blocks using SMC methodology
    """

    def __init__(self, timeframes: List[int] = None, min_strength_score: float = 70.0):
        """
        Initialize Order Block Engine
        
        Args:
            timeframes: List of timeframes to monitor
            min_strength_score: Minimum strength score to consider an OB (0-100)
        """
        self.timeframes = timeframes or [1, 5, 15]
        self.min_strength_score = min_strength_score
        self.order_blocks: Dict[int, List[OrderBlock]] = {tf: [] for tf in self.timeframes}
        self.active_order_blocks: Dict[int, List[OrderBlock]] = {tf: [] for tf in self.timeframes}

    def detect_order_block(
        self,
        timeframe: int,
        candles: List,
        bos_type: Optional[str] = None,
        liquidity_sweep_distance: float = 0.0,
    ) -> Optional[OrderBlock]:
        """
        Detect an order block (last candle before structure break)
        
        Args:
            timeframe: The timeframe
            candles: List of recent candles
            bos_type: Type of break of structure ('bullish' or 'bearish')
            liquidity_sweep_distance: Distance from liquidity sweep
        
        Returns:
            OrderBlock if detected, None otherwise
        """
        if len(candles) < 2:
            return None

        # The order block is the candle before the BOS
        # For bullish BOS: last bearish candle = bullish OB
        # For bearish BOS: last bullish candle = bearish OB

        ob_candle = candles[-2]  # Second to last

        if bos_type == "bullish":
            # Last bearish candle = bullish order block
            if ob_candle.close < ob_candle.open_price:
                ob = OrderBlock(
                    type="bullish",
                    high=ob_candle.high,
                    low=ob_candle.low,
                    created_at=ob_candle.timestamp,
                    created_candle_index=len(candles) - 2,
                    timeframe=timeframe,
                    previous_bos_type="bullish",
                    distance_from_liquidity_sweep=liquidity_sweep_distance,
                )
                ob.strength_score = self._calculate_ob_strength(ob, candles)
                ob.volume_proxy_score = self._calculate_volume_proxy(ob_candle)

                if ob.strength_score >= self.min_strength_score:
                    self._add_order_block(timeframe, ob)
                    logger.info(f"[TF:{timeframe}] Bullish OB detected: {ob.low} - {ob.high}")
                    return ob

        elif bos_type == "bearish":
            # Last bullish candle = bearish order block
            if ob_candle.close > ob_candle.open_price:
                ob = OrderBlock(
                    type="bearish",
                    high=ob_candle.high,
                    low=ob_candle.low,
                    created_at=ob_candle.timestamp,
                    created_candle_index=len(candles) - 2,
                    timeframe=timeframe,
                    previous_bos_type="bearish",
                    distance_from_liquidity_sweep=liquidity_sweep_distance,
                )
                ob.strength_score = self._calculate_ob_strength(ob, candles)
                ob.volume_proxy_score = self._calculate_volume_proxy(ob_candle)

                if ob.strength_score >= self.min_strength_score:
                    self._add_order_block(timeframe, ob)
                    logger.info(f"[TF:{timeframe}] Bearish OB detected: {ob.low} - {ob.high}")
                    return ob

        return None

    def update_order_block_touches(
        self,
        timeframe: int,
        current_price: float,
        candle_index: int,
        timestamp: datetime,
    ) -> None:
        """
        Update order block touch count and mitigation status
        
        Args:
            timeframe: The timeframe
            current_price: Current price
            candle_index: Current candle index
            timestamp: Current timestamp
        """
        if timeframe not in self.active_order_blocks:
            return

        for ob in self.active_order_blocks[timeframe]:
            if ob.is_mitigated:
                continue

            # Check if price touched the order block
            if ob.low <= current_price <= ob.high:
                ob.touches += 1
                logger.info(f"[TF:{timeframe}] OB touched (touches: {ob.touches})")

            # Check mitigation
            if ob.type == "bullish" and current_price > ob.high:
                ob.is_mitigated = True
                ob.mitigation_price = current_price
                ob.mitigation_candle_index = candle_index
                logger.info(f"[TF:{timeframe}] Bullish OB mitigated at {current_price}")

            elif ob.type == "bearish" and current_price < ob.low:
                ob.is_mitigated = True
                ob.mitigation_price = current_price
                ob.mitigation_candle_index = candle_index
                logger.info(f"[TF:{timeframe}] Bearish OB mitigated at {current_price}")

    def get_active_order_blocks(self, timeframe: int, ob_type: Optional[str] = None) -> List[OrderBlock]:
        """
        Get active (non-mitigated) order blocks
        
        Args:
            timeframe: The timeframe
            ob_type: Filter by 'bullish' or 'bearish', or None for all
        
        Returns:
            List of active order blocks
        """
        if timeframe not in self.active_order_blocks:
            return []

        obs = [o for o in self.active_order_blocks[timeframe] if not o.is_mitigated]
        if ob_type:
            obs = [o for o in obs if o.type == ob_type]

        return obs

    def _add_order_block(self, timeframe: int, ob: OrderBlock) -> None:
        """Add order block to tracking"""
        if timeframe not in self.order_blocks:
            self.order_blocks[timeframe] = []
            self.active_order_blocks[timeframe] = []

        self.order_blocks[timeframe].append(ob)
        self.active_order_blocks[timeframe].append(ob)

    def _calculate_ob_strength(self, ob: OrderBlock, candles: List) -> float:
        """
        Calculate order block strength (0-100)
        
        Factors:
        - Proximity to BOS
        - Candle structure clarity
        - Distance from liquidity
        """
        score = 50.0

        # Strong candle bodies = stronger OB
        ob_candle = candles[-2]
        candle_range = ob_candle.high - ob_candle.low
        candle_body = abs(ob_candle.close - ob_candle.open_price)
        body_ratio = candle_body / candle_range if candle_range > 0 else 0

        if body_ratio > 0.7:
            score += 20
        elif body_ratio > 0.5:
            score += 10

        # Close proximity to BOS (not too far back)
        if ob.distance_from_liquidity_sweep < 100:
            score += 15

        return min(100, score)

    def _calculate_volume_proxy(self, candle) -> float:
        """
        Estimate volume/strength from candle characteristics
        
        Args:
            candle: The candle to analyze
        
        Returns:
            Estimated volume proxy score (0-100)
        """
        candle_range = candle.high - candle.low
        candle_body = abs(candle.close - candle.open_price)
        
        # Larger candles = higher volume proxy
        score = min(100, (candle_range * 1000) % 100)
        return score
