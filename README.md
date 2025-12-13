# SAS EuroBonus Companion Finder

Local Streamlit app for checking award flights that can be booked with SAS EuroBonus points and an Amex 2-for-1 companion voucher. The app relies **only** on the Seats.aero Partner API (Pro key) and stores everything in a local SQLite database.

## What it does
- Searches EuroBonus availability for **2 passengers** (companion mode on by default) with filters for origin, destination/region, date range, cabin, nonstop, and SAS-operated only.
- Adds clear status badges per itinerary:
  - ✅ **EUROBONUS_CONFIRMED** – EuroBonus source shows ≥2 seats.
  - ⚠️ **VERIFY_ON_SAS** – Seat count missing/unknown.
  - ℹ️ **PARTNER_SIGNAL_ONLY** – Fallback partner signal; verify manually.
  - ❌ **NOT_AVAILABLE** – Seat count present and <2.
- Provides an **Open SAS Pay with points** button and a voucher checklist on every result (manual booking only; the app never applies the voucher for you).
- Saves searches/favorites, caches API responses, and includes a poller script for alerts on newly confirmed availability.

## Limitations
- The app **does not** scrape airline sites or automate booking. It only checks award availability and links you to SAS to complete the booking.
- The Amex companion voucher is applied manually in the SAS booking flow (after selecting **Pay with points**). This app only confirms whether EuroBonus space for two passengers exists.
- Partner-signal results are hints only; always verify on SAS before booking.

## Setup
1. **Create a virtual environment and install dependencies**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure environment variables**
   Copy `.env.example` to `.env` and fill in your Seats.aero API key. Optional: email/Telegram credentials for alerts and partner source overrides.
   ```bash
   cp .env.example .env
   ```

3. **Run the Streamlit app**
   ```bash
   streamlit run app.py
   ```
   Use the sidebar to search. Results are cached in `data/app.db` to stay under API limits.

4. **Run the poller once (optional alerts)**
   ```bash
   python scripts/poller.py --once
   ```
   Schedule via cron/Task Scheduler for continuous monitoring. Alerts fire when **EUROBONUS_CONFIRMED** offers become newly available.

## Configuration
Key environment variables (see `.env.example`):
- `SEATS_AERO_API_KEY`: Seats.aero Partner API key (required)
- `CACHE_TTL_HOURS`: Hours to keep cached responses (default 12)
- `MAX_API_CALLS`: Daily call guard for the poller (default 900)
- `PARTNER_SOURCES`: Comma list of partner programs to use for fallback signals (default: `flyingblue,delta,virgin`)
- Email alerts: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_FROM`, `EMAIL_TO`
- Telegram alerts: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`

## Data storage
All persistence lives in `data/app.db` (searches, caches, alert state, favorites). Delete the file to start fresh.
