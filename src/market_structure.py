"""
Market Structure Engine
Analyzes swing highs, swing lows, internal/external structure, BOS, CHoCH, and MSS
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class Candle:
    """Represents a single candle in market data"""
    timestamp: datetime
    open_price: float
    high: float
    low: float
    close: float
    volume: int
    timeframe: int  # in minutes


@dataclass
class SwingLevel:
    """Represents a swing high or low"""
    price: float
    timestamp: datetime
    candle_index: int
    is_high: bool  # True if swing high, False if swing low
    strength: int  # Number of touches (1-100)
    confirmed: bool = False


@dataclass
class StructureBreak:
    """Represents a Break of Structure (BOS)"""
    type: str  # 'bullish' or 'bearish'
    price: float
    timestamp: datetime
    candle_close_price: float  # Must break on close
    confidence_score: float  # 0-100
    previous_structure: Optional['StructureBreak'] = None


@dataclass
class CharacterChange:
    """Represents a Change of Character (CHoCH)"""
    type: str  # 'bullish' or 'bearish'
    price: float
    timestamp: datetime
    candle_close_price: float
    confidence_score: float  # 0-100
    structure_state: str  # 'internal' or 'external'


@dataclass
class MarketStructureState:
    """Current market structure state across timeframes"""
    timeframe: int
    trend_direction: str  # 'bullish', 'bearish', 'neutral'
    last_swing_high: Optional[SwingLevel] = None
    last_swing_low: Optional[SwingLevel] = None
    last_bos: Optional[StructureBreak] = None
    last_choch: Optional[CharacterChange] = None
    internal_structure: str = "unknown"  # 'bullish' or 'bearish'
    external_structure: str = "unknown"  # 'bullish' or 'bearish'
    is_in_premium: bool = False
    is_in_discount: bool = False


class MarketStructureEngine:
    """
    Core market structure analyzer using SMC principles
    """

    def __init__(self, lookback_candles: int = 50, timeframes: List[int] = None):
        """
        Initialize market structure engine
        
        Args:
            lookback_candles: Number of candles to analyze
            timeframes: List of timeframes to monitor (in minutes)
        """
        self.lookback_candles = lookback_candles
        self.timeframes = timeframes or [1, 5, 15]
        self.candle_history: Dict[int, List[Candle]] = {tf: [] for tf in self.timeframes}
        self.structure_state: Dict[int, MarketStructureState] = {
            tf: MarketStructureState(timeframe=tf) for tf in self.timeframes
        }
        self.swing_levels: Dict[int, List[SwingLevel]] = {tf: [] for tf in self.timeframes}

    def add_candle(self, candle: Candle, timeframe: int) -> None:
        """
        Add a new candle to the history
        
        Args:
            candle: The candle to add
            timeframe: The timeframe this candle belongs to
        """
        if timeframe not in self.candle_history:
            self.candle_history[timeframe] = []

        self.candle_history[timeframe].append(candle)

        # Keep only lookback candles
        if len(self.candle_history[timeframe]) > self.lookback_candles:
            self.candle_history[timeframe].pop(0)

        # Update structure analysis
        self._update_structure(timeframe)

    def _update_structure(self, timeframe: int) -> None:
        """Update market structure for a specific timeframe"""
        if len(self.candle_history[timeframe]) < 3:
            return

        # Detect swings
        self._detect_swings(timeframe)

        # Detect BOS/CHoCH
        self._detect_structure_breaks(timeframe)
        self._detect_character_changes(timeframe)

        # Update trend direction
        self._update_trend_direction(timeframe)

    def _detect_swings(self, timeframe: int) -> None:
        """
        Detect swing highs and swing lows
        Uses: High > 2 previous highs and > 2 next highs = Swing High
        """
        candles = self.candle_history[timeframe]
        if len(candles) < 5:
            return

        lookback = min(2, len(candles) - 1)

        for i in range(lookback, len(candles) - lookback):
            current = candles[i]

            # Detect Swing High
            is_swing_high = current.high == max(
                [candles[j].high for j in range(i - lookback, i + lookback + 1)]
            )

            # Detect Swing Low
            is_swing_low = current.low == min(
                [candles[j].low for j in range(i - lookback, i + lookback + 1)]
            )

            if is_swing_high:
                self._add_swing_level(timeframe, current.high, current.timestamp, i, True)

            if is_swing_low:
                self._add_swing_level(timeframe, current.low, current.timestamp, i, False)

    def _add_swing_level(
        self, timeframe: int, price: float, timestamp: datetime, candle_idx: int, is_high: bool
    ) -> None:
        """Add or update swing level"""
        swing = SwingLevel(
            price=price,
            timestamp=timestamp,
            candle_index=candle_idx,
            is_high=is_high,
            strength=1,
            confirmed=False,
        )

        existing = next(
            (s for s in self.swing_levels[timeframe] if abs(s.price - price) < 0.0001), None
        )

        if existing:
            existing.strength += 1
        else:
            self.swing_levels[timeframe].append(swing)

        # Keep structure clean
        if len(self.swing_levels[timeframe]) > 20:
            self.swing_levels[timeframe].pop(0)

        # Update last swing
        if is_high:
            self.structure_state[timeframe].last_swing_high = swing
        else:
            self.structure_state[timeframe].last_swing_low = swing

    def _detect_structure_breaks(self, timeframe: int) -> None:
        """
        Detect Break of Structure (BOS)
        Bullish BOS: Close above previous swing high
        Bearish BOS: Close below previous swing low
        """
        candles = self.candle_history[timeframe]
        if len(candles) < 2:
            return

        current_candle = candles[-1]
        state = self.structure_state[timeframe]

        # Bullish BOS detection
        if (
            state.last_swing_low
            and current_candle.close > state.last_swing_high.price
            and candles[-2].close <= state.last_swing_high.price
        ):
            bos = StructureBreak(
                type="bullish",
                price=state.last_swing_high.price,
                timestamp=current_candle.timestamp,
                candle_close_price=current_candle.close,
                confidence_score=self._calculate_bos_confidence(timeframe, True),
                previous_structure=state.last_bos,
            )
            state.last_bos = bos
            logger.info(f"[TF:{timeframe}] Bullish BOS detected at {bos.price}")

        # Bearish BOS detection
        if (
            state.last_swing_high
            and current_candle.close < state.last_swing_low.price
            and candles[-2].close >= state.last_swing_low.price
        ):
            bos = StructureBreak(
                type="bearish",
                price=state.last_swing_low.price,
                timestamp=current_candle.timestamp,
                candle_close_price=current_candle.close,
                confidence_score=self._calculate_bos_confidence(timeframe, False),
                previous_structure=state.last_bos,
            )
            state.last_bos = bos
            logger.info(f"[TF:{timeframe}] Bearish BOS detected at {bos.price}")

    def _detect_character_changes(self, timeframe: int) -> None:
        """
        Detect Change of Character (CHoCH)
        Marks shift in market structure strength and quality
        """
        candles = self.candle_history[timeframe]
        if len(candles) < 3:
            return

        state = self.structure_state[timeframe]
        current_candle = candles[-1]

        # This is a simplified CHoCH detector
        # In production, would analyze candle patterns, volume, structure quality
        recent_highs = [c.high for c in candles[-5:]]
        recent_lows = [c.low for c in candles[-5:]]

        if current_candle.close < min(recent_lows[:-1]):
            choch = CharacterChange(
                type="bearish",
                price=current_candle.close,
                timestamp=current_candle.timestamp,
                candle_close_price=current_candle.close,
                confidence_score=self._calculate_choch_confidence(timeframe, False),
                structure_state="internal",
            )
            state.last_choch = choch
            logger.info(f"[TF:{timeframe}] Bearish CHoCH detected at {choch.price}")

        elif current_candle.close > max(recent_highs[:-1]):
            choch = CharacterChange(
                type="bullish",
                price=current_candle.close,
                timestamp=current_candle.timestamp,
                candle_close_price=current_candle.close,
                confidence_score=self._calculate_choch_confidence(timeframe, True),
                structure_state="internal",
            )
            state.last_choch = choch
            logger.info(f"[TF:{timeframe}] Bullish CHoCH detected at {choch.price}")

    def _update_trend_direction(self, timeframe: int) -> None:
        """Update overall trend direction"""
        state = self.structure_state[timeframe]

        if state.last_bos:
            state.trend_direction = state.last_bos.type
        elif state.last_swing_high and state.last_swing_low:
            if state.last_swing_high.timestamp > state.last_swing_low.timestamp:
                state.trend_direction = "bullish"
            else:
                state.trend_direction = "bearish"

    def _calculate_bos_confidence(self, timeframe: int, is_bullish: bool) -> float:
        """Calculate confidence score for BOS (0-100)"""
        candles = self.candle_history[timeframe]
        if len(candles) < 2:
            return 0

        # Factors: candle size, close distance from break, momentum
        current = candles[-1]
        previous = candles[-2]

        candle_body = abs(current.close - current.open_price)
        candle_range = current.high - current.low
        body_to_range = candle_body / candle_range if candle_range > 0 else 0

        # Strong closes get higher scores
        confidence = min(100, 50 + (body_to_range * 50))
        return confidence

    def _calculate_choch_confidence(self, timeframe: int, is_bullish: bool) -> float:
        """Calculate confidence score for CHoCH (0-100)"""
        # Would analyze: candle patterns, structure clarity, volume
        return 65.0  # Placeholder

    def get_structure_state(self, timeframe: int) -> MarketStructureState:
        """Get current structure state for timeframe"""
        return self.structure_state[timeframe]

    def get_recent_swings(self, timeframe: int, limit: int = 5) -> List[SwingLevel]:
        """Get recent swing levels"""
        return self.swing_levels[timeframe][-limit:]

    def is_higher_timeframe_bullish(self, current_tf: int) -> bool:
        """Check if higher timeframes show bullish bias"""
        higher_tfs = [tf for tf in self.timeframes if tf > current_tf]
        if not higher_tfs:
            return True

        for tf in higher_tfs:
            state = self.structure_state[tf]
            if state.trend_direction == "bearish":
                return False

        return True

    def is_higher_timeframe_bearish(self, current_tf: int) -> bool:
        """Check if higher timeframes show bearish bias"""
        higher_tfs = [tf for tf in self.timeframes if tf > current_tf]
        if not higher_tfs:
            return True

        for tf in higher_tfs:
            state = self.structure_state[tf]
            if state.trend_direction == "bullish":
                return False

        return True
