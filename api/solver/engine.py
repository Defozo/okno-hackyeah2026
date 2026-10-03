"""Finite-domain CP-SAT planner with staged objectives and independent validation.

All requested dates are expanded. The explicit start grid and entered directed
travel bands define the search domain; every result discloses that boundary.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import math
import os
import time
from collections import defaultdict
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta

from ortools.sat.python import cp_model
from pydantic import ValidationError

from api.domain import Scenario
from .time import WARSAW, clock_minutes, days_between, format_clock, fresh, iso, local_minute, matches, window

_INPUT_CACHE = ContextVar("solver_input_cache", default=None)
# Candidate alternatives already encode the finite choices. On this model,
# probing and symmetry discovery duplicate expensive presolve work; disabling
# these optional heuristics does not remove constraints or weaken proofs.
# Assumption-based diagnosis retains the default CP-SAT settings.
_OPTIMIZATION_CP_PARAMETERS = {"cp_model_probing_level": 0, "symmetry_level": 0}


@dataclass
class Candidate:
    index: int
    occurrence: str
    activity_id: str | None
    day: date
    clock: int
    shift: int
    start: int
    end: int
    away_start: int
    away_end: int
    events: list[dict] = field(default_factory=list)
    issues: list[dict] = field(default_factory=list)
    resources: tuple = ()
    slack: int = 100_000
    care_only: bool = False
    user_blocks: tuple = ()


def issue(code, message, **kw):
    return {"code": code, "message": message, **kw}


def _event(kind, start, end, **kw):
    return {"kind": kind, "start": iso(start), "end": iso(end), "start_minute": start,
            "end_minute": end, **kw}


def _travel(scenario, origin, destination, target, backwards=False, leg_id=None):
    if origin == destination:
        return target, target, None
    cache = _INPUT_CACHE.get()
    key = ("travel", id(scenario), origin, destination, target, backwards, leg_id)
    if cache is not None and key in cache:
        return cache[key][1]
    choices = []
    for leg in scenario.travel_legs:
        if leg_id is not None and leg.id != leg_id:
            continue
        if (leg.origin, leg.destination) != (origin, destination):
            continue
        for band in leg.bands:
            if band.minutes is None:
                continue
            duration = band.minutes + leg.handoff_minutes + leg.buffer_minutes
            departure = target - duration if backwards else target
            dt = datetime.fromtimestamp(departure * 60, WARSAW)
            tod = dt.hour * 60 + dt.minute
            first, last = clock_minutes(band.start), clock_minutes(band.end)
            in_time = first <= tod < last if last > first else (tod >= first or tod < last)
            if not in_time or not matches(band, dt.date()) or not fresh(leg.source, dt.date()):
                continue
            arrival = departure + duration
            event = _event("travel", departure, arrival, label=f"{origin} → {destination}",
                           leg_id=leg.id, origin=origin, destination=destination, mode=leg.mode,
                           travel_minutes=band.minutes, handoff_minutes=leg.handoff_minutes,
                           buffer_minutes=leg.buffer_minutes, cost_grosze=band.cost_grosze,
                           source=leg.source.model_dump(mode="json"))
            choices.append((departure, arrival, event))
    result = (max(choices, key=lambda x: x[0]) if backwards else min(choices, key=lambda x: x[1])) if choices else None
    if cache is not None and len(cache) < 100_000:
        # Retain the input object with the value to prevent id reuse. Caches are
        # request-scoped, including isolated copies used by disruption probes.
        cache[key] = (scenario, result)
    return result


def _resource_windows(resource, day, busy=False):
    cache = _INPUT_CACHE.get()
    key = ("windows", id(resource), day, busy)
    if cache is not None and key in cache:
        return cache[key][1]
    rules = resource.busy if busy else resource.availability
    result = []
    for d in (day - timedelta(days=1), day, day + timedelta(days=1)):
        for rule in rules:
            if matches(rule, d) and rule.start is not None and rule.end is not None:
                result.append(window(d, rule.start, rule.end, rule.start_fold, rule.end_fold))
    # Adjacent availability is continuous, including across midnight and DST.
    merged = []
    for a, b in sorted(result):
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
        else:
            merged.append((a, b))
    if cache is not None and len(cache) < 100_000:
        cache[key] = (resource, merged)
    return merged


def _care_segments(event):
    cursor, end = event["start_minute"], event["end_minute"]
    while cursor < end:
        day = datetime.fromtimestamp(cursor * 60, WARSAW).date()
        stop = min(end, local_minute(day + timedelta(days=1), "00:00"))
        yield str(day), {**event, "start_minute": cursor, "end_minute": stop}
        cursor = stop


def _need_window(need, day):
    return window(day, need.start, need.end, need.start_fold, need.end_fold)


def _confirmed(resource, last_day):
    return resource.confirmed and resource.confirmation_valid_to is not None and resource.confirmation_valid_to >= last_day


def _build_candidate(s, activity, day, start_clock, allocations, needs, index):
    resources = [r for chain, arrangement in allocations for r in chain]
    start = local_minute(day, format_clock(start_clock), activity.start_fold)
    end = start + activity.duration_minutes
    c = Candidate(index, f"{activity.id}:{day}", activity.id, day, start_clock,
                  abs(start_clock - clock_minutes(activity.start)), start, end, start, end,
                  resources=tuple(r.id for r in resources))
    c.events.append(_event(activity.kind, start, end, activity_id=activity.id, label=activity.label,
                           location=activity.location, paid_minutes=activity.paid_minutes,
                           date=str(day), baseline_start=activity.start))
    if not fresh(activity.source, day):
        c.issues.append(issue("stale_source", "Źródło godzin aktywności nie jest aktualne", field=f"activities.{activity.id}.source"))
    for refused in s.forbidden_proposals:
        if refused.activity_id == activity.id and clock_minutes(refused.start) == start_clock and (not refused.valid_from or day >= refused.valid_from) and (not refused.valid_to or day <= refused.valid_to):
            c.issues.append(issue("refused_proposal", refused.reason, activity_id=activity.id, date=str(day)))
    first_stops, last_stops = [], []
    for chain, arrangement in allocations:
        if not chain:
            continue
        if chain[0].location not in first_stops:
            first_stops.append(chain[0].location)
        if chain[-1].location not in last_stops:
            last_stops.append(chain[-1].location)
    outward = [s.home_location, *first_stops, activity.location]
    returning = [activity.location, *reversed(last_stops), s.home_location]
    departure_by_location, arrival_by_location = {}, {}
    cursor = start
    outbound = []
    for origin, destination in reversed(list(zip(outward, outward[1:]))):
        route = _travel(s, origin, destination, cursor, backwards=True)
        if route is None:
            c.issues.append(issue("missing_route", f"Brak aktualnej trasy {origin} → {destination} dla wybranej godziny", date=str(day), origin=origin, destination=destination))
            continue
        departure, arrival, event = route
        departure_by_location[origin] = departure
        cursor = departure
        if event:
            outbound.insert(0, {**event, "activity_id": activity.id, "date": str(day)})
    c.away_start = cursor
    c.events.extend(outbound)
    cursor = end
    for origin, destination in zip(returning, returning[1:]):
        route = _travel(s, origin, destination, cursor)
        if route is None:
            c.issues.append(issue("missing_route", f"Brak aktualnej trasy {origin} → {destination} dla wybranej godziny", date=str(day), origin=origin, destination=destination))
            continue
        departure, arrival, event = route
        arrival_by_location[destination] = arrival
        cursor = arrival
        if event:
            c.events.append({**event, "activity_id": activity.id, "date": str(day)})
    c.away_end = cursor
    c.user_blocks = ((c.away_start, c.away_end),)
    for need, (chain, arrangement) in zip(needs, allocations):
        if not chain:
            continue
        dropoff = departure_by_location.get(chain[0].location, c.away_start)
        pickup = arrival_by_location.get(chain[-1].location, c.away_end)
        need_windows = [_need_window(need, d) for d in (day - timedelta(days=1), day, day + timedelta(days=1)) if matches(need, d)]
        relevant = [(a, b) for a, b in need_windows if a < pickup and b > dropoff]
        if not relevant:
            continue
        # The child travels with the user before drop-off and after pickup.
        # Consecutive calendar-day needs remain covered during overnight work.
        ns, ne = min(a for a, _ in relevant), max(b for _, b in relevant)
        care_start, care_end = max(ns, dropoff), min(ne, pickup)
        if not need.allow_self_care:
            care_start, care_end = _need_window(need, day)
            if (care_start < dropoff and chain[0].location != s.home_location) or (care_end > pickup and chain[-1].location != s.home_location):
                c.issues.append(issue("care_delivery", "Opieka poza samodzielną dostępnością wymaga jawnego dowozu i odbioru", need_id=need.id, date=str(day)))
        if care_start >= care_end:
            continue
        _append_chain(s, c, need, chain, arrangement, care_start, care_end, day)
    if any(e.get("cost_grosze", 0) is None for e in c.events):
        c.issues.append(issue("unknown_cost", "Uzupełnij koszt przejazdu", date=str(day)))
    if activity.cost_grosze is None:
        c.issues.append(issue("unknown_cost", "Uzupełnij koszt aktywności", activity_id=activity.id))
    return c


def _append_chain(s, c, need, chain, arrangement, care_start, care_end, day):
    handoff_times = []
    if arrangement:
        for hindex, handoff in enumerate(arrangement.handoffs):
            hday = datetime.fromtimestamp(care_start * 60, WARSAW).date()
            ht = local_minute(hday, handoff.at, handoff.at_fold)
            if ht <= (handoff_times[-1] if handoff_times else care_start):
                hday += timedelta(days=1)
                ht = local_minute(hday, handoff.at, handoff.at_fold)
            handoff_times.append(ht)
            if any(matches(rule, hday) for rule in arrangement.unavailable):
                c.issues.append(issue("refused_arrangement", "Odmowa tego przekazania opieki w podanym okresie", need_id=need.id, arrangement_id=arrangement.id, date=str(hday)))
            previous, following = chain[hindex], chain[hindex + 1]
            if handoff.by_resource_id != following.id:
                c.issues.append(issue("handoff_actor", "Opiekun przejmujący musi jawnie realizować przekazanie", need_id=need.id))
            route = _travel(s, previous.location, following.location, ht, leg_id=handoff.leg_id)
            if previous.location != following.location and (handoff.leg_id is None or route is None):
                c.issues.append(issue("missing_route", "Brak trasy przekazania pomiędzy zasobami opieki", need_id=need.id, date=str(day)))
            elif route:
                _, arrival, event = route
                if arrival > care_end:
                    c.issues.append(issue("handoff_timing", "Przekazanie kończy się po planowanym odbiorze", need_id=need.id))
                if event:
                    c.events.append({**event, "kind": "care_transfer", "activity_id": c.activity_id,
                                     "date": str(day), "dependent_id": need.dependent_id, "need_id": need.id,
                                     "arrangement_id": arrangement.id, "handoff_index": hindex, "resource_id": following.id,
                                     "confirmed": handoff.confirmed, "confirmation_valid_to": str(handoff.valid_to) if handoff.valid_to else None})
            if not fresh(handoff.source, hday):
                c.issues.append(issue("stale_source", "Nieaktualne ustalenie przekazania", need_id=need.id))
        if sorted(handoff_times) != handoff_times or any(t <= care_start or t >= care_end for t in handoff_times):
            c.issues.append(issue("handoff_timing", "Przekazanie musi wypaść wewnątrz potrzebnego okresu opieki", need_id=need.id))
    boundaries = [care_start, *handoff_times, care_end]
    for event in c.events:
        if event["kind"] == "care_transfer" and event.get("need_id") == need.id and event["end_minute"] > boundaries[event["handoff_index"] + 2]:
            c.issues.append(issue("handoff_timing", "Kolejne przekazanie zaczyna się przed zakończeniem podróży", need_id=need.id))
    for pos, resource in enumerate(chain):
        _add_care_segment(s, c, resource, need, boundaries[pos], boundaries[pos + 1], day,
                          arrangement.id if arrangement else None)


def _add_care_segment(s, c, resource, need, care_start, care_end, day, arrangement_id=None):
        c.events.append(_event("care", care_start, care_end, label=resource.label,
                               activity_id=c.activity_id, need_id=need.id, dependent_id=need.dependent_id,
                               resource_id=resource.id, location=resource.location, date=str(day), arrangement_id=arrangement_id))
        windows = _resource_windows(resource, day)
        containing = [(a, b) for a, b in windows if a <= care_start and b >= care_end]
        if not containing:
            nearby = [(a, b) for a, b in windows if a < care_end and b > care_start]
            a, b = min(nearby, key=lambda w: max(0, w[0] - care_start) + max(0, care_end - w[1])) if nearby else (care_start, care_start)
            late = max(0, care_end - b)
            early = max(0, a - care_start)
            c.issues.append(issue("care_window", f"{resource.label}: odbiór {late} min po zamknięciu" if late else f"{resource.label}: przekazanie {early} min przed otwarciem", date=str(day), minutes=max(late, early), need_id=need.id, resource_id=resource.id, arrival=iso(care_end), closes=iso(b)))
        else:
            c.slack = min(c.slack, max(min(care_start - a, b - care_end) for a, b in containing))
        for a, b in _resource_windows(resource, day, busy=True):
            if a < care_end and care_start < b:
                c.issues.append(issue("caregiver_busy", f"{resource.label}: inne zobowiązanie w czasie opieki", date=str(day), resource_id=resource.id))
        used_days = list(days_between(datetime.fromtimestamp(care_start * 60, WARSAW).date(), datetime.fromtimestamp((care_end - 1) * 60, WARSAW).date()))
        if any(not fresh(resource.source, d) for d in used_days):
            c.issues.append(issue("stale_source", f"{resource.label}: dane wymagają aktualizacji", resource_id=resource.id))
        if any(x is None for x in (resource.daily_cost_grosze, resource.hourly_cost_grosze, resource.one_time_cost_grosze)):
            c.issues.append(issue("unknown_cost", f"{resource.label}: uzupełnij koszt opieki", resource_id=resource.id))


def _standalone_care(s, need, day, chain, arrangement, index):
    """A whole care booking with independent, timed drop-off and pickup tours."""
    start, end = _need_window(need, day)
    c = Candidate(index, f"care:{need.id}:{day}", None, day, 0, 0, start, end, start, end,
                  resources=tuple(r.id for r in chain), care_only=True)
    blocks = []
    for label, stop, target in (("dropoff", chain[0].location, start), ("pickup", chain[-1].location, end)):
        before = _travel(s, s.home_location, stop, target, backwards=True)
        after = _travel(s, stop, s.home_location, target)
        if before is None or after is None:
            c.issues.append(issue("missing_route", "Brak osobnego dowozu lub odbioru dla zlecenia opieki", need_id=need.id, date=str(day)))
            continue
        if before[0] < after[1]:
            blocks.append((before[0], after[1]))
        for route in (before, after):
            if route[2]:
                c.events.append({**route[2], "activity_id": None, "date": str(day), "need_id": need.id, "journey": label})
    c.user_blocks = tuple(blocks)
    if any(a < d and begin < b for pos, (a, b) in enumerate(blocks) for begin, d in blocks[pos + 1:]):
        c.issues.append(issue("care_tours_overlap", "Osobny powrót po dowozie koliduje z wyjazdem na odbiór", need_id=need.id, date=str(day)))
    c.away_start = min([start, *[a for a, b in blocks]])
    c.away_end = max([end, *[b for a, b in blocks]])
    _append_chain(s, c, need, chain, arrangement, start, end, day)
    for event in c.events:
        event["care_only"] = True
    if any(e.get("cost_grosze", 0) is None for e in c.events):
        c.issues.append(issue("unknown_cost", "Uzupełnij koszt dowozu i odbioru opieki", need_id=need.id))
    return c


def _normalize(s, deadline):
    candidates, gaps, occurrences = [], [], {}
    for resource in s.care_resources:
        if any(rule.start is None or rule.end is None for rule in [*resource.availability, *resource.busy]):
            gaps.append(issue("missing_time", f"Uzupełnij dostępność: {resource.label}", field=f"care_resources.{resource.id}.availability"))
    for need in s.care_needs:
        if need.start is None or need.end is None:
            gaps.append(issue("missing_time", f"Uzupełnij godziny opieki: {need.label}", field=f"care_needs.{need.id}"))
    # Independent bookings also cover days without work and needs for which the
    # user explicitly cannot provide care. Their user tours remain constraints.
    standalone_days = set()
    resources_by_id = {r.id: r for r in s.care_resources}
    for need in s.care_needs:
        if need.start is None or need.end is None:
            continue
        options = [((r,), None) for r in s.care_resources if (not need.resource_ids or r.id in need.resource_ids)
                   and need.care_type in r.care_types and (not r.dependent_ids or need.dependent_id in r.dependent_ids)
                   and (r.confirmed or r.negotiable)]
        for arrangement in need.arrangements:
            chain = tuple(resources_by_id[rid] for rid in arrangement.resource_ids if rid in resources_by_id)
            if len(chain) == len(arrangement.resource_ids) and all(need.care_type in r.care_types and (not r.dependent_ids or need.dependent_id in r.dependent_ids) and (r.confirmed or r.negotiable) for r in chain):
                options.append((chain, arrangement))
        for day in days_between(s.start_date, s.end_date):
            if not matches(need, day):
                continue
            for chain, arrangement in options:
                if time.monotonic() > deadline or len(candidates) >= 60_000:
                    raise TimeoutError("Przekroczono wspólny limit analizy podczas planowania opieki")
                c = _standalone_care(s, need, day, chain, arrangement, len(candidates))
                # These are optional bookings. Impossible whole-day options must
                # not pollute the diagnosis of the actual work-day itinerary.
                if any(p["code"] not in ("unknown_cost", "stale_source") for p in c.issues):
                    continue
                candidates.append(c)
                occurrences.setdefault(c.occurrence, []).append(c.index)
                standalone_days.add((need.id, day))
    for activity in s.activities:
        outside_dates = [d for d in activity.dates if d not in activity.excluded_dates and not s.start_date <= d <= s.end_date]
        if outside_dates:
            gaps.append(issue("horizon_incomplete", f"Obowiązkowe daty {activity.label} wykraczają poza sprawdzany okres", field=f"activities.{activity.id}.dates", dates=[str(d) for d in outside_dates]))
        if activity.start is None:
            gaps.append(issue("missing_time", f"Podaj początek: {activity.label}", field=f"activities.{activity.id}.start"))
            continue
        current = clock_minutes(activity.start)
        if current == 1440:
            gaps.append(issue("invalid_time", "Początek aktywności musi należeć do wskazanej daty; zamiast 24:00 użyj następnej daty i 00:00", field=f"activities.{activity.id}.start"))
            continue
        starts = [current]
        if activity.negotiable:
            if activity.start_min is None or activity.start_max is None:
                gaps.append(issue("missing_range", f"Podaj dopuszczalny zakres: {activity.label}", field=f"activities.{activity.id}.start_min"))
                continue
            low, high = clock_minutes(activity.start_min), clock_minutes(activity.start_max)
            if low > high or high == 1440:
                gaps.append(issue("invalid_range", "Początek zakresu przekracza koniec", field=f"activities.{activity.id}.start_min"))
                continue
            starts = sorted(set(range(low, high + 1, activity.step_minutes)) | {current})
        for day in days_between(s.start_date, s.end_date):
            if not matches(activity, day):
                continue
            if time.monotonic() > deadline:
                raise TimeoutError("Normalizacja przekroczyła wspólny limit analizy")
            key = f"{activity.id}:{day}"
            occurrences[key] = []
            nearby_days = (day - timedelta(days=1), day, day + timedelta(days=1))
            needs = sorted([n for n in s.care_needs if any(matches(n, d) for d in nearby_days)], key=lambda n: (n.visit_order, n.id))
            choices = []
            for need in needs:
                if need.start is None or need.end is None:
                    gaps.append(issue("missing_time", f"Uzupełnij godziny opieki: {need.label}", field=f"care_needs.{need.id}"))
                    continue
                resources = [r for r in s.care_resources if (not need.resource_ids or r.id in need.resource_ids)
                             and need.care_type in r.care_types and (not r.dependent_ids or need.dependent_id in r.dependent_ids)
                             and (r.confirmed or r.negotiable)]
                options = [((r,), None) for r in resources]
                by_id = {r.id: r for r in s.care_resources}
                for arrangement in need.arrangements:
                    chain = tuple(by_id[rid] for rid in arrangement.resource_ids if rid in by_id)
                    if len(chain) != len(arrangement.resource_ids):
                        gaps.append(issue("missing_resource", "Łańcuch opieki wskazuje nieznany zasób", need_id=need.id))
                        continue
                    if all(need.care_type in r.care_types and (not r.dependent_ids or need.dependent_id in r.dependent_ids) and (r.confirmed or r.negotiable) for r in chain):
                        options.append((chain, arrangement))
                choices.append(options)
            if len(choices) != len(needs):
                continue
            for start_clock in starts:
                begin = local_minute(day, format_clock(start_clock), activity.start_fold)
                end = begin + activity.duration_minutes
                relevant_choices = []
                for need, options in zip(needs, choices):
                    overlaps = any(a < end and begin < b for a, b in [_need_window(need, d) for d in nearby_days if matches(need, d)])
                    choices_for_time = list(options) if overlaps or not need.allow_self_care else [((), None)]
                    if overlaps and any((need.id, d) in standalone_days for d in nearby_days):
                        choices_for_time.append(((), None))
                    relevant_choices.append(choices_for_time)
                products = itertools.product(*relevant_choices) if needs else [()]
                for allocations in products:
                    if len(candidates) >= 60_000 or time.monotonic() > deadline:
                        raise TimeoutError("Domena przekracza limit pamięci lub wspólny czas analizy; wynik pozostaje nierozstrzygnięty")
                    c = _build_candidate(s, activity, day, start_clock, allocations, needs, len(candidates))
                    candidates.append(c)
                    occurrences[key].append(c.index)
    return candidates, gaps, occurrences


def _care_coverage_is_implied(s, candidates):
    """Certify when full-coverage equations follow from occurrence selection.

    Every required minute during an activity must already be covered inside
    each individual candidate; outside activities explicit self-care can cover
    all needs. The separate user timeline prevents combining overlapping tours.
    Independent bookings and limited self-care always use the general model.
    """
    if s.self_care_capacity < len(s.care_needs) or any(not n.allow_self_care for n in s.care_needs) or any(c.care_only for c in candidates):
        return False
    for c in candidates:
        for need in s.care_needs:
            bookings = sorted((e["start_minute"], e["end_minute"]) for e in c.events if e["kind"] == "care" and e["need_id"] == need.id)
            for day in (c.day - timedelta(days=1), c.day, c.day + timedelta(days=1)):
                if not matches(need, day):
                    continue
                first, last = _need_window(need, day)
                cursor, stop = max(first, c.start), min(last, c.end)
                for begin, end in bookings:
                    if begin <= cursor:
                        cursor = max(cursor, end)
                if cursor < stop:
                    return False
    return True


def _build_model(s, candidates, occurrences, baseline=False, extra_buffer=0, exclude=None, deadline=None):
    def check_budget():
        if deadline is not None and time.monotonic() >= deadline:
            raise TimeoutError("Budowa modelu przekroczyła wspólny limit analizy")

    check_budget()
    model = cp_model.CpModel()
    xs = [model.new_bool_var(f"candidate_{c.index}") for c in candidates]
    assumptions = {}

    def guard(name, message):
        if name not in assumptions:
            lit = model.new_bool_var(name)
            assumptions[name] = (lit, message)
            if baseline:
                model.add_assumption(lit)
            else:
                # Explanations use the separate satisfaction model. Fixing these
                # guards in optimization permits ordinary CP-SAT presolve.
                model.add(lit == 1)
        return assumptions[name][0]

    activities = {a.id: a for a in s.activities}
    resources = {r.id: r for r in s.care_resources}
    enabled = {a.id: model.new_bool_var(f"activity_{a.id}") for a in s.activities}
    offers = defaultdict(list)
    for a in s.activities:
        if a.offer_group:
            offers[a.offer_group].append(enabled[a.id])
        elif a.required:
            model.add(enabled[a.id] == 1).only_enforce_if(guard(f"activity:{a.id}", f"Wymagana aktywność: {a.label}"))
        for dep in a.requires_activity_ids:
            if dep not in enabled:
                model.add(enabled[a.id] == 0).only_enforce_if(guard(f"course:{a.id}:{dep}", f"Brak wymaganego kursu {dep}"))
            else:
                model.add(enabled[a.id] <= enabled[dep])
    for group, choices in offers.items():
        model.add(sum(choices) == 1).only_enforce_if(guard(f"offer:{group}", "Wybór jednej oferty z grupy"))
    for occurrence, indexes in occurrences.items():
        if indexes and candidates[indexes[0]].care_only:
            model.add(sum(xs[i] for i in indexes) <= 1)
            continue
        aid = occurrence.rsplit(":", 1)[0]
        model.add(sum(xs[i] for i in indexes) == enabled[aid]).only_enforce_if(guard(f"occurrence:{occurrence}", f"Pełna zmiana {activities[aid].label}, {occurrence[-10:]}"))
    grouped_shifts = defaultdict(lambda: defaultdict(list))
    for c in candidates:
        check_budget()
        a = activities.get(c.activity_id)
        if a:
            grouped_shifts[a.agreement_id or a.id][c.clock - clock_minutes(a.start)].append(xs[c.index])
        for problem in c.issues:
            name = f"{problem['code']}:{problem.get('resource_id', problem.get('activity_id', 'route'))}"
            model.add(xs[c.index] == 0).only_enforce_if(guard(name, problem["message"]))
        if extra_buffer and c.slack < extra_buffer:
            model.add(xs[c.index] == 0)
        if baseline and c.shift and a:
            model.add(xs[c.index] == 0).only_enforce_if(guard(f"baseline:{a.id}", f"Obecne godziny: {a.start}"))
        if baseline:
            for rid in set(c.resources):
                r = resources[rid]
                last_day = max((datetime.fromtimestamp((e["end_minute"] - 1) * 60, WARSAW).date() for e in c.events if e["kind"] == "care" and e["resource_id"] == rid), default=c.day)
                if not _confirmed(r, last_day):
                    model.add(xs[c.index] == 0).only_enforce_if(guard(f"confirmation:{rid}", f"Brak aktualnego potwierdzenia: {r.label}"))
            for event in c.events:
                if event["kind"] == "care" and event.get("arrangement_id"):
                    need = next(n for n in s.care_needs if n.id == event["need_id"])
                    arrangement = next(a for a in need.arrangements if a.id == event["arrangement_id"])
                    if any(not h.confirmed or h.valid_to is None or h.valid_to < c.day for h in arrangement.handoffs):
                        model.add(xs[c.index] == 0).only_enforce_if(guard(f"handoff:{need.id}:{arrangement.id}", "Przekazanie opieki wymaga potwierdzenia"))
    change_vars, scale_terms = [], []
    for group, offsets in grouped_shifts.items():
        selections = []
        changed = []
        for offset, members in offsets.items():
            selected = model.new_bool_var(f"agreement:{group}:{offset}")
            model.add_max_equality(selected, members)
            selections.append(selected)
            if offset:
                changed.append(selected)
                scale_terms.append(abs(offset) * selected)
        model.add(sum(selections) <= 1).only_enforce_if(guard(f"agreement:{group}", "Spójny zakres jednej zgody na godziny"))
        if changed:
            cv = model.new_bool_var(f"changed:{group}")
            model.add_max_equality(cv, changed)
            change_vars.append(cv)
    # Pairwise timeline and course rules use only reifiable linear constraints.
    ordered = sorted(candidates, key=lambda c: c.away_start)
    for pos, c in enumerate(ordered):
        check_budget()
        for other in ordered[pos + 1:]:
            if other.away_start >= c.away_end + s.minimum_rest_minutes:
                break
            if c.occurrence == other.occurrence:
                continue
            overlap = any(a < d and begin < b for a, b in c.user_blocks for begin, d in other.user_blocks)
            cross_day_work = (not c.care_only and not other.care_only and c.day != other.day and activities[c.activity_id].kind == "work"
                              and activities[other.activity_id].kind == "work")
            rest_bad = cross_day_work and other.away_start - c.away_end < s.minimum_rest_minutes
            if overlap or rest_bad:
                model.add(xs[c.index] + xs[other.index] <= 1).only_enforce_if(guard("user_timeline", "Obowiązki, dojazdy lub odpoczynek kolidują"))
    for c in candidates:
        check_budget()
        if c.care_only:
            continue
        a = activities[c.activity_id]
        for dep in a.requires_activity_ids:
            for course in candidates:
                if course.activity_id == dep and course.end > c.start:
                    model.add(xs[c.index] + xs[course.index] <= 1).only_enforce_if(guard(f"course_order:{a.id}", "Wymagany kurs musi zakończyć się przed pracą"))
    cost_terms = []
    travel_terms = [xs[c.index] * sum(e.get("cost_grosze") or 0 for e in c.events if e["kind"] in ("travel", "care_transfer")) for c in candidates]
    cost_terms.extend(travel_terms)
    for a in s.activities:
        if a.cost_frequency == "once":
            cost_terms.append(enabled[a.id] * (a.cost_grosze or 0))
        else:
            cost_terms.extend(xs[c.index] * (a.cost_grosze or 0) for c in candidates if c.activity_id == a.id)
    bookings = defaultdict(list)
    for c in candidates:
        for e in c.events:
            if e["kind"] == "care":
                for cost_day, segment in _care_segments(e):
                    bookings[(e["resource_id"], cost_day)].append((c.index, segment))
    # Full care requirements, including non-work days and multiple dependents.
    # Self-care is explicit, has capacity, and is unavailable during work/course.
    needs_by_day = defaultdict(list)
    care_first_day = min([s.start_date, *[datetime.fromtimestamp(c.away_start * 60, WARSAW).date() for c in candidates]])
    care_last_day = max([s.end_date, *[datetime.fromtimestamp((c.away_end - 1) * 60, WARSAW).date() for c in candidates]])
    for need in s.care_needs:
        for day in days_between(care_first_day - timedelta(days=1), care_last_day):
            if matches(need, day) and need.start is not None and need.end is not None:
                a, b = _need_window(need, day)
                first = max(a, local_minute(care_first_day, "00:00"))
                last = min(b, local_minute(care_last_day, "24:00"))
                for covering_day in days_between(datetime.fromtimestamp(first * 60, WARSAW).date(), datetime.fromtimestamp((last - 1) * 60, WARSAW).date()):
                    needs_by_day[str(covering_day)].append((need, max(first, local_minute(covering_day, "00:00")), min(last, local_minute(covering_day, "24:00"))))
    candidates_by_day = defaultdict(list)
    for c in candidates:
        for day in days_between(datetime.fromtimestamp(c.away_start * 60, WARSAW).date(), datetime.fromtimestamp((c.away_end - 1) * 60, WARSAW).date()):
            candidates_by_day[str(day)].append(c)
    coverage_implied = not baseline and _care_coverage_is_implied(s, candidates)
    for day_string, care_needs in ([] if coverage_implied else needs_by_day.items()):
        check_budget()
        relevant = candidates_by_day[day_string]
        boundary = {x for _, a, b in care_needs for x in (a, b)}
        for c in relevant:
            boundary.update((c.start, c.end))
            for e in c.events:
                if e["kind"] == "care":
                    boundary.update((e["start_minute"], e["end_minute"]))
        boundary = sorted(boundary)
        for begin, end in zip(boundary, boundary[1:]):
            active = [(n, a, b) for n, a, b in care_needs if a <= begin < b]
            if not active:
                continue
            self_vars = []
            working = [xs[c.index] for c in relevant if not c.care_only and c.start <= begin < c.end]
            for need, _, _ in active:
                external = [xs[c.index] for c in relevant for e in c.events if e["kind"] == "care" and e["need_id"] == need.id and e["start_minute"] <= begin < e["end_minute"]]
                own = model.new_bool_var(f"self_care:{need.id}:{begin}")
                if not need.allow_self_care:
                    model.add(own == 0)
                model.add(own + sum(working) <= 1).only_enforce_if(guard("self_care_work", "Praca, także zdalna, nie oznacza jednoczesnej opieki"))
                model.add(own + sum(external) == 1).only_enforce_if(guard(f"full_care:{need.id}", f"Pełne pokrycie opieki: {need.label}"))
                self_vars.append(own)
            model.add(sum(self_vars) <= s.self_care_capacity).only_enforce_if(guard("self_care_capacity", "Jawna pojemność samodzielnej opieki"))
    resource_used = defaultdict(list)
    # One caregiver can escort several compatible dependents together, but cannot
    # travel between different places while another assigned dependent stays put.
    transfer_events = [(c.index, e) for c in candidates for e in c.events if e["kind"] == "care_transfer"]
    care_events = [(c.index, e) for c in candidates for e in c.events if e["kind"] == "care"]
    for idx, transfer in transfer_events:
        check_budget()
        for other_idx, booking in care_events:
            if booking["resource_id"] != transfer["resource_id"] or booking["dependent_id"] == transfer["dependent_id"]:
                continue
            if booking["start_minute"] >= transfer["end_minute"] or transfer["start_minute"] >= booking["end_minute"]:
                continue
            joint = any(e["kind"] == "care_transfer" and e.get("dependent_id") == booking["dependent_id"] and all(e.get(key) == transfer.get(key) for key in ("resource_id", "origin", "destination", "start_minute", "end_minute")) for e in candidates[other_idx].events)
            if not joint:
                model.add(xs[idx] + xs[other_idx] <= 1).only_enforce_if(guard(f"caregiver_transfer:{transfer['resource_id']}", "Opiekun nie może jednocześnie przebywać w różnych miejscach"))
    # When only one care-bearing occurrence can be selected on each date, daily
    # care billing is exactly a linear candidate cost. This equivalent form
    # removes thousands of redundant OR variables without pruning any option.
    occurrences_per_day = defaultdict(set)
    same_date_bookings = True
    for c in candidates:
        for e in c.events:
            if e["kind"] == "care":
                event_days = [d for d, _ in _care_segments(e)]
                same_date_bookings = same_date_bookings and event_days == [str(c.day)]
                for day in event_days:
                    occurrences_per_day[day].add(c.occurrence)
    direct_billing = same_date_bookings and all(len(items) == 1 for items in occurrences_per_day.values())
    if direct_billing:
        for c in candidates:
            grouped = defaultdict(list)
            for e in c.events:
                if e["kind"] == "care":
                    grouped[e["resource_id"]].append(e)
            candidate_cost = 0
            for rid, entries in grouped.items():
                r = resources[rid]
                resource_used[rid].append(xs[c.index])
                boundaries = sorted({e[k] for e in entries for k in ("start_minute", "end_minute")})
                duration = 0
                for begin, end in zip(boundaries, boundaries[1:]):
                    count = sum(e["start_minute"] <= begin < e["end_minute"] for e in entries)
                    if count:
                        duration += end - begin
                    if count > r.capacity:
                        model.add(xs[c.index] == 0).only_enforce_if(guard(f"capacity:{rid}", f"Pojemność opieki: {r.label}"))
                candidate_cost += (r.daily_cost_grosze or 0) + (duration * (r.hourly_cost_grosze or 0) + 59) // 60
            cost_terms.append(xs[c.index] * candidate_cost)
    for (rid, day), entries in ([] if direct_billing else bookings.items()):
        check_budget()
        r = resources[rid]
        member_indexes = set(i for i, _ in entries)
        used = model.new_bool_var(f"resource_day:{rid}:{day}")
        model.add_max_equality(used, [xs[i] for i in member_indexes])
        resource_used[rid].append(used)
        cost_terms.append(used * (r.daily_cost_grosze or 0))
        boundaries = sorted({e[k] for _, e in entries for k in ("start_minute", "end_minute")})
        occupied_terms = []
        for begin, end in zip(boundaries, boundaries[1:]):
            covering = [(i, e) for i, e in entries if e["start_minute"] <= begin < e["end_minute"]]
            if not covering:
                continue
            model.add(sum(xs[i] for i, _ in covering) <= r.capacity).only_enforce_if(guard(f"capacity:{rid}", f"Pojemność opieki: {r.label}"))
            occupied = model.new_bool_var(f"occupied:{rid}:{day}:{begin}")
            model.add_max_equality(occupied, [xs[i] for i in set(i for i, _ in covering)])
            occupied_terms.append(occupied * (end - begin))
        if r.hourly_cost_grosze:
            day_cost = model.new_int_var(0, 10**10, f"hourly:{rid}:{day}")
            # Round upward once per resource/date; rate is for the whole resource.
            numerator = sum(occupied_terms) * r.hourly_cost_grosze
            model.add(day_cost * 60 >= numerator)
            model.add(day_cost * 60 <= numerator + 59)
            cost_terms.append(day_cost)
    for rid, uses in resource_used.items():
        r = resources[rid]
        last_day = max(date.fromisoformat(day) for resource_id, day in bookings if resource_id == rid)
        if not r.one_time_cost_grosze and _confirmed(r, last_day):
            continue
        used = model.new_bool_var(f"resource:{rid}")
        model.add_max_equality(used, uses)
        cost_terms.append(used * (r.one_time_cost_grosze or 0))
        if not _confirmed(r, last_day):
            change_vars.append(used)
    handoff_choices = defaultdict(list)
    for c in candidates:
        seen = set()
        for event in c.events:
            if event["kind"] == "care" and event.get("arrangement_id"):
                need = next(n for n in s.care_needs if n.id == event["need_id"])
                arrangement = next(a for a in need.arrangements if a.id == event["arrangement_id"])
                for index, h in enumerate(arrangement.handoffs):
                    key = (need.id, arrangement.id, index)
                    if key not in seen and (not h.confirmed or h.valid_to is None or h.valid_to < s.end_date):
                        handoff_choices[key].append(xs[c.index])
                        seen.add(key)
    for key, values in handoff_choices.items():
        chosen = model.new_bool_var("handoff:" + ":".join(map(str, key)))
        model.add_max_equality(chosen, values)
        change_vars.append(chosen)
    paid = sum(xs[c.index] * activities[c.activity_id].paid_minutes for c in candidates if not c.care_only and activities[c.activity_id].kind == "work")
    model.add(paid >= s.minimum_paid_minutes).only_enforce_if(guard("work_dimension", "Wymagany płatny wymiar pracy"))
    cost = sum(cost_terms)
    if s.budget_grosze is not None:
        model.add(cost <= s.budget_grosze).only_enforce_if(guard("budget", "Twardy budżet na cały sprawdzany okres"))
    if exclude:
        for selected in exclude:
            # Exclude the organization of the whole plan, not a solver artefact.
            model.add(sum(xs[i] for i in selected) <= len(selected) - 1)
    metrics = {"changed_agreements": sum(change_vars), "shift_minutes": sum(scale_terms), "cost_grosze": cost}
    return model, xs, metrics, assumptions


def _run_model(model, deadline):
    invalid = model.validate()
    if invalid:
        return "MODEL_INVALID", None, invalid
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return "UNKNOWN", None, None
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = remaining
    solver.parameters.num_search_workers = 1
    solver.parameters.relative_gap_limit = 0
    solver.parameters.absolute_gap_limit = 0
    solver.parameters.max_memory_in_mb = 512
    if not model.proto.assumptions:
        for parameter, value in _OPTIMIZATION_CP_PARAMETERS.items():
            setattr(solver.parameters, parameter, value)
    status = solver.solve(model)
    return solver.status_name(status), solver, None


def _optimize(s, candidates, occurrences, deadline, extra_buffer=0, exclude=None, template=None, reference_proof=None):
    if template is None:
        model, xs, metrics, assumptions = _build_model(s, candidates, occurrences, extra_buffer=extra_buffer, exclude=exclude, deadline=deadline)
    else:
        original, xs, metrics, assumptions = template
        model = original.clone()
        for c in candidates:
            if extra_buffer and c.slack < extra_buffer:
                model.add(xs[c.index] == 0)
        for selection in exclude or []:
            model.add(sum(xs[i] for i in selection) <= len(selection) - 1)
    proof, last_solver, last_status = [], None, "UNKNOWN"
    for goal in s.objective_order:
        stage = len(proof)
        if (reference_proof and len(reference_proof) > stage
                and reference_proof[stage]["objective"] == goal
                and all(p["optimal"] for p in reference_proof[:stage + 1])
                and all(p["value"] == reference_proof[index]["value"] for index, p in enumerate(proof))):
            # Added buffer/exclusion constraints only remove schedules. An
            # already proven bound stays valid while previous lexicographic
            # objectives remain at the same minima. No heuristic bound is used.
            model.add(metrics[goal] >= reference_proof[stage]["value"])
        model.minimize(metrics[goal])
        status, solver, error = _run_model(model, deadline)
        if status not in ("OPTIMAL", "FEASIBLE"):
            return ("FEASIBLE" if last_solver else status), last_solver, xs, metrics, proof, error
        last_solver, last_status = solver, status
        value = solver.value(metrics[goal])
        proof.append({"objective": goal, "value": value, "status": status,
                      "best_bound": round(solver.best_objective_bound), "optimal": status == "OPTIMAL"})
        if status != "OPTIMAL":
            break
        model.add(metrics[goal] == value)
    if len(proof) != len(s.objective_order):
        last_status = "FEASIBLE" if last_solver else last_status
    return last_status, last_solver, xs, metrics, proof, None


def _delay_probe(s, chosen, alternative, delay):
    """Replay exactly the selected organization using changed travel durations."""
    from api.validation import validate_schedule
    disrupted = s.model_copy(deep=True)
    for leg in disrupted.travel_legs:
        for band in leg.bands:
            if band.minutes:
                band.minutes += delay
    activities = {a.id: a for a in disrupted.activities}
    resources = {r.id: r for r in disrupted.care_resources}
    events, issues = [], []
    for index, candidate in enumerate(chosen):
        nearby = (candidate.day - timedelta(days=1), candidate.day, candidate.day + timedelta(days=1))
        needs = sorted([n for n in disrupted.care_needs if any(matches(n, d) for d in nearby)], key=lambda n: (n.visit_order, n.id))
        allocations = []
        for need in needs:
            bookings = sorted([e for e in candidate.events if e["kind"] == "care" and e["need_id"] == need.id], key=lambda e: e["start_minute"])
            chain = tuple(resources[e["resource_id"]] for e in bookings)
            arrangement = next((a for a in need.arrangements if bookings and a.id == bookings[0].get("arrangement_id")), None)
            allocations.append((chain, arrangement))
        if candidate.care_only:
            position = next(i for i, (chain, _) in enumerate(allocations) if chain)
            rebuilt = _standalone_care(disrupted, needs[position], candidate.day, *allocations[position], index)
        else:
            rebuilt = _build_candidate(disrupted, activities[candidate.activity_id], candidate.day, candidate.clock, allocations, needs, index)
        events.extend(rebuilt.events)
        issues.extend(rebuilt.issues)
    checked = validate_schedule(disrupted.model_dump(mode="json"), {"schedule": events, "metrics": alternative["metrics"]})
    problems = [*issues, *[error for error in checked["errors"] if error["code"] != "cost_total"]]
    unknown = any(p["code"] in ("missing_route", "stale_source", "unknown_cost") for p in problems)
    feasible = None if unknown else not problems
    return {"kind": "travel_delay", "extra_minutes": delay, "feasible": feasible,
            "scope": "Każdy niezerowy odcinek podróży wydłużony o podaną liczbę minut, stałe godziny pracy i wybór opieki, ponowne sprawdzenie kierunkowych przedziałów tras",
            "cost_grosze": checked.get("cost_grosze"), "conflicts": problems,
            "message": f"Dodatkowe opóźnienie {delay} min na odcinek: " + ("potrzebne nowe dane tras" if unknown else "plan nadal spełnia ograniczenia" if feasible else "potrzebna zmiana planu")}


def _selection(s, candidates, xs, solver, metrics, proof, number, title, status):
    from api.validation import validate_schedule
    chosen = [c for c in candidates if solver.value(xs[c.index])]
    schedule = sorted([e for c in chosen for e in c.events], key=lambda e: (e["start_minute"], e["kind"], e.get("dependent_id", "")))
    dependencies, changes = [], []
    grouped = {}
    activities = {a.id: a for a in s.activities}
    for c in chosen:
        if c.care_only:
            continue
        a = activities[c.activity_id]
        if c.shift:
            group = a.agreement_id or a.id
            if group not in grouped:
                change = {"id": group, "kind": "work_hours", "activity_id": a.id,
                          "from": a.start, "to": format_clock(c.clock), "minutes": c.shift,
                          "label": f"{a.label}: {a.start} → {format_clock(c.clock)}"}
                changes.append(change)
                dependencies.append({"id": f"hours:{group}", "kind": "employer", "owner": "Pracodawca", "party": "Pracodawca", "activity_id": a.id,
                                     "description": f"Potwierdzić godziny {format_clock(c.clock)}–{format_clock(c.clock + a.duration_minutes)}",
                                     "proposal": {"start": format_clock(c.clock), "duration_minutes": a.duration_minutes},
                                     "fields": [f"activities.{a.id}.start", f"activities.{a.id}.duration_minutes"],
                                     "valid_from": str(s.start_date), "valid_to": str(s.end_date), "status": "pending"})
                grouped[group] = True
    for dependency in dependencies:
        group = dependency["id"].removeprefix("hours:")
        proposals = {}
        for c in chosen:
            if c.care_only:
                continue
            activity = activities[c.activity_id]
            if (activity.agreement_id or activity.id) == group:
                proposals[activity.id] = {"activity_id": activity.id, "start": format_clock(c.clock), "duration_minutes": activity.duration_minutes}
        dependency["proposal"]["activities"] = list(proposals.values())
        dependency["fields"] = [f"activities.{aid}.{field}" for aid in proposals for field in ("start", "duration_minutes")]
    used = {e["resource_id"] for e in schedule if e["kind"] == "care"}
    for r in s.care_resources:
        last_day = max((datetime.fromtimestamp((e["end_minute"] - 1) * 60, WARSAW).date() for e in schedule if e["kind"] == "care" and e["resource_id"] == r.id), default=s.end_date)
        if r.id in used and not _confirmed(r, last_day):
            dependencies.append({"id": f"care:{r.id}", "kind": "care", "owner": r.label, "party": r.label, "resource_id": r.id,
                                 "description": "Potwierdzić przyjęcie, godziny i cenę dla całego okresu",
                                 "fields": [f"care_resources.{r.id}"], "valid_from": str(s.start_date),
                                 "valid_to": str(max(s.end_date, last_day)), "status": "pending"})
    used_arrangements = {(e["need_id"], e["arrangement_id"]) for e in schedule if e["kind"] == "care" and e.get("arrangement_id")}
    for need_id, arrangement_id in sorted(used_arrangements):
        need = next(n for n in s.care_needs if n.id == need_id)
        arrangement = next(a for a in need.arrangements if a.id == arrangement_id)
        for index, handoff in enumerate(arrangement.handoffs):
            if not handoff.confirmed or handoff.valid_to is None or handoff.valid_to < s.end_date:
                resource = next(r for r in s.care_resources if r.id == handoff.by_resource_id)
                dependencies.append({"id": f"handoff:{need_id}:{arrangement_id}:{index}", "kind": "care_handoff", "owner": resource.label,
                                     "party": resource.label, "resource_id": resource.id, "need_id": need_id, "arrangement_id": arrangement_id,
                                     "description": f"Potwierdzić odbiór i przekazanie o {handoff.at}",
                                     "fields": [f"care_needs.{need_id}.arrangements"],
                                     "proposal": {"arrangement_id": arrangement_id, "at": handoff.at},
                                     "valid_from": str(s.start_date), "valid_to": str(s.end_date), "status": "pending"})
    cost = int(solver.value(metrics["cost_grosze"]))
    metric_values = {key: int(solver.value(value)) for key, value in metrics.items()}
    metric_values.update({"paid_minutes": sum(e["paid_minutes"] for e in schedule if e["kind"] == "work"),
                          "presence_minutes": sum(c.end - c.start for c in chosen if not c.care_only),
                          "travel_minutes": sum(e["end_minute"] - e["start_minute"] for e in schedule if e["kind"] == "travel"),
                          "minimum_slack_minutes": min([c.slack for c in chosen if c.slack != 100_000], default=0),
                          "coordination_actions": len(dependencies)})
    alternative = {"id": f"alternative-{number}", "title": title,
                   "status": "awaiting_confirmation" if dependencies else "confirmed", "solver_status": status,
                   "schedule": schedule, "changes": changes, "metrics": metric_values,
                   "dependencies": dependencies,
                   "actions": [{"id": d["id"], "owner": d["owner"], "description": d["description"],
                                "deadline": str(s.start_date), "depends_on": [], "source": "warunek obliczonego wariantu"} for d in dependencies],
                   "proof": {"stages": proof, "minimal_change_proven": s.objective_order[:2] == ["changed_agreements", "shift_minutes"] and len(proof) == 3 and all(p["optimal"] for p in proof),
                             "scope": "Pełny podany okres, jawny zakres godzin i wprowadzone kierunkowe przedziały tras"},
                   "robustness": []}
    check = validate_schedule(s.model_dump(mode="json"), alternative)
    alternative["validation"] = check
    if not check["valid"]:
        alternative["status"] = "draft"
        alternative["solver_status"] = "MODEL_INVALID"
    delay = s.preferred_extra_buffer_minutes
    alternative["robustness"].append(_delay_probe(s, chosen, alternative, delay))
    for r in s.care_resources:
        if r.id in used:
            alternative["robustness"].append({"kind": "caregiver_absence" if r.kind == "caregiver" else "care_cancellation",
                                               "resource_id": r.id, "feasible": False,
                                               "message": f"Brak {r.label}: zaplanowane pokrycie znika; wymagana ponowna analiza"})
    return alternative, [c.index for c in chosen]


def solve_scenario(payload: dict, budget_seconds: float | None = None) -> dict:
    started = time.monotonic()
    cache_token = _INPUT_CACHE.set({})
    budget = float(budget_seconds if budget_seconds is not None else os.getenv("SOLVER_TOTAL_BUDGET_SECONDS", "20"))
    deadline = started + max(0, min(budget, 120))
    result = {"status": "UNKNOWN", "data_status": "complete", "data_gaps": [], "conflicts": [],
              "baseline": {"status": "UNKNOWN", "conflicts": [], "schedule": []}, "alternatives": [],
              "checked_period": None, "solver_version": "okno-cpsat-1", "input_version": payload.get("version", 1),
              "scope": {"time_grid": "Wprowadzone start_min/start_max/step_minutes", "routes": "Wyłącznie podane kierunki, daty i przedziały odjazdu", "care": "Jawne kolejności odwiedzin i zasoby dopuszczone do opieki", "full_horizon": True},
              "warnings": [], "offers": []}
    try:
        s = Scenario.model_validate(payload)
        result["checked_period"] = {"start": str(s.start_date), "end": str(s.end_date), "timezone": s.timezone}
        result["input_hash"] = hashlib.sha256(json.dumps(s.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()
        candidates, gaps, occurrences = _normalize(s, deadline)
        result["data_gaps"] = gaps
        if gaps:
            result["data_status"] = "needs_input"
            return result
        if not occurrences:
            result["data_status"] = "needs_input"
            result["data_gaps"] = [issue("empty_period", "Brak aktywności w sprawdzanym okresie")]
            return result
        # Baseline's domain contains only the stated current hours. Renumbering
        # these candidates avoids constructing every negotiable shift again for
        # a diagnosis which must never choose one of them.
        baseline_candidates = [replace(c, index=index) for index, c in enumerate(c for c in candidates if c.shift == 0)]
        baseline_occurrences = {key: [] for key in occurrences}
        for c in baseline_candidates:
            baseline_occurrences[c.occurrence].append(c.index)
        baseline_model, baseline_xs, baseline_metrics, assumptions = _build_model(s, baseline_candidates, baseline_occurrences, baseline=True, deadline=deadline)
        bs, bsolver, error = _run_model(baseline_model, deadline)
        baseline_issues = []
        seen_issues = set()
        for c in candidates:
            if c.shift == 0 and not c.care_only:
                for p in c.issues:
                    key = json.dumps(p, sort_keys=True)
                    if key not in seen_issues:
                        seen_issues.add(key)
                        baseline_issues.append(p)
        result["baseline"]["status"] = bs
        if bs == "INFEASIBLE" and bsolver:
            by_index = {lit.index: (name, message) for name, (lit, message) in assumptions.items()}
            core = [by_index[index] for index in bsolver.sufficient_assumptions_for_infeasibility() if index in by_index]
            result["baseline"]["diagnosis"] = {"sufficient_core": [{"id": x[0], "message": x[1]} for x in core],
                                                   "minimal_core": False, "fixed_model_conflict": not bool(core)}
            if not baseline_issues:
                baseline_issues = [issue("constraint_conflict", message, constraint=name) for name, message in core]
        if bs in ("OPTIMAL", "FEASIBLE"):
            base, _ = _selection(s, baseline_candidates, baseline_xs, bsolver, baseline_metrics, [], 0, "Obecny plan", bs)
            result["baseline"].update({"schedule": base["schedule"], "metrics": base["metrics"], "validation": base["validation"]})
        else:
            # A representative full current timeline remains visible even if it conflicts.
            for indexes in occurrences.values():
                current = next((candidates[i] for i in indexes if candidates[i].shift == 0 and not candidates[i].care_only), None)
                if current:
                    result["baseline"]["schedule"].extend(current.events)
        result["baseline"]["conflicts"] = baseline_issues
        result["conflicts"] = baseline_issues
        # Every issue creates x == 0 in the model. Substitute that proven value
        # before constructing optimization variables; keep all original records
        # above for diagnosis and below for missing-data reporting.
        search_candidates = [replace(c, index=index) for index, c in enumerate(c for c in candidates if not c.issues)]
        search_occurrences = {key: [] for key, indexes in occurrences.items() if not indexes or not candidates[indexes[0]].care_only}
        for c in search_candidates:
            search_occurrences.setdefault(c.occurrence, []).append(c.index)
        template = _build_model(s, search_candidates, search_occurrences, deadline=deadline)
        status, solver, xs, metrics, proof, error = _optimize(s, search_candidates, search_occurrences, deadline, template=template)
        result["status"] = status
        selected = []
        if solver:
            all_objectives_proven = len(proof) == 3 and all(p["optimal"] for p in proof)
            title = "Najlepszy znaleziony wariant"
            if all_objectives_proven:
                title = "Najmniejsza zmiana" if s.objective_order[:2] == ["changed_agreements", "shift_minutes"] else "Najlepszy według priorytetów"
            alt, indexes = _selection(s, search_candidates, xs, solver, metrics, proof, 1,
                                      title, status)
            if alt["validation"]["valid"]:
                result["alternatives"].append(alt)
                selected.append(indexes)
            else:
                result["status"] = "MODEL_INVALID"
                result["warnings"].append("Niezależny walidator odrzucił wynik")
            if time.monotonic() < deadline and s.preferred_extra_buffer_minutes:
                st, sol, vx, met, prf, err = _optimize(s, search_candidates, search_occurrences, deadline, extra_buffer=s.preferred_extra_buffer_minutes, exclude=selected, template=template, reference_proof=proof)
                if sol:
                    a2, idx2 = _selection(s, search_candidates, vx, sol, met, prf, 2, "Większy zapas czasu", st)
                    if a2["validation"]["valid"]:
                        result["alternatives"].append(a2)
                        selected.append(idx2)
            if len(s.care_resources) > 1 and time.monotonic() < deadline:
                st, sol, vx, met, prf, err = _optimize(s, search_candidates, search_occurrences, deadline, exclude=selected, template=template, reference_proof=proof)
                if sol:
                    a3, _ = _selection(s, search_candidates, vx, sol, met, prf, 3, "Inna organizacja", st)
                    if a3["validation"]["valid"]:
                        result["alternatives"].append(a3)
        # Unknown or stale input is never converted into a proof of impossibility.
        data_issues = [p for c in candidates for p in c.issues if p["code"] in ("unknown_cost", "stale_source", "missing_route")]
        if data_issues and not result["alternatives"]:
            result["status"] = "UNKNOWN"
            result["data_status"] = "stale" if any(p["code"] == "stale_source" for p in data_issues) else "needs_input"
            result["data_gaps"] = list({json.dumps(p, sort_keys=True): p for p in data_issues}.values())
        if any(p["code"] == "missing_route" for p in data_issues):
            result["warnings"].append("Wynik dotyczy godzin objętych wprowadzonymi trasami. Pozostałe godziny wymagają potwierdzenia podróży.")
        for a in s.activities:
            if a.kind == "work":
                included = any(any(e.get("activity_id") == a.id and e["kind"] == "work" for e in alt["schedule"]) for alt in result["alternatives"])
                result["offers"].append({"id": a.id, "label": a.label, "included": included,
                                          "status": "candidate" if included else "not_in_presented_variants"})
        return result
    except ValidationError as exc:
        result["data_status"] = "needs_input"
        result["data_gaps"] = [issue("invalid_input", e["msg"], field=".".join(map(str, e["loc"]))) for e in exc.errors()]
        return result
    except ValueError as exc:
        result["data_status"] = "needs_input"
        result["data_gaps"] = [issue("invalid_time", str(exc))]
        return result
    except TimeoutError as exc:
        result["warnings"].append(str(exc))
        return result
    finally:
        _INPUT_CACHE.reset(cache_token)
        result["elapsed_ms"] = round((time.monotonic() - started) * 1000)
