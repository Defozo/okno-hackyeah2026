"""Independent, imperative validation of serialized schedules.

This module intentionally does not import solver code, candidate generation or
OR-Tools. A schedule is checked against the original normalized Pydantic input.
"""
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from api.domain import Scenario

TZ = ZoneInfo("Europe/Warsaw")


def _clock(value):
    h, m = map(int, value.split(":"))
    if h < 0 or h > 24 or m < 0 or m > 59 or (h == 24 and m):
        raise ValueError("Nieprawidłowa godzina")
    return h * 60 + m


def _minute(day, value, fold=None):
    dt = datetime.combine(day, datetime.min.time()) + timedelta(minutes=_clock(value))
    options = []
    for f in (0, 1):
        loc = dt.replace(tzinfo=TZ, fold=f)
        if loc.astimezone(timezone.utc).astimezone(TZ).replace(tzinfo=None) == dt:
            options.append((f, int(loc.timestamp() // 60)))
    if not options or (len({n for _, n in options}) > 1 and fold is None):
        raise ValueError("Niejednoznaczny lub nieistniejący czas lokalny")
    return next(n for f, n in options if fold is None or fold == f)


def _rule(rule, day):
    if day in rule.excluded_dates or rule.valid_from and day < rule.valid_from or rule.valid_to and day > rule.valid_to:
        return False
    return day in rule.dates if rule.dates else day.weekday() in rule.weekdays


def _fresh(source, day):
    return source.status == "current" and (not source.valid_from or day >= source.valid_from) and (not source.valid_to or day <= source.valid_to)


def _range(day, first, last, first_fold=None, last_fold=None):
    return _minute(day, first, first_fold), _minute(day + timedelta(days=_clock(last) <= _clock(first)), last, last_fold)


def _need_range(need, day):
    return _range(day, need.start, need.end, need.start_fold, need.end_fold)


def _union_minutes(intervals):
    total, end = 0, None
    for a, b in sorted(intervals):
        total += max(0, b - max(a, end if end is not None else a))
        end = max(b, end if end is not None else b)
    return total


def validate_schedule(payload: dict, alternative: dict) -> dict:
    errors = []

    def fail(code, message, **kw):
        errors.append({"code": code, "message": message, **kw})

    try:
        s = Scenario.model_validate(payload)
        events = alternative.get("schedule", [])
        acts = {a.id: a for a in s.activities}
        resources = {r.id: r for r in s.care_resources}
        needs = {n.id: n for n in s.care_needs}
        legs = {l.id: l for l in s.travel_legs}
        parsed = []
        for e in events:
            if e.get("kind") not in ("work", "course", "obligation", "travel", "care", "care_transfer"):
                fail("event_kind", "Nieznany rodzaj wydarzenia")
            a = int(datetime.fromisoformat(e["start"]).timestamp() // 60)
            b = int(datetime.fromisoformat(e["end"]).timestamp() // 60)
            if a > b or (a == b and e["kind"] not in ("travel", "care_transfer")):
                fail("interval", "Nieprawidłowy przedział wydarzenia")
            if e.get("start_minute") != a or e.get("end_minute") != b:
                fail("time_integrity", "Czas ISO różni się od czasu całkowitego")
            parsed.append((a, b, e))
        activity_events = defaultdict(list)
        per_occurrence = defaultdict(list)
        for a, b, e in parsed:
            per_occurrence[(e.get("activity_id"), e.get("date"), e.get("need_id") if e.get("care_only") else None)].append((a, b, e))
            if e["kind"] in ("work", "course", "obligation"):
                activity_events[e.get("activity_id")].append((a, b, e))
        group_count = defaultdict(int)
        agreement_offsets = defaultdict(set)
        paid, cost = 0, 0
        for activity in s.activities:
            found = activity_events.get(activity.id, [])
            if activity.offer_group and found:
                group_count[activity.offer_group] += 1
            if not found and not activity.required or not found and activity.offer_group:
                continue
            expected_dates = set()
            d = s.start_date
            while d <= s.end_date:
                if _rule(activity, d):
                    expected_dates.add(str(d))
                d += timedelta(days=1)
            actual_dates = [e["date"] for _, _, e in found]
            if set(actual_dates) != expected_dates or len(actual_dates) != len(set(actual_dates)):
                fail("required_dates", f"Brakuje pełnych obowiązkowych zmian: {activity.label}")
            if activity.cost_grosze is None:
                fail("unknown_cost", "Nieznana cena aktywności")
            else:
                cost += activity.cost_grosze * (len(found) if activity.cost_frequency == "occurrence" else bool(found))
            for start, end, e in found:
                if e["kind"] != activity.kind or end - start != activity.duration_minutes or e.get("paid_minutes") != activity.paid_minutes:
                    fail("work_dimension", "Zmieniono wymiar lub rodzaj aktywności")
                dt = datetime.fromtimestamp(start * 60, TZ)
                tod = dt.hour * 60 + dt.minute
                if str(dt.date()) != e["date"] or start != _minute(dt.date(), f"{tod // 60:02d}:{tod % 60:02d}", activity.start_fold):
                    fail("activity_date", "Aktywność nie odpowiada dacie i wybranemu wystąpieniu godziny")
                if not _fresh(activity.source, dt.date()):
                    fail("stale_source", "Nieaktualne godziny aktywności")
                offset = tod - _clock(activity.start)
                if any(f.activity_id == activity.id and _clock(f.start) == tod and (not f.valid_from or dt.date() >= f.valid_from) and (not f.valid_to or dt.date() <= f.valid_to) for f in s.forbidden_proposals):
                    fail("refused_proposal", "Wariant zawiera odrzucone godziny")
                agreement_offsets[activity.agreement_id or activity.id].add(offset)
                if offset and (not activity.negotiable or activity.start_min is None or activity.start_max is None or
                               not _clock(activity.start_min) <= tod <= _clock(activity.start_max) or
                               (tod - _clock(activity.start_min)) % activity.step_minutes):
                    fail("unauthorized_change", "Zmieniono godziny poza dopuszczonym zakresem")
                if activity.kind == "work":
                    paid += activity.paid_minutes
                for dep in activity.requires_activity_ids:
                    deps = activity_events.get(dep, [])
                    if not deps or any(stop > start for _, stop, _ in deps):
                        fail("course_dependency", "Kurs nie jest ukończony przed początkiem pracy")
        for group in {a.offer_group for a in s.activities if a.offer_group}:
            if group_count[group] != 1:
                fail("offer_selection", "Należy wybrać dokładnie jedną ofertę z grupy")
        if any(len(offsets) > 1 for offsets in agreement_offsets.values()):
            fail("agreement_consistency", "Jedna zgoda ma niespójne przesunięcia godzin")
        if paid < s.minimum_paid_minutes or alternative.get("metrics", {}).get("paid_minutes") != paid:
            fail("paid_minutes", "Nie zgadza się wymagany lub raportowany czas płatny")
        for start, end, e in [(a, b, event) for a, b, event in parsed if event["kind"] in ("travel", "care_transfer")]:
            leg = legs.get(e.get("leg_id"))
            if not leg or (e.get("origin"), e.get("destination")) != (leg.origin, leg.destination):
                fail("route_identity", "Brak właściwego kierunku trasy")
                continue
            dt = datetime.fromtimestamp(start * 60, TZ)
            tod = dt.hour * 60 + dt.minute
            band_matches = []
            for band in leg.bands:
                lo, hi = _clock(band.start), _clock(band.end)
                inside = lo <= tod < hi if hi > lo else tod >= lo or tod < hi
                if inside and _rule(band, dt.date()) and band.minutes is not None:
                    band_matches.append(band)
            valid_band = any(end - start == band.minutes + leg.handoff_minutes + leg.buffer_minutes
                             and e.get("cost_grosze") == band.cost_grosze
                             and e.get("travel_minutes") == band.minutes
                             and e.get("handoff_minutes") == leg.handoff_minutes
                             and e.get("buffer_minutes") == leg.buffer_minutes for band in band_matches)
            if not valid_band or not _fresh(leg.source, dt.date()):
                fail("route_time", "Trasa nie odpowiada dacie, godzinie, czasowi, cenie lub ważności danych")
            if e.get("cost_grosze") is None:
                fail("unknown_cost", "Brak ceny przejazdu")
            else:
                cost += e["cost_grosze"]
        user_intervals = []
        for (aid, day_string, care_only_id), occurrence in per_occurrence.items():
            if care_only_id:
                need = needs.get(care_only_id)
                day = date.fromisoformat(day_string)
                if need is None or not _rule(need, day) or not s.start_date <= day <= s.end_date:
                    fail("care_day", "Samodzielne zlecenie nie odpowiada potrzebie i dacie")
                    continue
                bookings = sorted([(a, b, e) for a, b, e in occurrence if e["kind"] == "care"], key=lambda x: x[0])
                if not bookings:
                    fail("care_booking", "Brak opieki w samodzielnym zleceniu")
                    continue
                arrangement_id = bookings[0][2].get("arrangement_id")
                arrangement = next((item for item in need.arrangements if item.id == arrangement_id), None) if arrangement_id else None
                chain = arrangement.resource_ids if arrangement else [bookings[0][2]["resource_id"]]
                if (arrangement_id and not arrangement) or [e["resource_id"] for _, _, e in bookings] != chain or any(rid not in resources for rid in chain):
                    fail("care_arrangement", "Niepoprawny łańcuch samodzielnego zlecenia")
                    continue
                ns, ne = _need_range(need, day)
                if bookings[0][0] != ns or bookings[-1][1] != ne or any(a[1] != b[0] for a, b in zip(bookings, bookings[1:])):
                    fail("care_coverage", "Samodzielne zlecenie nie pokrywa całej potrzeby")
                for a, b, e in bookings:
                    r = resources[e["resource_id"]]
                    if e.get("dependent_id") != need.dependent_id or e.get("location") != r.location or e.get("arrangement_id") != arrangement_id or need.care_type not in r.care_types or r.dependent_ids and need.dependent_id not in r.dependent_ids or not arrangement and need.resource_ids and r.id not in need.resource_ids or not r.confirmed and not r.negotiable:
                        fail("care_compatibility", "Samodzielne zlecenie nie jest dopuszczone")
                for journey, target, stop in (("dropoff", ns, resources[chain[0]].location), ("pickup", ne, resources[chain[-1]].location)):
                    travel = sorted([(a, b, e) for a, b, e in occurrence if e["kind"] == "travel" and e.get("journey") == journey], key=lambda x: x[0])
                    expected = [] if stop == s.home_location else [(s.home_location, stop), (stop, s.home_location)]
                    if [(e.get("origin"), e.get("destination")) for _, _, e in travel] != expected:
                        fail("missing_transfer", "Brak dowozu lub odbioru samodzielnego zlecenia")
                    if travel:
                        if len(travel) != 2 or travel[0][1] != target or travel[-1][0] != target:
                            fail("travel_continuity", "Dowóz lub odbiór nie odpowiada godzinie przekazania")
                        user_intervals.append((travel[0][0], travel[-1][1], "care_visit", day_string))
                if any(e["kind"] == "travel" and e.get("journey") not in ("dropoff", "pickup") for _, _, e in occurrence):
                    fail("care_journey", "Nieznana podróż samodzielnego zlecenia")
                if arrangement:
                    for index, handoff in enumerate(arrangement.handoffs):
                        previous, following = bookings[index], bookings[index + 1]
                        ht = datetime.fromtimestamp(previous[1] * 60, TZ)
                        if any(_rule(rule, ht.date()) for rule in arrangement.unavailable):
                            fail("refused_arrangement", "Odrzucone przekazanie opieki")
                        if previous[1] != _minute(ht.date(), handoff.at, handoff.at_fold) or not _fresh(handoff.source, ht.date()) or handoff.by_resource_id != following[2]["resource_id"]:
                            fail("handoff_actor", "Niepoprawne przekazanie samodzielnego zlecenia")
                        if previous[2]["location"] != following[2]["location"]:
                            transfers = [e for a, b, e in occurrence if e["kind"] == "care_transfer" and a == previous[1] and b <= following[1] and e.get("leg_id") == handoff.leg_id and e.get("resource_id") == handoff.by_resource_id and e.get("origin") == previous[2]["location"] and e.get("destination") == following[2]["location"]]
                            if len(transfers) != 1:
                                fail("handoff_transfer", "Brak podróży w samodzielnym przekazaniu")
                continue
            if aid not in acts or not day_string:
                fail("unknown_activity", "Wydarzenie nie ma rozpoznanej aktywności i daty")
                continue
            work = [(a, b, e) for a, b, e in occurrence if e["kind"] in ("work", "course", "obligation")]
            if len(work) != 1:
                fail("occurrence", "Wydarzenia nie są powiązane z jedną pełną aktywnością")
                continue
            ws, we, _ = work[0]
            travel = sorted([(a, b, e) for a, b, e in occurrence if e["kind"] == "travel"], key=lambda x: x[0])
            care_transfers = [(a, b, e) for a, b, e in occurrence if e["kind"] == "care_transfer"]
            cares = [(a, b, e) for a, b, e in occurrence if e["kind"] == "care"]
            # Reconstruct the complete tour to catch a removed transfer event.
            ordered_needs = sorted({e.get("need_id") for _, _, e in cares}, key=lambda key: (needs[key].visit_order, key))
            first_stops, last_stops = [], []
            for key in ordered_needs:
                sequence = sorted([(a, b, e) for a, b, e in cares if e.get("need_id") == key], key=lambda x: x[0])
                if sequence[0][2]["location"] not in first_stops:
                    first_stops.append(sequence[0][2]["location"])
                if sequence[-1][2]["location"] not in last_stops:
                    last_stops.append(sequence[-1][2]["location"])
            outward = [s.home_location, *first_stops, acts[aid].location]
            returning = [acts[aid].location, *reversed(last_stops), s.home_location]
            expected_out = [(a, b) for a, b in zip(outward, outward[1:]) if a != b]
            expected_back = [(a, b) for a, b in zip(returning, returning[1:]) if a != b]
            before = [(a, b, e) for a, b, e in travel if b <= ws]
            after = [(a, b, e) for a, b, e in travel if a >= we]
            if [(e["origin"], e["destination"]) for _, _, e in before] != expected_out or [(e["origin"], e["destination"]) for _, _, e in after] != expected_back or len(before) + len(after) != len(travel):
                fail("missing_transfer", "Brak pełnego łańcucha dojazdu, przekazań i powrotu")
            if before and before[-1][1] != ws or after and after[0][0] != we:
                fail("travel_continuity", "Przejazd nie jest połączony z aktywnością")
            for route in (before, after):
                for previous, following in zip(route, route[1:]):
                    if previous[1] != following[0]:
                        fail("travel_continuity", "Nieciągły łańcuch przekazań")
            away_start = before[0][0] if before else ws
            away_end = after[-1][1] if after else we
            user_intervals.append((away_start, away_end, acts[aid].kind, day_string))
            for need in s.care_needs:
                day = date.fromisoformat(day_string)
                need_windows = [_need_range(need, d) for d in (day - timedelta(days=1), day, day + timedelta(days=1)) if _rule(need, d)]
                relevant = [(a, b) for a, b in need_windows if a < away_end and b > away_start]
                if not relevant:
                    continue
                ns, ne = min(a for a, _ in relevant), max(b for _, b in relevant)
                needed_start, needed_end = max(ns, away_start), min(ne, away_end)
                if needed_start >= needed_end:
                    continue
                bookings = sorted([(a, b, e) for a, b, e in cares if e.get("need_id") == need.id], key=lambda x: x[0])
                if not bookings:
                    # An independent booking is checked separately and may
                    # cover this activity without a second reservation.
                    independent = [(a, b) for a, b, ev in parsed if ev["kind"] == "care" and ev.get("need_id") == need.id and ev.get("care_only")]
                    independently_covered = all(_union_minutes([(max(a, x), min(b, y)) for x, y in independent if x < b and a < y]) >= b - a for a, b in [(max(ws, a), min(we, b)) for a, b in relevant if a < we and ws < b])
                    if (any(a < we and ws < b for a, b in relevant) or not need.allow_self_care) and not independently_covered:
                        fail("care_coverage", f"Brak jednoznacznego pokrycia: {need.label}")
                    continue
                arrangement_id = bookings[0][2].get("arrangement_id")
                arrangement = next((a for a in need.arrangements if a.id == arrangement_id), None) if arrangement_id else None
                if arrangement_id and not arrangement or not arrangement and len(bookings) != 1:
                    fail("care_arrangement", "Nieznany lub niepełny łańcuch opieki")
                    continue
                chain_ids = arrangement.resource_ids if arrangement else [bookings[0][2]["resource_id"]]
                if [e["resource_id"] for _, _, e in bookings] != chain_ids or any(e.get("arrangement_id") != arrangement_id for _, _, e in bookings):
                    fail("care_arrangement", "Kolejność zasobów nie odpowiada uzgodnionemu łańcuchowi")
                    continue
                if any(rid not in resources for rid in chain_ids):
                    fail("care_resource", "Nieznany zasób opieki")
                    continue
                first_resource, last_resource = resources[chain_ids[0]], resources[chain_ids[-1]]
                depart = next((start for start, end, leg in before if leg["origin"] == first_resource.location), ws if first_resource.location == acts[aid].location else away_start)
                arrive = next((end for start, end, leg in after if leg["destination"] == last_resource.location), we if last_resource.location == acts[aid].location else away_end)
                expected_start, expected_end = (max(ns, depart), min(ne, arrive)) if need.allow_self_care else _need_range(need, day)
                if not need.allow_self_care and ((expected_start < depart and first_resource.location != s.home_location) or (expected_end > arrive and last_resource.location != s.home_location)):
                    fail("care_delivery", "Brak dowozu lub odbioru poza samodzielną dostępnością")
                if bookings[0][0] != expected_start or bookings[-1][1] != expected_end or any(previous[1] != following[0] for previous, following in zip(bookings, bookings[1:])):
                    fail("care_transfer", "Opieka nie obejmuje właściwych przekazań i przejazdów")
                for a, b, e in bookings:
                    resource = resources[e["resource_id"]]
                    if e.get("dependent_id") != need.dependent_id or e.get("location") != resource.location or need.care_type not in resource.care_types or resource.dependent_ids and need.dependent_id not in resource.dependent_ids or not arrangement and need.resource_ids and resource.id not in need.resource_ids:
                        fail("care_compatibility", "Opieka nie jest dopuszczona dla podopiecznego")
                    if not resource.confirmed and not resource.negotiable:
                        fail("care_permission", "Nie dopuszczono użycia niepotwierdzonego zasobu")
                if arrangement:
                    for index, handoff in enumerate(arrangement.handoffs):
                        old, new = bookings[index], bookings[index + 1]
                        ht = datetime.fromtimestamp(old[1] * 60, TZ)
                        if any(_rule(rule, ht.date()) for rule in arrangement.unavailable):
                            fail("refused_arrangement", "Odrzucone przekazanie opieki")
                        if ht.hour * 60 + ht.minute != _clock(handoff.at) or handoff.by_resource_id != new[2]["resource_id"]:
                            fail("handoff_actor", "Brak opiekuna na właściwym przekazaniu")
                        if old[1] != _minute(ht.date(), handoff.at, handoff.at_fold) or not _fresh(handoff.source, ht.date()):
                            fail("handoff_time", "Nieaktualna lub niejednoznaczna godzina przekazania")
                        if old[2]["location"] != new[2]["location"]:
                            transfer = [e for a, b, e in care_transfers if a == old[1] and b <= new[1] and e.get("need_id") == need.id and e.get("leg_id") == handoff.leg_id and e.get("resource_id") == handoff.by_resource_id and e.get("origin") == old[2]["location"] and e.get("destination") == new[2]["location"]]
                            if len(transfer) != 1:
                                fail("handoff_transfer", "Brak pełnego przejazdu podczas przekazania opieki")
        for i, (a, b, activity, day) in enumerate(sorted(user_intervals, key=lambda x: x[:2])):
            for c, d, other, otherday in sorted(user_intervals, key=lambda x: x[:2])[i + 1:]:
                if c >= b + s.minimum_rest_minutes:
                    break
                if a < d and c < b:
                    fail("user_overlap", "Nakładają się zobowiązania użytkowniczki")
                elif day != otherday and activity == other == "work" and c - b < s.minimum_rest_minutes:
                    fail("rest", "Niewystarczający odpoczynek między dniami pracy")
        # Reconstruct all care needs, including dates without a work occurrence.
        # This is independent of the solver's own optional self-care variables.
        first_day = min([s.start_date, *[datetime.fromtimestamp(a * 60, TZ).date() for a, _, _ in parsed]])
        last_day = max([s.end_date, *[datetime.fromtimestamp((b - 1) * 60, TZ).date() for a, b, _ in parsed if b > a]])
        care_windows = []
        day = first_day - timedelta(days=1)
        while day <= last_day:
            for need in s.care_needs:
                if _rule(need, day):
                    a, b = _need_range(need, day)
                    a, b = max(a, _minute(first_day, "00:00")), min(b, _minute(last_day, "24:00"))
                    if a < b:
                        care_windows.append((a, b, need))
            day += timedelta(days=1)
        boundaries = sorted({x for a, b, _ in [*care_windows, *parsed] for x in (a, b)})
        for begin, end in zip(boundaries, boundaries[1:]):
            active = [need for a, b, need in care_windows if a <= begin < b]
            self_count = 0
            working = any(a <= begin < b and e["kind"] in ("work", "course", "obligation") for a, b, e in parsed)
            for need in active:
                external = [e for a, b, e in parsed if e["kind"] == "care" and e.get("need_id") == need.id and a <= begin < b]
                if len(external) > 1:
                    fail("care_coverage", "Kilka przypisań obejmuje tę samą potrzebę opieki")
                elif not external:
                    if not need.allow_self_care or working:
                        fail("full_care", f"Niepokryta opieka: {need.label}")
                    self_count += 1
            if self_count > s.self_care_capacity:
                fail("self_care_capacity", "Przekroczono jawną pojemność samodzielnej opieki")
        for start, end, transfer in parsed:
            if transfer["kind"] != "care_transfer":
                continue
            for a, b, booking in parsed:
                if booking["kind"] != "care" or booking.get("resource_id") != transfer.get("resource_id") or booking.get("dependent_id") == transfer.get("dependent_id") or a >= end or start >= b:
                    continue
                joint = any(route["kind"] == "care_transfer" and route.get("dependent_id") == booking.get("dependent_id") and all(route.get(key) == transfer.get(key) for key in ("resource_id", "origin", "destination", "start_minute", "end_minute")) for _, _, route in parsed)
                if not joint:
                    fail("caregiver_location", "Opiekun jest jednocześnie przypisany w podróży i w innym miejscu")
        by_resource_day = defaultdict(list)
        by_dependent = defaultdict(list)
        for a, b, e in parsed:
            if e["kind"] != "care":
                continue
            resource = resources.get(e.get("resource_id"))
            if not resource:
                continue
            day = date.fromisoformat(e["date"])
            cursor = a
            while cursor < b:
                cost_day = datetime.fromtimestamp(cursor * 60, TZ).date()
                stop = min(b, _minute(cost_day + timedelta(days=1), "00:00"))
                by_resource_day[(resource.id, cost_day)].append((cursor, stop, e))
                cursor = stop
            by_dependent[e.get("dependent_id")].append((a, b, e))
            available = []
            busy = []
            for offset in (-1, 0, 1):
                d = day + timedelta(days=offset)
                available += [_range(d, x.start, x.end, x.start_fold, x.end_fold) for x in resource.availability if _rule(x, d) and x.start is not None and x.end is not None]
                busy += [_range(d, x.start, x.end, x.start_fold, x.end_fold) for x in resource.busy if _rule(x, d) and x.start is not None and x.end is not None]
            merged = []
            for begin, end in sorted(available):
                if merged and begin <= merged[-1][1]:
                    merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
                else:
                    merged.append((begin, end))
            if not any(start <= a and end >= b for start, end in merged):
                fail("care_hours", "Opieka wykracza poza godziny zasobu")
            if any(start < b and a < end for start, end in busy):
                fail("caregiver_busy", "Opiekun ma sprzeczne zobowiązanie")
            first_used_day, last_used_day = datetime.fromtimestamp(a * 60, TZ).date(), datetime.fromtimestamp((b - 1) * 60, TZ).date()
            if any(not _fresh(resource.source, first_used_day + timedelta(days=offset)) for offset in range((last_used_day - first_used_day).days + 1)):
                fail("stale_source", "Nieaktualne dane zasobu opieki")
        used_resources = set()
        for (rid, day), entries in by_resource_day.items():
            r = resources[rid]
            if any(x is None for x in (r.daily_cost_grosze, r.hourly_cost_grosze, r.one_time_cost_grosze)):
                fail("unknown_cost", "Nieznana cena opieki")
            else:
                minutes = _union_minutes([(a, b) for a, b, _ in entries])
                cost += r.daily_cost_grosze + (minutes * r.hourly_cost_grosze + 59) // 60
                if rid not in used_resources:
                    cost += r.one_time_cost_grosze
            used_resources.add(rid)
            for moment in sorted({x for a, b, e in entries for x in (a, b)}):
                active = [e for a, b, e in entries if a <= moment < b]
                if len(active) > r.capacity:
                    fail("capacity", "Przekroczono jawną pojemność zasobu opieki")
        for dep, entries in by_dependent.items():
            for i, (a, b, e) in enumerate(entries):
                for c, d, other in entries[i + 1:]:
                    if a < d and c < b:
                        fail("duplicate_assignment", "Podopieczny ma nakładające się przypisania opieki")
            ordered_entries = sorted(entries, key=lambda x: x[0])
            for previous, following in zip(ordered_entries, ordered_entries[1:]):
                a, b, e = previous
                c, d, other = following
                if e["location"] == other["location"] or e["date"] != other["date"]:
                    continue
                location, cursor = e["location"], b
                for start, end, route in sorted(parsed, key=lambda x: x[0]):
                    is_handoff = route["kind"] == "care_transfer" and route.get("dependent_id") == dep
                    if route["kind"] not in ("travel", "care_transfer") or start < cursor or end > (d if is_handoff else c):
                        continue
                    if route.get("origin") == location:
                        location, cursor = route.get("destination"), end
                        if location == other["location"]:
                            break
                if location != other["location"]:
                    fail("dependent_transfer", "Brak podróży podopiecznego między miejscami opieki")
        if alternative.get("metrics", {}).get("cost_grosze") != cost:
            fail("cost_total", "Raportowany koszt nie odpowiada kosztowi niezależnie wyliczonemu")
        if s.budget_grosze is not None and cost > s.budget_grosze:
            fail("budget", "Przekroczono budżet dla całego okresu")
        return {"valid": not errors, "errors": errors, "cost_grosze": cost, "paid_minutes": paid,
                "checked_period": {"start": str(s.start_date), "end": str(s.end_date)}}
    except (KeyError, ValueError, TypeError, StopIteration, AttributeError) as exc:
        return {"valid": False, "errors": [{"code": "malformed_schedule", "message": str(exc)}]}
