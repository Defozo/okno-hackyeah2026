"""Reproducible synthetic 28-day reference. Run with the project's Python."""
import argparse
import copy
import hashlib
import json
import math
import os
import platform
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import_started = time.perf_counter()
from api.solver import solve_scenario
from api.solver.engine import _OPTIMIZATION_CP_PARAMETERS
import ortools
import_seconds = time.perf_counter() - import_started


def processor_name():
    if platform.processor():
        return platform.processor()
    path = Path("/proc/cpuinfo")
    if path.exists():
        for line in path.read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    return "unreported"


def reference():
    base = json.loads((ROOT / "data/synthetic/single-parent.json").read_text(encoding="utf-8"))
    base.update(title="Referencja wydajności 28 dni", end_date="2026-11-01", minimum_paid_minutes=9600,
                budget_grosze=1_000_000, self_care_capacity=3)
    original_need, original_resource = base["care_needs"][0], base["care_resources"][0]
    base["care_needs"], base["care_resources"] = [], []
    allowed = [[0, 1, 2, 7], [3, 4, 8], [5, 6, 9]]
    for index in range(3):
        need = copy.deepcopy(original_need)
        need.update(id=f"need-{index}", dependent_id=f"dependent-{index}", label=f"Osoba {index + 1}",
                    resource_ids=[f"resource-{rid}" for rid in allowed[index]], visit_order=index)
        base["care_needs"].append(need)
    for index in range(10):
        resource = copy.deepcopy(original_resource)
        resource.update(id=f"resource-{index}", label=f"Zasób syntetyczny {index + 1}",
                        kind="caregiver" if index >= 7 else "facility", capacity=1,
                        dependent_ids=[f"dependent-{i}" for i in range(3) if index in allowed[i]],
                        daily_cost_grosze=3000 + index * 100)
        base["care_resources"].append(resource)
    base["notes"] = "Syntetyczna referencja: 28 dni, 3 podopiecznych, 3 opiekunów i 7 placówek. Wspólny punkt opieki, jawne zgodności 4/3/3, 5 dozwolonych startów, 20 dni pracy. Brak zewnętrznych API."
    return base


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=10)
    parser.add_argument("--budget", type=float, default=20)
    parser.add_argument("--scenario", choices=["reference", "demo"], default="reference")
    parser.add_argument("--output")
    args = parser.parse_args()
    scenario = reference() if args.scenario == "reference" else json.loads((ROOT / "data/synthetic/single-parent.json").read_text(encoding="utf-8"))
    if args.scenario == "reference":
        (ROOT / "data/synthetic/benchmark-reference.json").write_text(json.dumps(scenario, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    samples = []
    for index in range(args.samples + 1):
        started = time.perf_counter()
        result = solve_scenario(scenario, budget_seconds=args.budget)
        sample = {"index": index, "kind": "first_call" if index == 0 else "warm", "seconds": round(time.perf_counter() - started, 6),
                  "status": result["status"], "baseline_status": result["baseline"]["status"],
                  "alternatives": len(result["alternatives"]), "all_validated": all(a["validation"]["valid"] for a in result["alternatives"]),
                  "warnings": result["warnings"]}
        samples.append(sample)
        print(json.dumps(sample, ensure_ascii=False), flush=True)
    timings = sorted(s["seconds"] for s in samples[1:])
    p95 = timings[math.ceil(.95 * len(timings)) - 1]
    report = {
        "measured_at": datetime.now(timezone.utc).isoformat(), "data_mode": "synthetic",
        "hardware": {"platform": platform.platform(), "processor": processor_name(), "logical_cpus": os.cpu_count()},
        "runtime": {"python": platform.python_version(), "ortools": ortools.__version__, "workers_per_solve": 1,
                    "optimization_parameters": dict(_OPTIMIZATION_CP_PARAMETERS), "diagnosis_parameters": "CP-SAT defaults; one worker, zero optimality gaps, 512 MiB solver memory limit"},
        "scenario": args.scenario,
        "reference": {"days": 28 if args.scenario == "reference" else 5, "dependents": len(scenario["care_needs"]),
                      "caregivers": sum(r["kind"] == "caregiver" for r in scenario["care_resources"]),
                      "care_resources": len(scenario["care_resources"]), "work_occurrences": 20 if args.scenario == "reference" else 5,
                      "allowed_resource_counts": [len(n["resource_ids"]) for n in scenario["care_needs"]], "start_choices": 5, "routing": "manual_synthetic"},
        "code_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in ["api/domain.py", "api/solver/engine.py", "api/solver/time.py", "api/validation/schedule.py"]},
        "budget_seconds": args.budget, "import_seconds": round(import_seconds, 6), "samples": samples,
        "warm_summary": {"count": len(timings), "median_seconds": round(statistics.median(timings), 6), "p95_seconds": p95,
                         "maximum_seconds": max(timings), "target_seconds": 3, "target_met": p95 <= 3},
        "limits": ["Pomiar całej analizy: normalizacja, diagnoza, optymalizacja wariantów i walidator; bez sieci OTP i HTTP.",
                   "Pierwsze wywołanie i koszt importów podano osobno; nie jest to pomiar czystego startu kontenera.",
                   "Host współdzielony z innymi pracami; p95 opisuje wyłącznie podaną próbę.",
                   "Nie jest to badanie z użytkowniczkami ani pomiar osiągniętego wpływu."]}
    output = Path(args.output) if args.output else ROOT / "data/synthetic" / ("benchmark-results.json" if args.scenario == "reference" else "benchmark-demo-results.json")
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["warm_summary"], ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
