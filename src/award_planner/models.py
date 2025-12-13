from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator


class SearchParams(BaseModel):
    origins: List[str] = Field(..., description="IATA origin codes")
    destinations: Optional[List[str]] = Field(None, description="IATA destination codes")
    region: Optional[str] = Field(None, description="Region search target")
    start_date: date
    end_date: date
    cabin: str
    passengers: int = Field(1, ge=1)
    max_points: Optional[int]
    program_source: str
    companion_mode: bool = False

    @validator("origins", "destinations", each_item=True)
    def uppercase_codes(cls, value: str) -> str:
        return value.upper()

    @validator("end_date")
    def ensure_range(cls, end_date: date, values: Dict[str, Any]) -> date:
        start_date = values.get("start_date")
        if start_date and end_date < start_date:
            raise ValueError("end_date must be after start_date")
        return end_date

    def normalized(self) -> str:
        return json.dumps(self.dict(), default=str, sort_keys=True)


class Itinerary(BaseModel):
    origin: str
    destination: str
    departure_date: date
    cabin: str
    seats: int
    airline: Optional[str] = None
    program: Optional[str] = None
    points_cost: Optional[int] = None
    taxes: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def key(self) -> str:
        cost_part = self.points_cost if self.points_cost is not None else "NA"
        return f"{self.origin}-{self.destination}-{self.departure_date}-{self.cabin}-{cost_part}-{self.program or 'NA'}"


class AvailabilityResponse(BaseModel):
    search_params: SearchParams
    itineraries: List[Itinerary] = Field(default_factory=list)
    fetched_at: datetime = Field(default_factory=datetime.utcnow)

    def as_dataframe_records(self) -> List[Dict[str, Any]]:
        return [
            {
                "origin": it.origin,
                "destination": it.destination,
                "departure_date": it.departure_date,
                "cabin": it.cabin,
                "seats": it.seats,
                "airline": it.airline,
                "program": it.program,
                "points_cost": it.points_cost,
                "taxes": it.taxes,
            }
            for it in self.itineraries
        ]

    def digest(self) -> str:
        payload = json.dumps([it.key() for it in self.itineraries], sort_keys=True)
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
