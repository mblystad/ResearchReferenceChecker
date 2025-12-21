from __future__ import annotations

import os
from datetime import date
from typing import List

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from src.award_planner import alerts
from src.award_planner.cache import get_cached, set_cache
from src.award_planner.db import (
    add_favorite,
    get_connection,
    init_db,
    list_favorites,
    list_saved_searches,
    save_search,
    save_search_run,
    upsert_alert,
)
from src.award_planner.models import AvailabilityResponse, SearchParams
from src.award_planner.seats_aero_client import SeatsAeroClient

load_dotenv()

API_KEY = os.getenv("SEATS_AERO_API_KEY", "")
DEFAULT_TTL_HOURS = int(os.getenv("CACHE_TTL_HOURS", "12"))


@st.cache_resource
def get_db_connection():
    conn = get_connection()
    init_db(conn)
    return conn


def parse_csv(value: str) -> List[str]:
    return [item.strip().upper() for item in value.split(",") if item.strip()]


def run_search(params: SearchParams) -> AvailabilityResponse:
    conn = get_db_connection()
    cached = get_cached(conn, params)
    if cached:
        return AvailabilityResponse.parse_raw(cached)

    if not API_KEY:
        raise RuntimeError("Set SEATS_AERO_API_KEY in your environment to search.")

    client = SeatsAeroClient(API_KEY)
    response = client.bulk_availability(params)
    set_cache(conn, params, response.json(), ttl_hours=DEFAULT_TTL_HOURS)
    return response


def render_results(response: AvailabilityResponse) -> None:
    st.subheader("Results")
    if not response.itineraries:
        st.info("No availability returned for the current search.")
        return

    df = pd.DataFrame(response.as_dataframe_records())
    st.dataframe(df)

    dates = sorted({it.departure_date for it in response.itineraries})
    for d in dates:
        with st.expander(f"{d}"):
            day_itineraries = [it for it in response.itineraries if it.departure_date == d]
            for it in day_itineraries:
                st.markdown(
                    f"**{it.origin} → {it.destination}** | {it.cabin} | {it.seats} seats | "
                    f"{it.program or 'program?'} | {it.points_cost or 'points?'}"
                )
                if st.button("Add to favorites", key=f"fav-{it.key()}"):
                    conn = get_db_connection()
                    add_favorite(conn, it.key(), alerts.serialize_itinerary(it))
                    st.success("Added to favorites")


def render_watchlist() -> None:
    st.subheader("Watchlist")
    conn = get_db_connection()
    searches = list_saved_searches(conn)
    if not searches:
        st.caption("No saved searches yet.")
        return

    for search in searches:
        st.markdown(f"**{search['name']}** — {search['params'].origins} → {search['params'].destinations or search['params'].region}")
        cols = st.columns(3)
        if cols[0].button("Run now", key=f"run-{search['id']}"):
            response = run_search(search["params"])
            save_search_run(conn, search["id"], response)
            render_results(response)
        if cols[1].button("Enable alerts", key=f"alert-{search['id']}"):
            upsert_alert(conn, search["id"], channels=default_channels())
            st.success("Alert enabled")
        if cols[2].button("Copy BA workflow", key=f"ba-{search['id']}"):
            st.info(alerts.describe_ba_companion_workflow())


def render_favorites() -> None:
    st.subheader("Favorites")
    conn = get_db_connection()
    favorites = list_favorites(conn)
    if not favorites:
        st.caption("No favorites saved.")
        return
    for fav in favorites:
        st.markdown(f"{fav['itinerary_key']} — {fav['notes'] or ''}")


def default_channels() -> List[str]:
    channels: List[str] = []
    if os.getenv("SMTP_HOST") and os.getenv("EMAIL_TO"):
        channels.append("email")
    if os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"):
        channels.append("telegram")
    return channels


def render_ba_companion_section(companion_mode: bool) -> None:
    if companion_mode:
        st.warning(alerts.describe_ba_companion_workflow())
        st.markdown("[Open BA Reward Flight Finder](https://www.britishairways.com/travel/redeem-flight/public/en_gb)")


def main() -> None:
    st.title("Award Planner (Seats.aero)")
    st.caption("Local, non-commercial tool for browsing and tracking award availability.")

    with st.sidebar:
        st.header("Search")
        with st.form("search_form"):
            origins = st.text_input("Origins (comma separated)")
            destinations = st.text_input("Destinations (comma separated)")
            region = st.text_input("Region (optional)")
            col1, col2 = st.columns(2)
            start_date = col1.date_input("Start date", value=date.today())
            end_date = col2.date_input("End date", value=date.today())
            cabin = st.selectbox("Cabin", ["economy", "premium_economy", "business", "first"])
            passengers = st.number_input("Passengers", min_value=1, max_value=9, value=1)
            max_points = st.number_input("Max points", min_value=0, value=0, help="0 to skip filter")
            program_source = st.text_input("Mileage program", value="avios")
            companion_mode = st.checkbox("BA Companion Voucher mode")
            search_name = st.text_input("Save search as", value="")
            alert_channel_choices = st.multiselect(
                "Alert channels", options=["email", "telegram"], default=default_channels()
            )
            submitted = st.form_submit_button("Search availability")

    response: AvailabilityResponse | None = None
    if submitted:
        try:
            params = SearchParams(
                origins=parse_csv(origins),
                destinations=parse_csv(destinations) if destinations else None,
                region=region or None,
                start_date=start_date,
                end_date=end_date,
                cabin=cabin,
                passengers=passengers,
                max_points=max_points or None,
                program_source=program_source,
                companion_mode=companion_mode,
            )
            response = run_search(params)
            render_results(response)
            render_ba_companion_section(companion_mode)
            conn = get_db_connection()
            if search_name:
                saved_id = save_search(conn, search_name, params)
                save_search_run(conn, saved_id, response)
                if alert_channel_choices:
                    upsert_alert(conn, saved_id, alert_channel_choices)
                    st.success("Alert configured for saved search")
                st.success("Search saved")
        except Exception as exc:  # noqa: BLE001
            st.error(str(exc))

    render_watchlist()
    render_favorites()


if __name__ == "__main__":
    main()
