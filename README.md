# Deriv SMC Trading Bot

**Professional-Grade Smart Money Concepts Trading Bot for Deriv Volatility Indices**

## Overview

This is a sophisticated, production-ready automated trading bot that analyzes Deriv volatility indices (R_100, R_50, R_10) using advanced **Smart Money Concepts (SMC)** methodology.

The bot independently analyzes multiple volatility markets simultaneously, detects high-quality trading setups, and alerts you when trade opportunities become available.

## Key Features

### 🎯 Core SMC Analysis
- **Market Structure Detection**: Swing highs/lows, Break of Structure (BOS), Change of Character (CHoCH)
- **Liquidity Analysis**: Identifies and tracks liquidity zones, detects sweeps
- **Fair Value Gap (FVG) Detection**: 3-candle imbalances with fill tracking
- **Order Block Analysis**: Detects high-quality order blocks with strength scoring
- **Premium/Discount Arrays**: Identifies optimal long/short zones
- **Multi-Timeframe Confirmation**: 15m bias → 5m confirmation → 1m execution

### 📊 Intelligent Trade Scoring
- **Confluence Factors**: Requires at least 3 SMC factors to align
- **Dynamic Scoring**: Each setup scores 0-100 based on confluence
- **Minimum Threshold**: Only enters trades scoring 80+ points
- **Risk:Reward Validation**: Enforces minimum 1:3 ratio

### 🚀 Multi-Symbol Capability
- **Simultaneous Analysis**: Monitors R_100, R_50, R_10 at the same time
- **Independent Scoring**: Each symbol analyzed separately
- **Prioritized Alerts**: High-quality setups flagged first

### 🔔 Real-Time Alert System
- **Telegram Notifications**: Instant alerts when setups form
- **Email Alerts**: Detailed trade information delivered to inbox
- **Desktop Notifications**: Pop-up alerts for immediate attention
- **Trade Lifecycle Alerts**: Setup formation → Entry → Exit

### 💰 Professional Risk Management
- **Position Sizing**: Automatic calculation based on risk tolerance
- **Daily Loss Limits**: Max 3 losing trades per day
- **Drawdown Protection**: Stops trading if drawdown exceeds 5%
- **Risk:Reward Enforcement**: Minimum 1:3 ratio required
- **Account Balance Tracking**: Real-time P&L calculation

### 📚 Learning Engine
- **Trade Database**: SQLite storage of all trades with analysis
- **Win Rate Tracking**: By setup type, timeframe, and symbol
- **Performance Analytics**: Identify best-performing setups
- **Backtesting Ready**: Historical data for strategy validation

## Installation

### Prerequisites
- Python 3.8+
- Deriv Account with API access
- Telegram Bot (optional, for alerts)

### Setup

1. **Clone the repository**
```bash
git clone https://github.com/Darknight254/deriv-smc-bot.git
cd deriv-smc-bot
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure environment**
```bash
cp .env.example .env
```

Edit `.env` and add your Deriv API token:
```
DERIV_API_TOKEN=your_token_here
DERIV_APP_ID=9305

# Optional: Telegram alerts
TELEGRAM_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

4. **Create data directory**
```bash
mkdir -p data logs
```

## Usage

### Run the Bot
```bash
python src/bot.py
```

The bot will:
1. Connect to Deriv API
2. Subscribe to R_100, R_50, R_10 data
3. Analyze candles on 1m, 5m, 15m timeframes
4. Detect trade setups in real-time
5. Send alerts when opportunities appear
6. Store all data for analysis

### Check Status
```python
from src.bot import DerivSMCBot

bot = DerivSMCBot(api_token="your_token")
status = bot.get_bot_status()
print(status)
```

## Architecture

### Core Modules

```
src/
├── market_structure.py      # BOS, CHoCH, swing detection
├── liquidity_engine.py      # Liquidity zones & sweeps
├── fvg_engine.py           # Fair value gap detection
├── order_block_engine.py   # Order block analysis
├── pd_array_engine.py      # Premium/discount zones
├── trade_scoring.py        # Confluence scoring system
├── alert_system.py         # Telegram/Email/Desktop alerts
├── risk_manager.py         # Position sizing & risk limits
├── database_manager.py     # Trade history storage
├── deriv_api_client.py     # Deriv WebSocket client
├── multi_symbol_manager.py # Multi-symbol orchestration
└── bot.py                  # Main bot orchestrator
```

### Data Flow

```
Deriv API (WebSocket)
     ↓
Candle Data (1m, 5m, 15m)
     ↓
Market Structure Analysis
     ↓
Liquidity Detection
     ↓
FVG & Order Block Analysis
     ↓
Trade Scoring (Confluence)
     ↓
Risk Checks
     ↓
[Alert System] → Telegram/Email/Desktop
[Risk Manager] → Position Sizing
[Database] → Trade Storage
```

## Configuration

Edit `config.yaml` to customize:

```yaml
trading:
  symbols:
    - R_100      # Volatility 100 Index
    - R_50       # Volatility 50 Index
    - R_10       # Volatility 10 Index
  
  timeframes:
    primary: 15      # Minutes (bias confirmation)
    confirmation: 5  # Minutes (structure confirmation)
    execution: 1     # Minutes (entry execution)

risk_management:
  risk_per_trade: 0.5       # % of account per trade
  max_daily_losses: 3       # Stop after 3 losses
  max_drawdown_percent: 5.0 # Max drawdown allowed
  min_risk_reward_ratio: 3.0 # Minimum 1:3 ratio

smc_settings:
  liquidity:
    swing_lookback: 20
    equal_high_tolerance: 0.0005
  fvg:
    min_gap_size: 0.0010
  order_block:
    min_strength_score: 70

scoring:
  liquidity_sweep: 20       # Points
  bos_confirmation: 20      # Points
  choch_confirmation: 20    # Points
  fvg_alignment: 15         # Points
  order_block_alignment: 15 # Points
  pd_array_alignment: 10    # Points
  total_threshold: 80       # Minimum to enter
```

## Trade Analysis

### Example Trade Setup

```
Symbol: R_100 | TF: 5m | Score: 92/100

✅ Confluence Factors (4/6):
  • Sell-side liquidity swept
  • Bearish BOS confirmed
  • Bearish CHoCH detected  
  • Price in bearish FVG
  ✗ Order block not active
  ✗ Not in premium zone

Entry: 120.50
Stop Loss: 120.75 (25 pips)
Take Profit: 119.75 (75 pips)
Risk:Reward: 1:3.0 ✅
```

## Performance Tracking

View trade statistics:

```python
from src.database_manager import DatabaseManager

db = DatabaseManager()

# Get trade history
trades = db.get_trade_history(symbol="R_100", limit=50)

# Get win rate
stats = db.get_win_rate(symbol="R_100")
print(f"Win Rate: {stats['win_rate']:.1f}%")
print(f"Profit Factor: {stats['profit_factor']:.2f}")
```

## Alerts

The bot sends alerts for:
- **Setup Formed**: High-quality confluence detected
- **Entry Executed**: Trade entered automatically
- **Liquidation Sweep**: Liquidity zone swept
- **BOS/CHoCH**: Market structure breaks detected
- **FVG Detected**: Fair value gaps identified
- **Exit Signal**: TP/SL/Manual close

## Safety Features

✅ **Risk Controls**
- Max 2 concurrent trades
- Max 3 daily losses before stopping
- Position sizing auto-calculated
- Minimum RR ratio enforced
- Daily drawdown limits

✅ **Data Integrity**
- SQLite database with automatic backup
- Detailed logging of all actions
- Trade validation before execution
- Error recovery mechanisms

✅ **Account Protection**
- Demo/Live account support
- Dry-run mode for testing
- Trade review before execution
- Automatic stop on critical errors

## Disclaimer

**This bot is for educational purposes only.** Trading involves significant risk. Past performance does not guarantee future results. Always use a demo account first, understand the risks, and trade responsibly.

## Support & Documentation

- **Issues**: [GitHub Issues](https://github.com/Darknight254/deriv-smc-bot/issues)
- **Deriv API**: [Deriv API Documentation](https://api.deriv.com/)
- **SMC Resources**: [Smart Money Concepts Learning](https://smartmoneytraders.com/)

## License

MIT License - See LICENSE file for details

## Contributing

Contributions welcome! Please submit pull requests to improve the bot.

---

**Made with ❤️ by Darknight254**
