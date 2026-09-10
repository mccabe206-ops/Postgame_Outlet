# Task 3: Opening-night official injury check

Status: **COMPLETE for the bounded current-source check; final inactives PENDING.**
No forecast, model coefficient, McCabe grade, or published page was changed by
this task. All new raw bytes remain under
`research/pgo_opening_night_20260909/injuries/`.

## Integrate these artifacts

- `injury-source.json`: existing `pgo_injury_source.load_snapshot` schema 2;
  validated successfully with exactly 32 team coverage rows and 29 player rows.
  Generated `2026-09-09T14:49:44.763962+00:00`. The actual individual source
  capture clocks are retained separately; generation time is not publication.
- `annotations-reviewed.json`: eight dated official-source player annotations
  and the Donald/Collins source conflicts. Use this reviewed file. Earlier
  `annotations.json` is an unchanged draft; the reviewed version avoids assuming
  publication order for the undated league table.
- `evidence-manifest.json`: 13 successful full HTML captures, exact URLs,
  capture clocks, byte sizes and SHA-256 values; primary NewsArticle publication
  and update timestamps; one disclosed unsuccessful Bills URL discovery.
- `league-table-observations.json`: exact five-cell NFL table values for all
  29 listed players, with team and verified GSIS.
- `roster-identity-check.json`: each player joins one exact same-team roster
  full name after punctuation/whitespace folding. No fuzzy name matching.

The pinned roster is
`docs/evidence/forecast-lab-2026/september-08-corrected/roster.csv.gz`,
360,272 bytes, SHA-256
`2b2c39db80f1c9d9bf68b956a475cfba9ca19d4b456eefd2b4fa045f3a757965`,
provider clock `2026-09-08 07:56:45 EDT`. Its status observations are dated to
that snapshot and do not establish live roster or final inactive status.

Use the new ledger and supplemental text for reader annotations only. Do not
call `build_overlay` or `import_snapshot`: those create numerical availability
probabilities and are unnecessary for this task. The existing forecast-refresh
qualification format likewise separates formal observations, known unavailable
players and missing coverage; no corrected forecast package was generated here.

## Opening game: verified current designations

NE at SEA is scheduled for September 9 at 8:20 p.m. Eastern. Its 7:20 p.m.
Eastern T-60 boundary is a later operational check, not a lock produced here.

| Team | Player | GSIS | Official game designation | Injury / practice |
| --- | --- | --- | --- | --- |
| NE | Ben Brown | `00-0037413` | Out | Knee; did not travel. NFL table also lists DNP. |
| NE | TreVeyon Henderson | `00-0040734` | Out | Ankle; DNP |
| SEA | Ty Okada | `00-0038765` | Out | Hamstring; DNP |
| SEA | Nick Emmanwori | `00-0040733` | Questionable | Ankle; limited |
| SEA | Tory Horton | `00-0040648` | Questionable | Hamstring; limited |

The [Patriots' full Tuesday report](https://www.patriots.com/news/week-1-injury-report-patriots-at-seahawks)
was captured at `2026-09-09T14:42:35.171518+00:00`; its main article metadata
gives publication `2026-09-08T20:50:00Z` and update
`2026-09-08T20:55:53.502Z`. The
[Seahawks' full report](https://www.seahawks.com/news/2026-week-1-injury-report-seahawks-vs-patriots)
was captured at `2026-09-09T14:42:35.128903+00:00`; publication
`2026-09-08T22:00:00Z`, update `2026-09-08T22:29:51.204Z`. Later timestamps in
the Seahawks HTML belong to an embedded gallery and were not attributed to the
injury report. Seattle describes Tuesday practice as an estimated walkthrough.

The [NFL Week 1 game-status article](https://www.nfl.com/news/nfl-week-1-injury-report-2026-season)
also corroborates all five designations. Its update clock is
`2026-09-09T12:36:06.292Z`, captured at
`2026-09-09T14:46:46.770517+00:00`. Christian Barmore has full participation and
no final game-status label in the formal report. No captured source here is a
released final game-day inactive list.

## Tomorrow's game and source conflicts

The [NFL injury overview](https://www.nfl.com/injuries/), captured at
`2026-09-09T14:42:35.114360+00:00`, contains 11 San Francisco and seven Rams
practice rows. It supplies neither a report publication clock nor final game
designations for these two teams. The exact blank injuries/statuses are preserved
in the raw table observation artifact; no diagnosis or availability was invented.

Two entries require a visible supplemental note:

- Aaron Donald (`LAR`, `00-0031388`) appears as Limited with blank game status.
  The [Rams' September 8 announcement](https://www.therams.com/news/aaron-donald-will-not-play-week-1-2026-49ers-myles-garrett-ready-to-go)
  explicitly says he will not play or travel for the opener. Published
  `2026-09-08T20:47:00.598Z`, updated `20:52:17.668Z`, captured
  `2026-09-09T14:44:34.992846+00:00`. Preserve the practice entry and display the
  announcement; do not translate limited participation into availability.
- Alfred Collins (`SF`, `00-0040721`) appears as Limited with blank game status.
  The [NFL September 8 news roundup](https://www.nfl.com/news/nfl-news-roundup-latest-league-updates-from-tuesday-sept-8)
  reports Shanahan's announcement that Collins tore his patellar tendon and will
  miss the season. The roundup was updated `2026-09-09T03:02:31.577Z` and captured
  `2026-09-09T14:46:46.830026+00:00`. The pinned roster's earlier ACT designation
  does not invalidate this injury announcement. Because the formal table is
  undated, relative publication order is not inferred.

The Rams announcement also says McVay expects Myles Garrett (`00-0033868`) to
be ready for Week 1 despite his knee issue; the table lists DNP. George Kittle
(`SF`, `00-0033288`) is limited, with the NFL roundup identifying the Achilles
issue; no final game designation is verified here. Kittle's pinned roster status
is ACT, not PUP. DNP, limited participation and a coach's expectation remain
distinct from a final inactive list.

## Exact writeup corrections for the root editor

These are source-backed wording changes, not numerical grade recommendations.
The source snippets below come from the user's supplied mock.

| Team | Exact supplied snippet / claim | Finding and recommended replacement |
| --- | --- | --- |
| LAR | `Aaron Donald back (though rusty after a couple of years retired, so his bump is modest)` and `Donald is ramping up after his layoff` | Material update. Replace with: `Aaron Donald has returned from retirement, but the Rams announced September 8 that he will not play or travel for the opener against San Francisco.` Cite the Rams announcement above. Do not attribute an opening-game contribution to him. |
| LAR | `Garrett is working through left knee swelling (missed most of camp; McVay says he's good to go for Week 1)` | Narrow to verified current language: `Myles Garrett is managing a knee issue; McVay said September 8 that he expects him ready for the opener, despite the captured DNP practice entry.` Cite the same announcement. Specific swelling and camp absence were not reverified here. |
| LAR | `and Kobie Turner is questionable` | No current official Questionable designation was found in the captured sources. Replace with: `A current final game designation for Kobie Turner was not verified in this check.` He is absent from the captured table; that absence is not a healthy assertion. |
| LAR | `Nacua is working back from a psoas injury (a hip-flexor-area strain from August; expected to play the opener)` | [The Rams documented psoas soreness August 13](https://www.therams.com/news/rams-puka-nacua-injury-update-cowboys-joint-practice-psoas), but that preseason expectation does not establish current status. Replace with: `The Rams documented Puka Nacua's psoas soreness in August. No current final game designation was verified in this September 9 check.` Do not infer health from absence in the current table. |
| LAR | `left tackle Alaric Jackson is banged up too — a camp ankle injury plus an ongoing blood-clot condition he manages, and he's expected to play but hasn't been full-go` | Current captured evidence supports DNP, with injury reason and game status blank. Replace with: `Alaric Jackson was listed as a non-participant in the captured Week 1 practice report; that table did not provide an injury reason or final game designation.` Detailed diagnoses and expected availability were not reverified. |
| SF | `Kittle working back from an Achilles issue (PUP, projected Week 1)` | Stale current-list claim. Replace with: `George Kittle is listed active in the pinned September 8 roster and limited with an Achilles issue in the current injury reporting; his final game designation was not yet verified.` Cite the NFL roundup and distinguish the roster's date. |
| SF | `McCaffrey banged up` | Not verified by the captured Week 1 report. Replace with: `A current injury designation for Christian McCaffrey was not verified in this check.` His absence from the report does not prove health. |
| SF | `Defense (+0.5): above average, with Odighizuwa and Greenlaw as the anchors.` | Add dated context without altering +0.5: `September 9 injury update: the NFL reported that Alfred Collins will miss the season after a patellar-tendon tear; Dre Greenlaw was listed limited with an Achilles issue.` Cite NFL roundup. |
| NE | `rookie RB TreVeyon Henderson is out for Week 1 (ankle), so Hassan Haskins leads the backfield to open the season` | Out is verified. The report does not establish a replacement starter. Pinned roster lists Haskins DEV and Rhamondre Stevenson ACT; Henderson entered in 2025. Replace with: `TreVeyon Henderson is Out for Week 1 with an ankle injury, and Ben Brown is Out with a knee injury after not traveling with the team, per the September 8 final report.` Avoid an unsupported backfield-role inference. |
| NE | `Barmore is expected to go` | Prefer directly observed status: `Christian Barmore practiced fully and had no game designation in the September 8 final injury report.` |
| SEA | `Ty Okada is out (hamstring), Nick Emmanwori is questionable (ankle, coming off July surgery)` | Current designations confirmed. Add `Tory Horton is also Questionable with a hamstring injury` and cite the September 8 club report. Do not turn questionable into inactive. |
| BUF | `Keon Coleman is working back from a sprained right foot/toe (Aug 15; out of the walking boot and practicing, expected to play Week 1)` and `Khalil Shakir is working through an ankle injury (reported high-ankle sprain, "week-to-week")` | Current specifics not verified. Replace with: `No current Buffalo formal injury report was present in the captured Week 1 overview; Coleman and Shakir's current injury and game-status claims remain unverified.` Do not declare them healthy or ruled out. Remove the later unsupported `two banged-up complementary starters` assertion or label it explicitly as unverified historical context. |

The [Bills' September 1 official update](https://www.buffalobills.com/news/bills-gm-brandon-beane-provides-team-injury-updates-prior-to-week-1-of-2026-season)
confirms Zane Durant's injured-reserve placement and discusses other players,
but does not verify the Coleman/Shakir details above. It is dated supplemental
news, not a new formal report. The remaining teams' detailed roster/injury prose
was not exhaustively fact-checked; unknown formal coverage must stay explicit.

## All 32 coverage

Checked the successful current NFL Week 1 overview for every team, and
individually examined official club pages for NE, SEA, LAR, SF and BUF. This is
not a claim that all 32 club websites were separately inspected.

| Coverage | Teams |
| --- | --- |
| Final game designations and practice report verified | NE, SEA |
| Practice report present; final game designations not supplied | SF, LAR |
| NFL overview placeholder; formal coverage unknown | ARI, ATL, BAL, BUF, CAR, CHI, CIN, CLE, DAL, DEN, DET, GB, HOU, IND, JAX, KC, LAC, LV, MIA, MIN, NO, NYG, NYJ, PHI, PIT, TB, TEN, WAS |

The placeholder may reflect a report not yet published or not yet reflected
there. It does not establish an uninjured roster. Source-backed news annotations
can coexist with unknown formal coverage.

## Exact next capture command

Run a fresh capture near the next official release; it creates a new directory
and refuses an existing one. This command captures evidence only. The root must
inspect the new actual article/list, preserve its publication and capture clocks,
and verify exact GSIS before issuing any later inactive lock. Final inactives are
not fabricated from this command or from an injury report.

```powershell
$injuryStamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
python -B research/pgo_opening_night_20260909/injuries/capture_injuries.py --output "research/pgo_opening_night_20260909/injuries/capture-$injuryStamp" --source 'nfl-injuries=https://www.nfl.com/injuries/' --source 'nfl-week1-statuses=https://www.nfl.com/news/nfl-week-1-injury-report-2026-season' --source 'patriots-week1=https://www.patriots.com/news/week-1-injury-report-patriots-at-seahawks' --source 'seahawks-week1=https://www.seahawks.com/news/2026-week-1-injury-report-seahawks-vs-patriots' --source 'patriots-news=https://www.patriots.com/news/' --source 'seahawks-news=https://www.seahawks.com/news/'
```

For SF/LAR and the other teams, revisit the formal overview after subsequent
practice/game-status releases. Preserve every earlier capture. Nothing in this
task authorizes a model fit, forecast rewrite, or publication.
