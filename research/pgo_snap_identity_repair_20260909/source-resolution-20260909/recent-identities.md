# Four recent snap/roster identity conflicts: provider resolution

Research date: 2026-09-09. Scope: read-only identifier research for the four
specified identities; no raw source edits, model-input capture, history builds,
fits, forecasts, production resolver changes, or publication. The only files
written by this investigator are this note and the separately authorized
`provider-evidence.json` excerpt.

**Result: all four GSIS-to-PFR identities are resolved with high confidence.**
For these exact conflicts, the frozen weekly-roster `pfr_id` field is wrong and
the frozen snap `pfr_player_id` agrees with primary identifier-provider evidence.
This resolves 39 inventoried rows / 1,201 offense-plus-defense snaps as an
evidence conclusion; it does not apply a correction or qualify a model source.

| Frozen GSIS identity | Exact scope | Frozen roster PFR | Supported PFR | Rows / volume |
| --- | --- | --- | --- | ---: |
| Tyler Conklin `00-0034270` | 2023 NYJ, W1-6 and W8-18 | `IzzoRy00` | `ConkTy00` | 17 / 772 |
| Byron Young `00-0038978` | 2023 LV, W1-3 and W5-7 | `YounBy01` | `YounBy00` | 6 / 99 |
| Jonah Williams `00-0035944` | 2025 NO, W1-6, W9-10, W12-18 | `WillJo10` | `WillJo16` | 15 / 319 |
| Jacoby Jones `00-0040317` | 2025 WAS, W11 | `JoneJa15` | `JoneJa16` | 1 / 11 |

## Evidence custody and provider authority

Frozen conflict evidence is `../source-conflict-inventory.json`, SHA-256
`c3f721962886ba77fd1ff8d45637508d2050fd294c0f3185dff77f3561a66a29`.
The complete counterpart rows are retained there. For each GSIS above, all
inventoried conflicting roster rows have one consistent combination of birth
date, college, position, PFR, ESB, SMART ID, entry year, and draft metadata.

I independently read and hashed the four relevant pinned files in
`D:\Postgame_Outlet-pgo-model\.cache\pgo_v1`; each still matches the inventory:

| Source | Bytes | SHA-256 / cache filename stem |
| --- | ---: | --- |
| 2023 weekly rosters | 14,612,235 | `1433f1f239784dde7fcb35349d211a9b83abfc0156337b72ec4f923abf715bd3` |
| 2023 snaps | 2,394,875 | `303b61aa5c33ffda863f93a750fc14483f397f9187ad502b1ce71e9b516a64c0` |
| 2025 weekly rosters | 15,385,661 | `c2f7a1ffebe06058400af1989d1cd2900cc5c9659f084623708a06d4e28de35b` |
| 2025 snaps | 2,401,193 | `80b02a6e511aa20283551cae622b29ba4d0a6f006c489a2d91591fcad33792e7` |

The [nflverse players crosswalk](https://github.com/nflverse/nflverse-data/releases/download/players/players.csv)
was read in memory at `2026-09-09T14:21:18.992003+00:00`. Its response was
7,288,456 bytes, SHA-256
`a33998d3981bda4f49f40390c5c0fa30036112ee1ea5de19ed4609e2ad3be3e2`, HTTP
Last-Modified `Wed, 09 Sep 2026 12:41:38 GMT`. Its exact selected fields for all
seven investigation GSIS and six opposite-ID owners are in
`provider-evidence.json`, SHA-256
`a48acc5cd40d598a41b1a247ff6e1dbeb2af03c3ec647d4e6a59b953b0e86799`.
The full crosswalk was not saved or imported into modeling inputs.

The [nflverse-players README](https://github.com/nflverse/nflverse-players)
describes its PFR component as joinable by GSIS and its manual overwrite file as
the provider's mechanism for correcting source IDs. The
[commit-pinned manual overwrite file](https://raw.githubusercontent.com/nflverse/nflverse-players/fda1babceb8f9642261b81306fced6ae5bf29f94/inst/players_manual_overwrite.json)
was read at `2026-09-09T14:21:19.771397+00:00`, 292,642 bytes, SHA-256
`fe2e02668b40048e0adc8cfa62dabd2015c6a77a70188365859d057842e201de`.
Commit `fda1babceb8f9642261b81306fced6ae5bf29f94` is dated
`2026-09-05T09:19:20Z`. Exact relevant override entries are preserved in the
excerpt, including Jacoby and both Byron and Jonah identities. The crosswalk and
manual overwrite are related provider evidence, not independent databases.

PFR profile content below was returned through the web search index on
2026-09-09. Direct page opens for Byron, Jonah DE, and Jacoby returned HTTP 403
or an internal retrieval error; no claim of a successful direct-page fetch is
made. The PFR URLs and indexed biographical fields agree with the exact GSIS
crosswalk and official club/college evidence.

## Tyler Conklin

Frozen GSIS `00-0034270` has DOB `1995-07-30`, Central Michigan, TE, entry 2018,
Minnesota draft pick 157, ESB `CON185250`, ESPN `3915486`, and SMART
`3200434f-4e18-5250-1988-fe7b6c249df3`. The current provider row preserves those
identifiers and DOB and supplies `ConkTy00`; its college field additionally
includes Northwood.

The [PFR Conklin profile](https://www.pro-football-reference.com/players/C/ConkTy00.htm)
identifies a TE born July 30, 1995, from Central Michigan, drafted by Minnesota
157th in 2018. The [Chargers' Conklin biography](https://www.chargers.com/news/tyler-conklin-free-agency-5-things)
independently confirms Central Michigan, the Minnesota selection, his Northwood
background, and his later Jets tenure.

`IzzoRy00` belongs to Ryan Izzo, GSIS `00-0034439`, DOB `1995-12-21`, Florida
State, TE, New England pick 250 in 2018. These exact crosswalk fields agree with
the [PFR Izzo profile](https://www.pro-football-reference.com/players/I/IzzoRy00.htm)
and [Patriots draft signing announcement](https://www.patriots.com/news/patriots-sign-six-of-nine-2018-nfl-draft-selections-sign-nine-rookie-free-330046).
This is a different person despite the shared TE position and draft year.

Conclusion: retain GSIS `00-0034270`; evidence supports roster PFR
`IzzoRy00` -> `ConkTy00` for the inventoried scope. No snap name fallback is
needed. A PFR-only correction must not claim the remaining roster IDs are all
validated.

## Byron Young

Frozen GSIS `00-0038978` has DOB `2000-11-10`, Alabama, DL/DT, entry 2023, Las
Vegas pick 70, ESB `YOU126665`, and SMART
`3200594f-5512-6665-2db8-5dfb5c289094`. The crosswalk preserves those fields and
assigns `YounBy00`; the provider manual override explicitly assigns the same
pair.

The [PFR Alabama Byron profile](https://www.pro-football-reference.com/players/Y/YounBy00.htm)
has the same DOB, college, draft team and pick. Its indexed snap table also has
2023 Las Vegas, DT, jersey 93, six games, and 99 defensive snaps, agreeing with
the inventoried conflict count and volume. The [Raiders draft announcement](https://www.raiders.com/news/byron-young-defensive-tackle-alabama-number-70-overall-pick-nfl-2023-draft)
confirms the Alabama DT selected 70th. The [Eagles biography](https://www.philadelphiaeagles.com/team/players-roster/byron-young/)
corroborates his six Las Vegas appearances in 2023.

`YounBy01` belongs to GSIS `00-0039137`, DOB `1998-03-13`, Tennessee, linebacker,
Los Angeles Rams pick 77 in 2023. The provider explicitly overrides this second
GSIS to `YounBy01`. The [PFR Tennessee Byron profile](https://www.pro-football-reference.com/players/Y/YounBy01.htm)
and [Rams biography](https://www.therams.com/team/players-roster/byron-young/career)
distinguish that OLB from the Alabama DT by birth date, college, team and draft
pick.

Conclusion: retain GSIS `00-0038978`; evidence supports roster PFR
`YounBy01` -> `YounBy00` for the inventoried Las Vegas rows. The two same-name
players must retain separate identities.

## Jonah Williams

Frozen GSIS `00-0035944` has DOB `1995-08-17`, Weber State, DL/DE, entry 2020,
ESB `WIL385174`, ESPN `4032481`, and SMART
`32005749-4c38-5174-f257-0dbf37fd035c`. The crosswalk preserves those exact
identifiers and DOB and assigns `WillJo16`; the provider manual override
explicitly assigns that pair.

The [PFR defensive end profile](https://www.pro-football-reference.com/players/W/WillJo16.htm)
identifies the player born August 17, 1995, from Weber State. The [Saints signing
announcement](https://www.neworleanssaints.com/news/jonah-williams-defensive-end-nfl-free-agency-2025-new-orleans-saints-roster),
dated March 17, 2025, identifies their DE as a 2020 Rams undrafted signing from
Weber State, 6-5 and 275 pounds. The [Saints August 2025 practice-squad
announcement](https://www.neworleanssaints.com/news/new-orleans-saints-2025-practice-squad-announced-roster-moves-transactions-2025-nfl-season)
also identifies him as a 30-year-old Weber State DE.

`WillJo10` belongs to GSIS `00-0035629`, DOB `1997-11-17`, Alabama, offensive
tackle, Cincinnati pick 11 in 2019. The provider manual overwrite explicitly
assigns this second pair. The [PFR offensive line profile](https://www.pro-football-reference.com/players/W/WillJo10.htm)
confirms the DOB, college and first-round draft history; the [Cardinals
biography](https://www.azcardinals.com/team/players-roster/jonah-williams/splits/2019/reg/)
identifies their Alabama offensive lineman and Cincinnati draft origin.

Conclusion: retain GSIS `00-0035944`; evidence supports roster PFR
`WillJo10` -> `WillJo16` for the inventoried New Orleans rows. Additional
out-of-scope observation: frozen DE `draft_club=CIN` conflicts with the official
undrafted Rams history and appears alongside the offensive tackle's PFR ID.
The mechanism of that source corruption is not established here.

## Jacoby Jones

Frozen GSIS `00-0040317` has DOB `2001-07-18`, UCF; Ohio, WR, entry 2025, ESB
`JON403986`, ESPN `5083297`, SMART
`32004a4f-4e40-3986-293f-a86a1e58355c`, height 75 inches and weight 228 pounds.
The current crosswalk preserves those identifiers and biographical fields and
assigns `JoneJa16`; the commit-pinned manual overwrite explicitly assigns
`00-0040317` -> `JoneJa16`.

The [PFR profile at JoneJa16](https://www.pro-football-reference.com/players/J/JoneJa16.htm)
identifies the Washington WR born July 18, 2001, with Ohio/Central Florida
college history. [UCF's own biography](https://ucfknights.com/sports/football/roster/player/jacoby-jones)
gives that exact DOB, WR position, 6-3/228 measurements, and prior Ohio tenure.
[UCF's April 27, 2025 signing report](https://ucfknights.com/news/2025/04/27/four-knights-sign-deals-with-nfl-clubs)
identifies Jones's Washington signing. The [Commanders' November 11, 2025 roster
announcement](https://www.commanders.com/news/commanders-trey-amos-demarcus-walker-robbie-chosen-river-cracraft-jacoby-jones)
identifies their newly promoted WR as the UCF undrafted signing, consistent with
the frozen week-11 active roster.

Conclusion: retain GSIS `00-0040317`; evidence supports roster PFR
`JoneJa15` -> `JoneJa16` for the inventoried Washington row. No current
crosswalk record owns `JoneJa15`. Its PFR URL could not be fetched and no
defensible owner or historical alias relationship was established. In
particular, do not assign `JoneJa15` to the older NFL Jacoby Jones simply because
he shares the name. The positive correction is supported by the exact GSIS
manual override, matching DOB/other IDs, and the correct PFR profile; it does
not depend on identifying the obsolete or erroneous value's owner.

## Limits

This is a current, explicitly dated provider resolution used to investigate
frozen disagreements. It does not prove when the original upstream mistakes
were introduced or corrected. Official biographies corroborate people and
career context; the explicit GSIS/PFR relationship comes from nflverse. PFR
profile evidence was available through indexed retrieval, with the direct
retrieval failures stated above.

The four original PFR conflicts may be represented in a separate reviewable
correction ledger without altering the raw files or prior STOP receipts. This
note neither applies such a ledger nor establishes end-to-end source
qualification. Existing ambiguity guards, other unresolved identities, and
model/publication gates remain the parent investigation's responsibility.
