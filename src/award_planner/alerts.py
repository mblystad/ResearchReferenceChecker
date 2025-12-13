from __future__ import annotations

import json
from typing import Dict, Iterable, List, Sequence

from .models import AvailabilityResponse, Offer, OfferStatus


def offer_index(offers: Sequence[Offer]) -> Dict[str, Offer]:
    return {it.key(): it for it in offers}


def detect_new_offers(previous: Sequence[Offer], current: Sequence[Offer]) -> List[Offer]:
    previous_keys = set(it.key() for it in previous)
    return [it for it in current if it.key() not in previous_keys]


def format_alert_message(title: str, new_offers: Sequence[Offer]) -> str:
    header = f"New EuroBonus award space for {title}\n"
    lines = [
        "- {date}: {orig} -> {dest} ({cabin}) via {prog} | status: {status} | seats: {seats}".format(
            date=it.departure_date,
            orig=it.origin,
            dest=it.destination,
            cabin=it.cabin,
            prog=it.source_program,
            status=it.status,
            seats=it.seats_available or "unknown",
        )
        for it in new_offers
    ]
    return header + "\n".join(lines)


def serialize_offer(offer: Offer) -> str:
    return json.dumps(offer.dict(), default=str)


def diff_against_last(previous_json: str, current_response: AvailabilityResponse) -> List[Offer]:
    try:
        previous_data = json.loads(previous_json).get("offers", [])
    except json.JSONDecodeError:
        previous_data = []
    previous_offers = [Offer.parse_obj(item) for item in previous_data]
    return detect_new_offers(previous_offers, current_response.offers)


def describe_sas_companion_workflow() -> str:
    return (
        "Confirm EuroBonus award space for 2 passengers, then book manually on SAS. "
        "In the SAS booking flow, choose 'Pay with points' and apply the Amex 2-for-1 "
        "companion voucher at checkout; the discount shows in the price overview."
    )


def confirmed_offers_only(offers: Iterable[Offer]) -> List[Offer]:
    return [offer for offer in offers if offer.status == OfferStatus.EUROBONUS_CONFIRMED]
