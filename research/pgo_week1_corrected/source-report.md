# September 8 Week 1 source qualification

Status: **PASS for source engineering; EXPERIMENTAL / HOLD for forecasts.** The capture and qualification do not approve a model, prediction build, weekly registration, or publication.

## Frozen pair

- Capture directory: `output/pgo-week1-corrected-20260908/sources-20260908T150137Z`
- `capture.json`: `122ef5740e94ba2e8b4464d7ea9e6e8fe953d0e0ac49527fee5a6050039672f2`
- `qualification.json`: `4c7f700531dc43b38181f9c205564057615ff54613832a2c2970d1963d60d76b`
- Charter: `643cdc172fc3ad15393989d8e9b021b3975833d6ae51f7ee162a837c39a25c12`
- Qualification: 166 checks passed, zero failed.

All 13 source responses were HTTPS HTTP 200 captures whose stored bytes, sizes, timestamps, release metadata, and provider digests were verified. Provider vintages were roster `2026-09-08 07:56:45 EDT`, depth chart `2026-09-08 07:57:03 EDT`, and schedule `2026-09-08 10:47:03 EDT`. The latest internally coherent depth snapshot is `2026-09-08T11:56:57Z`.

## Roster, quarterback, and schedule findings

The roster contains 1,693 ACT, 545 DEV, 414 CUT, 275 RES, 23 RET, and 5 EXE rows. Compared with the September 7 capture, the only identity/status change is the addition of SEA player D'Anthony Bell (`00-0037332`) as DEV. The 32 depth-rank-1 expected quarterbacks all uniquely join to ACT quarterback rows. There are **zero expected-quarterback changes** from the September 7 snapshot and **zero confirmed-unavailable expected-quarterback blocks**.

All 16 Week 1 game identities, teams, locations, rest values, and kickoffs match both the captured official NFL schedule and the registered September 7 weekly revision. The qualification records raw RES and EXE exclusions as non-ACT and unpriced. Their opaque provider subcodes are preserved and are not decoded into injury, PUP, suspension, or health claims.

| Game | Matchup | Kickoff | T-60 deadline |
|---|---|---|---|
| `2026_01_NE_SEA` | NE at SEA | 2026-09-09 8:20 PM EDT | 2026-09-09 7:20 PM EDT |
| `2026_01_SF_LA` | SF at LAR | 2026-09-10 8:35 PM EDT | 2026-09-10 7:35 PM EDT |
| `2026_01_ATL_PIT` | ATL at PIT | 2026-09-13 1:00 PM EDT | 2026-09-13 12:00 PM EDT |
| `2026_01_BAL_IND` | BAL at IND | 2026-09-13 1:00 PM EDT | 2026-09-13 12:00 PM EDT |
| `2026_01_BUF_HOU` | BUF at HOU | 2026-09-13 1:00 PM EDT | 2026-09-13 12:00 PM EDT |
| `2026_01_CHI_CAR` | CHI at CAR | 2026-09-13 1:00 PM EDT | 2026-09-13 12:00 PM EDT |
| `2026_01_CLE_JAX` | CLE at JAX | 2026-09-13 1:00 PM EDT | 2026-09-13 12:00 PM EDT |
| `2026_01_NO_DET` | NO at DET | 2026-09-13 1:00 PM EDT | 2026-09-13 12:00 PM EDT |
| `2026_01_NYJ_TEN` | NYJ at TEN | 2026-09-13 1:00 PM EDT | 2026-09-13 12:00 PM EDT |
| `2026_01_TB_CIN` | TB at CIN | 2026-09-13 1:00 PM EDT | 2026-09-13 12:00 PM EDT |
| `2026_01_ARI_LAC` | ARI at LAC | 2026-09-13 4:25 PM EDT | 2026-09-13 3:25 PM EDT |
| `2026_01_GB_MIN` | GB at MIN | 2026-09-13 4:25 PM EDT | 2026-09-13 3:25 PM EDT |
| `2026_01_MIA_LV` | MIA at LV | 2026-09-13 4:25 PM EDT | 2026-09-13 3:25 PM EDT |
| `2026_01_WAS_PHI` | WAS at PHI | 2026-09-13 4:25 PM EDT | 2026-09-13 3:25 PM EDT |
| `2026_01_DAL_NYG` | DAL at NYG | 2026-09-13 8:20 PM EDT | 2026-09-13 7:20 PM EDT |
| `2026_01_DEN_KC` | DEN at KC | 2026-09-14 8:15 PM EDT | 2026-09-14 7:15 PM EDT |

## Injury coverage

Only NE and SEA had a formal report in the official NFL overview at capture time. The captured reports are dated September 7 and contain 11 observations. Ben Brown (`00-0037413`, NE, report position C/roster position OL, knee) was the only player with an official game designation: **Out**. He remained ACT in the roster source. This records a known absence but does not price it; the corrected model has no admitted non-QB injury effect.

TreVeyon Henderson and Ty Okada were DNP; Nick Emmanwori, Tory Horton, and Josh Jones were limited; Christian Barmore, AJ Barner, Anthony Bradford, Julian Neal, and Emanuel Wilson were full participants. None had a game designation in the captured Monday report. They remain dated observations with no probability mapping and no numerical adjustment.

The other 30 teams are explicitly `no_formal_report`, linked to the captured NFL injury overview. That state is unknown and never means healthy. A later pre-cutoff refresh is required as final reports become available.

## Preserved blocked attempt

The first qualification attempt required official report positions such as C, G, T, DT, S, and CB to equal nflverse's broader OL, DL, and DB roster positions. It blocked six valid identities. That receipt is preserved as `qualification-attempt-01-blocked.json`. The final qualifier joins on team, GSIS ID, and exact player name and records both position systems. It did not change any captured source byte.

The preserved qualifier is a one-shot full-Week-1 check and required all 16 T-60 deadlines to remain open at issuance. Future refreshes after an earlier game expires must use a selection-aware rule that quarantines expired games and requires at least one still-eligible game, as specified in `source-refresh-clarification.md`; they must not reuse this condition unchanged.
