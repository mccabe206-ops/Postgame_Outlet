"""Nightly Prop Board upkeep (launchd com.mccabe.powerratings.props.nightly).

  1. refresh KB player_week (full range — the table is rebuilt whole) + pbp (2016+)
  2. grade the forward ledger against the new box scores

Lane 2: lives on `testing`. If the repo is on `main` this file doesn't exist and the
launchd job simply logs a missing-file error — nothing else is touched.
"""

import sys
from datetime import datetime

import kb_build
import props_model


def main():
    print(f"== props nightly {datetime.now():%Y-%m-%d %H:%M}")
    kb_build.main(["--sources", "player_week,pbp"])
    print("ledger:", props_model.grade_ledger(), props_model.ledger_summary())
    print("bets:", props_model.grade_bets())
    return 0


if __name__ == "__main__":
    sys.exit(main())
