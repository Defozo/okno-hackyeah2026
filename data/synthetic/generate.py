"""Recreate additional synthetic fixtures from the reference, without external data."""
import copy
import json
from pathlib import Path

HERE = Path(__file__).parent
base = json.loads((HERE / "single-parent.json").read_text(encoding="utf-8"))


def save(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


two = copy.deepcopy(base)
two["title"] = "Dwie placówki i zmienny rozkład"
two["budget_grosze"] = 100_000
two["self_care_capacity"] = 2
two["notes"] = "Scenariusz syntetyczny. Dwoje podopiecznych, dwie placówki. O 16:15 czas powrotu rośnie o 15 minut. Zmiana na 08:15 nie wystarcza; 08:00 umożliwia oba odbiory."
second = copy.deepcopy(two["care_needs"][0])
second.update(id="need-2", dependent_id="child-2", label="Dziecko 2", resource_ids=["daycare-2"], visit_order=1)
two["care_needs"].append(second)
resource = copy.deepcopy(two["care_resources"][0])
resource.update(id="daycare-2", label="Druga placówka demonstracyjna", location="care-2", dependent_ids=["child-2"])
resource["availability"][0]["end"] = "16:45"
two["care_resources"].append(resource)
two["travel_legs"][1]["origin"] = "care-2"
two["travel_legs"][2]["destination"] = "care-2"
two["travel_legs"][2]["bands"] = [
    {"start": "00:00", "end": "16:15", "minutes": 25, "cost_grosze": 400},
    {"start": "16:15", "end": "24:00", "minutes": 40, "cost_grosze": 400}]
two["travel_legs"] += [
    {"id": "between-out", "origin": "care", "destination": "care-2", "bands": [{"start": "00:00", "end": "24:00", "minutes": 10, "cost_grosze": 0}]},
    {"id": "between-back", "origin": "care-2", "destination": "care", "bands": [{"start": "00:00", "end": "24:00", "minutes": 10, "cost_grosze": 0}]}]
for leg in two["travel_legs"]:
    leg["mode"] = "transit" if leg["id"] in ("care-work", "work-care") else "walk"
    leg["source"] = {"label": "syntetyczny rozkład demonstracyjny", "checked_at": "2026-10-03", "valid_to": "2026-12-31"}
save("two-dependents.json", two)

handoff = copy.deepcopy(base)
handoff["title"] = "Uzgodniony odbiór przez opiekunkę"
handoff["notes"] = "Scenariusz syntetyczny. Opiekunka może przybyć do placówki o 16:30, przejąć dziecko i odprowadzić do domu. Przybycie, przyjęcie i cena wymagają osobnego potwierdzenia."
handoff["activities"][0]["negotiable"] = False
handoff["budget_grosze"] = 100_000
handoff["care_resources"].append({
    "id": "helper", "label": "Opiekunka demonstracyjna", "location": "home", "kind": "caregiver",
    "capacity": 1, "dependent_ids": ["child-1"], "confirmed": False,
    "availability": [{"start": "16:30", "end": "18:30"}], "hourly_cost_grosze": 3000,
    "daily_cost_grosze": 0, "one_time_cost_grosze": 0})
handoff["care_needs"][0]["arrangements"] = [{
    "id": "afternoon-handoff", "resource_ids": ["daycare", "helper"],
    "handoffs": [{"at": "16:30", "by_resource_id": "helper", "leg_id": "care-home", "confirmed": False}]}]
handoff["travel_legs"].append({
    "id": "work-home", "origin": "work", "destination": "home", "bands": [{"start": "00:00", "end": "24:00", "minutes": 25, "cost_grosze": 400}], "buffer_minutes": 15})
handoff["travel_legs"][3]["bands"][0]["minutes"] = 10
save("care-handoff.json", handoff)
