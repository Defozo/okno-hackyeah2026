"""Verify directional, time-dependent routing against the running real graph."""
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from api.routes import get_routes


async def main():
    os.environ.setdefault("OTP_URL", "http://127.0.0.1:18440")
    base = {"origin": "Rondo Mogilskie", "destination": "Teatr Słowackiego", "mode": "transit",
            "from_point": {"lat": 50.06577, "lon": 19.95957}, "to_point": {"lat": 50.06594, "lon": 19.94587},
            "cost_grosze": None, "buffer_minutes": 10, "handoff_minutes": 5}
    queries = [{**base, "id": "morning-0800", "when": "2026-10-05T08:00:00+02:00"},
               {**base, "id": "morning-0815", "when": "2026-10-05T08:15:00+02:00"},
               {**base, "id": "arrive-0900", "when": "2026-10-05T09:00:00+02:00", "arrive_by": True},
               {**base, "id": "return", "origin": base["destination"], "destination": base["origin"], "from_point": base["to_point"], "to_point": base["from_point"], "when": "2026-10-05T17:00:00+02:00"},
               {**base, "id": "expired", "when": "2027-01-04T08:00:00+01:00"}]
    started = time.monotonic()
    result = await get_routes({"queries": queries})
    report = {"run_at": datetime.now(timezone.utc).isoformat(), "elapsed_seconds": round(time.monotonic() - started, 3), "otp_url": os.environ["OTP_URL"], **result}
    destination = Path(__file__).parent / "live-verification.json"
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"routes": [{"id": r["id"], "status": r["status"], "minutes": r.get("minutes"), "modes": r.get("modes")} for r in result["routes"]], "elapsed_seconds": report["elapsed_seconds"]}))
    assert all(r["status"] == "ok" for r in result["routes"][:4]), "Live route failed; inspect report"
    assert result["routes"][4]["status"] == "stale"


if __name__ == "__main__":
    asyncio.run(main())
