#!/usr/bin/env python3
"""
Test suite for SMC bot components
"""

import unittest
from datetime import datetime
from src.market_structure import MarketStructureEngine, Candle
from src.liquidity_engine import LiquidityEngine
from src.fvg_engine import FVGEngine
from src.trade_scoring import TradeScorer
from src.risk_manager import RiskManager


class TestMarketStructure(unittest.TestCase):
    """Test market structure detection"""

    def setUp(self):
        self.engine = MarketStructureEngine()

    def test_candle_addition(self):
        """Test adding candles"""
        candle = Candle(
            timestamp=datetime.utcnow(),
            open_price=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=1000,
            timeframe=5,
        )
        
        self.engine.add_candle(candle, 5)
        self.assertEqual(len(self.engine.candle_history[5]), 1)


class TestLiquidityEngine(unittest.TestCase):
    """Test liquidity detection"""

    def setUp(self):
        self.engine = LiquidityEngine()

    def test_liquidity_zone_creation(self):
        """Test liquidity zone detection"""
        swing_highs = [101.0, 102.0]
        swing_lows = [99.0, 98.0]
        
        self.engine.detect_liquidity_zones(
            timeframe=5,
            swing_highs=swing_highs,
            swing_lows=swing_lows,
            current_price=100.0,
            current_timestamp=datetime.utcnow(),
        )
        
        zones = self.engine.get_liquidity_zones(5)
        self.assertGreater(len(zones), 0)


class TestTradeScoring(unittest.TestCase):
    """Test trade scoring system"""

    def setUp(self):
        self.scorer = TradeScorer()

    def test_quick_score(self):
        """Test quick scoring calculation"""
        score = self.scorer.calculate_quick_score(
            has_liquidity_sweep=True,
            has_bos=True,
            has_choch=True,
            has_fvg=True,
            has_order_block=False,
            has_pd_alignment=False,
        )
        
        self.assertEqual(score, 80.0)  # 20+20+20+20

    def test_score_validation(self):
        """Test score validation"""
        score = self.scorer.calculate_quick_score(
            has_liquidity_sweep=True,
            has_bos=True,
            has_choch=False,
            has_fvg=False,
            has_order_block=False,
            has_pd_alignment=False,
        )
        
        self.assertEqual(score, 40.0)  # 20+20


class TestRiskManager(unittest.TestCase):
    """Test risk management"""

    def setUp(self):
        self.risk_mgr = RiskManager(account_balance=1000.0)

    def test_position_creation(self):
        """Test position creation"""
        position = self.risk_mgr.create_position(
            position_id="trade_1",
            symbol="R_100",
            direction="long",
            entry_price=100.0,
            stop_loss=99.5,
            take_profit=103.0,
            quantity=1.0,
            trade_score=85.0,
            setup_factors=4,
            candle_index=0,
        )
        
        self.assertIsNotNone(position)
        self.assertEqual(position.symbol, "R_100")
        self.assertEqual(position.direction, "long")

    def test_position_sizing(self):
        """Test position size calculation"""
        size = self.risk_mgr.calculate_position_size(
            entry_price=100.0,
            stop_loss=99.5,
            symbol="R_100",
        )
        
        self.assertGreater(size, 0)


if __name__ == "__main__":
    unittest.main()
