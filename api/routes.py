"""Time-dependent, directional transport. No fallback between transport modes.

OTP is private infrastructure. Coordinates and schedules are never sent to LLMs.
Only exact queried minutes become solver bands; shifts outside those bands require
another route query. A feed snapshot is mandatory for transit and walking alike.
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
import json
import math
import os
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

from api.domain import TravelLeg
from api.calendar_clock import warsaw_today

WARSAW = ZoneInfo("Europe/Warsaw")
MANIFEST = Path(__file__).resolve().parents[1] / "infra" / "otp" / "manifest.json"


class Point(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class RouteQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(default="route", max_length=100)
    origin: str = Field(max_length=150)
    destination: str = Field(max_length=150)
    when: datetime
    arrive_by: bool = False
    mode: Literal["manual", "walk", "transit"] = "manual"
    from_point: Point | None = None
    to_point: Point | None = None
    manual_leg: TravelLeg | None = None
    handoff_minutes: int = Field(0, ge=0, le=120)
    buffer_minutes: int = Field(0, ge=0, le=120)
    access_minutes: int = Field(0, ge=0, le=180)
    cost_grosze: int | None = Field(None, ge=0)

    @model_validator(mode="after")
    def explicit_timezone(self):
        if self.when.tzinfo is None:
            raise ValueError("Podaj godzinę ze strefą Europe/Warsaw lub offsetem UTC")
        local = self.when.astimezone(WARSAW)
        # Offset timestamps resolve repeated DST hours; reject imaginary local times.
        if self.when.utcoffset() not in {local.utcoffset(), timedelta(0)}:
            raise ValueError("Podana strefa nie odpowiada Europe/Warsaw")
        if self.mode == "manual" and self.manual_leg is None:
            raise ValueError("Ręczna trasa wymaga czasu, kierunku i okresu ważności")
        if self.mode != "manual" and (self.from_point is None or self.to_point is None):
            raise ValueError("Trasa obliczana wymaga dwóch punktów")
        return self


class RoutesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    queries: list[RouteQuery] = Field(min_length=1, max_length=100)


def _minute(value: str) -> int:
    hour, minute = map(int, value.split(":"))
    if minute > 59 or hour > 24 or hour < 0 or minute < 0 or (hour == 24 and minute):
        raise ValueError("Niepoprawna godzina")
    return hour * 60 + minute


def _active(rule, day: date) -> bool:
    if rule.valid_from and day < rule.valid_from or rule.valid_to and day > rule.valid_to:
        return False
    if day in rule.excluded_dates:
        return False
    return day in rule.dates or (not rule.dates and day.weekday() in rule.weekdays)


def route_for_leg(leg: TravelLeg | dict, departure: datetime) -> dict:
    """Resolve manual or previously calculated exact bands at a departure instant."""
    leg = TravelLeg.model_validate(leg) if isinstance(leg, dict) else leg
    if departure.tzinfo is None:
        raise ValueError("Departure requires an explicit UTC offset")
    local = departure.astimezone(WARSAW)
    source = leg.source
    if source.status != "current" or (source.valid_from and local.date() < source.valid_from) or (source.valid_to and local.date() > source.valid_to):
        return {"status": "stale", "minutes": None, "reason": "Źródło trasy wymaga ponownego sprawdzenia"}
    def in_band(band):
        first, last = _minute(band.start), _minute(band.end)
        minute = local.hour * 60 + local.minute
        return first <= minute < last if last > first else minute >= first or minute < last
    matches = [band for band in leg.bands if _active(band, local.date()) and in_band(band)]
    if not matches or any(band.minutes is None for band in matches):
        return {"status": "needs_input", "minutes": None, "reason": "Nowa godzina jest poza potwierdzonym zakresem trasy"}
    if len({(band.minutes, band.cost_grosze) for band in matches}) > 1:
        return {"status": "needs_input", "minutes": None, "reason": "Nakładające się zakresy mają różne czasy lub ceny"}
    band = matches[0]
    return {"status": "ok", "minutes": band.minutes, "total_minutes": band.minutes + leg.handoff_minutes + leg.buffer_minutes,
            "cost_grosze": band.cost_grosze, "source": source.model_dump(mode="json"), "leg": leg.model_dump(mode="json")}


def _manifest() -> dict | None:
    path = Path(os.getenv("OTP_MANIFEST_PATH", str(MANIFEST)))
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def otp_readiness() -> dict:
    data = _manifest()
    if data is None:
        return {"status": "unconfigured", "reason": "Brak przypiętej migawki GTFS/OSM"}
    return {"status": "configured", "valid_from": data["valid_from"], "valid_to": data["valid_to"],
            "otp_version": data["otp_version"], "graph_verified": bool(data.get("graph_sha256"))}


async def _otp_query(query: RouteQuery, client: httpx.AsyncClient, manifest: dict | None) -> dict:
    local = query.when.astimezone(WARSAW)
    common = {"id": query.id, "origin": query.origin, "destination": query.destination, "when": local.isoformat(), "mode": query.mode}
    if manifest is None:
        return {**common, "status": "unavailable", "reason": "Nie zbudowano lokalnego grafu transportowego", "minutes": None}
    if not manifest["valid_from"] <= local.date().isoformat() <= manifest["valid_to"]:
        return {**common, "status": "stale", "reason": "Rozkład nie obejmuje wybranego dnia. Podaj własny, potwierdzony czas.", "minutes": None,
                "valid_from": manifest["valid_from"], "valid_to": manifest["valid_to"]}
    # Pydantic validates coordinates before interpolation. No user text enters GraphQL.
    modes = "[{mode: WALK}, {mode: TRANSIT}]" if query.mode == "transit" else "[{mode: WALK}]"
    routing_time = local - timedelta(minutes=query.handoff_minutes + query.buffer_minutes) if query.arrive_by else local + timedelta(minutes=query.access_minutes)
    gql = """query { plan(from: {lat: %s, lon: %s}, to: {lat: %s, lon: %s}, date: "%s", time: "%s", arriveBy: %s, transportModes: %s, numItineraries: 3) {
      itineraries { startTime endTime duration walkTime waitingTime legs { mode startTime endTime } }
    } }""" % (query.from_point.lat, query.from_point.lon, query.to_point.lat, query.to_point.lon,
               routing_time.date().isoformat(), routing_time.strftime("%H:%M:%S"), "true" if query.arrive_by else "false", modes)
    try:
        response = await client.post(os.getenv("OTP_URL", "http://otp:8080") + "/otp/gtfs/v1", json={"query": gql})
        response.raise_for_status()
        body = response.json()
        if body.get("errors"):
            return {**common, "status": "unavailable", "reason": "Usługa tras nie mogła zweryfikować żądania", "minutes": None}
        itineraries = ((body.get("data") or {}).get("plan") or {}).get("itineraries") or []
    except (httpx.HTTPError, ValueError, TypeError):
        return {**common, "status": "unavailable", "reason": "Usługa tras jest niedostępna. Możesz podać własny czas.", "minutes": None}
    if not itineraries:
        return {**common, "status": "no_route", "reason": "Brak trasy dla tego kierunku, dnia i godziny", "minutes": None}
    valid = []
    requested_ms = routing_time.timestamp() * 1000
    for itinerary in itineraries:
        start_ms, end_ms = itinerary["startTime"], itinerary["endTime"]
        if query.arrive_by and end_ms > requested_ms or not query.arrive_by and start_ms < requested_ms:
            continue
        elapsed = requested_ms - start_ms if query.arrive_by else end_ms - requested_ms
        if elapsed < 0:
            continue
        valid.append((math.ceil(elapsed / 60_000), itinerary))
    if not valid:
        return {**common, "status": "no_route", "reason": "Zwrócone trasy nie mieszczą się w wymaganej godzinie", "minutes": None}
    minutes, itinerary = min(valid, key=lambda pair: pair[0])
    minutes += query.access_minutes
    depart = local - timedelta(minutes=minutes + query.handoff_minutes + query.buffer_minutes) if query.arrive_by else local
    start_minute = depart.hour * 60 + depart.minute
    end_minute = start_minute + 1
    hhmm = lambda value: f"{value // 60:02d}:{value % 60:02d}"
    source = {"label": "OpenTripPlanner 2.7.0; OSM i rozkład ZTP Kraków", "url": "https://gtfs.ztp.krakow.pl/",
              "checked_at": warsaw_today().isoformat(), "valid_from": manifest["valid_from"], "valid_to": manifest["valid_to"], "status": "current"}
    leg = {"id": query.id, "origin": query.origin, "destination": query.destination, "mode": query.mode,
           "bands": [{"weekdays": [], "dates": [depart.date().isoformat()], "start": hhmm(start_minute), "end": hhmm(end_minute),
                      "minutes": minutes, "cost_grosze": query.cost_grosze}],
           "handoff_minutes": query.handoff_minutes, "buffer_minutes": query.buffer_minutes,
           "access_minutes": query.access_minutes, "source": source}
    return {**common, "status": "ok", "minutes": minutes, "total_minutes": minutes + query.handoff_minutes + query.buffer_minutes,
            "cost_grosze": query.cost_grosze, "source": source, "leg": leg,
            "departure": depart.isoformat(), "arrival": datetime.fromtimestamp(itinerary["endTime"] / 1000, WARSAW).isoformat(),
            "modes": [part["mode"] for part in itinerary.get("legs", [])],
            "limitations": ["Rozkład planowy, bez gwarancji punktualności", "Sprawdzono konkretną minutę i kierunek; zmiana wymaga nowego zapytania"]}


async def get_routes(request: RoutesRequest | dict, *, client: httpx.AsyncClient | None = None, manifest: dict | None = None) -> dict:
    request = RoutesRequest.model_validate(request) if isinstance(request, dict) else request
    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=httpx.Timeout(10), follow_redirects=False)
    snapshot = manifest if manifest is not None else _manifest()
    semaphore = asyncio.Semaphore(4)

    async def execute(query):
        async with semaphore:
            if query.mode != "manual":
                return await _otp_query(query, client, snapshot)
            if query.manual_leg.origin != query.origin or query.manual_leg.destination != query.destination:
                return {"id": query.id, "status": "needs_input", "reason": "Deklaracja dotyczy innego kierunku", "minutes": None}
            if not query.arrive_by:
                result = route_for_leg(query.manual_leg, query.when)
            else:
                # Search backwards through the bounded duration domain. A departure
                # band applies at departure, never at the requested arrival minute.
                result = {"status": "needs_input", "minutes": None, "reason": "Brak potwierdzonego dojazdu na wymaganą godzinę"}
                for delta in range(0, 961):
                    departure = query.when - timedelta(minutes=delta)
                    candidate = route_for_leg(query.manual_leg, departure)
                    if candidate["status"] == "ok" and candidate["total_minutes"] <= delta:
                        result = {**candidate, "departure": departure.isoformat()}
                        break
            return {"id": query.id, "origin": query.origin, "destination": query.destination, "when": query.when.isoformat(), "mode": query.mode, **result}

    try:
        results = await asyncio.gather(*(execute(query) for query in request.queries))
    finally:
        if owns_client:
            await client.aclose()
    return {"routes": results, "all_resolved": all(x["status"] == "ok" for x in results), "timezone": "Europe/Warsaw"}
