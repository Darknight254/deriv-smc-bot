"""
Premium/Discount Array Engine
Calculates premium zones (above equilibrium) and discount zones (below)
Based on significant swing highs and lows
"""

from dataclasses import dataclass
from typing import Optional, Dict, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class PremiumDiscountArray:
    """Represents the Premium/Discount Array structure"""
    timeframe: int
    significant_swing_high: float
    significant_swing_low: float
    equilibrium: float
    premium_zone_high: float
    premium_zone_low: float
    discount_zone_high: float
    discount_zone_low: float
    last_updated: datetime
    swing_high_timestamp: datetime
    swing_low_timestamp: datetime


class PDArrayEngine:
    """
    Manages Premium/Discount Array analysis
    """

    def __init__(self, timeframes: list = None, significant_move_percent: float = 1.5):
        """
        Initialize PD Array Engine
        
        Args:
            timeframes: List of timeframes to monitor
            significant_move_percent: % move to define a significant swing
        """
        self.timeframes = timeframes or [1, 5, 15]
        self.significant_move_percent = significant_move_percent
        self.pd_arrays: Dict[int, Optional[PremiumDiscountArray]] = {tf: None for tf in self.timeframes}

    def update_pd_array(
        self,
        timeframe: int,
        swing_high: float,
        swing_low: float,
        swing_high_timestamp: datetime,
        swing_low_timestamp: datetime,
    ) -> Optional[PremiumDiscountArray]:
        """
        Update the Premium/Discount array for a timeframe
        
        Args:
            timeframe: The timeframe
            swing_high: Recent significant swing high
            swing_low: Recent significant swing low
            swing_high_timestamp: Timestamp of swing high
            swing_low_timestamp: Timestamp of swing low
        
        Returns:
            Updated PremiumDiscountArray, or None if not significant
        """
        if swing_high <= swing_low:
            return None

        # Calculate equilibrium
        equilibrium = (swing_high + swing_low) / 2
        
        # Premium zone: from equilibrium to swing high
        premium_zone_high = swing_high
        premium_zone_low = equilibrium
        
        # Discount zone: from swing low to equilibrium
        discount_zone_high = equilibrium
        discount_zone_low = swing_low

        pd_array = PremiumDiscountArray(
            timeframe=timeframe,
            significant_swing_high=swing_high,
            significant_swing_low=swing_low,
            equilibrium=equilibrium,
            premium_zone_high=premium_zone_high,
            premium_zone_low=premium_zone_low,
            discount_zone_high=discount_zone_high,
            discount_zone_low=discount_zone_low,
            last_updated=datetime.utcnow(),
            swing_high_timestamp=swing_high_timestamp,
            swing_low_timestamp=swing_low_timestamp,
        )

        self.pd_arrays[timeframe] = pd_array
        logger.info(
            f"[TF:{timeframe}] PD Array updated - Premium: {premium_zone_low}-{premium_zone_high}, "
            f"Discount: {discount_zone_low}-{discount_zone_high}"
        )

        return pd_array

    def is_price_in_premium(self, timeframe: int, price: float) -> bool:
        """
        Check if price is in the premium zone
        
        Args:
            timeframe: The timeframe
            price: The price to check
        
        Returns:
            True if in premium, False otherwise
        """
        pd = self.pd_arrays[timeframe]
        if not pd:
            return False

        return pd.premium_zone_low <= price <= pd.premium_zone_high

    def is_price_in_discount(self, timeframe: int, price: float) -> bool:
        """
        Check if price is in the discount zone
        
        Args:
            timeframe: The timeframe
            price: The price to check
        
        Returns:
            True if in discount, False otherwise
        """
        pd = self.pd_arrays[timeframe]
        if not pd:
            return False

        return pd.discount_zone_low <= price <= pd.discount_zone_high

    def get_pd_array(self, timeframe: int) -> Optional[PremiumDiscountArray]:
        """
        Get the current PD array for a timeframe
        
        Args:
            timeframe: The timeframe
        
        Returns:
            PremiumDiscountArray or None
        """
        return self.pd_arrays.get(timeframe)

    def get_distance_to_equilibrium(self, timeframe: int, price: float) -> Optional[float]:
        """
        Get distance from price to equilibrium
        
        Args:
            timeframe: The timeframe
            price: The price
        
        Returns:
            Distance to equilibrium, or None if no PD array
        """
        pd = self.pd_arrays[timeframe]
        if not pd:
            return None

        return abs(price - pd.equilibrium)

    def get_zone_info(self, timeframe: int, price: float) -> Dict:
        """
        Get information about which zone the price is in
        
        Args:
            timeframe: The timeframe
            price: The price
        
        Returns:
            Dict with zone information
        """
        pd = self.pd_arrays[timeframe]
        if not pd:
            return {"zone": "unknown", "details": "No PD array available"}

        if self.is_price_in_premium(timeframe, price):
            return {
                "zone": "premium",
                "zone_high": pd.premium_zone_high,
                "zone_low": pd.premium_zone_low,
                "distance_to_equilibrium": abs(price - pd.equilibrium),
                "distance_to_top": pd.premium_zone_high - price,
            }
        elif self.is_price_in_discount(timeframe, price):
            return {
                "zone": "discount",
                "zone_high": pd.discount_zone_high,
                "zone_low": pd.discount_zone_low,
                "distance_to_equilibrium": abs(price - pd.equilibrium),
                "distance_to_bottom": price - pd.discount_zone_low,
            }
        else:
            return {"zone": "outside", "details": "Price outside current PD array"}
