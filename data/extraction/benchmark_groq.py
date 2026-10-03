"""Run the optional versioned public-only extraction benchmark via psst.

No personal schedules are accepted by this command. Public fixtures are versioned
and selected from this repository. Errors count as failures, never as null facts.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time
from api.importer import extract_groq

HERE = Path(__file__).resolve().parent


def run_one(case):
    started = time.monotonic()
    try:
        result = extract_groq({"public": True, "source_url": case["source_url"], "text": case["text"]})
        actual = {"hours": result.hours.value.model_dump() if result.hours else None,
                  "cost_grosze": {"value": result.cost_grosze.value, "period": result.cost_grosze.period} if result.cost_grosze else None,
                  "cost_component": result.cost_grosze.component if result.cost_grosze else None}
        expected = {**case["expected"], "cost_component": case.get("expected_cost_component")}
        return {"id": case["id"], "passed": actual == expected, "actual": actual, "expected": expected, "seconds": round(time.monotonic() - started, 3)}
    except Exception as exc:
        return {"id": case["id"], "passed": False, "error_type": type(exc).__name__, "error": str(exc)[:240], "seconds": round(time.monotonic() - started, 3)}


def main():
    data = (HERE / "public-pl.json").read_bytes()
    cases = json.loads(data)["fixtures"]
    assert all(case["provenance"] == "public" for case in cases)
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(run_one, cases))
    report = {"run_at": datetime.now(timezone.utc).isoformat(), "model": os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
              "corpus_sha256": hashlib.sha256(data).hexdigest(), "public_cases": len(cases), "passed": sum(r["passed"] for r in results),
              "extractor_sha256": hashlib.sha256((HERE.parents[1] / "api/importer.py").read_bytes()).hexdigest(),
              "measurement": "Validated Groq extraction pipeline, including exact evidence, quantity, period and cost component; provider or validation errors count as failures",
              "composition": {"positive_hours": sum(c['expected']['hours'] is not None for c in cases),
                              "positive_prices": sum(c['expected']['cost_grosze'] is not None for c in cases),
                              "both_missing": sum(all(v is None for v in c['expected'].values()) for c in cases),
                              "negated_hours": sum('negated_hours' in c.get('tags', []) for c in cases),
                              "excluded_prices": sum('excluded_price' in c.get('tags', []) for c in cases)},
              "limitations": "Purposive corpus, still skewed toward missing data and childcare. Not a representative quality estimate or independent human audit. Errors count as failures.",
              "results": results}
    previous = HERE / "groq-benchmark.json"
    if previous.exists():
        history = HERE / "history"
        history.mkdir(exist_ok=True)
        prior = previous.read_bytes()
        (history / ("groq-" + hashlib.sha256(prior).hexdigest()[:16] + ".json")).write_bytes(prior)
    (HERE / "groq-benchmark.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "results"}))


if __name__ == "__main__":
    main()
