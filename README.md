# Award Planner (Seats.aero)

A private, non-commercial award-flight planning app that runs locally with Streamlit. It relies on the Seats.aero Partner API (Pro key) for cached/bulk availability and optional live searches. All data stays in a local SQLite database (`data/app.db`), and a separate poller script can send notifications via email or Telegram.

## Features
- Streamlit UI with a simple search form (origins, destinations/region, date range, cabin, passengers, max points, mileage program, BA companion toggle).
- Results table with per-day expanders and buttons to add itineraries to favorites.
- Watchlist of saved searches with optional alerts; BA companion voucher workflow is a link-out to BA Reward Flight Finder (no scraping).
- SQLite persistence for searches, alert state, cached responses, and favorites.
- Poller script (`scripts/poller.py`) to re-run saved searches, diff against the last snapshot, and send notifications.
- Caching layer to minimize Seats.aero calls (TTL configurable via environment variables) and a rate-limit guard (default ≤ 900 calls/day).

## Requirements
- Python 3.11+
- Seats.aero Partner API key (Pro tier) for non-commercial use

## Setup
1. **Create a virtual environment and install dependencies**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
   pip install -r requirements.txt
   ```

2. **Configure environment variables**
   Copy `.env.example` to `.env` and fill in your Seats.aero API key. Optional: email or Telegram credentials for alerts.
   ```bash
   cp .env.example .env
   ```

3. **Run the Streamlit app**
   ```bash
   streamlit run app.py
   ```
   Open the printed localhost URL in your browser. Searches use cached responses when available; otherwise the app calls Seats.aero with your API key.

4. **Run the poller once**
   ```bash
   python scripts/poller.py --once
   ```
   Schedule it via cron/Task Scheduler for continuous monitoring (the script is intentionally simple and single-run by default).

## Configuration
Key environment variables (see `.env.example`):
- `SEATS_AERO_API_KEY`: Seats.aero Partner API key (required for live calls)
- `CACHE_TTL_HOURS`: Hours to keep cached responses (default 12)
- `MAX_API_CALLS`: Daily call guard for the poller (default 900)
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_FROM`, `EMAIL_TO`: Email settings for alerts (optional)
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`: Telegram bot credentials for alerts (optional)

## Notes
- The app does **not** scrape airline sites. British Airways companion-voucher planning is handled via link-out to BA's Reward Flight Finder for manual booking.
- All persistence is local under `data/app.db`; delete the file to start fresh.
