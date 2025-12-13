from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

import httpx

from .models import AvailabilityResponse, Offer, OfferStatus, SearchParams

API_BASE_URL = "https://partner-api.seats.aero/v1"
DEFAULT_BOOKING_URL = "https://www.flysas.com/en/book-flights/"  # manual booking


class SeatsAeroClient:
    def __init__(
        self,
        api_key: str,
        timeout: float = 10.0,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
    ) -> None:
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self._client = httpx.Client(timeout=timeout, headers=self._headers())

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "User-Agent": "award-planner/0.1",
        }

    def search_eurobonus(self, params: SearchParams, partner_sources: Optional[List[str]] = None) -> AvailabilityResponse:
        partner_sources = partner_sources or self._default_partner_sources()
        offers = self._fetch_program(params, program="eurobonus")

        if self._should_fallback_to_partners(offers, params):
            for program in partner_sources:
                offers.extend(self._fetch_program(params, program=program, partner_signal=True))

        return AvailabilityResponse(search_params=params, offers=offers)

    def _post_with_retries(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{API_BASE_URL}/{path}"
        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self._client.post(url, json=payload)
                response.raise_for_status()
                return response.json()
            except httpx.RequestError as exc:
                last_error = exc
            except httpx.HTTPStatusError as exc:
                last_error = exc
                if exc.response.status_code in {401, 403, 404}:
                    break
            sleep_time = self.backoff_factor * (2 ** (attempt - 1))
            time.sleep(sleep_time)
        message = "Seats.aero request failed"
        if last_error:
            message = f"{message}: {last_error}"
        raise RuntimeError(message)

    def _build_payload(self, params: SearchParams, program: str) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "origins": [params.origin],
            "startDate": params.start_date.isoformat(),
            "endDate": params.end_date.isoformat(),
            "cabin": params.cabin,
            "passengers": params.passengers,
            "program": program,
        }
        if params.destination:
            payload["destinations"] = [params.destination]
        if params.region:
            payload["region"] = params.region
        if params.nonstop_only:
            payload["nonstop"] = True
        return payload

    def _fetch_program(self, params: SearchParams, program: str, partner_signal: bool = False) -> List[Offer]:
        payload = self._build_payload(params, program=program)
        response_data = self._post_with_retries("availability/bulk", payload)
        offers: List[Offer] = []
        for item in response_data.get("data", []):
            offer = self._parse_offer(item, program, partner_signal)
            if params.sas_only and offer.airline and offer.airline.upper() != "SK":
                continue
            if params.companion_mode and offer.seats_available is not None and offer.seats_available < params.passengers:
                continue
            offers.append(offer)
        return offers

    def _parse_offer(self, item: Dict[str, Any], program: str, partner_signal: bool) -> Offer:
        metadata = {k: v for k, v in item.items() if k not in {
            "origin",
            "destination",
            "departureDate",
            "cabin",
            "seats",
            "airline",
            "pointsCost",
            "taxes",
        }}
        seats = item.get("seats")
        status = self._derive_status(seats, partner_signal)
        notes = None
        if partner_signal:
            notes = "Availability shown via partner program; verify on SAS EuroBonus."
        return Offer(
            origin=item.get("origin", ""),
            destination=item.get("destination", ""),
            departure_date=item.get("departureDate"),
            cabin=item.get("cabin", ""),
            source_program=program,
            status=status,
            seats_available=seats,
            airline=item.get("airline"),
            points_cost=item.get("pointsCost"),
            taxes=item.get("taxes"),
            booking_url=DEFAULT_BOOKING_URL,
            notes=notes,
            metadata=metadata,
        )

    def _should_fallback_to_partners(self, offers: List[Offer], params: SearchParams) -> bool:
        if not params.fallback_enabled:
            return False
        if not offers:
            return True
        eurobonus_offers = [o for o in offers if o.status == OfferStatus.VERIFY_ON_SAS]
        return len(eurobonus_offers) == len(offers)

    def _derive_status(self, seats: Optional[int], partner_signal: bool) -> str:
        if partner_signal:
            return OfferStatus.PARTNER_SIGNAL_ONLY
        if seats is None:
            return OfferStatus.VERIFY_ON_SAS
        if seats >= 2:
            return OfferStatus.EUROBONUS_CONFIRMED
        return OfferStatus.NOT_AVAILABLE

    def _default_partner_sources(self) -> List[str]:
        env_value = os.getenv("PARTNER_SOURCES", "")
        if env_value:
            return [item.strip() for item in env_value.split(",") if item.strip()]
        return ["flyingblue", "delta", "virgin"]
