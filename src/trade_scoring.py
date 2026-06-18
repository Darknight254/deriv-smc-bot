"""
Trade Scoring System
Calculates confluence score based on multiple SMC factors
Scores must exceed 80 to trigger trade entries
"""

from dataclasses import dataclass, field
from typing import Dict, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ScoreComponent(Enum):
    """Scoring components"""
    LIQUIDITY_SWEEP = "liquidity_sweep"
    BOS_CONFIRMATION = "bos_confirmation"
    CHOCH_CONFIRMATION = "choch_confirmation"
    FVG_ALIGNMENT = "fvg_alignment"
    ORDER_BLOCK_ALIGNMENT = "order_block_alignment"
    PD_ARRAY_ALIGNMENT = "pd_array_alignment"


@dataclass
class TradeScore:
    """Represents a trade opportunity score"""
    symbol: str
    timeframe: int
    direction: str  # 'long' or 'short'
    total_score: float = 0.0
    score_breakdown: Dict[str, float] = field(default_factory=dict)
    confluence_factors: int = 0
    is_valid_entry: bool = False
    confidence_level: str = "low"  # 'low', 'medium', 'high'
    
    # Context
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    risk_reward_ratio: Optional[float] = None


class TradeScorer:
    """
    Calculates trade confluence scores using SMC factors
    """

    def __init__(self, min_confluence_factors: int = 3, min_total_score: float = 80.0):
        """
        Initialize Trade Scorer
        
        Args:
            min_confluence_factors: Minimum number of factors needed
            min_total_score: Minimum score to consider a valid entry (0-100)
        """
        self.min_confluence_factors = min_confluence_factors
        self.min_total_score = min_total_score

        # Default point values
        self.score_weights = {
            "liquidity_sweep": 20.0,
            "bos_confirmation": 20.0,
            "choch_confirmation": 20.0,
            "fvg_alignment": 15.0,
            "order_block_alignment": 15.0,
            "pd_array_alignment": 10.0,
        }

    def calculate_score(
        self,
        symbol: str,
        timeframe: int,
        direction: str,
        factors: Dict[str, float],
        entry_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> TradeScore:
        """
        Calculate composite trade score
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe being analyzed
            direction: 'long' or 'short'
            factors: Dict of factor scores (0-1.0 or 0-100)
            entry_price: Entry price
            stop_loss: Stop loss price
            take_profit: Take profit price
        
        Returns:
            TradeScore object with total score and breakdown
        """
        score = TradeScore(
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

        total_score = 0.0
        active_factors = 0

        # Calculate each component
        for component, weight in self.score_weights.items():
            if component in factors:
                factor_value = factors[component]
                
                # Normalize to 0-1 range if needed
                if factor_value > 1.0:
                    factor_value = factor_value / 100.0
                
                if factor_value > 0:
                    component_score = weight * factor_value
                    score.score_breakdown[component] = component_score
                    total_score += component_score
                    active_factors += 1

        score.total_score = total_score
        score.confluence_factors = active_factors

        # Determine if valid entry
        if (
            score.confluence_factors >= self.min_confluence_factors
            and score.total_score >= self.min_total_score
        ):
            score.is_valid_entry = True

        # Set confidence level
        if score.total_score >= 90:
            score.confidence_level = "high"
        elif score.total_score >= 85:
            score.confidence_level = "medium"
        else:
            score.confidence_level = "low"

        # Calculate risk:reward if prices provided
        if entry_price and stop_loss and take_profit:
            risk = abs(entry_price - stop_loss)
            reward = abs(take_profit - entry_price)
            if risk > 0:
                score.risk_reward_ratio = reward / risk

        logger.info(
            f"[{symbol}] TF:{timeframe} {direction.upper()} Score: {score.total_score:.1f} "
            f"(Factors: {active_factors}, Valid: {score.is_valid_entry})"
        )

        return score

    def calculate_quick_score(
        self,
        has_liquidity_sweep: bool,
        has_bos: bool,
        has_choch: bool,
        has_fvg: bool,
        has_order_block: bool,
        has_pd_alignment: bool,
    ) -> float:
        """
        Quick score calculation with binary inputs (0 or 1)
        
        Args:
            has_liquidity_sweep: Bool
            has_bos: Bool
            has_choch: Bool
            has_fvg: Bool
            has_order_block: Bool
            has_pd_alignment: Bool
        
        Returns:
            Total score (0-100)
        """
        score = 0.0
        
        if has_liquidity_sweep:
            score += self.score_weights["liquidity_sweep"]
        if has_bos:
            score += self.score_weights["bos_confirmation"]
        if has_choch:
            score += self.score_weights["choch_confirmation"]
        if has_fvg:
            score += self.score_weights["fvg_alignment"]
        if has_order_block:
            score += self.score_weights["order_block_alignment"]
        if has_pd_alignment:
            score += self.score_weights["pd_array_alignment"]
        
        return min(100.0, score)

    def adjust_weights(self, new_weights: Dict[str, float]) -> None:
        """
        Adjust scoring weights for different market conditions
        
        Args:
            new_weights: Dict of new weight values
        """
        for key, value in new_weights.items():
            if key in self.score_weights:
                self.score_weights[key] = value
                logger.info(f"Score weight updated: {key} = {value}")
