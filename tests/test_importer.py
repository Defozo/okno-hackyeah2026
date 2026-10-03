from datetime import date
import json
from pathlib import Path
import socket
import pytest
from pydantic import ValidationError
from api.catalog import SourceRecord, load_catalog, transition_record
from api.importer import ImportRejected, extract_rules, sanitize_html, validate_extraction, validate_public_url

ROOT = Path(__file__).resolve().parents[1]


def resolver(ip):
    return lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443))]


@pytest.mark.parametrize("url", ["http://bip.krakow.pl/", "https://evil.test/", "https://bip.krakow.pl.evil.test/", "https://user:pass@bip.krakow.pl/", "https://bip.krakow.pl:8443/", "https://bip.krakow.pl/#fragment"])
def test_url_allowlist(url):
    with pytest.raises(ImportRejected):
        validate_public_url(url, resolver=resolver("8.8.8.8"))


@pytest.mark.parametrize("ip", ["127.0.0.1", "10.0.0.1", "192.168.1.1", "169.254.169.254", "::1", "fe80::1", "::ffff:127.0.0.1"])
def test_dns_private_ranges_rejected(ip):
    with pytest.raises(ImportRejected):
        validate_public_url("https://bip.krakow.pl/", resolver=resolver(ip))


def test_sanitization_discards_active_content():
    assert sanitize_html('<script>sendSecrets()</script><p>Godziny 07:00-17:00</p><iframe>hidden</iframe>') == "Godziny 07:00-17:00"


def test_unbacked_hallucination_and_negation_rejected():
    payload = {"hours": {"value": {"start": "07:00", "end": "17:00"}, "evidence": "Godziny 07:00-17:00"}}
    with pytest.raises(ImportRejected):
        validate_extraction(payload, "Nie podano godzin")
    payload["hours"]["evidence"] = "Nie pracujemy w godzinach 07:00-17:00"
    with pytest.raises(ImportRejected):
        validate_extraction(payload, payload["hours"]["evidence"])


def test_money_must_be_grounded():
    with pytest.raises(ImportRejected):
        validate_extraction({"cost_grosze": {"value": 0, "period": "day", "evidence": "Koszt do ustalenia"}}, "Koszt do ustalenia")


def test_cost_period_must_be_grounded():
    text = "Opłata: 20 zł/godzinę."
    with pytest.raises(ImportRejected):
        validate_extraction({"cost_grosze": {"value": 2000, "period": "month", "evidence": text}}, text)


@pytest.mark.parametrize("text", ["Godziny zamknięcia placówki 12:00-14:00.",
    "Placówka będzie nieczynna w godzinach 12:00-14:00.",
    "Godziny otwarcia: 12:00-14:00; 16:00-18:00."])
def test_closed_or_multiple_ranges_cannot_become_single_open_range(text):
    assert extract_rules(text).hours is None
    with pytest.raises(ImportRejected):
        validate_extraction({"hours": {"value": {"start": "12:00", "end": "14:00"}, "evidence": "12:00-14:00"}}, text)


@pytest.mark.parametrize("text,value,period,evidence", [
    ("Wyżywienie – ok. 400 zł / mies.", 40000, "month", "400 zł / mies."),
    ("Opłata miesięczna 1500 zł, dzienna opłata za wyżywienie 12 zł za dzień.", 150000, "day", "1500 zł"),
    ("Miesięczna opłata 0 zł lub 1500 zł zależnie od świadczenia.", 0, "month", "0 zł"),
])
def test_cropped_evidence_cannot_remove_price_qualification(text, value, period, evidence):
    with pytest.raises(ImportRejected):
        validate_extraction({"cost_grosze": {"value": value, "period": period, "evidence": evidence}}, text)


def test_food_cost_keeps_its_component_and_public_review_revalidates():
    from api.importer import make_draft
    text = "Opłata za wyżywienie 12 zł za dzień."
    facts = extract_rules(text)
    assert facts.cost_grosze.component == "food"
    record = make_draft({"text": text, "source_url": "https://bip.krakow.pl/", "fetched_at": "2026-10-03T12:00:00Z", "content_hash": "test"}, facts, "meal", "Wyżywienie", "care", "Test")
    assert record.fields["cost_component"].value == "food"
    assert transition_record(record, "reviewed", "tester").status == "reviewed"
    record.fields["cost_period"].value = "month"
    with pytest.raises(ImportRejected):
        transition_record(record, "reviewed", "tester")


@pytest.mark.parametrize("text", ["Opłata: od 20 zł/godzinę.", "Cena około 20 zł/godzinę.", "Koszt 10-20 zł/godzinę."])
def test_inexact_cost_cannot_become_exact_budget_input(text):
    with pytest.raises(ImportRejected):
        validate_extraction({"cost_grosze": {"value": 2000, "period": "hour", "evidence": text}}, text)
    assert extract_rules(text).cost_grosze is None


def test_csv_preserves_nulls_evidence_and_draft_review(tmp_path, monkeypatch):
    import csv
    from api import importer
    monkeypatch.setattr(importer, "validate_public_url", lambda url: ("bip.krakow.pl", "8.8.8.8"))
    row = {"id": "csv-care", "title": "Placówka", "kind": "care", "source_url": "https://bip.krakow.pl/",
           "fetched_at": "2026-10-03T12:00:00Z", "terms": "Fakty do przeglądu", "hours_start": "07:00", "hours_end": "17:00",
           "hours_excerpt": "Godziny otwarcia 07:00-17:00", "cost_grosze": "", "valid_to": "2026-10-10"}
    path = tmp_path / "source.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
    records = importer.import_csv(path)
    assert len(records) == 1 and records[0].status == "draft"
    assert not records[0].admission_confirmed
    assert records[0].fields["hours"].excerpt == row["hours_excerpt"]
    assert records[0].fields["cost_grosze"].value is None
    assert records[0].valid_to == date(2026, 10, 10)


def test_publication_needs_review_and_admission_always_false():
    item = load_catalog("verified", today=date(2026, 10, 3))["records"][0]
    item.pop("admission_note")
    item["admission_confirmed"] = True
    with pytest.raises(ValidationError):
        SourceRecord.model_validate(item)
    item["admission_confirmed"] = False
    item["fields"]["hours"]["excerpt"] = None
    with pytest.raises(ValidationError):
        SourceRecord.model_validate(item)


def test_catalog_ages_without_reconfirming_admission():
    records = load_catalog("verified", today=date(2026, 10, 31))["records"]
    assert records and all(r["status"] == "stale" and not r["admission_confirmed"] for r in records)


def test_expired_essential_field_marks_record_stale(tmp_path):
    item = load_catalog("verified", today=date(2026, 10, 3))["records"][0]
    item.pop("admission_note")
    item["valid_to"] = "2026-12-31"
    item["fields"]["hours"]["valid_to"] = "2026-10-04"
    (tmp_path / "source.json").write_text(json.dumps({"records": [item]}), encoding="utf-8")
    record = load_catalog("verified", directory=tmp_path, today=date(2026, 10, 5))["records"][0]
    assert record["status"] == "stale"
    assert record["fields"]["hours"]["status"] == "stale"


FIXTURES = []
for name in ["public-pl.json", "adversarial-pl.json"]:
    FIXTURES.extend(json.loads((ROOT / "data" / "extraction" / name).read_text(encoding="utf-8"))["fixtures"])


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda f: f["id"])
def test_labeled_polish_extraction(fixture):
    result = extract_rules(fixture["text"])
    actual = {"hours": result.hours.value.model_dump() if result.hours else None,
              "cost_grosze": {"value": result.cost_grosze.value, "period": result.cost_grosze.period} if result.cost_grosze else None}
    assert actual == fixture["expected"]
    if "expected_cost_component" in fixture:
        assert (result.cost_grosze.component if result.cost_grosze else None) == fixture["expected_cost_component"]
    for fact in [result.hours, result.cost_grosze]:
        if fact:
            assert fact.evidence in fixture["text"]
