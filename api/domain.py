"""Public, versioned contracts. Money is PLN grosze, durations are integer minutes."""
from __future__ import annotations

from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Source(Model):
    label: str = "deklaracja użytkowniczki"
    url: str | None = None
    checked_at: date | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    status: Literal["current", "stale", "unknown"] = "current"


class CalendarRule(Model):
    weekdays: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])
    dates: list[date] = Field(default_factory=list)
    excluded_dates: list[date] = Field(default_factory=list)
    valid_from: date | None = None
    valid_to: date | None = None

    @model_validator(mode="after")
    def validate_days(self):
        if any(x < 0 or x > 6 for x in self.weekdays):
            raise ValueError("weekdays: poniedziałek=0, niedziela=6")
        return self


class Availability(CalendarRule):
    start: str | None = "07:00"
    end: str | None = "17:00"
    start_fold: int | None = Field(None, ge=0, le=1)
    end_fold: int | None = Field(None, ge=0, le=1)


class Activity(CalendarRule):
    id: str
    label: str
    kind: Literal["work", "course", "obligation"] = "work"
    location: str = "work"
    start: str | None = "09:00"
    start_fold: int | None = Field(None, ge=0, le=1)
    duration_minutes: int = Field(480, gt=0, le=1440)
    paid_minutes: int = Field(480, ge=0, le=1440)
    negotiable: bool = False
    start_min: str | None = None
    start_max: str | None = None
    step_minutes: int = Field(15, ge=1, le=120)
    agreement_id: str | None = None
    required: bool = True
    offer_group: str | None = None
    requires_activity_ids: list[str] = Field(default_factory=list)
    cost_grosze: int | None = Field(0, ge=0)
    cost_frequency: Literal["once", "occurrence"] = "once"
    source: Source = Field(default_factory=Source)

    @model_validator(mode="after")
    def validate_activity(self):
        if self.paid_minutes > self.duration_minutes:
            raise ValueError("Czas płatny nie może przekraczać obecności")
        return self


class CareHandoff(Model):
    at: str
    at_fold: int | None = Field(None, ge=0, le=1)
    by_resource_id: str
    leg_id: str | None = None
    confirmed: bool = False
    valid_to: date | None = None
    source: Source = Field(default_factory=Source)


class CareArrangement(Model):
    id: str
    resource_ids: list[str]
    handoffs: list[CareHandoff] = Field(default_factory=list)
    unavailable: list[CalendarRule] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_chain(self):
        if not self.resource_ids or len(self.handoffs) != len(self.resource_ids) - 1:
            raise ValueError("Łańcuch opieki wymaga jednego przekazania między każdą parą zasobów")
        return self


class CareNeed(CalendarRule):
    id: str
    dependent_id: str
    label: str
    care_type: str = "child"
    start: str | None = "00:00"
    end: str | None = "24:00"
    start_fold: int | None = Field(None, ge=0, le=1)
    end_fold: int | None = Field(None, ge=0, le=1)
    allow_self_care: bool = True
    resource_ids: list[str] = Field(default_factory=list)
    visit_order: int = 0
    arrangements: list[CareArrangement] = Field(default_factory=list)


class CareResource(Model):
    id: str
    label: str
    location: str
    kind: Literal["facility", "caregiver", "service"] = "facility"
    capacity: int = Field(1, ge=1, le=100)
    dependent_ids: list[str] = Field(default_factory=list)
    care_types: list[str] = Field(default_factory=lambda: ["child"])
    availability: list[Availability] = Field(default_factory=lambda: [Availability()])
    busy: list[Availability] = Field(default_factory=list)
    confirmed: bool = False
    negotiable: bool = True
    confirmation_valid_to: date | None = None
    daily_cost_grosze: int | None = Field(0, ge=0)
    hourly_cost_grosze: int | None = Field(0, ge=0)
    one_time_cost_grosze: int | None = Field(0, ge=0)
    source: Source = Field(default_factory=Source)


class TravelBand(CalendarRule):
    start: str = "00:00"
    end: str = "24:00"
    minutes: int | None = Field(None, ge=0, le=720)
    cost_grosze: int | None = Field(0, ge=0)


class TravelLeg(Model):
    id: str
    origin: str
    destination: str
    mode: Literal["manual", "walk", "transit", "bike", "car"] = "manual"
    bands: list[TravelBand]
    handoff_minutes: int = Field(0, ge=0, le=120)
    buffer_minutes: int = Field(0, ge=0, le=120)
    access_minutes: int = Field(0, ge=0, le=180)
    source: Source = Field(default_factory=Source)


class ForbiddenProposal(Model):
    activity_id: str
    start: str
    valid_from: date | None = None
    valid_to: date | None = None
    reason: str = "Odmowa zmiany godzin"


class Coordinate(Model):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class Scenario(Model):
    schema_version: Literal[1] = 1
    title: str = "Mój plan"
    version: int = Field(1, ge=1)
    data_mode: Literal["synthetic", "personal"] = "personal"
    start_date: date
    end_date: date
    timezone: Literal["Europe/Warsaw"] = "Europe/Warsaw"
    home_location: str = "home"
    location_coordinates: dict[str, Coordinate] = Field(default_factory=dict)
    self_care_capacity: int = Field(1, ge=0, le=20)
    activities: list[Activity]
    care_needs: list[CareNeed] = Field(default_factory=list)
    care_resources: list[CareResource] = Field(default_factory=list)
    travel_legs: list[TravelLeg] = Field(default_factory=list)
    budget_grosze: int | None = Field(None, ge=0)
    minimum_paid_minutes: int = Field(0, ge=0)
    minimum_rest_minutes: int = Field(660, ge=0, le=1440)
    preferred_extra_buffer_minutes: int = Field(15, ge=0, le=240)
    objective_order: list[Literal["changed_agreements", "shift_minutes", "cost_grosze"]] = Field(
        default_factory=lambda: ["changed_agreements", "shift_minutes", "cost_grosze"])
    notes: str = ""
    forbidden_proposals: list[ForbiddenProposal] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_scenario(self):
        if self.end_date < self.start_date:
            raise ValueError("Koniec okresu poprzedza początek")
        if (self.end_date - self.start_date).days > 730:
            raise ValueError("Jedna analiza obejmuje najwyżej 731 dni; podziel dłuższy okres")
        for collection in [self.activities, self.care_needs, self.care_resources, self.travel_legs]:
            ids = [x.id for x in collection]
            if len(ids) != len(set(ids)):
                raise ValueError("Identyfikatory muszą być unikalne w kolekcji")
        if len(self.objective_order) != 3 or set(self.objective_order) != {"changed_agreements", "shift_minutes", "cost_grosze"}:
            raise ValueError("Priorytety muszą zawierać każdy z trzech celów dokładnie raz")
        for need in self.care_needs:
            ids = [arrangement.id for arrangement in need.arrangements]
            if len(ids) != len(set(ids)):
                raise ValueError("Identyfikatory łańcuchów opieki muszą być unikalne dla potrzeby")
        return self
