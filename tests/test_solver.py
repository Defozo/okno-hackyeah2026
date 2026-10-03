import copy
import json
from pathlib import Path

import pytest

from api.solver import solve_scenario
from api.solver.time import local_minute
from api.validation import validate_schedule


@pytest.fixture
def scenario():
    return json.loads((Path(__file__).parents[1] / "data/synthetic/single-parent.json").read_text(encoding="utf-8"))


def test_reference_conflict_and_exact_staged_optimum(scenario):
    result = solve_scenario(scenario)
    assert result["baseline"]["status"] == "INFEASIBLE"
    assert {c["minutes"] for c in result["conflicts"]} == {45}
    first, robust = result["alternatives"]
    assert first["changes"][0]["to"] == "08:15"
    assert robust["changes"][0]["to"] == "08:00"
    assert first["metrics"]["paid_minutes"] == 2400
    assert first["metrics"]["changed_agreements"] == 1
    assert first["metrics"]["shift_minutes"] == 45
    assert robust["metrics"]["minimum_slack_minutes"] == 15
    assert first["metrics"]["cost_grosze"] == 19000
    assert all(a["validation"]["valid"] for a in result["alternatives"])
    assert all(p["optimal"] for p in first["proof"]["stages"])
    assert first["status"] == "awaiting_confirmation"
    assert result["baseline"]["diagnosis"]["sufficient_core"]
    assert result["baseline"]["diagnosis"]["minimal_core"] is False


def test_counteroffer_still_conflicts_15(scenario):
    scenario["activities"][0].update(start="08:30", negotiable=False)
    result = solve_scenario(scenario)
    assert result["status"] == "INFEASIBLE"
    assert {c["minutes"] for c in result["conflicts"]} == {15}


def test_closure_beyond_first_28_days_is_checked(scenario):
    scenario["end_date"] = "2026-11-09"
    scenario["budget_grosze"] = 1_000_000
    scenario["care_resources"][0]["availability"][0]["excluded_dates"] = ["2026-11-09"]
    result = solve_scenario(scenario)
    assert result["status"] == "INFEASIBLE"
    assert any(c.get("date") == "2026-11-09" for c in result["conflicts"])
    assert result["checked_period"]["end"] == "2026-11-09"


def test_missing_cost_never_becomes_zero(scenario):
    scenario["care_resources"][0]["daily_cost_grosze"] = None
    result = solve_scenario(scenario)
    assert not result["alternatives"]
    assert result["data_status"] == "needs_input"
    assert any(g["code"] == "unknown_cost" for g in result["data_gaps"])


def test_missing_time_requires_input(scenario):
    scenario["activities"][0]["start"] = None
    result = solve_scenario(scenario)
    assert result["status"] == "UNKNOWN"
    assert result["data_status"] == "needs_input"


def test_unknown_is_not_infeasible(scenario):
    result = solve_scenario(scenario, budget_seconds=0)
    assert result["status"] == "UNKNOWN"
    assert not result["alternatives"]


def test_budget_is_integer_and_hard(scenario):
    scenario["budget_grosze"] = 18_999
    assert solve_scenario(scenario)["status"] == "INFEASIBLE"
    scenario["budget_grosze"] = 19_000
    assert solve_scenario(scenario)["status"] == "OPTIMAL"


def test_stale_route_is_not_reused(scenario):
    scenario["travel_legs"][2]["source"] = {"valid_to": "2026-10-04"}
    result = solve_scenario(scenario)
    assert not result["alternatives"]
    assert result["data_status"] in ("needs_input", "stale")


def test_manual_time_band_is_rechecked_after_shift(scenario):
    scenario["travel_legs"][2]["bands"] = [
        {"start": "16:00", "end": "16:15", "minutes": 25, "cost_grosze": 400},
        {"start": "16:15", "end": "24:00", "minutes": 40, "cost_grosze": 400}]
    result = solve_scenario(scenario)
    assert result["alternatives"][0]["changes"][0]["to"] == "08:00"
    assert all(e["travel_minutes"] == 25 for e in result["alternatives"][0]["schedule"] if e.get("leg_id") == "work-care")


def test_forward_and_return_are_distinct(scenario):
    scenario["travel_legs"] = [leg for leg in scenario["travel_legs"] if leg["id"] != "work-care"]
    result = solve_scenario(scenario)
    assert not result["alternatives"]
    assert any(g["code"] == "missing_route" for g in result["data_gaps"])


def test_two_dependents_require_explicit_capacity(scenario):
    second = copy.deepcopy(scenario["care_needs"][0])
    second.update(id="care-2", dependent_id="child-2", label="Dziecko 2")
    scenario["care_needs"].append(second)
    scenario["care_resources"][0]["dependent_ids"].append("child-2")
    assert solve_scenario(scenario)["status"] == "INFEASIBLE"
    scenario["care_resources"][0]["capacity"] = 2
    # Outside external care the user also needs capacity for both children.
    assert solve_scenario(scenario)["status"] == "INFEASIBLE"
    scenario["self_care_capacity"] = 2
    result = solve_scenario(scenario)
    assert result["status"] == "OPTIMAL"
    assert result["alternatives"][0]["validation"]["valid"]


def test_caregiver_other_commitment_blocks_coverage(scenario):
    scenario["care_resources"][0]["kind"] = "caregiver"
    scenario["care_resources"][0]["busy"] = [{"start": "12:00", "end": "13:00"}]
    assert solve_scenario(scenario)["status"] == "INFEASIBLE"


def test_nonconfirmed_service_produces_dependency(scenario):
    scenario["care_resources"][0]["confirmed"] = False
    result = solve_scenario(scenario)
    assert result["alternatives"]
    assert any(d["kind"] == "care" for d in result["alternatives"][0]["dependencies"])
    assert result["alternatives"][0]["status"] == "awaiting_confirmation"


def test_expired_confirmation_is_not_confirmed(scenario):
    scenario["care_resources"][0]["confirmation_valid_to"] = "2026-10-07"
    result = solve_scenario(scenario)
    assert result["baseline"]["status"] == "INFEASIBLE"
    assert any(d["kind"] == "care" for d in result["alternatives"][0]["dependencies"])


def test_course_completion_is_a_hard_dependency(scenario):
    scenario["care_needs"] = []
    scenario["travel_legs"] = []
    scenario["activities"][0]["location"] = "home"
    scenario["activities"][0]["requires_activity_ids"] = ["course"]
    scenario["activities"].append({"id": "course", "label": "Kurs wymagany", "kind": "course", "location": "home",
        "start": "18:00", "duration_minutes": 60, "paid_minutes": 0, "dates": ["2026-10-07"]})
    assert solve_scenario(scenario)["status"] == "INFEASIBLE"
    scenario["start_date"] = "2026-10-04"
    scenario["activities"][1]["dates"] = ["2026-10-04"]
    assert solve_scenario(scenario)["status"] == "OPTIMAL"


def test_dst_nonexistent_and_ambiguous_times_require_choice():
    with pytest.raises(ValueError, match="nie istnieje"):
        local_minute(__import__("datetime").date(2026, 3, 29), "02:30")
    with pytest.raises(ValueError, match="dwukrotnie"):
        local_minute(__import__("datetime").date(2026, 10, 25), "02:30")
    day = __import__("datetime").date(2026, 10, 25)
    assert local_minute(day, "02:30", 1) - local_minute(day, "02:30", 0) == 60


@pytest.mark.parametrize("corruption", ["transfer", "duplicate", "cost", "paid", "route_time"])
def test_independent_validator_rejects_corruption(scenario, corruption):
    alternative = copy.deepcopy(solve_scenario(scenario)["alternatives"][0])
    if corruption == "transfer":
        alternative["schedule"] = [e for e in alternative["schedule"] if e.get("leg_id") != "care-work"]
    elif corruption == "duplicate":
        alternative["schedule"].append(next(e.copy() for e in alternative["schedule"] if e["kind"] == "care"))
    elif corruption == "cost":
        alternative["metrics"]["cost_grosze"] -= 1
    elif corruption == "paid":
        next(e for e in alternative["schedule"] if e["kind"] == "work")["paid_minutes"] -= 1
    else:
        next(e for e in alternative["schedule"] if e.get("leg_id") == "work-care")["travel_minutes"] -= 1
    assert not validate_schedule(scenario, alternative)["valid"]


def test_small_domain_matches_exhaustive_manual_arithmetic(scenario):
    feasible = []
    for start_minute in range(480, 541, 15):
        fixed = copy.deepcopy(scenario)
        fixed["activities"][0].update(start=f"{start_minute // 60:02d}:{start_minute % 60:02d}", negotiable=False)
        result = solve_scenario(fixed)
        expected = start_minute - 45 >= 420 and start_minute + 480 + 45 <= 1020
        assert bool(result["alternatives"]) == expected
        if expected:
            feasible.append(start_minute)
    optimum = solve_scenario(scenario)["alternatives"][0]
    assert optimum["metrics"]["shift_minutes"] == 540 - max(feasible)


def test_tightening_closure_does_not_add_solutions(scenario):
    possible = []
    for close in ["17:30", "17:15", "17:00", "16:45", "16:30"]:
        fixed = copy.deepcopy(scenario)
        fixed["care_resources"][0]["availability"][0]["end"] = close
        viable = set()
        for clock in ["08:00", "08:15", "08:30", "08:45", "09:00"]:
            fixed["activities"][0].update(start=clock, negotiable=False)
            if solve_scenario(fixed)["alternatives"]:
                viable.add(clock)
        possible.append(viable)
    assert all(b <= a for a, b in zip(possible, possible[1:]))


def test_overnight_dst_duration_cost_and_coverage(scenario):
    scenario.update(start_date="2026-10-24", end_date="2026-10-24", minimum_paid_minutes=480, budget_grosze=100_000)
    scenario["activities"][0].update(start="22:00", negotiable=False, dates=["2026-10-24"])
    scenario["care_resources"][0]["availability"] = [{"weekdays": list(range(7)), "start": "00:00", "end": "24:00"}]
    result = solve_scenario(scenario)
    assert result["status"] == "OPTIMAL"
    alternative = result["alternatives"][0]
    work = next(e for e in alternative["schedule"] if e["kind"] == "work")
    care = next(e for e in alternative["schedule"] if e["kind"] == "care")
    assert work["end"][11:16] == "05:00"  # Eight actual hours across the fall-back night.
    assert care["end"][11:16] == "05:45"
    assert alternative["metrics"]["cost_grosze"] == 6800  # Two calendar-day fees + two fares.


def fixture_named(name):
    return json.loads((Path(__file__).parents[1] / f"data/synthetic/{name}.json").read_text(encoding="utf-8"))


def test_two_places_and_departure_dependent_transport():
    scenario = fixture_named("two-dependents")
    result = solve_scenario(scenario)
    assert result["status"] == "OPTIMAL"
    alternative = result["alternatives"][0]
    assert alternative["changes"][0]["to"] == "08:00"
    assert {e["location"] for e in alternative["schedule"] if e["kind"] == "care"} == {"care", "care-2"}
    assert all(e["travel_minutes"] == 25 for e in alternative["schedule"] if e.get("leg_id") == "work-care")
    scenario["activities"][0].update(start="08:15", negotiable=False)
    fixed = solve_scenario(scenario)
    assert fixed["status"] == "INFEASIBLE"
    assert {p["minutes"] for p in fixed["conflicts"]} == {25, 30}


def test_explicit_handoff_covers_transfer_and_requires_confirmation():
    scenario = fixture_named("care-handoff")
    result = solve_scenario(scenario)
    assert result["status"] == "OPTIMAL"
    alternative = result["alternatives"][0]
    assert alternative["validation"]["valid"]
    assert alternative["metrics"]["paid_minutes"] == 2400
    assert alternative["metrics"]["cost_grosze"] == 36500
    assert {d["kind"] for d in alternative["dependencies"]} == {"care", "care_handoff"}
    assert len([e for e in alternative["schedule"] if e["kind"] == "care_transfer"]) == 5
    corrupted = copy.deepcopy(alternative)
    corrupted["schedule"] = [e for e in corrupted["schedule"] if e["kind"] != "care_transfer"]
    assert not validate_schedule(scenario, corrupted)["valid"]
    scenario["care_resources"][1]["busy"] = [{"start": "16:35", "end": "16:45"}]
    assert solve_scenario(scenario)["status"] == "INFEASIBLE"


def test_handoff_without_directed_transfer_is_not_feasible():
    scenario = fixture_named("care-handoff")
    scenario["care_needs"][0]["arrangements"][0]["handoffs"][0]["leg_id"] = "missing"
    result = solve_scenario(scenario)
    assert not result["alternatives"]
    assert any(p["code"] == "missing_route" for p in result["data_gaps"])


def test_unlimited_confirmation_is_not_inferred(scenario):
    scenario["care_resources"][0]["confirmation_valid_to"] = None
    result = solve_scenario(scenario)
    assert result["alternatives"][0]["status"] == "awaiting_confirmation"
    assert any(d["kind"] == "care" for d in result["alternatives"][0]["dependencies"])


def test_refused_proposal_never_reappears(scenario):
    scenario["forbidden_proposals"] = [{"activity_id": "work", "start": "08:15", "valid_from": "2026-10-05", "valid_to": "2026-10-09"}]
    result = solve_scenario(scenario)
    assert result["alternatives"][0]["changes"][0]["to"] == "08:00"
    assert all(a["changes"][0]["to"] != "08:15" for a in result["alternatives"])


def test_minimum_rest_counts_commute_on_both_sides(scenario):
    scenario.update(start_date="2026-10-05", end_date="2026-10-06", minimum_paid_minutes=960)
    scenario["activities"][0].update(start="09:00", negotiable=False)
    scenario["care_needs"] = []
    scenario["care_resources"] = []
    scenario["travel_legs"] = [
        {"id": "out", "origin": "home", "destination": "work", "bands": [{"minutes": 60}]},
        {"id": "back", "origin": "work", "destination": "home", "bands": [{"minutes": 60}]}]
    scenario["minimum_rest_minutes"] = 840  # Home at 18, departure at 08.
    assert solve_scenario(scenario)["status"] == "OPTIMAL"
    scenario["minimum_rest_minutes"] = 841
    assert solve_scenario(scenario)["status"] == "INFEASIBLE"


def test_remote_work_does_not_grant_self_care(scenario):
    scenario["activities"][0]["location"] = "home"
    scenario["care_resources"] = []
    scenario["travel_legs"] = []
    assert solve_scenario(scenario)["status"] == "INFEASIBLE"


def test_care_outside_work_can_use_self_care(scenario):
    scenario["activities"][0].update(location="home", start="09:00", negotiable=False)
    scenario["care_needs"][0].update(start="18:00", end="20:00")
    scenario["care_resources"] = []
    scenario["travel_legs"] = []
    result = solve_scenario(scenario)
    assert result["status"] == "OPTIMAL"
    assert result["alternatives"][0]["validation"]["valid"]


def test_validator_independently_checks_self_care_outside_work(scenario):
    alternative = solve_scenario(scenario)["alternatives"][0]
    scenario["self_care_capacity"] = 0
    result = validate_schedule(scenario, alternative)
    assert not result["valid"]
    assert any(e["code"] == "self_care_capacity" for e in result["errors"])


def test_adult_care_compatibility_is_required(scenario):
    scenario["care_needs"][0]["care_type"] = "adult"
    assert solve_scenario(scenario)["status"] == "INFEASIBLE"
    scenario["care_resources"][0]["care_types"] = ["adult"]
    assert solve_scenario(scenario)["status"] == "OPTIMAL"


def test_full_required_course_dates_cannot_be_truncated(scenario):
    scenario["activities"][0]["dates"] = ["2026-10-05", "2026-11-16"]
    result = solve_scenario(scenario)
    assert result["status"] == "UNKNOWN"
    assert any(e["code"] == "horizon_incomplete" for e in result["data_gaps"])


def test_one_time_and_occurrence_costs_are_distinct(scenario):
    scenario["activities"][0]["cost_grosze"] = 500
    scenario["care_resources"][0]["one_time_cost_grosze"] = 1200
    assert solve_scenario(scenario)["alternatives"][0]["metrics"]["cost_grosze"] == 20700
    scenario["activities"][0]["cost_frequency"] = "occurrence"
    assert solve_scenario(scenario)["alternatives"][0]["metrics"]["cost_grosze"] == 22700


def test_incomplete_optimization_is_feasible_not_optimal(scenario, monkeypatch):
    from api.solver import engine
    original = engine._run_model
    calls = 0

    def partial(model, deadline):
        nonlocal calls
        calls += 1
        # Baseline and first objective succeed, later objectives time out.
        return original(model, deadline) if calls <= 2 else ("UNKNOWN", None, None)

    monkeypatch.setattr(engine, "_run_model", partial)
    result = solve_scenario(scenario)
    assert result["status"] == "FEASIBLE"
    alternative = result["alternatives"][0]
    assert alternative["title"] == "Najlepszy znaleziony wariant"
    assert not alternative["proof"]["minimal_change_proven"]


@pytest.mark.parametrize("location", ["home", "care"])
def test_independent_care_without_work_and_complete_transfer(location):
    scenario = {
        "start_date": "2026-10-05", "end_date": "2026-10-05", "activities": [],
        "care_needs": [{"id": "adult", "dependent_id": "person", "label": "Bliska osoba", "care_type": "adult", "start": "09:00", "end": "10:00", "allow_self_care": False}],
        "care_resources": [{"id": "service", "label": "Dzienna opieka", "location": location, "care_types": ["adult"], "confirmed": True, "confirmation_valid_to": "2026-10-05", "daily_cost_grosze": 500}],
        "travel_legs": [{"id": "out", "origin": "home", "destination": "care", "bands": [{"minutes": 10, "cost_grosze": 100}]}, {"id": "back", "origin": "care", "destination": "home", "bands": [{"minutes": 10, "cost_grosze": 100}]}]
    }
    result = solve_scenario(scenario)
    assert result["status"] == "OPTIMAL", result
    alternative = result["alternatives"][0]
    assert alternative["status"] == "confirmed"
    assert alternative["metrics"]["cost_grosze"] == (500 if location == "home" else 900)
    assert alternative["validation"]["valid"]
    if location == "care":
        alternative["schedule"] = [e for e in alternative["schedule"] if not (e["kind"] == "travel" and e["journey"] == "pickup")]
        assert not validate_schedule(scenario, alternative)["valid"]


def test_independent_full_day_home_care_supports_work_and_weekend(scenario):
    scenario.update(start_date="2026-10-05", end_date="2026-10-10", budget_grosze=100000)
    scenario["activities"][0].update(location="home", negotiable=False)
    scenario["care_needs"][0].update(allow_self_care=False)
    scenario["care_resources"][0].update(location="home", availability=[{"weekdays": list(range(7)), "start": "00:00", "end": "24:00"}])
    scenario["travel_legs"] = []
    result = solve_scenario(scenario)
    assert result["status"] == "OPTIMAL", result
    assert any(e["kind"] == "care" and e["date"] == "2026-10-10" for e in result["alternatives"][0]["schedule"])
    assert result["alternatives"][0]["validation"]["valid"]


def test_caregiver_capacity_does_not_allow_simultaneous_travel_from_two_places():
    scenario = fixture_named("care-handoff")
    scenario["self_care_capacity"] = 2
    scenario["care_resources"][1].update(capacity=2, dependent_ids=["child-1", "child-2"])
    second_need = copy.deepcopy(scenario["care_needs"][0])
    second_need.update(id="second", dependent_id="child-2", resource_ids=["second-place"], visit_order=1)
    second_need["arrangements"][0]["resource_ids"] = ["second-place", "helper"]
    second_need["arrangements"][0]["handoffs"][0]["leg_id"] = "second-home"
    scenario["care_needs"].append(second_need)
    second_resource = copy.deepcopy(scenario["care_resources"][0])
    second_resource.update(id="second-place", location="second-place", dependent_ids=["child-2"])
    scenario["care_resources"].append(second_resource)
    scenario["travel_legs"][1]["origin"] = "second-place"
    scenario["travel_legs"].extend([
        {"id": "between", "origin": "care", "destination": "second-place", "bands": [{"minutes": 5}]},
        {"id": "second-home", "origin": "second-place", "destination": "home", "bands": [{"minutes": 10}]}])
    result = solve_scenario(scenario)
    assert not result["alternatives"]
    core = result["baseline"].get("diagnosis", {}).get("sufficient_core", [])
    assert result["status"] in ("INFEASIBLE", "UNKNOWN")  # Missing routes of other organizations remain explicit.


def test_validator_detects_concurrent_self_care_on_day_without_work(scenario):
    scenario["end_date"] = "2026-10-10"
    alternative = solve_scenario(scenario)["alternatives"][0]
    second = copy.deepcopy(scenario["care_needs"][0])
    second.update(id="saturday", dependent_id="person-2", dates=["2026-10-10"])
    scenario["care_needs"].append(second)
    validation = validate_schedule(scenario, alternative)
    assert not validation["valid"]
    assert any(e["code"] == "self_care_capacity" for e in validation["errors"])


def test_custom_objective_order_does_not_claim_absolute_smallest_change(scenario):
    scenario["objective_order"] = ["cost_grosze", "changed_agreements", "shift_minutes"]
    alternative = solve_scenario(scenario)["alternatives"][0]
    assert alternative["title"] == "Najlepszy według priorytetów"
    assert not alternative["proof"]["minimal_change_proven"]
    assert all(stage["optimal"] for stage in alternative["proof"]["stages"])


def test_shared_agreement_depends_on_every_activity(scenario):
    scenario["activities"][0]["weekdays"] = [0, 2, 4]
    second = copy.deepcopy(scenario["activities"][0])
    second.update(id="other-days", weekdays=[1, 3])
    scenario["activities"].append(second)
    alternative = solve_scenario(scenario)["alternatives"][0]
    assert alternative["metrics"]["changed_agreements"] == 1
    dependency = next(d for d in alternative["dependencies"] if d["kind"] == "employer")
    assert {a["activity_id"] for a in dependency["proposal"]["activities"]} == {"work", "other-days"}
    assert "activities.other-days.start" in dependency["fields"]


def test_known_unknown_cost_is_unknown_not_impossibility(scenario):
    scenario["care_resources"][0]["daily_cost_grosze"] = None
    result = solve_scenario(scenario)
    assert result["status"] == "UNKNOWN"
    assert result["data_status"] == "needs_input"


def test_refused_handoff_is_excluded_only_during_its_scope():
    scenario = fixture_named("care-handoff")
    original = solve_scenario(scenario)["alternatives"][0]
    scenario["care_needs"][0]["arrangements"][0]["unavailable"] = [{"weekdays": list(range(7)), "valid_from": "2026-10-07", "valid_to": "2026-10-07"}]
    assert solve_scenario(scenario)["status"] == "INFEASIBLE"
    assert not validate_schedule(scenario, original)["valid"]
    scenario["end_date"] = "2026-10-06"
    scenario["minimum_paid_minutes"] = 960
    assert solve_scenario(scenario)["status"] == "OPTIMAL"


def test_delay_probe_rechecks_chosen_organization(scenario):
    result = solve_scenario(scenario)
    ordinary, robust = result["alternatives"]
    assert ordinary["robustness"][0]["feasible"] is False
    assert robust["robustness"][0]["feasible"] is True
    assert ordinary["robustness"][0]["conflicts"]
    handoff = solve_scenario(fixture_named("care-handoff"))["alternatives"][0]
    assert handoff["metrics"]["minimum_slack_minutes"] == 0
    # Zero slack at the start of a fixed handoff does not make every travel delay
    # infeasible. Replay checks actual transfers and care end, not just min slack.
    assert handoff["robustness"][0]["feasible"] is True


def test_fixed_model_conflict_has_explicit_empty_core(scenario, monkeypatch):
    from api.solver import engine
    original = engine._build_model

    def conflicting(*args, **kwargs):
        built = original(*args, **kwargs)
        built[0].add(0 == 1)
        return built

    monkeypatch.setattr(engine, "_build_model", conflicting)
    result = solve_scenario(scenario)
    assert result["status"] == "INFEASIBLE"
    assert result["baseline"]["diagnosis"]["fixed_model_conflict"] is True
    assert result["baseline"]["diagnosis"]["sufficient_core"] == []


def test_invalid_cp_model_is_rejected_before_search():
    import time
    from ortools.sat.python import cp_model
    from api.solver.engine import _run_model
    model = cp_model.CpModel()
    result = model.new_int_var(0, 1, "result")
    model.add_division_equality(result, 1, 0)
    status, solver, error = _run_model(model, time.monotonic() + 1)
    assert status == "MODEL_INVALID"
    assert solver is None
    assert error


def test_actual_ambiguous_shift_requires_and_honors_fold(scenario):
    scenario.update(start_date="2026-10-25", end_date="2026-10-25", minimum_paid_minutes=60)
    scenario["activities"][0].update(start="02:30", dates=["2026-10-25"], negotiable=False,
        duration_minutes=60, paid_minutes=60, location="home")
    scenario["care_needs"], scenario["care_resources"], scenario["travel_legs"] = [], [], []
    assert solve_scenario(scenario)["data_status"] == "needs_input"
    scenario["activities"][0]["start_fold"] = 0
    first = solve_scenario(scenario)["alternatives"][0]["schedule"][0]
    assert first["start"].endswith("+02:00")
    assert first["end"].endswith("+01:00")
    assert first["start"][11:16] == first["end"][11:16] == "02:30"


def test_prior_optimum_bound_is_not_reused_when_earlier_objective_changes():
    scenario = fixture_named("care-handoff")
    scenario["activities"][0].update(negotiable=True, start_min="08:15", start_max="09:00")
    scenario["care_resources"][1]["availability"][0]["start"] = "16:00"
    ordinary, robust, *_ = solve_scenario(scenario)["alternatives"]
    assert ordinary["metrics"]["changed_agreements"] == 1
    assert ordinary["metrics"]["shift_minutes"] == 45
    assert robust["title"] == "Większy zapas czasu"
    assert robust["metrics"]["changed_agreements"] == 2
    assert robust["metrics"]["shift_minutes"] == 0
    assert robust["validation"]["valid"]


@pytest.mark.parametrize("name", ["single-parent", "two-dependents", "care-handoff", "benchmark-reference"])
def test_certified_coverage_elimination_matches_general_model(name, monkeypatch):
    from api.solver import engine
    scenario = fixture_named(name)
    specialized = solve_scenario(scenario)
    monkeypatch.setattr(engine, "_care_coverage_is_implied", lambda *_: False)
    general = solve_scenario(scenario)
    assert specialized["status"] == general["status"] == "OPTIMAL"
    fields = ("changed_agreements", "shift_minutes", "cost_grosze", "paid_minutes")
    expected = [tuple(a["metrics"][field] for field in fields) for a in general["alternatives"]]
    actual = [tuple(a["metrics"][field] for field in fields) for a in specialized["alternatives"]]
    assert actual == expected
    assert all(a["validation"]["valid"] for a in specialized["alternatives"])


@pytest.mark.parametrize("name", ["single-parent", "two-dependents", "care-handoff", "benchmark-reference"])
def test_optimization_search_settings_preserve_lexicographic_optima(name, monkeypatch):
    from api.solver import engine
    scenario = fixture_named(name)
    tuned = solve_scenario(scenario)
    monkeypatch.setattr(engine, "_OPTIMIZATION_CP_PARAMETERS", {})
    default = solve_scenario(scenario)
    assert tuned["status"] == default["status"] == "OPTIMAL"
    assert tuned["baseline"]["status"] == default["baseline"]["status"]
    assert len(tuned["alternatives"]) == len(default["alternatives"])
    for actual, expected in zip(tuned["alternatives"], default["alternatives"]):
        assert actual["validation"]["valid"] and expected["validation"]["valid"]
        assert actual["proof"]["minimal_change_proven"] == expected["proof"]["minimal_change_proven"]
        assert [(p["objective"], p["value"], p["optimal"]) for p in actual["proof"]["stages"]] == [
            (p["objective"], p["value"], p["optimal"]) for p in expected["proof"]["stages"]]
