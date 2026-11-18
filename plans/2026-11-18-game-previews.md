# Game Previews tab — plan (2026-11-18, Sean-approved decisions)

## Goal
A write-up for every game, published as early as Tuesday, explaining why our number is what it is,
with Sean's bets flagged and three ATS records on top. Built as a new tab on the existing board
(`pgo_comparison.py` output -> docs/index.html), so one build/publish.

## Decisions (Sean, 11/18)
- **Bets visible Tuesday**: the side + confidence badge shows as soon as the preview publishes.
  This deliberately relaxes the "no pick public before final" rule — for the previews tab only.
- **Records graded three ways**: vs opening line, vs closing line, and vs the line
  actually available **when the pick was made** (`market_at_pick`, already stored per pick).
  For the model records, "at pick" = the market line frozen when the preview was written.
- **Placement**: new tab on the board.

## Records banner
| Record | What it is | Source |
|---|---|---|
| McCabe Bets | Sean's 5 weekly picks | data/picks/week_*.json |
| Strict model | edge side of every game | picks.records() "model" |
| Biggest edge | the model's 5 largest edges per week | picks.records() "top5" |
Each shows Open / At pick / Close. Weeks 1-9 picks were backfilled (`market_at_pick` = line at
backfill, `picked_at` null) — flag those as approximate in the fine print, or grade at-pick from Wk10+.

## Data per game: data/previews/<year>_wk<W>/<AWAY>-<HOME>.md
Front matter (frozen when written):
- `status`: draft | ready  (drafts are left off the page; they never fail CI)
- `written_at`, `market_at_write`, `our_line_at_write`, `edge_at_write`
- rating snapshot per side: QB (name, value), Off, Def, HFA, situational adj
- `assumptions`: list ("IND 1st string LT Raimann OUT")
Body: the "why the number" write-up, then dated `### Update (Thu 11/19)` notes appended.
Bet badge comes from the pick sheet (single entry point), not the preview file.
The current live line/number is shown next to the frozen Tuesday one when they differ.

## Build steps (on `testing`, promote to `main` when Sean signs off)
1. `previews.py`: draft generator. For a week: pull the slate + market lines, compute our line from
   ratings.csv/hfa.csv, snapshot the ratings, list injury assumptions (Sleeper), situational
   factors; write `status: draft` files. Never overwrites existing files.
2. `picks.py`: add an "at pick" tally alongside open/close for mine/model/top5; model's at-pick
   line = `market_at_write` from the preview. Extend `write_records_json` with it.
3. `pgo_comparison.py`: `inject_previews_panel()` — new `tab-previews` + `panel-previews`;
   records banner + game cards in kickoff order. Bets are read from a small public
   `data/previews/<wk>/bets.json` exported from the pick sheet at publish time (picks dir is gitignored).
4. Editorial gate: a `ready` preview must have a non-empty write-up and assumptions block;
   QB names in the snapshot must match ratings.csv at write time.
5. Tests for the panel + at-pick grading; regenerate docs/index.html locally on publish.
6. Dry run on the Week 11 slate, local preview, Sean review, then go live.

## Weekly rhythm
Mon night/Tue AM drafts -> Sean edits + marks bets on the pick sheet -> publish Tue ->
dated updates Wed-Sat -> after games, regrade records (write_records_json) and publish.

## Housekeeping
- records.json is only graded through Wk9; run write_records_json for Wk10.
