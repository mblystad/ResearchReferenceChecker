from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from typing import List

import httpx
from dotenv import load_dotenv

from src.award_planner import alerts
from src.award_planner.cache import get_cached, set_cache
from src.award_planner.db import (
    enabled_alerts,
    get_connection,
    get_last_run,
    init_db,
    record_notification,
    save_search_run,
)
from src.award_planner.models import AvailabilityResponse, SearchParams
from src.award_planner.seats_aero_client import SeatsAeroClient

load_dotenv()

API_KEY = os.getenv("SEATS_AERO_API_KEY", "")


class RateLimiter:
    def __init__(self, max_calls: int) -> None:
        self.max_calls = max_calls
        self.calls = 0

    def allow(self) -> bool:
        return self.calls < self.max_calls

    def increment(self) -> None:
        self.calls += 1


def notify_email(subject: str, body: str) -> None:
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    email_from = os.getenv("EMAIL_FROM")
    email_to = os.getenv("EMAIL_TO")
    if not all([smtp_host, smtp_user, smtp_password, email_from, email_to]):
        return
    import smtplib
    from email.message import EmailMessage

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = email_from
    msg["To"] = email_to
    msg.set_content(body)

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)


def notify_telegram(body: str) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": body}
    with httpx.Client(timeout=10.0) as client:
        client.post(url, json=payload)


def run_once(ttl_hours: int, max_calls: int) -> None:
    conn = get_connection()
    init_db(conn)
    limiter = RateLimiter(max_calls)

    alerts_enabled = enabled_alerts(conn)
    if not alerts_enabled:
        print("No alerts enabled; exiting.")
        return

    if not API_KEY:
        print("Seats.aero API key missing; set SEATS_AERO_API_KEY.")
        return

    client = SeatsAeroClient(API_KEY)

    for alert_entry in alerts_enabled:
        if not limiter.allow():
            print("Rate limit reached; stopping cycle.")
            break
        params: SearchParams = alert_entry["params"]
        cached = get_cached(conn, params)
        if cached:
            response = AvailabilityResponse.parse_raw(cached)
        else:
            response = client.bulk_availability(params)
            set_cache(conn, params, response.json(), ttl_hours=ttl_hours)
            limiter.increment()

        last_run = get_last_run(conn, alert_entry["saved_search_id"])
        new_itins = []
        if last_run:
            new_itins = alerts.diff_against_last(last_run["response_json"], response)
        if not last_run or new_itins:
            save_search_run(conn, alert_entry["saved_search_id"], response)
        if new_itins:
            message = alerts.format_alert_message(alert_entry["name"], new_itins)
            channels: List[str] = alert_entry["channels"] or []
            if "email" in channels:
                notify_email(f"Award alert: {alert_entry['name']}", message)
            if "telegram" in channels:
                notify_telegram(message)
            record_notification(conn, alert_entry["alert_id"])
            print(f"Notified for {alert_entry['name']} at {datetime.utcnow().isoformat()}.")


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Poll Seats.aero searches and send alerts.")
    parser.add_argument("--once", action="store_true", help="Run a single polling cycle and exit")
    parser.add_argument("--ttl-hours", type=int, default=int(os.getenv("CACHE_TTL_HOURS", "12")))
    parser.add_argument("--max-calls", type=int, default=int(os.getenv("MAX_API_CALLS", "900")))
    args = parser.parse_args(argv)

    if not args.once:
        print("Use --once for now; scheduling can be done via cron or task scheduler.")

    run_once(args.ttl_hours, args.max_calls)
    return 0


if __name__ == "__main__":
    sys.exit(main())
