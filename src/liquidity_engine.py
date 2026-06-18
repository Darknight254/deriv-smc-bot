"""
Liquidity Engine
Detects liquidity zones, sweeps, equal highs/lows, and inducement zones
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class LiquidityZone:
    """Represents a liquidity pool (buy-side or sell-side)"""
    price_level: float
    type: str  # 'buy_side' or 'sell_side'
    source: str  # 'swing_high', 'swing_low', 'equal_high', 'equal_low', 'previous_day'
    created_at: datetime
    strength: int  # Number of touches (0-100)
    timeframe: int
    is_swept: bool = False
    sweep_timestamp: Optional[datetime] = None
    sweep_price: float = 0.0


@dataclass
class LiquiditySweep:
    """Represents a liquidity sweep event"""
    liquidity_zone: LiquidityZone
    sweep_timestamp: datetime
    sweep_price: float
    direction: str  # 'up' (price above level) or 'down' (price below level)
    candle_index: int
    confirmation_candles: int = 0  # Candles since sweep occurred


@dataclass
class InducementZone:
    """Represents an inducement zone (price manipulation area)"""
    high: float
    low: float
    created_at: datetime
    origin_liquidity: LiquidityZone
    is_active: bool = True
    touches: int = 0


class LiquidityEngine:
    """
    Detects and tracks liquidity zones for SMC trading
    """

    def __init__(self, timeframes: List[int] = None, equal_high_tolerance: float = 0.0005):
        """
        Initialize liquidity engine
        
        Args:
            timeframes: List of timeframes to monitor
            equal_high_tolerance: Tolerance for equal high/low detection (as % of price)
        """
        self.timeframes = timeframes or [1, 5, 15]
        self.equal_high_tolerance = equal_high_tolerance
        self.liquidity_zones: Dict[int, List[LiquidityZone]] = {tf: [] for tf in self.timeframes}
        self.recent_sweeps: Dict[int, List[LiquiditySweep]] = {tf: [] for tf in self.timeframes}
        self.inducement_zones: Dict[int, List[InducementZone]] = {tf: [] for tf in self.timeframes}

    def detect_liquidity_zones(
        self,
        timeframe: int,
        swing_highs: List[float],
        swing_lows: List[float],
        current_price: float,
        current_timestamp: datetime,
    ) -> None:
        """
        Detect liquidity zones from swing levels
        
        Args:
            timeframe: The timeframe to analyze
            swing_highs: List of recent swing highs
            swing_lows: List of recent swing lows
            current_price: Current price
            current_timestamp: Current timestamp
        """
        if timeframe not in self.liquidity_zones:
            self.liquidity_zones[timeframe] = []

        # Detect buy-side liquidity (below current price)
        for swing_low in swing_lows:
            if swing_low < current_price:
                self._add_liquidity_zone(
                    timeframe=timeframe,
                    price_level=swing_low,
                    zone_type="buy_side",
                    source="swing_low",
                    created_at=current_timestamp,
                )

        # Detect sell-side liquidity (above current price)
        for swing_high in swing_highs:
            if swing_high > current_price:
                self._add_liquidity_zone(
                    timeframe=timeframe,
                    price_level=swing_high,
                    zone_type="sell_side",
                    source="swing_high",
                    created_at=current_timestamp,
                )

    def detect_equal_highs(
        self,
        timeframe: int,
        recent_highs: List[float],
        current_timestamp: datetime,
    ) -> None:
        """Detect equal highs (buy-side liquidity above current price)"""
        if len(recent_highs) < 2:
            return

        tolerance = recent_highs[-1] * self.equal_high_tolerance

        for i, high in enumerate(recent_highs[:-1]):
            if abs(high - recent_highs[-1]) < tolerance and high > recent_highs[-1]:
                self._add_liquidity_zone(
                    timeframe=timeframe,
                    price_level=high,
                    zone_type="sell_side",
                    source="equal_high",
                    created_at=current_timestamp,
                )
                logger.info(f"[TF:{timeframe}] Equal High detected at {high}")

    def detect_equal_lows(
        self,
        timeframe: int,
        recent_lows: List[float],
        current_timestamp: datetime,
    ) -> None:
        """Detect equal lows (sell-side liquidity below current price)"""
        if len(recent_lows) < 2:
            return

        tolerance = recent_lows[-1] * self.equal_high_tolerance

        for i, low in enumerate(recent_lows[:-1]):
            if abs(low - recent_lows[-1]) < tolerance and low < recent_lows[-1]:
                self._add_liquidity_zone(
                    timeframe=timeframe,
                    price_level=low,
                    zone_type="buy_side",
                    source="equal_low",
                    created_at=current_timestamp,
                )
                logger.info(f"[TF:{timeframe}] Equal Low detected at {low}")

    def detect_liquidity_sweep(
        self,
        timeframe: int,
        current_price: float,
        current_timestamp: datetime,
        candle_index: int,
    ) -> Optional[LiquiditySweep]:
        """
        Detect when price sweeps through a liquidity zone
        
        Returns:
            LiquiditySweep object if a sweep is detected, None otherwise
        """
        if timeframe not in self.liquidity_zones:
            return None

        for zone in self.liquidity_zones[timeframe]:
            if zone.is_swept:
                continue

            # Buy-side sweep (price goes below)
            if zone.type == "buy_side" and current_price < zone.price_level:
                sweep = LiquiditySweep(
                    liquidity_zone=zone,
                    sweep_timestamp=current_timestamp,
                    sweep_price=current_price,
                    direction="down",
                    candle_index=candle_index,
                )
                zone.is_swept = True
                zone.sweep_timestamp = current_timestamp
                zone.sweep_price = current_price

                self.recent_sweeps[timeframe].append(sweep)
                logger.info(f"[TF:{timeframe}] Buy-side liquidity swept at {current_price}")
                return sweep

            # Sell-side sweep (price goes above)
            elif zone.type == "sell_side" and current_price > zone.price_level:
                sweep = LiquiditySweep(
                    liquidity_zone=zone,
                    sweep_timestamp=current_timestamp,
                    sweep_price=current_price,
                    direction="up",
                    candle_index=candle_index,
                )
                zone.is_swept = True
                zone.sweep_timestamp = current_timestamp
                zone.sweep_price = current_price

                self.recent_sweeps[timeframe].append(sweep)
                logger.info(f"[TF:{timeframe}] Sell-side liquidity swept at {current_price}")
                return sweep

        return None

    def get_recent_sweep(self, timeframe: int, direction: str) -> Optional[LiquiditySweep]:
        """
        Get the most recent liquidity sweep in a direction
        
        Args:
            timeframe: The timeframe to check
            direction: 'up' for bullish sweep, 'down' for bearish sweep
        
        Returns:
            Most recent LiquiditySweep of that direction, or None
        """
        if timeframe not in self.recent_sweeps:
            return None

        matching = [s for s in self.recent_sweeps[timeframe] if s.direction == direction]
        return matching[-1] if matching else None

    def _add_liquidity_zone(
        self,
        timeframe: int,
        price_level: float,
        zone_type: str,
        source: str,
        created_at: datetime,
    ) -> None:
        """Add a liquidity zone (avoid duplicates)"""
        if timeframe not in self.liquidity_zones:
            self.liquidity_zones[timeframe] = []

        # Check if zone already exists near this price
        tolerance = price_level * 0.0001
        existing = next(
            (z for z in self.liquidity_zones[timeframe] if abs(z.price_level - price_level) < tolerance),
            None,
        )

        if existing:
            existing.strength = min(100, existing.strength + 10)
        else:
            zone = LiquidityZone(
                price_level=price_level,
                type=zone_type,
                source=source,
                created_at=created_at,
                strength=50,
                timeframe=timeframe,
            )
            self.liquidity_zones[timeframe].append(zone)

    def get_liquidity_zones(self, timeframe: int, zone_type: Optional[str] = None) -> List[LiquidityZone]:
        """
        Get liquidity zones for a timeframe
        
        Args:
            timeframe: The timeframe
            zone_type: Filter by 'buy_side' or 'sell_side', or None for all
        
        Returns:
            List of liquidity zones
        """
        if timeframe not in self.liquidity_zones:
            return []

        zones = self.liquidity_zones[timeframe]
        if zone_type:
            zones = [z for z in zones if z.type == zone_type]

        return zones

    def get_nearest_liquidity(self, timeframe: int, zone_type: str) -> Optional[LiquidityZone]:
        """Get the nearest liquidity zone of a given type"""
        zones = self.get_liquidity_zones(timeframe, zone_type)
        if not zones:
            return None

        return zones[-1]  # Assumes zones are sorted by recency

    def cleanup_old_zones(self, timeframe: int, max_age_minutes: int = 240) -> None:
        """Remove liquidity zones older than max_age_minutes"""
        if timeframe not in self.liquidity_zones:
            return

        current_time = datetime.utcnow()
        self.liquidity_zones[timeframe] = [
            z
            for z in self.liquidity_zones[timeframe]
            if (current_time - z.created_at).total_seconds() < max_age_minutes * 60
        ]

    def has_recent_sweep(self, timeframe: int, direction: str, max_candles_ago: int = 5) -> bool:
        """Check if there was a recent sweep in the given direction"""
        sweep = self.get_recent_sweep(timeframe, direction)
        if not sweep:
            return False

        return sweep.candle_index >= (sweep.candle_index - max_candles_ago)
