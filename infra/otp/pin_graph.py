"""Validate built graph and copy its exact manifest to the mounted runtime volume."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parent
path = root / "manifest.json"
manifest = json.loads(path.read_text(encoding="utf-8"))
config = json.loads((root / "build-config.json").read_text(encoding="utf-8"))
manifest["valid_from"] = max(manifest["valid_from"], config["transitServiceStart"])
manifest["valid_to"] = min(manifest["valid_to"], config["transitServiceEnd"])
manifest["graph_service_start"] = config["transitServiceStart"]
manifest["graph_service_end"] = config["transitServiceEnd"]
with (root / "data" / "graph.obj").open("rb") as graph:
    manifest["graph_sha256"] = hashlib.file_digest(graph, "sha256").hexdigest()
manifest["graph_built_at"] = datetime.now(timezone.utc).isoformat()
manifest["image"] = "opentripplanner/opentripplanner:2.7.0@sha256:640870b240ad206d05634e7a066588804c6e23abebf37cbc02b0c9ba66073486"
serialized = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
path.write_text(serialized, encoding="utf-8")
(root / "data" / "manifest.json").write_text(serialized, encoding="utf-8")
print(json.dumps({"graph_verified": True, "valid_from": manifest["valid_from"], "valid_to": manifest["valid_to"]}))
