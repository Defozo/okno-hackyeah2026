"""Real OTP candidate hydration plus solver/validator, using synthetic care data."""
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time

from api.transit import hydrate_scenario_routes
from api.solver import solve_scenario

ROOT = Path(__file__).resolve().parents[2]


async def main():
    os.environ.setdefault("OTP_URL", "http://127.0.0.1:18440")
    scenario = json.loads((ROOT / "data/synthetic/two-dependents.json").read_text(encoding="utf-8"))
    scenario.update(start_date="2026-10-05", end_date="2026-10-05", minimum_paid_minutes=480, self_care_capacity=2)
    scenario["activities"][0]["step_minutes"] = 30
    scenario["location_coordinates"] = {
        "home": {"lat": 50.06455, "lon": 19.96144},
        "care": {"lat": 50.06577, "lon": 19.95957},
        "care-2": {"lat": 50.06594, "lon": 19.94587},
        "work": {"lat": 50.06435, "lon": 19.93868},
    }
    # Points identify transport test locations only, not actual childcare sites.
    # Prices, admission and schedules remain explicit synthetic assumptions.
    for leg in scenario["travel_legs"]:
        leg["mode"] = "transit"
        leg["bands"] = [{"start": "00:00", "end": "24:00", "minutes": 1, "cost_grosze": 0}]
    started = time.monotonic()
    hydrated = await hydrate_scenario_routes(scenario, budget_seconds=18)
    remaining = max(.01, 20 - (time.monotonic() - started))
    result = solve_scenario(hydrated["scenario"], budget_seconds=remaining) if hydrated["complete"] else None
    report = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "scenario": "Synthetic two dependents, two care places, real OSM/ZTP routes, one Monday, three allowed starts",
        "synthetic_care_and_prices": True,
        "otp_url": os.environ["OTP_URL"],
        "graph_sha256": json.loads((ROOT / "infra/otp/manifest.json").read_text(encoding="utf-8"))["graph_sha256"],
        "hydration": {key: value for key, value in hydrated.items() if key != "scenario"},
        "route_snapshot": hydrated["scenario"]["travel_legs"],
        "solver": result,
        "total_elapsed_seconds": round(time.monotonic() - started, 3),
    }
    (ROOT / "infra/otp/hydration-verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"complete": hydrated["complete"], "queries": hydrated["queries"],
                      "solver_status": result["status"] if result else None,
                      "alternatives": len(result.get("alternatives", [])) if result else 0,
                      "seconds": report["total_elapsed_seconds"]}))
    assert hydrated["complete"], "Inspect hydration-verification.json for routes or budget failure"
    assert hydrated["queries"] >= 18, "All candidate directions must be queried"
    assert result and result["status"] in {"OPTIMAL", "FEASIBLE"}
    assert result["alternatives"], "Expected a validator-accepted alternative"
    assert report["total_elapsed_seconds"] <= 20, "Shared analysis budget exceeded"


if __name__ == "__main__":
    asyncio.run(main())
