"""Acquire bounded, source-exact labelled cases. Never modify historical results."""
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
from api.importer import extract_rules, fetch_public, make_draft, Extraction
from api.catalog import transition_record

ROOT = Path(__file__).resolve().parents[2]
URLS = [
    "https://pokazswiat.pl/",
    "https://chatkakajtka.pl/%C5%BC%C5%82obek/cennik",
    "https://tup-tup.com.pl/rodzic/cennik",
    "https://kidsspace.pl/barska-zlobek/",
    "https://ojp.uws.edu.pl/oferta/kurs-roczny",
    "https://snow4fun.com.pl/kursy-6-dniowe/",
    "https://lubienkujawski.pl/komunikat-jutro-piatek-kasa-urzedu-miejskiego-bedzie-przejsciowo-nieczynna-w-godzinach-rannych/",
    "https://www.future-gorzow.pl/cennik/cennik-kursow/",
    "https://szkolajazdy.krakow.pl/cennik/",
    "https://cok.agh.edu.pl/oplaty/zasady-pobierania-oplat/najczesciej-zadawane-pytania-faq",
    "https://www.bip.krakow.pl/?news_id=247942",
]


def acquire():
    out = ROOT / ".runtime/corpus-expansion-pages.json"
    docs = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    for url in URLS:
        if url in docs:
            continue
        try:
            docs[url] = fetch_public(url)
            print(json.dumps({"url": url, "characters": len(docs[url]["text"])}), flush=True)
        except Exception as error:
            print(json.dumps({"url": url, "error": type(error).__name__, "reason": str(error)}), flush=True)
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps(docs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build():
    here = ROOT / "data/extraction"
    original = here / "public-pl-original50.json"
    if not original.exists():
        shutil.copyfile(here / "public-pl.json", original)
    old_report = here / "groq-benchmark-original50.json"
    if not old_report.exists():
        shutil.copyfile(here / "groq-benchmark.json", old_report)
    data = json.loads(original.read_text(encoding="utf-8"))
    docs = json.loads((ROOT / ".runtime/corpus-expansion-pages.json").read_text(encoding="utf-8"))
    # Labels are explicit annotations made before running either extractor.
    # Regex only locates the verbatim substring; it never rewrites the quotation.
    specifications = [
        (0, r"810 zł\s+Czesne/miesiąc", None, (81000, "month"), ["price", "month"]),
        (0, r"Godziny pobytu: 6:30 – 17:00", ("06:30", "17:00"), None, ["hours"]),
        (0, r"Godziny pobytu: 6:30 – 13:00", ("06:30", "13:00"), None, ["hours"]),
        (1, r"Dzienna stawka żywieniowa:\s*21,00\s*zł\s*/dzień", None, (2100, "day"), ["price", "day"]),
        (2, r"Opieka poza godzinami pracy placówki 50 zł/h\.", None, (5000, "hour"), ["price", "hour"]),
        (3, r"Jednorazowa opłata rekrutacyjna 500 zł płatna wyłącznie przy zapisie dziecka\.", None, (50000, "once"), ["price", "once"]),
        (3, r"Wyżywienie – ok\. 400 zł / mies\.", None, None, ["approximate_price", "missing_cost"]),
        (3, r"Godziny 7:00–17:00", ("07:00", "17:00"), None, ["hours"]),
        (4, r"Cena kursu: 5000 PLN", None, (500000, "once"), ["price", "once", "course"]),
        (5, r"CENA ZA KURS\s+1300 zł", None, (130000, "once"), ["price", "once", "course"]),
        (5, r"Godziny otwarcia: 8:30 – 22:00", ("08:30", "22:00"), None, ["hours"]),
        (5, r"Godziny otwarcia: 8:30 – 16:00; 18:00 – 21:00", None, None, ["multiple_intervals", "missing_hours"]),
        (6, r"w godzinach od 7:30 do 10:00 kasa Urzędu Miejskiego w Lubieniu Kujawskim będzie nieczynna\.", None, None, ["negation", "negated_hours", "missing_hours"]),
        (7, r"CENA NIE obejmuje Pakietu Edukacyjnego 295 pln", None, None, ["negation", "excluded_price", "missing_cost"]),
        (8, r"1 godz\. jazdy na placu\s+170,00 zł", None, (17000, "hour"), ["price", "hour", "course"]),
        (9, r"Wysokość stawki za jedną godzinę zajęć wynosi 10 zł\.", None, (1000, "hour"), ["price", "hour", "university"]),
        (10, r"miesięczna ryczałtowa opłata,[\s\S]{0,180}?1 500 zł", None, (150000, "month"), ["price", "month", "public_contract"]),
    ]
    additions = []
    component_labels = {51: "care", 54: "food", 55: "additional_care", 56: "enrollment", 59: "course",
                        60: "course", 65: "course", 66: "course", 67: "care"}
    for index, (source_index, pattern, hours, cost, tags) in enumerate(specifications, 51):
        doc = docs[URLS[source_index]]
        match = re.search(pattern, doc["text"])
        if not match:
            raise ValueError(f"Public source no longer contains case {index}: {pattern}")
        snippet = match.group(0)
        additions.append({"id": f"public-{index:03}", "provenance": "public", "source_url": doc["source_url"],
            "fetched_at": doc["fetched_at"], "source_content_hash": doc["content_hash"], "text": snippet,
            "excerpt_sha256": hashlib.sha256(snippet.encode()).hexdigest(),
            "expected": {"hours": {"start": hours[0], "end": hours[1]} if hours else None,
                         "cost_grosze": {"value": cost[0], "period": cost[1]} if cost else None}, "tags": tags,
            "expected_cost_component": component_labels.get(index),
            "label_note": "AI-assisted annotation of literal excerpt, not independent human audit; no claim of current admission or applicability to a user"})
    data.update({"scope": "Purposive public Polish excerpts covering positive prices/hours, absent facts, explicit negation and ambiguity; not representative",
                 "annotation_policy": "Labels set before extraction. Excerpts are exact substrings of sanitized fetched HTML; no wording rewritten.",
                 "extended_at": datetime.now(timezone.utc).isoformat(), "fixtures": data["fixtures"] + additions})
    (here / "public-pl.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"public_cases": len(data["fixtures"]), "added": len(additions)}))


def catalog_example():
    here = ROOT / "data/extraction"
    cases = {c["id"]: c for c in json.loads((here / "public-pl.json").read_text(encoding="utf-8"))["fixtures"]}
    docs = json.loads((ROOT / ".runtime/corpus-expansion-pages.json").read_text(encoding="utf-8"))
    doc = docs[URLS[3]]
    hours = extract_rules(cases["public-058"]["text"]).hours
    cost = extract_rules(cases["public-056"]["text"]).cost_grosze
    assert hours and cost and cost.component == "enrollment"
    record = make_draft(doc, Extraction(hours=hours, cost_grosze=cost), "kids-space-barska-enrollment",
        "KIDS SPACE Barska: opłata rekrutacyjna", "care", "Krótkie fakty z publicznej strony placówki; brak redystrybucji pełnej strony, brak potwierdzenia przyjęcia")
    record.valid_to = date(2026, 10, 10)
    record.missing_fields = ["ongoing_care_cost", "food_cost", "admission", "date_exceptions"]
    for field in record.fields.values():
        field.valid_to = record.valid_to
    reviewer = "asystent AI Codex: porównanie dokładnych fragmentów z pobraną publiczną stroną; bez niezależnego audytu człowieka"
    record = transition_record(record, "reviewed", reviewer)
    record = transition_record(record, "published", reviewer)
    (ROOT / "data/catalog/kids-space-barska.json").write_text(json.dumps({"records": [record.model_dump(mode="json")]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    acquire()
    build()
    catalog_example()
