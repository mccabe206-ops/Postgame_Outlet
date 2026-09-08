"""Capture one opening-week input package without changing prior evidence."""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
output = ROOT / ("sources-" + stamp)
output.mkdir(parents=True, exist_ok=False)

SOURCES = {
    "roster.csv.gz": "https://github.com/nflverse/nflverse-data/releases/download/rosters/roster_2026.csv.gz",
    "depth.csv.gz": "https://github.com/nflverse/nflverse-data/releases/download/depth_charts/depth_charts_2026.csv.gz",
    "schedule.csv.gz": "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv.gz",
    "nfl-week-1.html": "https://www.nfl.com/schedules/2026/by-week/reg-1",
    "nfl-injuries.html": "https://www.nfl.com/injuries/",
    "patriots-week1-injury.html": "https://www.patriots.com/news/week-1-injury-report-patriots-at-seahawks",
    "seahawks-week1-injury.html": "https://www.seahawks.com/news/2026-week-1-injury-report-seahawks-vs-patriots",
}
for tag in ("rosters", "depth_charts", "schedules"):
    SOURCES[f"{tag}-release.json"] = (
        f"https://api.github.com/repos/nflverse/nflverse-data/releases/tags/{tag}"
    )
    SOURCES[f"{tag}-timestamp.json"] = (
        f"https://github.com/nflverse/nflverse-data/releases/download/{tag}/timestamp.json"
    )


def capture(item):
    name, url = item
    started_at = datetime.now(timezone.utc).isoformat()
    try:
        request = Request(url, headers={"User-Agent": "PGO-Week1-Corrected/1.0"})
        with urlopen(request, timeout=50) as response:
            raw = response.read()
            record = {
                "file": name,
                "url": url,
                "final_url": response.url,
                "status": response.status,
                "started_at": started_at,
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "last_modified": response.headers.get("Last-Modified"),
                "etag": response.headers.get("ETag"),
            }
        with (output / name).open("xb") as handle:
            handle.write(raw)
        return record
    except Exception as error:
        return {
            "file": name,
            "url": url,
            "started_at": started_at,
            "failed_at": datetime.now(timezone.utc).isoformat(),
            "error": str(error),
        }


with ThreadPoolExecutor(max_workers=3) as pool:
    records = list(pool.map(capture, SOURCES.items()))

manifest = {
    "schema_version": 1,
    "captured_at": datetime.now(timezone.utc).isoformat(),
    "sources": records,
}
with (output / "capture.json").open("x", encoding="utf-8", newline="\n") as handle:
    json.dump(manifest, handle, indent=2, sort_keys=True)
    handle.write("\n")

for record in records:
    if "sha256" in record:
        assert hashlib.sha256((output / record["file"]).read_bytes()).hexdigest() == record["sha256"]

print(json.dumps({"directory": str(output), "sources": records}, indent=2))
if any("error" in record for record in records):
    raise SystemExit(1)
