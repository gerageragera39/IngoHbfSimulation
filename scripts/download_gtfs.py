"""Acquire public GTFS snapshots and optional DB station PDFs without overwrites."""

import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys
from tempfile import NamedTemporaryFile
from urllib.request import Request, urlopen
from zipfile import BadZipFile, ZipFile

from timetable_sources import RAW, SOURCES, local_source, sha256, write_json


def verify_payload(path, suffix):
    if suffix.casefold() == ".zip":
        with ZipFile(path) as archive:
            damaged = archive.testzip()
            if damaged or "stop_times.txt" not in archive.namelist():
                raise ValueError(f"Invalid GTFS archive {path} ({damaged or 'stop_times.txt missing'})")
    else:
        with path.open("rb") as stream:
            if stream.read(5) != b"%PDF-":
                raise ValueError(f"Expected a PDF in {path}")


def acquire(key, directory):
    path = local_source(directory, key)
    url = SOURCES[key][1]
    if path.is_file():
        verify_payload(path, path.suffix)
        print(f"Using existing {path} (SHA-256 {sha256(path)})")
        return

    temporary = None
    try:
        request = Request(url, headers={"User-Agent": "IngoHbfSimulation/2.1"})
        with urlopen(request, timeout=45) as response:
            with NamedTemporaryFile(dir=directory, prefix=".download-", delete=False) as stream:
                temporary = Path(stream.name)
                shutil.copyfileobj(response, stream)
            receipt = {
                "url": url, "resolved_url": response.url,
                "http_last_modified": response.headers.get("Last-Modified"),
                "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
                "sha256": sha256(temporary),
            }
        verify_payload(temporary, path.suffix)
        # Linking publishes the completed file atomically and fails if another writer won.
        path.hardlink_to(temporary)
        write_json(path.with_name(path.name + ".download.json"), receipt)
        print(f"Downloaded {path} (SHA-256 {receipt['sha256']})")
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=RAW,
                        help="Use a new directory to acquire a fresh snapshot")
    parser.add_argument("--with-pdfs", action="store_true", help="Also acquire the DB station posters")
    args = parser.parse_args()
    args.raw_dir.mkdir(parents=True, exist_ok=True)
    failed = False
    for key in SOURCES if args.with_pdfs else ("fv", "rv"):
        try:
            acquire(key, args.raw_dir)
        except (OSError, ValueError, BadZipFile) as exc:
            failed = True
            name, url, _ = SOURCES[key]
            print(f"{name}: {exc}. Download {url} to {args.raw_dir / name}.", file=sys.stderr)
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
