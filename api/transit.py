"""Materialize OTP routes for every candidate in the explicitly allowed domain.

The same analysis deadline covers route discovery and solver execution. No partial
route domain is labelled exhaustive. Coordinates remain within the operator's OTP.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import itertools
import json
import time

import httpx

from api.domain import Scenario, TravelBand, TravelLeg
from api.routes import RouteQuery, _manifest, _otp_query, route_for_leg
from api.solver.time import WARSAW, clock_minutes, days_between, format_clock, fresh, local_minute, matches


def _manual_route(legs, origin, destination, target, backwards):
    choices = []
    for leg in legs:
        if (leg.origin, leg.destination) != (origin, destination):
            continue
        for band in leg.bands:
            if band.minutes is None:
                continue
            duration = band.minutes + leg.buffer_minutes + leg.handoff_minutes
            departure = target - duration if backwards else target
            dt = datetime.fromtimestamp(departure * 60, WARSAW)
            start, end = clock_minutes(band.start), clock_minutes(band.end)
            minute = dt.hour * 60 + dt.minute
            within = start <= minute < end if start < end else minute >= start or minute < end
            if within and matches(band, dt.date()) and fresh(leg.source, dt.date()):
                choices.append((departure, departure + duration))
    return (max(choices, key=lambda pair: pair[0]) if backwards else min(choices, key=lambda pair: pair[1])) if choices else None


def _candidate_chains(s):
    """Mirror the solver's public candidate domain, not its feasibility decisions."""
    resources_by_id = {resource.id: resource for resource in s.care_resources}
    for activity in s.activities:
        if activity.start is None:
            continue
        current = clock_minutes(activity.start)
        starts = [current]
        if activity.negotiable and activity.start_min is not None and activity.start_max is not None:
            starts = sorted(set(range(clock_minutes(activity.start_min), clock_minutes(activity.start_max) + 1, activity.step_minutes)) | {current})
        for day in days_between(s.start_date, s.end_date):
            if not matches(activity, day):
                continue
            touches_next = max(starts) + activity.duration_minutes > 1440
            needs = sorted([need for need in s.care_needs if matches(need, day) or touches_next and matches(need, day + timedelta(days=1))], key=lambda need: (need.visit_order, need.id))
            choices = []
            for need in needs:
                options = [(resource,) for resource in s.care_resources if (not need.resource_ids or resource.id in need.resource_ids)
                           and need.care_type in resource.care_types and (not resource.dependent_ids or need.dependent_id in resource.dependent_ids)
                           and (resource.confirmed or resource.negotiable)]
                for arrangement in getattr(need, "arrangements", []):
                    chain = tuple(resources_by_id[rid] for rid in arrangement.resource_ids if rid in resources_by_id)
                    if len(chain) == len(arrangement.resource_ids) and chain and all(need.care_type in resource.care_types
                            and (not resource.dependent_ids or need.dependent_id in resource.dependent_ids)
                            and (resource.confirmed or resource.negotiable) for resource in chain):
                        options.append(chain)
                choices.append(options)
            for start_clock in starts:
                for selection in itertools.product(*choices) if needs else [()]:
                    first, last = [], []
                    for chain in selection:
                        if chain[0].location not in first:
                            first.append(chain[0].location)
                        if chain[-1].location not in last:
                            last.append(chain[-1].location)
                    start = local_minute(day, format_clock(start_clock), activity.start_fold)
                    yield ([s.home_location, *first, activity.location], [activity.location, *reversed(last), s.home_location], start, start + activity.duration_minutes)


async def hydrate_scenario_routes(scenario: Scenario | dict, budget_seconds: float = 20, *, client: httpx.AsyncClient | None = None, manifest: dict | None = None) -> dict:
    started = time.monotonic()
    s = Scenario.model_validate(scenario) if isinstance(scenario, dict) else scenario.model_copy(deep=True)
    legs = [leg for leg in s.travel_legs if leg.mode in {"walk", "transit"} and leg.origin in s.location_coordinates and leg.destination in s.location_coordinates]
    if not legs:
        return {"scenario": s.model_dump(mode="json"), "complete": True, "elapsed_ms": 0, "queries": 0, "issues": [], "active": False}
    by_direction = {}
    original_bands = {}
    for leg in legs:
        by_direction.setdefault((leg.origin, leg.destination), []).append(leg)
        original_bands[leg.id] = leg.bands[:]
        leg.bands = []  # Previous calculations must never silently survive a shift.
    cache = {}
    pending = {}
    issues = []
    completed = 0
    snapshot = manifest if manifest is not None else _manifest()
    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=httpx.Timeout(min(10, max(.1, budget_seconds))), follow_redirects=False)
    semaphore = asyncio.Semaphore(8)

    async def resolve_one(leg, target, backwards):
        nonlocal completed
        key = (leg.id, target, backwards)
        if key in cache:
            return cache[key]
        if key in pending:
            return await pending[key]
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        pending[key] = future
        try:
            async with semaphore:
                query = RouteQuery(id=leg.id, origin=leg.origin, destination=leg.destination,
                    when=datetime.fromtimestamp(target * 60, WARSAW), arrive_by=backwards, mode=leg.mode,
                    from_point=s.location_coordinates[leg.origin].model_dump(), to_point=s.location_coordinates[leg.destination].model_dump(),
                    handoff_minutes=leg.handoff_minutes, buffer_minutes=leg.buffer_minutes,
                    access_minutes=leg.access_minutes,
                    cost_grosze=None)
                result = await _otp_query(query, client, snapshot)
                completed += 1
                if result["status"] == "ok":
                    new = TravelLeg.model_validate(result["leg"])
                    for band in new.bands:
                        departure = target - result["total_minutes"] if backwards else target
                        when = datetime.fromtimestamp(departure * 60, WARSAW)
                        minute = when.hour * 60 + when.minute
                        def fare_applies(item):
                            first, last = clock_minutes(item.start), clock_minutes(item.end)
                            in_time = first <= minute < last if last > first else minute >= first or minute < last
                            return matches(item, when.date()) and in_time
                        costs = {item.cost_grosze for item in original_bands[leg.id] if fare_applies(item)}
                        if len(costs) == 1:
                            band.cost_grosze = next(iter(costs))
                        if not any(b.model_dump() == band.model_dump() for b in leg.bands):
                            leg.bands.append(band)
                    leg.source = new.source
                    # An explicitly supplied fare remains personal input. OTP
                    # doesn't infer net income, ticket entitlements or free travel.
                    returned = (target - result["total_minutes"], target) if backwards else (target, target + result["total_minutes"])
                else:
                    issues.append({"code": "route_" + result["status"], "origin": leg.origin, "destination": leg.destination,
                                   "when": query.when.isoformat(), "message": result.get("reason", "Trasa wymaga sprawdzenia")})
                    returned = None
                cache[key] = returned
                future.set_result(returned)
                return returned
        except BaseException:
            if not future.done():
                future.cancel()
            raise
        finally:
            pending.pop(key, None)

    async def resolve(origin, destination, target, backwards):
        if origin == destination:
            return target, target
        candidates = by_direction.get((origin, destination))
        if candidates:
            results = await asyncio.gather(*(resolve_one(leg, target, backwards) for leg in candidates))
            results = [result for result in results if result]
            return (max(results, key=lambda pair: pair[0]) if backwards else min(results, key=lambda pair: pair[1])) if results else None
        return _manual_route(s.travel_legs, origin, destination, target, backwards)

    async def chain(outward, returning, start, end):
        cursor = start
        for origin, destination in reversed(list(zip(outward, outward[1:]))):
            result = await resolve(origin, destination, cursor, True)
            if result is None:
                break
            cursor = result[0]
        cursor = end
        for origin, destination in zip(returning, returning[1:]):
            result = await resolve(origin, destination, cursor, False)
            if result is None:
                break
            cursor = result[1]

    async def work():
        queue = asyncio.Queue(maxsize=64)
        async def produce():
            count = 0
            for candidate in _candidate_chains(s):
                count += 1
                if count > 60_000:
                    raise TimeoutError("Domena przekracza limit normalizacji")
                await queue.put(candidate)
            for _ in range(12):
                await queue.put(None)
        async def consume():
            while (candidate := await queue.get()) is not None:
                await chain(*candidate)
        tasks = [asyncio.create_task(produce()), *(asyncio.create_task(consume()) for _ in range(12))]
        try:
            await asyncio.gather(*tasks)
            # Independently performed care handoffs also need their own route.
            for need in s.care_needs:
                for arrangement in getattr(need, "arrangements", []):
                    for handoff in arrangement.handoffs:
                        leg = next((item for item in legs if item.id == handoff.leg_id), None)
                        if leg:
                            for day in days_between(s.start_date, s.end_date):
                                if matches(need, day):
                                    await resolve_one(leg, local_minute(day, handoff.at), False)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    complete = True
    try:
        await asyncio.wait_for(work(), timeout=max(.01, budget_seconds))
    except (asyncio.TimeoutError, TimeoutError):
        complete = False
        issues.append({"code": "routing_budget", "message": "Nie sprawdzono wszystkich tras w limicie analizy. Wynik pozostaje nierozstrzygnięty."})
    except (ValueError, KeyError) as exc:
        complete = False
        issues.append({"code": "routing_input", "message": str(exc)})
    finally:
        if owns_client:
            await client.aclose()
    if any(issue["code"] in {"route_unavailable", "route_stale"} for issue in issues):
        complete = False
    return {"scenario": s.model_dump(mode="json"), "complete": complete, "elapsed_ms": round((time.monotonic() - started) * 1000),
            "queries": completed, "issues": issues, "active": True}
