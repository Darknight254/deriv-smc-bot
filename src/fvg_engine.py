"""
Fair Value Gap (FVG) Engine
Detects and tracks 3-candle imbalances (bullish and bearish FVGs)
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class FairValueGap:
    """Represents a Fair Value Gap (3-candle imbalance)"""
    type: str  # 'bullish' or 'bearish'
    gap_high: float
    gap_low: float
    gap_size: float
    gap_size_percent: float
    created_at: datetime
    created_candle_index: int
    timeframe: int
    
    # Tracking
    fill_percentage: float = 0.0  # 0-100%
    is_filled: bool = False
    filled_at: Optional[datetime] = None
    filled_candle_index: Optional[int] = None
    
    # Quality metrics
    candle_1_high: float = 0.0
    candle_1_low: float = 0.0
    candle_2_high: float = 0.0
    candle_2_low: float = 0.0
    candle_3_high: float = 0.0
    candle_3_low: float = 0.0
    
    # Strength scoring
    strength_score: float = 50.0  # 0-100
    reaction_strength: int = 0  # Number of times price rejected from FVG
    touches: int = 0  # Number of times price touched FVG


class FVGEngine:
    """
    Detects Fair Value Gaps using SMC methodology
    """

    def __init__(self, timeframes: List[int] = None, min_gap_size_percent: float = 0.001):
        """
        Initialize FVG Engine
        
        Args:
            timeframes: List of timeframes to monitor
            min_gap_size_percent: Minimum gap size as % of price
        """
        self.timeframes = timeframes or [1, 5, 15]
        self.min_gap_size_percent = min_gap_size_percent
        self.fvgs: Dict[int, List[FairValueGap]] = {tf: [] for tf in self.timeframes}
        self.active_fvgs: Dict[int, List[FairValueGap]] = {tf: [] for tf in self.timeframes}

    def detect_fvgs(self, timeframe: int, candles: List) -> Optional[FairValueGap]:
        """
        Detect Fair Value Gaps from candle data
        
        FVG Definition:
        - Bullish FVG: Candle 1 high < Candle 3 low (gap between them)
        - Bearish FVG: Candle 1 low > Candle 3 high (gap between them)
        
        Args:
            timeframe: The timeframe
            candles: List of recent candles
        
        Returns:
            FairValueGap if detected, None otherwise
        """
        if len(candles) < 3:
            return None

        # Get the last 3 candles
        c1 = candles[-3]
        c2 = candles[-2]
        c3 = candles[-1]

        # Bullish FVG: C1 high < C3 low
        if c1.high < c3.low:
            gap_low = c1.high
            gap_high = c3.low
            gap_size = gap_high - gap_low
            gap_size_percent = (gap_size / c1.close) * 100

            if gap_size_percent >= self.min_gap_size_percent:
                fvg = FairValueGap(
                    type="bullish",
                    gap_high=gap_high,
                    gap_low=gap_low,
                    gap_size=gap_size,
                    gap_size_percent=gap_size_percent,
                    created_at=c3.timestamp,
                    created_candle_index=len(candles) - 1,
                    timeframe=timeframe,
                    candle_1_high=c1.high,
                    candle_1_low=c1.low,
                    candle_2_high=c2.high,
                    candle_2_low=c2.low,
                    candle_3_high=c3.high,
                    candle_3_low=c3.low,
                )
                fvg.strength_score = self._calculate_fvg_strength(fvg, True)
                self._add_fvg(timeframe, fvg)
                logger.info(f"[TF:{timeframe}] Bullish FVG detected: {gap_low} - {gap_high}")
                return fvg

        # Bearish FVG: C1 low > C3 high
        elif c1.low > c3.high:
            gap_high = c1.low
            gap_low = c3.high
            gap_size = gap_high - gap_low
            gap_size_percent = (gap_size / c1.close) * 100

            if gap_size_percent >= self.min_gap_size_percent:
                fvg = FairValueGap(
                    type="bearish",
                    gap_high=gap_high,
                    gap_low=gap_low,
                    gap_size=gap_size,
                    gap_size_percent=gap_size_percent,
                    created_at=c3.timestamp,
                    created_candle_index=len(candles) - 1,
                    timeframe=timeframe,
                    candle_1_high=c1.high,
                    candle_1_low=c1.low,
                    candle_2_high=c2.high,
                    candle_2_low=c2.low,
                    candle_3_high=c3.high,
                    candle_3_low=c3.low,
                )
                fvg.strength_score = self._calculate_fvg_strength(fvg, False)
                self._add_fvg(timeframe, fvg)
                logger.info(f"[TF:{timeframe}] Bearish FVG detected: {gap_low} - {gap_high}")
                return fvg

        return None

    def update_fvg_fill(self, timeframe: int, current_price: float, candle_index: int, timestamp: datetime) -> None:
        """
        Update FVG fill percentage as price moves through the gap
        
        Args:
            timeframe: The timeframe
            current_price: Current price
            candle_index: Current candle index
            timestamp: Current timestamp
        """
        if timeframe not in self.active_fvgs:
            return

        for fvg in self.active_fvgs[timeframe]:
            if fvg.is_filled:
                continue

            # For bullish FVG (gap goes up)
            if fvg.type == "bullish":
                if current_price >= fvg.gap_low and current_price <= fvg.gap_high:
                    fvg.fill_percentage = ((current_price - fvg.gap_low) / (fvg.gap_high - fvg.gap_low)) * 100
                    fvg.touches += 1
                elif current_price > fvg.gap_high:
                    fvg.is_filled = True
                    fvg.filled_at = timestamp
                    fvg.filled_candle_index = candle_index
                    fvg.fill_percentage = 100.0
                    logger.info(f"[TF:{timeframe}] Bullish FVG filled at {current_price}")

            # For bearish FVG (gap goes down)
            elif fvg.type == "bearish":
                if current_price >= fvg.gap_low and current_price <= fvg.gap_high:
                    fvg.fill_percentage = ((fvg.gap_high - current_price) / (fvg.gap_high - fvg.gap_low)) * 100
                    fvg.touches += 1
                elif current_price < fvg.gap_low:
                    fvg.is_filled = True
                    fvg.filled_at = timestamp
                    fvg.filled_candle_index = candle_index
                    fvg.fill_percentage = 100.0
                    logger.info(f"[TF:{timeframe}] Bearish FVG filled at {current_price}")

    def get_active_fvgs(self, timeframe: int, fvg_type: Optional[str] = None) -> List[FairValueGap]:
        """
        Get active (unfilled) FVGs
        
        Args:
            timeframe: The timeframe
            fvg_type: Filter by 'bullish' or 'bearish', or None for all
        
        Returns:
            List of active FVGs
        """
        if timeframe not in self.active_fvgs:
            return []

        fvgs = [f for f in self.active_fvgs[timeframe] if not f.is_filled]
        if fvg_type:
            fvgs = [f for f in fvgs if f.type == fvg_type]

        return fvgs

    def _add_fvg(self, timeframe: int, fvg: FairValueGap) -> None:
        """Add FVG to tracking"""
        if timeframe not in self.fvgs:
            self.fvgs[timeframe] = []
            self.active_fvgs[timeframe] = []

        self.fvgs[timeframe].append(fvg)
        self.active_fvgs[timeframe].append(fvg)

    def _calculate_fvg_strength(self, fvg: FairValueGap, is_bullish: bool) -> float:
        """
        Calculate FVG strength score (0-100)
        
        Factors:
        - Gap size
        - Candle structure
        - Imbalance clarity
        """
        score = 50.0

        # Larger gaps = stronger
        if fvg.gap_size_percent > 0.005:
            score += 20
        elif fvg.gap_size_percent > 0.002:
            score += 10

        # Clear imbalance structure
        if is_bullish:
            if fvg.candle_1_high < fvg.candle_3_low:
                score += 20
        else:
            if fvg.candle_1_low > fvg.candle_3_high:
                score += 20

        return min(100, score)
