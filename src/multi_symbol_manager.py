"""
Multi-Symbol Manager
Handles simultaneous analysis of multiple volatility symbols (R_100, R_50, R_10)
"""

from typing import Dict, List, Optional
from datetime import datetime
import logging
from dataclasses import dataclass

from src.market_structure import MarketStructureEngine, Candle
from src.liquidity_engine import LiquidityEngine
from src.fvg_engine import FVGEngine
from src.order_block_engine import OrderBlockEngine
from src.pd_array_engine import PDArrayEngine
from src.trade_scoring import TradeScorer

logger = logging.getLogger(__name__)


@dataclass
class SymbolAnalysis:
    """Analysis state for a single symbol"""
    symbol: str
    timeframes: List[int]
    market_structure: MarketStructureEngine
    liquidity_engine: LiquidityEngine
    fvg_engine: FVGEngine
    order_block_engine: OrderBlockEngine
    pd_array_engine: PDArrayEngine
    trade_scorer: TradeScorer
    last_candle_time: Dict[int, datetime] = None
    analysis_complete: bool = False


class MultiSymbolManager:
    """
    Manages analysis across multiple symbols simultaneously
    """

    def __init__(self, timeframes: List[int] = None):
        """
        Initialize Multi-Symbol Manager
        
        Args:
            timeframes: List of timeframes to analyze
        """
        self.timeframes = timeframes or [1, 5, 15]
        self.symbols_analysis: Dict[str, SymbolAnalysis] = {}
        self.all_trade_opportunities: List[Dict] = []

    def add_symbol(self, symbol: str) -> SymbolAnalysis:
        """
        Add a new symbol for analysis
        
        Args:
            symbol: Trading symbol (e.g., 'R_100')
        
        Returns:
            SymbolAnalysis object for the symbol
        """
        if symbol in self.symbols_analysis:
            logger.warning(f"Symbol {symbol} already added")
            return self.symbols_analysis[symbol]

        analysis = SymbolAnalysis(
            symbol=symbol,
            timeframes=self.timeframes,
            market_structure=MarketStructureEngine(timeframes=self.timeframes),
            liquidity_engine=LiquidityEngine(timeframes=self.timeframes),
            fvg_engine=FVGEngine(timeframes=self.timeframes),
            order_block_engine=OrderBlockEngine(timeframes=self.timeframes),
            pd_array_engine=PDArrayEngine(timeframes=self.timeframes),
            trade_scorer=TradeScorer(),
            last_candle_time={},
        )

        self.symbols_analysis[symbol] = analysis
        logger.info(f"Symbol {symbol} added for analysis")
        return analysis

    def process_candle(
        self,
        symbol: str,
        timeframe: int,
        candle: Candle,
    ) -> Optional[Dict]:
        """
        Process a new candle for a symbol
        
        Args:
            symbol: Trading symbol
            timeframe: Candle timeframe
            candle: Candle data
        
        Returns:
            Dict with trade opportunity if signal found, None otherwise
        """
        if symbol not in self.symbols_analysis:
            logger.warning(f"Symbol {symbol} not added to manager")
            return None

        analysis = self.symbols_analysis[symbol]

        # Add candle to market structure
        analysis.market_structure.add_candle(candle, timeframe)

        # Detect FVGs
        analysis.fvg_engine.detect_fvgs(timeframe, analysis.market_structure.candle_history[timeframe])

        # Update FVG fills
        analysis.fvg_engine.update_fvg_fill(timeframe, candle.close, 0, candle.timestamp)

        # Analyze for trade opportunities
        opportunity = self._analyze_for_entry(
            symbol=symbol,
            timeframe=timeframe,
            analysis=analysis,
            candle=candle,
        )

        return opportunity

    def _analyze_for_entry(
        self,
        symbol: str,
        timeframe: int,
        analysis: SymbolAnalysis,
        candle: Candle,
    ) -> Optional[Dict]:
        """
        Analyze current candle for trade entry signals
        
        Args:
            symbol: Trading symbol
            timeframe: Analysis timeframe
            analysis: SymbolAnalysis object
            candle: Current candle
        
        Returns:
            Trade opportunity dict if found, None otherwise
        """
        structure_state = analysis.market_structure.get_structure_state(timeframe)
        liquidity_zones = analysis.liquidity_engine.get_liquidity_zones(timeframe)
        active_fvgs = analysis.fvg_engine.get_active_fvgs(timeframe)
        active_obs = analysis.order_block_engine.get_active_order_blocks(timeframe)

        # Check for bullish setup
        bullish_opportunity = self._check_bullish_setup(
            symbol, timeframe, analysis, structure_state, liquidity_zones, active_fvgs, active_obs, candle
        )

        if bullish_opportunity:
            return bullish_opportunity

        # Check for bearish setup
        bearish_opportunity = self._check_bearish_setup(
            symbol, timeframe, analysis, structure_state, liquidity_zones, active_fvgs, active_obs, candle
        )

        if bearish_opportunity:
            return bearish_opportunity

        return None

    def _check_bullish_setup(
        self,
        symbol: str,
        timeframe: int,
        analysis: SymbolAnalysis,
        structure_state,
        liquidity_zones,
        active_fvgs,
        active_obs,
        candle: Candle,
    ) -> Optional[Dict]:
        """
        Check for bullish entry conditions
        """
        # Must have bullish bias on higher timeframes
        if not analysis.market_structure.is_higher_timeframe_bullish(timeframe):
            return None

        # Count confluence factors
        factors = {}

        # Factor 1: Liquidity sweep (buy-side liquidity swept)
        buy_side_sweep = analysis.liquidity_engine.get_recent_sweep(timeframe, "down")
        if buy_side_sweep:
            factors["liquidity_sweep"] = 1.0

        # Factor 2: BOS (Bullish break of structure)
        if structure_state.last_bos and structure_state.last_bos.type == "bullish":
            factors["bos_confirmation"] = structure_state.last_bos.confidence_score / 100

        # Factor 3: CHoCH (Bullish change of character)
        if structure_state.last_choch and structure_state.last_choch.type == "bullish":
            factors["choch_confirmation"] = structure_state.last_choch.confidence_score / 100

        # Factor 4: FVG (Price in bullish FVG)
        bullish_fvgs = [f for f in active_fvgs if f.type == "bullish"]
        if bullish_fvgs and any(candle.close >= f.gap_low and candle.close <= f.gap_high for f in bullish_fvgs):
            factors["fvg_alignment"] = max(f.strength_score / 100 for f in bullish_fvgs if candle.close >= f.gap_low and candle.close <= f.gap_high)

        # Factor 5: Order Block (Price in bullish OB)
        bullish_obs = [o for o in active_obs if o.type == "bullish"]
        if bullish_obs and any(candle.close >= o.low and candle.close <= o.high for o in bullish_obs):
            factors["order_block_alignment"] = max(o.strength_score / 100 for o in bullish_obs if candle.close >= o.low and candle.close <= o.high)

        # Factor 6: PD Array (Price in discount)
        pd_info = analysis.pd_array_engine.get_zone_info(timeframe, candle.close)
        if pd_info["zone"] == "discount":
            factors["pd_array_alignment"] = 1.0

        # Calculate score
        score = analysis.trade_scorer.calculate_quick_score(
            has_liquidity_sweep="liquidity_sweep" in factors,
            has_bos="bos_confirmation" in factors,
            has_choch="choch_confirmation" in factors,
            has_fvg="fvg_alignment" in factors,
            has_order_block="order_block_alignment" in factors,
            has_pd_alignment="pd_array_alignment" in factors,
        )

        if score >= 80 and len(factors) >= 3:
            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "direction": "long",
                "entry_price": candle.close,
                "score": score,
                "confluence_factors": len(factors),
                "factors": list(factors.keys()),
                "timestamp": candle.timestamp,
            }

        return None

    def _check_bearish_setup(
        self,
        symbol: str,
        timeframe: int,
        analysis: SymbolAnalysis,
        structure_state,
        liquidity_zones,
        active_fvgs,
        active_obs,
        candle: Candle,
    ) -> Optional[Dict]:
        """
        Check for bearish entry conditions (similar to bullish but opposite)
        """
        # Must have bearish bias on higher timeframes
        if not analysis.market_structure.is_higher_timeframe_bearish(timeframe):
            return None

        factors = {}

        # Factor 1: Liquidity sweep (sell-side liquidity swept)
        sell_side_sweep = analysis.liquidity_engine.get_recent_sweep(timeframe, "up")
        if sell_side_sweep:
            factors["liquidity_sweep"] = 1.0

        # Factor 2: BOS (Bearish break of structure)
        if structure_state.last_bos and structure_state.last_bos.type == "bearish":
            factors["bos_confirmation"] = structure_state.last_bos.confidence_score / 100

        # Factor 3: CHoCH (Bearish change of character)
        if structure_state.last_choch and structure_state.last_choch.type == "bearish":
            factors["choch_confirmation"] = structure_state.last_choch.confidence_score / 100

        # Factor 4: FVG (Price in bearish FVG)
        bearish_fvgs = [f for f in active_fvgs if f.type == "bearish"]
        if bearish_fvgs and any(candle.close >= f.gap_low and candle.close <= f.gap_high for f in bearish_fvgs):
            factors["fvg_alignment"] = max(f.strength_score / 100 for f in bearish_fvgs if candle.close >= f.gap_low and candle.close <= f.gap_high)

        # Factor 5: Order Block (Price in bearish OB)
        bearish_obs = [o for o in active_obs if o.type == "bearish"]
        if bearish_obs and any(candle.close >= o.low and candle.close <= o.high for o in bearish_obs):
            factors["order_block_alignment"] = max(o.strength_score / 100 for o in bearish_obs if candle.close >= o.low and candle.close <= o.high)

        # Factor 6: PD Array (Price in premium)
        pd_info = analysis.pd_array_engine.get_zone_info(timeframe, candle.close)
        if pd_info["zone"] == "premium":
            factors["pd_array_alignment"] = 1.0

        # Calculate score
        score = analysis.trade_scorer.calculate_quick_score(
            has_liquidity_sweep="liquidity_sweep" in factors,
            has_bos="bos_confirmation" in factors,
            has_choch="choch_confirmation" in factors,
            has_fvg="fvg_alignment" in factors,
            has_order_block="order_block_alignment" in factors,
            has_pd_alignment="pd_array_alignment" in factors,
        )

        if score >= 80 and len(factors) >= 3:
            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "direction": "short",
                "entry_price": candle.close,
                "score": score,
                "confluence_factors": len(factors),
                "factors": list(factors.keys()),
                "timestamp": candle.timestamp,
            }

        return None

    def get_all_opportunities(self) -> List[Dict]:
        """Get all recent trade opportunities across all symbols"""
        return self.all_trade_opportunities

    def get_symbol_status(self, symbol: str) -> Optional[Dict]:
        """Get analysis status for a symbol"""
        if symbol not in self.symbols_analysis:
            return None

        analysis = self.symbols_analysis[symbol]
        return {
            "symbol": symbol,
            "timeframes_monitored": analysis.timeframes,
            "market_structures": {
                tf: {
                    "trend": analysis.market_structure.structure_state[tf].trend_direction,
                    "last_bos": analysis.market_structure.structure_state[tf].last_bos is not None,
                    "last_choch": analysis.market_structure.structure_state[tf].last_choch is not None,
                }
                for tf in analysis.timeframes
            },
        }
