# Deriv SMC Bot - Quick Start Guide

## Installation

### 1. Clone Repository
```bash
git clone https://github.com/Darknight254/deriv-smc-bot.git
cd deriv-smc-bot
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure API Token
```bash
cp .env.example .env
```

Edit `.env` and add your Deriv API token:
```
DERIV_API_TOKEN=your_token_here
```

### 4. Run the Bot
```bash
python src/bot.py
```

## Configuration

Edit `config.yaml` to customize:
- Symbols: R_100, R_50, R_10
- Timeframes: 1m, 5m, 15m
- Risk parameters
- Scoring thresholds
- Alert channels

## Understanding the Bot

### Market Structure
- **Swing Highs/Lows**: Support and resistance levels
- **BOS (Break of Structure)**: Price breaks through previous swing
- **CHoCH (Change of Character)**: Market structure shift

### Trade Setup Signals
1. **Liquidity Sweep**: Price sweeps buy-side or sell-side liquidity
2. **BOS Confirmation**: Market breaks structure on candle close
3. **CHoCH Detected**: Change in market character
4. **FVG Retracement**: Price enters fair value gap
5. **Order Block**: Price approaches order block zone
6. **PD Array**: Price in discount (long) or premium (short)

### Scoring System
- Each factor = points
- Minimum 80/100 to enter
- Minimum 3 factors required
- Enforces 1:3 risk:reward ratio

## Trade Alerts

Receive notifications when:
- ✅ High-quality setup forms
- ✅ Trade entered automatically
- ✅ Liquidity swept
- ✅ Exit signal generated

## Risk Management

- **Position Sizing**: Auto-calculated
- **Daily Loss Limit**: Max 3 losses/day
- **Drawdown Protection**: Stop at 5% loss
- **Account Tracking**: Real-time P&L

## Performance Tracking

View statistics:
```python
from src.database_manager import DatabaseManager

db = DatabaseManager()
stats = db.get_win_rate(symbol="R_100")
print(f"Win Rate: {stats['win_rate']:.1f}%")
```

## Testing

Run tests:
```bash
python -m pytest tests/
```

Run backtester:
```bash
python -c "from src.backtester import Backtester; bt = Backtester(); print('Backtester ready')"
```

## Support

- **Issues**: GitHub Issues
- **Docs**: README.md
- **API**: Deriv API Documentation

## Disclaimer

⚠️ **Educational purposes only**. Trading involves risk. Always test on demo first.
