# 📈 Market Scanner: SPY/QQQ FVG Setup Finder

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-WebSocket-teal)
![React](https://img.shields.io/badge/React-18%2B-61DAFB)
![Alpaca](https://img.shields.io/badge/Market%20Data-Alpaca-yellow)
![License](https://img.shields.io/badge/License-MIT-yellow)

A real-time trading assistant that scans SPY and QQQ for aligned trend + Fair Value Gap (FVG) setups during the New York session, auto-detects entries via 1-minute Inverse FVG confirmation, forward-tests trades with a fixed risk/reward model, and streams everything live to a React dashboard over WebSockets — with Telegram alerts along the way.

> ⚠️ **Disclaimer:** This project is for educational and research purposes only. It does not place real trades and is not financial advice. Use at your own risk.

---

## ✨ Features

- 📊 **Live Market Data** — Pulls 1-minute and 5-minute SPY/QQQ bars from Alpaca's IEX feed on a rolling schedule.
- 📐 **Trend Detection** — Identifies the most recent swing-based trend (bullish/bearish/none) on the 5-minute chart.
- 🕳️ **Fair Value Gap (FVG) Scanning** — Detects and tracks active, untapped 5-minute FVGs aligned with the current trend.
- 🎯 **1-Minute Inverse FVG Entry Trigger** — Confirms precision entries on the 1-minute chart once a 5m FVG is tapped.
- 🛡️ **Automated Risk Management** — Calculates stop-loss from recent 1m swing structure and targets a fixed 4R take-profit.
- 🧪 **Forward-Testing Ledger** — Tracks simulated active trades and full trade history (win/loss) in memory.
- 🔔 **Telegram Alerts** — Sends real-time notifications for session open/close, trend alignment, FVG taps, trade execution, and trade outcomes.
- 🌐 **Live WebSocket Feed** — Broadcasts scanner state every minute to all connected dashboard clients.
- 🕐 **NY Session Awareness** — Automatically gates scanning to 9:30 AM–4:00 PM ET on weekdays, with a live countdown timer on the frontend.
- 🖥️ **Real-Time Dashboard** — Visual trend cards, pre-trade checklist with progress bar, trade ledger, and a live execution log.

---

## 🏗️ Tech Stack

### Backend
| Component | Technology |
|---|---|
| API / Realtime | FastAPI + native WebSockets |
| Market Data | Alpaca (`alpaca-py`, IEX feed) |
| Data Processing | pandas |
| Timezone Handling | pytz |
| Notifications | Telegram Bot API |
| Async Scheduling | asyncio background task |

### Frontend
| Component | Technology |
|---|---|
| Framework | React |
| Animation | Framer Motion |
| Styling | Tailwind CSS |
| Icons | lucide-react |
| Realtime | Native WebSocket API |

---

## 📁 Project Structure

```
market-scanner/
├── backend/
│   ├── main.py              # FastAPI app, scanner loop, FVG/trend logic, WebSocket broadcast
│   ├── requirements.txt
│   └── .env                 # API keys (not committed)
└── frontend/
    ├── src/
    │   └── App.jsx           # Dashboard UI + WebSocket client
    ├── package.json
    └── .env
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- An [Alpaca](https://alpaca.markets/) account (for market data API keys)
- A [Telegram bot](https://core.telegram.org/bots#how-do-i-create-a-bot) token and chat ID (optional, for alerts)

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/market-scanner.git
cd market-scanner
```

### 2. Backend setup

```bash
cd backend
python -m venv venv
source venv/bin/activate      # On Windows: venv\Scripts\activate

pip install -r requirements.txt
```

Create a `.env` file in `backend/`:

```env
ALPACA_API_KEY=your_alpaca_api_key
ALPACA_SECRET_KEY=your_alpaca_secret_key
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
```

Run the server:

```bash
uvicorn main:app --reload
```

The API and WebSocket endpoint will be available at `http://localhost:8000` (WebSocket at `ws://localhost:8000/ws`).

### 3. Frontend setup

```bash
cd frontend
npm install
```

Update the WebSocket URL in `src/App.jsx` to point at your backend:

```js
const ws = new WebSocket('ws://localhost:8000/ws');
```

Run the dev server:

```bash
npm run dev
```

The dashboard will be available at `http://localhost:5173`.

---

## 🔌 API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` / `HEAD` | `/` | Health check |
| `WS` | `/ws` | Live scanner state stream (trend, FVGs, alerts, trades) |

### WebSocket payload shape

```json
{
  "timestamp": "2026-07-15 10:32:00",
  "spy_trend": 1,
  "qqq_trend": 1,
  "shared_trend": 1,
  "spy_active_fvgs": [{ "type": "BULLISH", "timestamp": "...", "gap": "601.20 - 602.10", "status": "Open (Untouched)" }],
  "qqq_active_fvgs": [],
  "execution_alerts": ["🟢 EXECUTE TRADE: LONG at ... | SL: 600.80 | TP: 604.00"],
  "active_trades": [{ "id": "...", "asset": "SPY", "direction": "LONG", "entry": 602.0, "sl": 600.8, "tp": 606.8, "status": "ACTIVE" }],
  "trade_history": []
}
```

---

## ⚙️ How the Strategy Works

1. **Session Gate** — The scanner only runs during regular NY trading hours (9:30 AM–4:00 PM ET, weekdays).
2. **Trend Alignment** — SPY and QQQ 5-minute trends are computed independently via swing high/low breaks; a "shared trend" only exists when both indices agree.
3. **5m FVG Detection** — Active, untapped Fair Value Gaps aligned with the shared trend are tracked as potential entry zones.
4. **Tap Confirmation** — Once price taps into an aligned 5m FVG, the scanner starts hunting for a 1-minute Inverse FVG in the same direction.
5. **Entry Trigger** — A confirmed 1m Inverse FVG close triggers a simulated trade, with stop-loss derived from recent 1m swing structure and take-profit set at 4x the risk (4R).
6. **Trade Management** — Active trades are monitored each cycle against live prices and closed out as a win (4R) or loss (1R), with results logged and alerted via Telegram.
7. **Live Broadcast** — Every cycle, the full scanner state is pushed to all connected WebSocket clients for real-time dashboard updates.

---

## 🗺️ Roadmap Ideas

- [ ] Persist trade history to a database instead of in-memory storage
- [ ] Support additional symbols beyond SPY/QQQ
- [ ] Configurable risk/reward ratio and lookback windows
- [ ] Historical backtesting mode
- [ ] Broker integration for live order execution

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome. Feel free to open an issue or submit a pull request.

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
