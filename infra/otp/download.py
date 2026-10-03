"""Acquire versioned public GTFS/OSM inputs; record hashes and service dates.

Run with Python 3.12: python infra/otp/download.py. Existing files are reused.
Use --refresh to acquire another snapshot; it never silently rewrites the manifest.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
from datetime import datetime, timezone
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SOURCES = {
    "malopolskie.osm.pbf": "https://download.geofabrik.de/europe/poland/malopolskie-latest.osm.pbf",
    "krakow-a.gtfs.zip": "https://gtfs.ztp.krakow.pl/GTFS_KRK_A.zip",
    "krakow-m.gtfs.zip": "https://gtfs.ztp.krakow.pl/GTFS_KRK_M.zip",
    "krakow-t.gtfs.zip": "https://gtfs.ztp.krakow.pl/GTFS_KRK_T.zip",
}


def feed_dates(path: Path) -> tuple[str, str]:
    dates = []
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            base = name.rsplit("/", 1)[-1]
            if base not in {"calendar.txt", "calendar_dates.txt"}:
                continue
            for row in csv.DictReader(io.TextIOWrapper(archive.open(name), encoding="utf-8-sig")):
                if base == "calendar.txt":
                    dates.extend([row["start_date"], row["end_date"]])
                elif row.get("exception_type") == "1":
                    dates.append(row["date"])
    if not dates:
        raise ValueError(f"No service dates in {path.name}")
    iso = lambda d: f"{d[:4]}-{d[4:6]}-{d[6:]}"
    return iso(min(dates)), iso(max(dates))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    DATA.mkdir(parents=True, exist_ok=True)
    manifest_path = ROOT / "manifest.json"
    if manifest_path.exists() and not args.refresh:
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        previous = None
    entries = []
    for filename, url in SOURCES.items():
        destination = DATA / filename
        if args.refresh or not destination.exists():
            print(f"Downloading {filename}", flush=True)
            request = urllib.request.Request(url, headers={"User-Agent": "OknoPublicData/1.0"})
            temporary = destination.with_suffix(destination.suffix + ".part")
            with urllib.request.urlopen(request, timeout=90) as response, temporary.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
            temporary.replace(destination)
        with destination.open("rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
        entry = {"file": filename, "url": url, "sha256": digest, "bytes": destination.stat().st_size}
        if filename.endswith(".zip"):
            entry["valid_from"], entry["valid_to"] = feed_dates(destination)
        if previous:
            old = next((x for x in previous["inputs"] if x["file"] == filename), None)
            if old and old["sha256"] != digest:
                raise ValueError(f"{filename}: pinned input changed; explicitly use --refresh and rebuild")
        entries.append(entry)
        print(f"Verified {filename}: {destination.stat().st_size} bytes", flush=True)
    feeds = [x for x in entries if "valid_from" in x]
    build_config = json.loads((ROOT / "build-config.json").read_text(encoding="utf-8"))
    manifest = {
        "schema_version": 1,
        "otp_version": "2.7.0",
        "image": "opentripplanner/opentripplanner:2.7.0",
        "acquired_at": datetime.now(timezone.utc).isoformat(),
        "valid_from": max(max(x["valid_from"] for x in feeds), build_config["transitServiceStart"]),
        "valid_to": min(min(x["valid_to"] for x in feeds), build_config["transitServiceEnd"]),
        "graph_service_start": build_config["transitServiceStart"],
        "graph_service_end": build_config["transitServiceEnd"],
        "coverage": "Kraków and Małopolskie; actual GTFS service and mapped walking links only",
        "inputs": entries,
        "licenses": {"osm": "OpenStreetMap contributors, ODbL 1.0; Geofabrik extract", "gtfs": "ZTP public feed; operator must verify redistribution terms before publication"},
    }
    if not previous or args.refresh:
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Manifest verified. Build graph before enabling ROUTING_MODE=otp.", flush=True)


if __name__ == "__main__":
    main()
