# Alpha Trading Platform

**Paper trading research and signal monitoring system.**

> ⚠️ PAPER TRADING ONLY — No real orders are executed.
> Manual execution is done by the operator in Binance / Ziraat mobile apps.

---

## What This Is

A complete end-to-end platform for:

- **Historical data research** — CSV-based OHLCV ingestion
- **Backtesting** — event-driven bar-by-bar simulation with commission + slippage
- **Walk-forward optimization** — anti-overfitting research engine
- **Strategy ranking** — robustness-first selection (not just profit)
- **Live paper trading** — signal monitoring, state persistence, restart recovery
- **Dashboard** — Streamlit web UI for all data
- **Telegram alerts** — instant signal and risk notifications
- **AI reporting** — Claude-powered strategy diagnostics
- **Risk controls** — soft stop / hard stop / emergency workflows

**Assets:** BTCUSDT (4y), XAUUSD (5y), EURUSD (5y)
**No leverage. No real orders. Paper only.**

---

## Quick Start (Local)

### 1. Clone and install

```bash
git clone <repo>
cd alpha-platform
python3 -m venv .venv && source .venv/bin/activate
make dev-install
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — at minimum set DATABASE_URL and REDIS_URL
```

### 3. Start infrastructure (Docker)

```bash
make up
# Starts: PostgreSQL, Redis
```

### 4. Run migrations

```bash
make migrate
```

### 5. Generate sample data

```bash
make generate-data
# Creates synthetic CSV files in data/historical/
# Replace with real data before serious research
```

### 6. Run the research pipeline

```bash
make research-run
# Runs backtest + OOS + walk-forward for all asset/strategy combos
# Results printed to console and saved to data/results/
```

### 7. Start the API + Dashboard

```bash
# Terminal 1
make api

# Terminal 2
make dashboard
# Open http://localhost:8501
```

### 8. Enable Telegram (optional)

```env
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id
```

### 9. Enable AI Reports (optional)

```env
AI_REPORTS_ENABLED=true
AI_API_KEY=sk-ant-your-key
AI_MODEL=claude-sonnet-4-5
```

---

## Full Docker Deployment

```bash
make up        # starts all: postgres, redis, api, dashboard, worker
make logs      # tail all logs
make down      # stop everything
```

Services:
| Service    | Port  | Description                  |
|------------|-------|------------------------------|
| API        | 8000  | FastAPI backend              |
| Dashboard  | 8501  | Streamlit UI                 |
| PostgreSQL | 5432  | Primary database             |
| Redis      | 6379  | Cache / queue / pub-sub      |

---

## Project Structure

```
alpha-platform/
├── app/
│   ├── core/           # Enums, models, exceptions, interfaces, constants
│   ├── config/         # Settings loader (YAML + env vars)
│   ├── data/           # Data providers (CSV, stubs for TV/Binance)
│   ├── research/       # Backtest runner, metrics, WF optimizer, ranking
│   ├── strategies/     # Strategy base class, registry, examples
│   ├── portfolio/      # Exposure + correlation checks
│   ├── paper_engine/   # Paper broker, state persistence, recovery
│   ├── risk/           # Risk manager, circuit breakers, emergency stop
│   ├── notifications/  # Telegram service
│   ├── ai_reports/     # AI report generator (Claude API)
│   ├── dashboard/      # Streamlit app + pages
│   ├── api/            # FastAPI app + endpoints
│   ├── storage/        # SQLAlchemy models, repositories
│   ├── workers/        # Celery tasks
│   ├── services/       # Heartbeat, scheduler, reconciliation
│   └── utils/          # Logging, time utils
├── scripts/
│   ├── generate_sample_data.py
│   └── run_research.py
├── tests/
│   ├── unit/
│   └── integration/
├── alembic/            # DB migrations
├── config/
│   └── settings.yaml
├── deploy/
│   ├── Dockerfile.api
│   └── Dockerfile.dashboard
├── data/
│   ├── historical/     # CSV data (gitignored)
│   ├── results/        # Research output (gitignored)
│   └── state/          # Paper engine state (gitignored)
├── .env.example
├── docker-compose.yml
├── Makefile
└── pyproject.toml
```

---

## Risk Management

| Level      | Daily DD | Weekly DD | Total DD | Action                        |
|------------|----------|-----------|----------|-------------------------------|
| WARNING    | 4%       | 8%        | 20%      | Log + monitor                 |
| SOFT STOP  | 5%       | 10%       | —        | Pause new signals             |
| HARD STOP  | —        | —         | 25%      | Emergency stop, block signals |

Re-enabling after a stop requires **manual operator action** via dashboard or API.

---

## Robustness Scoring

Strategies are ranked by a composite robustness score, not profit alone:

| Component              | Weight |
|------------------------|--------|
| Profit Factor          | 20%    |
| Sharpe Ratio           | 20%    |
| Max Drawdown (penalty) | 15%    |
| Expectancy             | 15%    |
| Win Rate               | 10%    |
| OOS Degradation        | 10%    |
| WF Consistency         | 10%    |

Labels: `ROBUST` (≥0.70) · `ACCEPTABLE` (≥0.50) · `FRAGILE` (≥0.30) · `OVERFIT` (<0.30)

Strategies labeled `OVERFIT` or `INSUFFICIENT_DATA` are **automatically rejected**.

---

## Adding a New Strategy

```python
# app/strategies/examples/my_strategy.py
from app.strategies.base import BaseStrategy, StrategyRegistry

@StrategyRegistry.register
class MyStrategy(BaseStrategy):

    @property
    def name(self): return "MY_STRATEGY"

    @property
    def family(self): return "TREND_FOLLOWING"

    def default_parameters(self): return {"period": 20}

    def validate_config(self, config): return True

    def _compute_signal(self, data, config):
        # Your logic here — return Signal or None
        ...
```

Then import it in `app/strategies/__init__.py`.

---

## Adding a New Data Source

```python
# app/data/providers/my_provider.py
from app.core.interfaces import IDataProvider

class MyProvider(IDataProvider):
    @property
    def source_name(self): return "MY_SOURCE"

    def is_available(self, asset, timeframe): ...

    def get_ohlcv(self, asset, timeframe, ...): ...
```

---

## Testing

```bash
make test           # all tests
make test-unit      # unit tests only
make test-cov       # with HTML coverage report
```

---

## Known TODOs / Future Work

- [ ] TradingView webhook ingestion (stub exists in `app/data/providers/`)
- [ ] Binance API live price feed for position updates
- [ ] Celery workers: scheduled equity snapshots, nightly research jobs
- [ ] Portfolio-level exposure and correlation limits
- [ ] Regime detection module (trend/range classifier)
- [ ] Strategy degradation auto-detection and alerts
- [ ] Cloud deployment guide (Railway / Fly.io / GCP)
- [ ] Multi-user access control for dashboard
- [ ] Backtest result persistence to PostgreSQL (currently JSON files)
- [ ] Walk-forward parameter stability heatmaps
- [ ] Telegram bot interactive commands (/status, /positions, /stop)

---

## Architecture Principles

1. **Streamlit owns no state** — only reads from API/services
2. **Research engine ≠ live engine** — separate code paths
3. **Data provider is abstracted** — swap CSV → API without touching strategies
4. **Risk layer is independent** — evaluated before every signal submission
5. **Notifications are modular** — Telegram today, Email/webhook tomorrow
6. **Config is environment-driven** — no hardcoded secrets, no prod/dev forks
7. **Persistence survives restarts** — engine state written to disk atomically

---

## License

Internal use only. Not for distribution.
