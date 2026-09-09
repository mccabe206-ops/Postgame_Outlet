"""Capture explicitly listed official injury pages into a new evidence directory."""

import argparse
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source", action="append", required=True, metavar="NAME=HTTPS_URL")
    args = parser.parse_args()
    sources = [value.split("=", 1) for value in args.source]
    if any(len(value) != 2 for value in sources):
        parser.error("each source must be NAME=HTTPS_URL")
    names = [name for name, _ in sources]
    if len(names) != len(set(names)) or any(not name.replace("-", "").isalnum() for name in names):
        parser.error("source names must be unique alphanumeric names with optional hyphens")
    if any(urlsplit(url).scheme != "https" or not urlsplit(url).netloc for _, url in sources):
        parser.error("source URLs must use HTTPS")
    args.output.mkdir(parents=True, exist_ok=False)

    def capture(item):
        name, url = item
        record = {"name": name, "url": url, "started_at": datetime.now(timezone.utc).isoformat()}
        try:
            with urlopen(Request(url, headers={"User-Agent": "PGO-Injury-Evidence/1.0"}), timeout=40) as response:
                raw = response.read()
                record.update(final_url=response.url, status=response.status,
                              captured_at=datetime.now(timezone.utc).isoformat(),
                              bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
                              file=name + ".html", http_date=response.headers.get("Date"),
                              last_modified=response.headers.get("Last-Modified"))
            with (args.output / record["file"]).open("xb") as handle:
                handle.write(raw)
            assert hashlib.sha256((args.output / record["file"]).read_bytes()).hexdigest() == record["sha256"]
        except Exception as error:
            record.update(failed_at=datetime.now(timezone.utc).isoformat(), error=str(error))
        return record

    with ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(capture, sources))
    manifest = {"captured_at": datetime.now(timezone.utc).isoformat(), "sources": records}
    with (args.output / "capture.json").open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps(manifest, indent=2))
    return int(any("error" in row for row in records))


if __name__ == "__main__":
    raise SystemExit(main())
