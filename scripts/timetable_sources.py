"""Source registry and acquisition receipts shared by the timetable commands."""

import hashlib
import json
from pathlib import Path


TIMETABLE = Path(__file__).resolve().parents[1] / "data" / "timetable"
RAW = TIMETABLE / "raw"
CONFIG = TIMETABLE / "config"
SPEC = "https://gtfs.org/documentation/schedule/reference/"
DB_STATION = "https://db.info/ingolstadt-hbf/fahrplan"
LICENSE = "https://creativecommons.org/licenses/by/4.0/"
SOURCES = {
    "fv": ("fernverkehr.zip", "https://download.gtfs.de/germany/fv_free/latest.zip",
           "https://www.gtfs.de/de/feeds/de_fv/"),
    "rv": ("regionalverkehr.zip", "https://download.gtfs.de/germany/rv_free/latest.zip",
           "https://www.gtfs.de/de/feeds/de_rv/"),
    "regel": ("regelfahrplan.pdf", "https://db.info/downloads/schedule/Regeltafel_2993.pdf",
              DB_STATION),
    "aenderung": ("aenderungsfahrplan.pdf",
                  "https://db.info/downloads/schedule/Aenderungstafel_2993.pdf", DB_STATION),
}


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def local_source(directory, key):
    name = SOURCES[key][0]
    matches = sorted(path for path in directory.glob("*") if path.name.casefold() == name)
    if len(matches) > 1:
        raise ValueError(f"Multiple files match {name} in {directory}. Specify the path explicitly.")
    return matches[0] if matches else directory / name


def provenance(key, path):
    _, url, documentation = SOURCES[key]
    result = {
        "file": SOURCES[key][0], "url": url, "documentation_url": documentation,
        "sha256": sha256(path), "bytes": path.stat().st_size,
        "license": "CC BY 4.0" if key in ("fv", "rv") else "No reuse license verified",
        "license_url": LICENSE if key in ("fv", "rv") else None,
        "downloaded_at_utc": None, "http_last_modified": None, "resolved_url": None,
    }
    pinned = TIMETABLE / "metadata" / "archive_snapshots.json"
    receipt = path.with_name(path.name + ".download.json")
    candidates = [
        read_json(pinned).get(key, {}) if pinned.is_file() else {},
        read_json(receipt) if receipt.is_file() else {},
    ]
    for recorded in candidates:
        if recorded.get("sha256") == result["sha256"] and recorded.get("url") == url:
            for field in ("downloaded_at_utc", "http_last_modified", "resolved_url"):
                result[field] = recorded.get(field)
            break
    return result
