from __future__ import annotations

import json
from typing import Dict, Iterable, List, Sequence

from .models import AvailabilityResponse, Itinerary


def itinerary_index(itineraries: Sequence[Itinerary]) -> Dict[str, Itinerary]:
    return {it.key(): it for it in itineraries}


def detect_new_itineraries(previous: Sequence[Itinerary], current: Sequence[Itinerary]) -> List[Itinerary]:
    previous_keys = set(it.key() for it in previous)
    return [it for it in current if it.key() not in previous_keys]


def format_alert_message(title: str, new_itineraries: Sequence[Itinerary]) -> str:
    header = f"New award space for {title}\n"
    lines = [
        f"- {it.departure_date}: {it.origin} -> {it.destination} ({it.cabin}), {it.seats} seats"
        f" via {it.program or 'unknown'} for {it.points_cost or 'N/A'}"
        for it in new_itineraries
    ]
    return header + "\n".join(lines)


def serialize_itinerary(itinerary: Itinerary) -> str:
    return json.dumps(itinerary.dict(), default=str)


def diff_against_last(previous_json: str, current_response: AvailabilityResponse) -> List[Itinerary]:
    try:
        previous_data = json.loads(previous_json).get("itineraries", [])
    except json.JSONDecodeError:
        previous_data = []
    previous_itineraries = [Itinerary.parse_obj(item) for item in previous_data]
    return detect_new_itineraries(previous_itineraries, current_response.itineraries)


def describe_ba_companion_workflow() -> str:
    return (
        "Use the BA Reward Flight Finder to confirm companion-voucher inventory. "
        "Copy the search parameters from this app and complete booking manually at "
        "https://www.britishairways.com/travel/redeem-flight/public/en_gb."
    )
