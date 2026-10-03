import asyncio
from datetime import datetime
import json
import httpx
import pytest
from pydantic import ValidationError
from api.routes import RoutesRequest, get_routes, route_for_leg


def leg():
    return {"id": "out", "origin": "care", "destination": "work", "mode": "manual", "bands": [
        {"start": "07:00", "end": "08:00", "minutes": 20, "cost_grosze": 500},
        {"start": "08:00", "end": "09:00", "minutes": 40, "cost_grosze": 500}],
        "handoff_minutes": 5, "buffer_minutes": 10, "source": {"valid_to": "2026-10-30"}}


def query(mode="manual"):
    return {"id": "trip", "origin": "care", "destination": "work", "when": "2026-10-05T08:00:00+02:00", "mode": mode,
            **({"manual_leg": leg()} if mode == "manual" else {"from_point": {"lat": 50.06, "lon": 19.94}, "to_point": {"lat": 50.07, "lon": 19.96}})}


def run(q, handler=None, manifest=None):
    async def call():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler or (lambda _: httpx.Response(500)))) as client:
            return await get_routes({"queries": [q]}, client=client, manifest=manifest)
    return asyncio.run(call())["routes"][0]


def test_manual_recalculates_shift_and_keeps_buffer_separate():
    assert route_for_leg(leg(), datetime.fromisoformat("2026-10-05T07:45:00+02:00"))["total_minutes"] == 35
    assert route_for_leg(leg(), datetime.fromisoformat("2026-10-05T08:15:00+02:00"))["total_minutes"] == 55
    assert route_for_leg(leg(), datetime.fromisoformat("2026-10-05T09:15:00+02:00"))["status"] == "needs_input"


def test_direction_cannot_be_reused():
    q = query()
    q["origin"], q["destination"] = "work", "care"
    assert run(q)["status"] == "needs_input"


def test_manual_stale_and_excluded_day():
    assert route_for_leg(leg(), datetime.fromisoformat("2026-11-02T08:15:00+01:00"))["status"] == "stale"
    assert route_for_leg(leg(), datetime.fromisoformat("2026-10-04T08:15:00+02:00"))["status"] == "needs_input"


def test_manual_arrive_by_checks_departure_band():
    q = query()
    q["arrive_by"] = True
    q["when"] = "2026-10-05T08:15:00+02:00"
    result = run(q)
    assert result["departure"] == "2026-10-05T07:40:00+02:00"
    assert result["minutes"] == 20


def test_manual_overnight_band_matches_solver_departure_day_semantics():
    data = leg()
    data["bands"] = [{"start": "22:00", "end": "04:00", "minutes": 20, "cost_grosze": 500}]
    assert route_for_leg(data, datetime.fromisoformat("2026-10-05T23:00:00+02:00"))["status"] == "ok"
    assert route_for_leg(data, datetime.fromisoformat("2026-10-06T02:00:00+02:00"))["status"] == "ok"
    assert route_for_leg(data, datetime.fromisoformat("2026-10-05T12:00:00+02:00"))["status"] == "needs_input"


def test_timezone_required_and_imaginary_time_rejected():
    for value in ["2026-10-05T08:00:00", "2026-03-29T02:30:00+01:00"]:
        q = query()
        q["when"] = value
        with pytest.raises(ValidationError):
            RoutesRequest(queries=[q])


FEED = {"valid_from": "2026-10-01", "valid_to": "2026-10-31", "otp_version": "2.7.0"}


def test_otp_expired_does_not_call_network():
    q = query("transit")
    q["when"] = "2026-11-02T08:00:00+01:00"
    def handler(_):
        raise AssertionError("expired feed must not be queried")
    assert run(q, handler, FEED)["status"] == "stale"


def test_otp_request_contains_exact_time_and_returns_exact_band():
    q = query("transit")
    base = datetime.fromisoformat(q["when"]).timestamp() * 1000
    def handler(request):
        text = json.loads(request.content)["query"]
        assert 'time: "08:00:00"' in text
        assert "mode: TRANSIT" in text
        return httpx.Response(200, json={"data": {"plan": {"itineraries": [
            {"startTime": base + 5 * 60000, "endTime": base + 25 * 60000, "duration": 1200, "legs": [{"mode": "BUS"}]}]}}})
    result = run(q, handler, FEED)
    assert result["minutes"] == 25  # Includes initial wait, not only itinerary duration.
    assert result["leg"]["bands"][0]["start"] == "08:00"
    assert result["leg"]["bands"][0]["end"] == "08:01"
    assert result["cost_grosze"] is None


def test_otp_arrive_by_reserves_handoff_and_buffer_before_routing():
    q = query("transit")
    q.update(arrive_by=True, handoff_minutes=5, buffer_minutes=10, access_minutes=4)
    requested = datetime.fromisoformat(q["when"]).timestamp() * 1000
    def handler(request):
        text = json.loads(request.content)["query"]
        assert 'time: "07:45:00"' in text
        assert 'arriveBy: true' in text
        return httpx.Response(200, json={"data": {"plan": {"itineraries": [
            {"startTime": requested - 35 * 60000, "endTime": requested - 15 * 60000, "legs": [{"mode": "BUS"}]}]}}})
    result = run(q, handler, FEED)
    assert result["minutes"] == 24
    assert result["total_minutes"] == 39
    assert result["departure"] == "2026-10-05T07:21:00+02:00"
    assert result["leg"]["bands"][0]["start"] == "07:21"
    assert result["leg"]["access_minutes"] == 4


@pytest.mark.parametrize("response,status", [(httpx.Response(200, json={"data": {"plan": {"itineraries": []}}}), "no_route"),
                                             (httpx.Response(503), "unavailable"),
                                             (httpx.Response(200, json={"errors": [{"message": "bad"}]}), "unavailable")])
def test_otp_no_route_and_failure_never_fabricate_manual_minutes(response, status):
    result = run(query("transit"), lambda _: response, FEED)
    assert result["status"] == status
    assert result["minutes"] is None
