import asyncio
from datetime import datetime
import json
import httpx
from api.transit import hydrate_scenario_routes


def scenario():
    return {"start_date": "2026-10-05", "end_date": "2026-10-05", "activities": [{"id": "work", "label": "Praca", "start": "09:00", "duration_minutes": 480,
        "negotiable": True, "start_min": "08:00", "start_max": "09:00", "step_minutes": 30}],
        "care_needs": [], "care_resources": [],
        "location_coordinates": {"home": {"lat": 50.06, "lon": 19.94}, "work": {"lat": 50.07, "lon": 19.96}},
        "travel_legs": [{"id": "out", "origin": "home", "destination": "work", "mode": "transit", "bands": [{"minutes": 1, "cost_grosze": 600}]},
                        {"id": "back", "origin": "work", "destination": "home", "mode": "transit", "bands": [{"minutes": 1, "cost_grosze": 600}]}]}


def test_hydration_queries_all_candidate_starts_and_returns_exact_bands(monkeypatch):
    from api import transit
    calls = []
    async def fake_query(query, client, manifest):
        if query.id == "out":
            assert query.access_minutes == 4
        calls.append((query.id, query.when.hour, query.when.minute, query.arrive_by))
        duration = 20 if query.when.hour < 9 else 40
        departure = query.when.timestamp() / 60 - duration if query.arrive_by else query.when.timestamp() / 60
        local = datetime.fromtimestamp(departure * 60, query.when.tzinfo)
        minute = local.hour * 60 + local.minute
        return {"status": "ok", "total_minutes": duration, "leg": {"id": query.id, "origin": query.origin, "destination": query.destination,
            "mode": query.mode, "bands": [{"dates": [str(local.date())], "weekdays": [], "start": f"{minute//60:02}:{minute%60:02}",
            "end": f"{(minute+1)//60:02}:{(minute+1)%60:02}", "minutes": duration, "cost_grosze": None}], "source": {"label": "OTP", "valid_to": "2026-10-31"}}}
    monkeypatch.setattr(transit, "_otp_query", fake_query)
    data = scenario()
    data["travel_legs"][0]["access_minutes"] = 4
    result = asyncio.run(hydrate_scenario_routes(data, 5))
    assert result["complete"] and result["queries"] == 6
    assert ("out", 8, 0, True) in calls and ("out", 9, 0, True) in calls
    assert ("back", 16, 0, False) in calls and ("back", 17, 0, False) in calls
    assert all(len(leg["bands"]) == 3 for leg in result["scenario"]["travel_legs"])
    assert all(band["minutes"] != 1 and band["cost_grosze"] == 600 for leg in result["scenario"]["travel_legs"] for band in leg["bands"])


def test_hydration_timeout_never_claims_full_domain(monkeypatch):
    from api import transit
    async def stalled(*args):
        await asyncio.sleep(1)
    monkeypatch.setattr(transit, "_otp_query", stalled)
    result = asyncio.run(hydrate_scenario_routes(scenario(), .02))
    assert not result["complete"]
    assert any(issue["code"] == "routing_budget" for issue in result["issues"])


def test_no_transit_keeps_manual_independent():
    data = scenario()
    for leg in data["travel_legs"]:
        leg["mode"] = "manual"
    result = asyncio.run(hydrate_scenario_routes(data))
    assert result["complete"] and not result["active"] and result["queries"] == 0
