"""Weekly unattended refresh of Ourlads depth charts + ESPN roster snapshots.

Run by launchd once a week (see com.mccabe.powerratings.weekly.plist). Polite:
real UA + a delay between Ourlads requests. Writes to the gitignored caches; the
per-team workspace then reads fresh data with no per-view scraping.

Usage:  python3 weekly_refresh.py
"""

import sys
from datetime import datetime, timezone

import depthchart as D
import rosters as R
import team_view as TV


def main():
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    idx = TV.espn_team_index()
    names = sorted(idx)
    abbrs = [idx[n]["abbr"] for n in names]

    print(f"[{now_iso}] weekly refresh starting — {len(names)} teams")

    # ESPN roster snapshots (fast JSON; baseline for change-detection)
    done_r = R.snapshot_all(now_iso=now_iso, sleep_between=0.2)
    print(f"  ESPN roster snapshots: {len(done_r)} teams")

    # Ourlads depth charts (polite: 2s between teams)
    done_d = D.refresh_all(abbrs, now_iso=now_iso, sleep_between=2.0)
    ok = [x for x in done_d if not x.endswith(":ERR")]
    err = [x for x in done_d if x.endswith(":ERR")]
    print(f"  Ourlads depth charts: {len(ok)} ok" + (f", {len(err)} errors: {err}" if err else ""))
    print(f"[{now_iso}] weekly refresh done.")


if __name__ == "__main__":
    sys.exit(main())
