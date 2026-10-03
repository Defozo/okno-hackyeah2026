"""Public catalogue snapshots and operator-only editorial transitions."""
from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from api.calendar_clock import warsaw_today

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "data" / "catalog"


class FieldEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: Any = None
    source_url: str | None = None
    excerpt: str | None = Field(None, max_length=1000)
    fetched_at: datetime
    checked_at: datetime | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    status: Literal["unknown", "extracted", "reviewed", "stale", "synthetic"] = "unknown"


class SourceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,99}$")
    title: str = Field(max_length=200)
    kind: Literal["care", "adult_care", "work", "course", "directory"]
    synthetic: bool = False
    status: Literal["draft", "reviewed", "published", "stale", "withdrawn"] = "draft"
    source_url: str | None = None
    fetched_at: datetime
    checked_at: datetime | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    content_hash: str
    license_or_terms: str
    fields: dict[str, FieldEvidence]
    missing_fields: list[str] = Field(default_factory=list)
    admission_confirmed: Literal[False] = False
    editorial_history: list[dict] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_sources(self):
        if not self.synthetic and not self.source_url:
            raise ValueError("Publiczny rekord wymaga URL źródła")
        if self.status in {"reviewed", "published"}:
            if self.checked_at is None:
                raise ValueError("Publikacja wymaga odnotowanego sprawdzenia")
            for name, field in self.fields.items():
                if field.value is not None and not self.synthetic:
                    if not field.source_url or not field.excerpt or field.status != "reviewed" or not field.checked_at:
                        raise ValueError(f"Pole {name} wymaga źródła i przeglądu")
        return self


def load_catalog(mode: str = "synthetic", *, directory: Path | None = None, today: date | None = None) -> dict:
    if mode not in {"synthetic", "verified", "all"}:
        raise ValueError("Nieznany tryb katalogu")
    directory = directory or Path(os.getenv("CATALOG_PATH", str(DEFAULT_PATH)))
    today = today or warsaw_today()
    paths = [directory] if directory.is_file() else sorted(directory.glob("*.json"))
    records = []
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        for item in (payload.get("records", []) if isinstance(payload, dict) else payload):
            record = SourceRecord.model_validate(item)
            if record.status not in {"published", "stale"}:
                continue
            if mode == "synthetic" and not record.synthetic or mode == "verified" and record.synthetic:
                continue
            data = record.model_dump(mode="json")
            if record.valid_to and record.valid_to < today:
                data["status"] = "stale"
            for name, field in record.fields.items():
                if field.value is not None and (field.status == "stale" or field.valid_to and field.valid_to < today):
                    data["fields"][name]["status"] = "stale"
                    data["status"] = "stale"
            data["admission_note"] = "Przykład fikcyjny" if record.synthetic else "Rekord nie potwierdza wolnego miejsca ani przyjęcia. Godziny i cenę potwierdź dla swojego okresu."
            records.append(data)
    return {"mode": mode, "records": records, "count": len(records), "checked_on": today.isoformat(),
            "notice": "Dane demonstracyjne" if mode == "synthetic" else "Dane publiczne z datą sprawdzenia; każde przyjęcie wymaga odrębnego uzgodnienia"}


TRANSITIONS = {"draft": {"reviewed", "withdrawn"}, "reviewed": {"published", "draft", "withdrawn"}, "published": {"stale", "withdrawn"}, "stale": {"draft", "withdrawn"}, "withdrawn": {"draft"}}


def transition_record(record: SourceRecord, status: str, reviewer: str, *, now: datetime | None = None) -> SourceRecord:
    if status not in TRANSITIONS[record.status]:
        raise ValueError(f"Niedozwolona zmiana {record.status} -> {status}")
    if not reviewer.strip():
        raise ValueError("Wymagany identyfikator redaktora")
    if status in {"reviewed", "published"} and not record.synthetic:
        # Delayed import avoids the importer/catalog module dependency cycle.
        from api.importer import validate_extraction
        hours = record.fields.get("hours")
        cost = record.fields.get("cost_grosze")
        if hours and hours.value is not None:
            validate_extraction({"hours": {"value": hours.value, "evidence": hours.excerpt}}, hours.excerpt or "")
        if cost and cost.value is not None:
            period = record.fields.get("cost_period")
            component = record.fields.get("cost_component")
            if not period or not component:
                raise ValueError("Przegląd ceny wymaga okresu i określenia składnika kosztu")
            validate_extraction({"cost_grosze": {"value": cost.value, "period": period.value,
                "component": component.value, "evidence": cost.excerpt}}, cost.excerpt or "")
    now = now or datetime.now(timezone.utc)
    data = record.model_dump(mode="json")
    if status == "reviewed":
        data["checked_at"] = now.isoformat()
        for field in data["fields"].values():
            if field["value"] is not None:
                field["checked_at"] = now.isoformat()
                field["status"] = "synthetic" if record.synthetic else "reviewed"
    data["editorial_history"].append({"from": record.status, "to": status, "reviewer": reviewer.strip(), "at": now.isoformat()})
    data["status"] = status
    return SourceRecord.model_validate(data)


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
