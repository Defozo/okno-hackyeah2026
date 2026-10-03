"""Deterministic, explicitly synthetic catalogue and a verified public fact."""
from datetime import datetime, timezone
import json
from pathlib import Path
from api.catalog import SourceRecord, content_hash, transition_record

root = Path(__file__).parent
now = datetime.now(timezone.utc).isoformat()
records = []
for record_id, title, kind, hours, price, period in [
    ("synthetic-care-basic", "Opieka A · przykład fikcyjny", "care", {"start": "07:00", "end": "17:00"}, 0, "day"),
    ("synthetic-care-late", "Opieka popołudniowa · przykład fikcyjny", "care", {"start": "16:00", "end": "19:00"}, 2500, "hour"),
    ("synthetic-adult-care", "Dzienna opieka nad dorosłym · przykład fikcyjny", "adult_care", {"start": "07:00", "end": "17:30"}, 5000, "day"),
    ("synthetic-work-office", "Własna oferta biurowa · przykład fikcyjny", "work", {"start": "09:00", "end": "17:00"}, None, None),
    ("synthetic-course", "Kurs przygotowawczy · przykład fikcyjny", "course", {"start": "08:00", "end": "12:00"}, 30000, "once"),
    ("synthetic-care-unknown", "Usługa z nieznaną ceną · przykład fikcyjny", "care", {"start": "07:00", "end": "18:00"}, None, None),
]:
    fields = {name: {"value": value, "fetched_at": now, "checked_at": now, "status": "synthetic" if value is not None else "unknown"}
              for name, value in {"hours": hours, "cost_grosze": price, "cost_period": period}.items()}
    records.append(SourceRecord(id=record_id, title=title, kind=kind, synthetic=True, status="published", fetched_at=now, checked_at=now,
        content_hash=content_hash(title), license_or_terms="Autorski przykład testowy, CC0", fields=fields,
        missing_fields=[name for name, field in fields.items() if field["value"] is None] + ["admission"]).model_dump(mode="json"))
(root / "synthetic.json").write_text(json.dumps({"records": records}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# Factual verification against the observed source, never an admission claim.
public_path = root / "zlobek6.json"
if public_path.exists():
    data = json.loads(public_path.read_text(encoding="utf-8"))["records"][0]
    data["fields"]["hours"]["excerpt"] = "otwarta w godzinach od 6:00 do 17:00"
    data["valid_to"] = "2026-10-10"
    data["fields"]["hours"]["valid_to"] = "2026-10-10"
    record = SourceRecord.model_validate(data)
    if record.status == "draft":
        record = transition_record(record, "reviewed", "source-check-assisted-by-codex-2026-10-03")
        record = transition_record(record, "published", "source-check-assisted-by-codex-2026-10-03")
    public_path.write_text(json.dumps({"records": [record.model_dump(mode="json")]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"synthetic_records": len(records), "real_records": 1 if public_path.exists() else 0}))
