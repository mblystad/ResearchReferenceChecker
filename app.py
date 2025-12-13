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
from src.award_planner.models import AvailabilityResponse, Offer, OfferStatus, SearchParams
from src.award_planner.seats_aero_client import SeatsAeroClient

load_dotenv()

API_KEY = os.getenv("SEATS_AERO_API_KEY", "")
DEFAULT_TTL_HOURS = int(os.getenv("CACHE_TTL_HOURS", "12"))


@st.cache_resource
def get_db_connection():
    conn = get_connection()
    init_db(conn)
    return conn


def run_search(params: SearchParams) -> AvailabilityResponse:
    conn = get_db_connection()
    cached = get_cached(conn, params)
    if cached:
        return AvailabilityResponse.parse_raw(cached)

    if not API_KEY:
        raise RuntimeError("Set SEATS_AERO_API_KEY in your environment to search.")

    client = SeatsAeroClient(API_KEY)
    response = client.search_eurobonus(params)
    set_cache(conn, params, response.json(), ttl_hours=DEFAULT_TTL_HOURS)
    return response


def status_badge(status: str) -> str:
    mapping = {
        OfferStatus.EUROBONUS_CONFIRMED: "✅ EUROBONUS_CONFIRMED",
        OfferStatus.VERIFY_ON_SAS: "⚠️ VERIFY_ON_SAS",
        OfferStatus.PARTNER_SIGNAL_ONLY: "ℹ️ PARTNER_SIGNAL_ONLY",
        OfferStatus.NOT_AVAILABLE: "❌ NOT_AVAILABLE",
    }
    return mapping.get(status, status)


def render_checklist() -> None:
    with st.expander("How to use your SAS Amex companion voucher"):
        st.markdown(
            "- Log in to SAS.\n"
            "- Choose **Pay with points**.\n"
            "- Confirm there are **2 seats** in your cabin.\n"
            "- Apply the Amex 2-for-1 voucher during checkout (discount shows in the price overview)."
        )


def render_results(response: AvailabilityResponse) -> None:
    st.subheader("Results")
    if not response.offers:
        st.info("No availability returned for the current search.")
        return

    df = pd.DataFrame(response.as_dataframe_records())
    st.dataframe(df)

    dates = sorted({it.departure_date for it in response.offers})
    for d in dates:
        with st.expander(f"{d}"):
            day_offers = [it for it in response.offers if it.departure_date == d]
            for it in day_offers:
                st.markdown(
                    f"**{it.origin} → {it.destination}** | {it.cabin.upper()} | {status_badge(it.status)}\n\n"
                    f"Points: {it.points_cost or '—'} | Taxes/fees: {it.taxes or '—'} | "
                    f"Seats: {it.seats_available or 'unknown'} | Source: {it.source_program}"
                )
                cols = st.columns([1, 1])
                with cols[0]:
                    st.link_button("Open SAS Pay with points", it.booking_url or "https://www.flysas.com")
                with cols[1]:
                    if st.button("Add to favorites", key=f"fav-{it.key()}"):
                        conn = get_db_connection()
                        add_favorite(conn, it.key(), alerts.serialize_offer(it))
                        st.success("Added to favorites")
                render_checklist()


def render_watchlist() -> None:
    st.subheader("Watchlist")
    conn = get_db_connection()
    searches = list_saved_searches(conn)
    if not searches:
        st.caption("No saved searches yet.")
        return

    for search in searches:
        params: SearchParams = search["params"]
        destination_label = params.destination or params.region or ""
        st.markdown(f"**{search['name']}** — {params.origin} → {destination_label}")
        cols = st.columns(3)
        if cols[0].button("Run now", key=f"run-{search['id']}"):
            response = run_search(params)
            save_search_run(conn, search["id"], response)
            render_results(response)
        if cols[1].button("Enable alerts", key=f"alert-{search['id']}"):
            upsert_alert(conn, search["id"], channels=default_channels())
            st.success("Alert enabled")
        if cols[2].button("SAS voucher checklist", key=f"sas-{search['id']}"):
            st.info(alerts.describe_sas_companion_workflow())


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


def render_companion_section(companion_mode: bool) -> None:
    if companion_mode:
        st.info(alerts.describe_sas_companion_workflow())
        st.markdown("[Open SAS Pay with points](https://www.flysas.com/en/book-flights/)")


def main() -> None:
    st.title("SAS EuroBonus Companion Finder")
    st.caption("Check EuroBonus award space for 2 passengers and prepare SAS Amex companion bookings.")

    with st.sidebar:
        st.header("Search")
        with st.form("search_form"):
            origin = st.text_input("Origin (airport)")
            destination_or_region = st.text_input("Destination (airport or region)")
            col1, col2 = st.columns(2)
            start_date = col1.date_input("Start date", value=date.today())
            end_date = col2.date_input("End date", value=date.today())
            cabin = st.selectbox("Cabin", ["economy", "premium_economy", "business"])
            st.caption("Passengers fixed to 2 when companion mode is on (default).")
            companion_mode = st.checkbox("SAS Amex Companion Mode", value=True)
            nonstop_only = st.checkbox("Nonstop only", value=False)
            sas_only = st.checkbox("SAS-operated only", value=False)
            fallback_enabled = st.checkbox("Enable partner-signal fallback", value=True)
            search_name = st.text_input("Save search as", value="")
            alert_channel_choices = st.multiselect(
                "Alert channels", options=["email", "telegram"], default=default_channels()
            )
            submitted = st.form_submit_button("Search availability")

    response: AvailabilityResponse | None = None
    if submitted:
        try:
            dest_clean = destination_or_region.strip().upper()
            destination = dest_clean if dest_clean else None
            region = None
            if destination and len(destination) != 3:
                region = destination
                destination = None

            params = SearchParams(
                origin=origin.strip().upper(),
                destination=destination,
                region=region,
                start_date=start_date,
                end_date=end_date,
                cabin=cabin,
                companion_mode=companion_mode,
                nonstop_only=nonstop_only,
                sas_only=sas_only,
                fallback_enabled=fallback_enabled,
            )
            response = run_search(params)
            render_results(response)
            render_companion_section(companion_mode)
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
