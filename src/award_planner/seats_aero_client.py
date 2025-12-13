from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import httpx

from .models import AvailabilityResponse, Itinerary, SearchParams

API_BASE_URL = "https://partner-api.seats.aero/v1"


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

    def bulk_availability(self, params: SearchParams) -> AvailabilityResponse:
        payload = self._build_bulk_payload(params)
        response_data = self._post_with_retries("availability/bulk", payload)
        itineraries = [self._parse_itinerary(item) for item in response_data.get("data", [])]
        return AvailabilityResponse(search_params=params, itineraries=itineraries)

    def live_search(self, params: SearchParams) -> AvailabilityResponse:
        payload = self._build_bulk_payload(params)
        response_data = self._post_with_retries("availability/search", payload)
        itineraries = [self._parse_itinerary(item) for item in response_data.get("data", [])]
        return AvailabilityResponse(search_params=params, itineraries=itineraries)

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

    def _build_bulk_payload(self, params: SearchParams) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "origins": params.origins,
            "startDate": params.start_date.isoformat(),
            "endDate": params.end_date.isoformat(),
            "cabin": params.cabin,
            "passengers": params.passengers,
        }
        if params.destinations:
            payload["destinations"] = params.destinations
        if params.region:
            payload["region"] = params.region
        if params.max_points is not None:
            payload["maxPoints"] = params.max_points
        payload["program"] = params.program_source
        if params.companion_mode:
            payload["companionVoucher"] = True
        return payload

    def _parse_itinerary(self, item: Dict[str, Any]) -> Itinerary:
        metadata = {k: v for k, v in item.items() if k not in {
            "origin",
            "destination",
            "departureDate",
            "cabin",
            "seats",
            "airline",
            "program",
            "pointsCost",
            "taxes",
        }}
        return Itinerary(
            origin=item.get("origin", ""),
            destination=item.get("destination", ""),
            departure_date=item.get("departureDate"),
            cabin=item.get("cabin", ""),
            seats=item.get("seats", 0),
            airline=item.get("airline"),
            program=item.get("program"),
            points_cost=item.get("pointsCost"),
            taxes=item.get("taxes"),
            metadata=metadata,
        )
