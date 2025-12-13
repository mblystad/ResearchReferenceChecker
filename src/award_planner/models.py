from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, root_validator, validator


class OfferStatus:
    EUROBONUS_CONFIRMED = "EUROBONUS_CONFIRMED"
    VERIFY_ON_SAS = "VERIFY_ON_SAS"
    PARTNER_SIGNAL_ONLY = "PARTNER_SIGNAL_ONLY"
    NOT_AVAILABLE = "NOT_AVAILABLE"


class SearchParams(BaseModel):
    origin: str = Field(..., description="IATA origin code")
    destination: Optional[str] = Field(None, description="IATA destination or region code")
    region: Optional[str] = Field(None, description="Region search target")
    start_date: date
    end_date: date
    cabin: str
    passengers: int = Field(2, const=True)
    nonstop_only: bool = False
    sas_only: bool = False
    fallback_enabled: bool = True
    companion_mode: bool = True

    @validator("origin", "destination")
    def uppercase_codes(cls, value: Optional[str]) -> Optional[str]:
        return value.upper() if value else value

    @validator("end_date")
    def ensure_range(cls, end_date: date, values: Dict[str, Any]) -> date:
        start_date = values.get("start_date")
        if start_date and end_date < start_date:
            raise ValueError("end_date must be after start_date")
        return end_date

    def normalized(self) -> str:
        return json.dumps(self.dict(), default=str, sort_keys=True)

    @root_validator
    def require_destination_or_region(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        if not values.get("destination") and not values.get("region"):
            raise ValueError("Provide a destination or region")
        return values


class Offer(BaseModel):
    origin: str
    destination: str
    departure_date: date
    cabin: str
    source_program: str
    status: str
    seats_available: Optional[int] = None
    points_cost: Optional[int] = None
    taxes: Optional[float] = None
    airline: Optional[str] = None
    booking_url: Optional[str] = None
    notes: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def key(self) -> str:
        cost_part = self.points_cost if self.points_cost is not None else "NA"
        seats_part = self.seats_available if self.seats_available is not None else "NA"
        return (
            f"{self.origin}-{self.destination}-{self.departure_date}-{self.cabin}-"
            f"{self.source_program}-{self.status}-{cost_part}-{seats_part}"
        )


class AvailabilityResponse(BaseModel):
    search_params: SearchParams
    offers: List[Offer] = Field(default_factory=list)
    fetched_at: datetime = Field(default_factory=datetime.utcnow)

    def as_dataframe_records(self) -> List[Dict[str, Any]]:
        return [
            {
                "origin": it.origin,
                "destination": it.destination,
                "departure_date": it.departure_date,
                "cabin": it.cabin,
                "status": it.status,
                "seats_available": it.seats_available,
                "source_program": it.source_program,
                "points_cost": it.points_cost,
                "taxes": it.taxes,
            }
            for it in self.offers
        ]

    def digest(self) -> str:
        payload = json.dumps([it.key() for it in self.offers], sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()


class SavedSearch(BaseModel):
    id: int
    name: str
    params: SearchParams
    created_at: datetime


class SearchRun(BaseModel):
    id: int
    saved_search_id: int
    run_at: datetime
    response_hash: str
    response_json: str
