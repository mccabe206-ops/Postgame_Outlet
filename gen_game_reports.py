"""Generate BASELINE embedded game-report drafts for a week — one markdown file
per completed game at data/game_reports/<year>_wk<week>_<AWAY>-<HOME>.md, read by
game_server.py and shown in hub card 15.

Baseline = the model's estimated-vs-actual score + the "why" + game shape (from
game_estimate). The deeper layer (QB week-by-week, PFF standouts, injuries mapped
to role, proposed rating moves) is added per game as it's worked; this just makes
sure every game is readable in the UI immediately. Existing files are NEVER
overwritten, so hand-written full reports are preserved.

Usage: python3 gen_game_reports.py <week> [year]     (year defaults to 2026)
"""
import io
import os
import sys
import contextlib

import game_estimate as GE
from espn_api import fetch_json

REPO = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(REPO, "data", "game_reports")


def _games(week, year):
    sb = fetch_json("https://site.api.espn.com/apis/site/v2/sports/football/nfl/"
                    f"scoreboard?dates={year}&seasontype=2&week={week}")
    out = []
    for e in sb.get("events", []):
        c = e["competitions"][0]
        if not c.get("status", {}).get("type", {}).get("completed"):
            continue
        comp = {t["homeAway"]: t["team"]["abbreviation"] for t in c["competitors"]}
        out.append((comp["away"], comp["home"]))
    return out


def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        return 1
    week = int(a[0])
    year = int(a[1]) if len(a) > 1 else 2026
    os.makedirs(OUT, exist_ok=True)
    made, skipped = [], []
    for away, home in _games(week, year):
        path = os.path.join(OUT, f"{year}_wk{week}_{away.upper()}-{home.upper()}.md")
        if os.path.exists(path):
            skipped.append(f"{away}@{home}")
            continue
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            GE.estimate_week(week, year, away)
        block = buf.getvalue().strip()
        # drop the model-formula preamble line (keep just this game's block)
        lines = [ln for ln in block.splitlines() if not ln.startswith("Expected-points model:")]
        block = "\n".join(lines).strip()
        md = (f"## {away} @ {home} — Week {week} {year}\n\n"
              f"### Model estimate — expected vs. actual score (and why)\n\n"
              f"```\n{block}\n```\n\n"
              f"*Baseline auto-report. QB week-by-week, PFF standouts, injuries mapped to role, "
              f"and proposed rating moves are added when this game is worked.*\n")
        with open(path, "w", encoding="utf-8") as f:
            f.write(md)
        made.append(f"{away}@{home}")
    print(f"wrote {len(made)}: {', '.join(made)}")
    if skipped:
        print(f"skipped {len(skipped)} existing (preserved): {', '.join(skipped)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
