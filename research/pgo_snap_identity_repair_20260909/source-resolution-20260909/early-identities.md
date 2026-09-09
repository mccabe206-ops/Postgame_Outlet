# Identity evidence: Damaris Johnson, T.J. Johnson, Kwamie Lassiter II

Recorded 2026-09-09, approximately 14:20 UTC. Evidence investigation only. No
source files, code, histories, fits, forecasts or earlier receipts were changed.
Current provider data were read in memory for corroboration, not admitted to or
saved in the model-source cache. The historical source qualification STOP is not
removed by this note.

## Conclusions

The frozen roster PFR fields identify different people in all three cases. The
snap PFR IDs agree with the roster GSIS identities, birth dates, positions,
colleges and career context. These are supported identity corrections, scoped
to the documented records; this note does not authorize a general name override.

| Roster GSIS | Person | Frozen roster PFR | Supported PFR | Inventory conflicts | Offense + defense snaps |
| --- | --- | --- | --- | ---: | ---: |
| 00-0029435 | Damaris Johnson | JohnDe22 | JohnDa04 | 30 | 632 |
| 00-0030126 | T.J. Johnson | JohnTo20 | JohnTJ00 | 45 | 357 |
| 00-0037420 | Kwamie Lassiter II | LassKw20 | LassKw00 | 1 | 5 |

## Frozen evidence and exact record locations

Input: `../source-conflict-inventory.json`, SHA-256
`c3f721962886ba77fd1ff8d45637508d2050fd294c0f3185dff77f3561a66a29`.
Its `resolver_conflicts` array contains the complete snap row and named roster
counterpart. Array indices below are zero-based. Source locations are the
inventory's `verified_sources` entries; all twelve relevant raw-file hashes were
rechecked against those entries during this investigation.

- Damaris: indices 16-31, 33-40, 42-43, 46-48 and 57; PHI 2013, HOU 2014,
  NE 2015. Example `/resolver_conflicts/16`: game `2013_01_PHI_WAS`, roster
  GSIS `00-0029435`, DOB `1989-11-22`, Tulsa WR, entry 2012, roster PFR
  `JohnDe22`; snap row `Damaris Johnson`, `JohnDa04`, one offensive snap.
- T.J.: indices 32, 41, 44-45, 49-56 and 58-90; CIN 2014-2017. Example
  `/resolver_conflicts/32`: game `2014_03_TEN_CIN`, roster GSIS `00-0030126`,
  DOB `1990-07-17`, South Carolina G, entry 2013, CIN draft pick 251, roster
  PFR `JohnTo20`; snap row `T.J. Johnson`, `JohnTJ00`, three offensive snaps.
- Kwamie II: `/resolver_conflicts/98`, game `2023_05_CIN_ARI`; roster name
  `Kwamie Lassiter`, GSIS `00-0037420`, DOB `1998-01-21`, Kansas WR, entry
  2022, roster PFR `LassKw20`; snap name `Kwamie Lassiter II`, `LassKw00`,
  five offensive snaps. Removing a generational suffix is not itself the
  evidence: the birth date, role, career and provider crosswalk identify the son.

All raw files reside under `D:\Postgame_Outlet-pgo-model\.cache\pgo_v1\` and
have filename `<SHA-256>.csv`:

| Season | Weekly roster SHA-256 | Snap-count SHA-256 |
| --- | --- | --- |
| 2013 | 76c47a629075ffd75f9c4ee49fadb6dad45396be486af897078fee5722969781 | 9d1fdd557875b9a2c71d88e583da24a739dfca671edf8223d6171e39a421000e |
| 2014 | 331022cd3b0c69d99c581f02b6fde6853e87ac431739c4b49841ee6e02893d6c | 84540709d9483552185c8ca3ef30b2f66fb94b30c3e6c21e7a27205f337f21d3 |
| 2015 | 198904f48eeebafc1f34028a00c1b8c0fc135aba04fc4b276e636ef87709751a | 841496252ada825c3c50d3ba9b4b26d3f4fabd0fedc5fb44f286ddaaa5bdb7e0 |
| 2016 | ab05dfeffe6f9a1d969133cd6740f1625d135bfad672aaa916adb609ab662883 | a778e24e9eb665ffe8f16093b03c5a263dca0250b3aa92bd6002f61f534bea59 |
| 2017 | fd3fe005b676fe0ad8d88c50701d71adef4287501397c33f479c9765cd8c45d4 | eab2fad2df99249d4061ed9c5c34d312cdba07cf3159d027d255bdc9b6526917 |
| 2023 | 1433f1f239784dde7fcb35349d211a9b83abfc0156337b72ec4f923abf715bd3 | 303b61aa5c33ffda863f93a750fc14483f397f9187ad502b1ce71e9b516a64c0 |

## Provider and club corroboration

Direct browser-tool opens of all six PFR profiles returned HTTP 403. The same
provider's search-indexed profile content was available and supplied the facts
below. This is indexed provider evidence, not a successful live profile fetch.
No third-party biography was relied on for the conclusions.

### Damaris Johnson

[PFR JohnDa04](https://www.pro-football-reference.com/players/J/JohnDa04.htm)
identifies the Tulsa WR born November 22, 1989. Its indexed snap table reports
53 offense snaps for PHI in 2013, 576 for HOU in 2014, and three for New England
in 2015: 632 in the same years as the frozen conflict inventory.
[PFR JohnDe22](https://www.pro-football-reference.com/players/J/JohnDe22.htm)
instead identifies Dennis Alan Johnson, Kentucky DE born December 4, 1979,
Arizona's 2002 third-round pick (98), with 2002-2004 NFL appearances.

The [Patriots' December 16, 2015 release notice](https://www.patriots.com/news/patriots-place-rb-legarrette-blount-on-injured-reserve-release-wr-damaris-250086)
directly corroborates Damaris's position, Tulsa background, Philadelphia
2012-2013 / Houston 2014 career and one New England appearance in 2015.
The article was successfully opened; its relevant text is the Johnson paragraph
following the Blount injury paragraph (browser text lines 113-114).

### T.J. Johnson

[PFR JohnTJ00](https://www.pro-football-reference.com/players/J/JohnTJ00.htm)
identifies Anthony Eugene Johnson, South Carolina center born July 17, 1990,
Cincinnati's 2013 seventh-round pick (251). Its indexed table shows CIN in
2014-2017, 45 appearances and 357 offensive snaps, agreeing with the inventory.
[PFR JohnTo20](https://www.pro-football-reference.com/players/J/JohnTo20.htm)
instead identifies Todd Edward Johnson, Florida defensive back born December 18,
1978, Chicago's 2003 fourth-round pick (100).

The [Bengals' 2013 draft account](https://www.bengals.com/news/bengals-beef-up-depth-10041889)
was successfully opened and corroborates South Carolina center T.J. Johnson
selected with the seventh-round compensatory pick at 251. Center versus guard
is consistent offensive-line categorization; it does not resemble Todd's DB role.

### Kwamie Lassiter II

[PFR LassKw00](https://www.pro-football-reference.com/players/L/LassKw00.htm)
identifies Kwamie Lassiter II, Kansas WR born January 21, 1998. Its indexed
table shows CIN in 2022 and 2023, including five offensive snaps in 2023.
[PFR LassKw20](https://www.pro-football-reference.com/players/L/LassKw20.htm)
instead identifies Kwamie Jerome Lassiter, DB born December 3, 1969, and names
Kwamie Lassiter II as his son. Its NFL career ended in 2004.

The [Bengals' May 13, 2022 signings notice](https://www.bengals.com/news/bengals-sign-16-college-free-agents)
was successfully opened and lists Kwamie Lassiter II as a Kansas WR signed among
that year's college free agents. Shared surname and college do not establish
identity; the dates, position and explicit father/son relationship distinguish them.

## Current nflverse identifier crosswalk

Read-only corroboration URL:
[nflverse players.csv](https://github.com/nflverse/nflverse-data/releases/download/players/players.csv).
The file was read into memory with Python stdlib `urllib.request`, then parsed
with `csv.DictReader`; neither its bytes nor a model source receipt were saved.
Observed entity SHA-256:
`a33998d3981bda4f49f40390c5c0fa30036112ee1ea5de19ed4609e2ad3be3e2`,
7,288,456 bytes; HTTP `Last-Modified: Wed, 09 Sep 2026 12:41:38 GMT`.
The six relevant rows, selected by exact GSIS or exact PFR key, provide:

| GSIS | display_name | pfr_id | birth_date | position | college_name | rookie_season | last_season |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 00-0029435 | Damaris Johnson | JohnDa04 | 1989-11-22 | WR | Tulsa | 2012 | 2015 |
| 00-0021086 | Dennis Johnson | JohnDe22 | 1979-12-04 | DE | Kentucky | 2002 | 2004 |
| 00-0030126 | T.J. Johnson | JohnTJ00 | 1990-07-17 | G | South Carolina | 2013 | 2017 |
| 00-0021952 | Todd Johnson | JohnTo20 | 1978-12-18 | DB | Florida | 2003 | 2009 |
| 00-0037420 | Kwamie Lassiter II | LassKw00 | 1998-01-21 | WR | Kansas | 2022 | 2023 |
| 00-0009659 | Kwamie Lassiter | LassKw20 | 1969-12-03 | DB | Kansas; Butler County JC | 1995 | 2004 |

This current crosswalk explicitly corroborates the three GSIS-to-snap-PFR links
and assigns each conflicting roster PFR to a different GSIS/person. It is a
mutable present-day file, not proof that those corrected mappings were published
before the historical decision cutoff. nflverse and its PFR-derived snap data
also are not independent statistical sources; matching totals are corroborating
consistency checks, not independent verification of every snap count.

## Limits and permitted use of these findings

The evidence supports an explicit, reviewable correction record for the three
GSIS/PFR mismatches and the listed frozen rows. It does not establish a blanket
crosswalk repair for other names, identity truth from fuzzy matching, historical
publication timing, numerical role values, or predictive improvement. Separate
source qualification and a new model charter would still be needed for future
reconstruction. Prior raw files, spent study, STOP receipts and HOLD status stay
preserved.
