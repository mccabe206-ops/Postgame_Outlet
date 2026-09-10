# Frozen player input trace: September 8 diagnostic

Input clock: `2026-09-08T15:01:38.802823+00:00`. HEAD checked: `275289e71ae4d8950b621f86447fff673f84840d`. Analysis performed September 9 UTC / September 8 local. Read-only source inspection and independent arithmetic; no fit, history-construction replay, source refresh or model change.

Independent reconstruction matched all 320 saved ten-feature cells across 32 teams; maximum absolute difference 0. Unit counts and known-role counts also matched the saved coverage.

## Main observations

- Pittsburgh: Aaron Rodgers is the frozen selected QB; DOB 1983-12-02 produces age 42.768845, centered age 15.768845 and squared age 248.656484. This unusually large squared input is arithmetic from the DOB, not a player skill evaluation. Defense draft prior 0.165147 is led by Jalen Ramsey (pick 5, median role 0.990196), Patrick Queen (28, 1), and Joey Porter Jr. (32, 1). Offense rookie capital 0.031814 includes Max Iheanachor (pick 21, contribution 0.009919) and Germie Bernard (47, 0.006630); both have no prior role.

- Minnesota: the frozen selected QB is Kyler Murray, while J.J. McCarthy and Carson Wentz are also ACT. Selection is inherited from the verified expected-QB snapshot, not chosen by this adapter. Defense draft prior 0.077153 includes blank-draft Eric Wilson (role 0.985714), James Pierre (0.725368), and Jalen Redmond (0.767188) as zero draft values in its numerator while retaining their roles in the denominator. Gavin Bartholomew has experience 1 and no role history; he enters the offense unit denominator for rookie capital but contributes neither a rookie numerator nor an age/role/draft-prior observation.

- New York Giants: defense draft prior 0.197649 is led by Abdul Carter (pick 3, role 0.891498, feature contribution 0.045779), Kayvon Thibodeaux (5, 0.665411, 0.026467), and Tremaine Edmunds (16, 0.979357, 0.021776). Jaxson Dart is the frozen selected QB. Malik Nabers has a prior role median 0.932709, not a new estimate of Week 1 availability. Jon Runyan is incorrectly represented by inherited zero roles because the historical identity fallback fails; see exact source evidence below.

- Kansas City: defense draft prior 0.103951 has no individual contribution above 0.013286 (George Karlaftis, pick 30, role 0.748106). Defense rookie capital 0.035327 is primarily Mansoor Delane (pick 6, 0.017010), Peter Woods (29, 0.007737), and R Mason Thomas (40, 0.006588), all with no prior roles. Jake Briningstool has experience 1 and no prior role; he is not encoded as a rookie.

- Denver: defense draft prior 0.102031 includes blank-draft Alex Singleton (role 0.980796), Malcolm Roach (0.512126), Ja'Quan McMillian (0.627026), and Dondrea Tillman (0.330519) with draft value zero. Pat Surtain II contributes 0.030923 of the feature. Only 11.390988% of known-age defensive role mass is under 26: Surtain, Riley Moss and Talanoa Hufanga are just above the hard cutoff; no smooth age transition is modeled.

- Rams: frozen source uses raw team code LA, normalized to LAR. Matthew Stafford DOB 1988-02-07 gives age 38.585323, centered 11.585323, squared 134.219719. Myles Garrett is ACT on this frozen LA roster; pick 1 and role 0.947638 contribute 0.072486 of the defense draft prior 0.149323. This source entry is being reported as frozen input, not independently verified current roster news. Defense rookie capital is zero because the sole defensive rookie is Wesley Bailey with blank draft number.

- New England: defense draft prior 0.089337 includes nine blank-draft records; seven have positive prior roles, including Robert Spillane, Christian Elliss, Cory Durden and Leonard Taylor III. Offense role mass omits Mike Onwenu through an inherited identity mismatch and carries Alijah Vera-Tucker's 2024 Jets usage. Ben Brown remains ACT with role median 0.540541 despite the frozen Out annotation, because all ACT records have weight one.

- Detroit: defense draft prior 0.182215 is dominated by Aidan Hutchinson (pick 2, role 0.807995, contribution 0.049379) and Devin White (5, 1, 0.038651). Offense young-role share is 0.728831, including Penei Sewell, Jameson Williams, Sam LaPorta, Jahmyr Gibbs, Christian Mahogany and Tate Ratledge. Sewell (25.914) and Mahogany (25.909) are close to the hard under-26 threshold at the frozen source date.

## Meaning and limits

Each role is the median of up to four prior ACT roster-game entries in the saved final-2025 context. No new 2026 usage or non-QB performance is estimated. All ACT players receive availability weight one. Missing role is excluded from age/young/draft-role means; a saved zero is included as known role but adds zero mass. Missing or zero draft number encodes zero draft prior, not confirmed undrafted status or zero talent. Rookie capital sums 1/sqrt(pick) for experience zero and divides by the entire selected unit count, including players with missing/zero roles. A player may affect the denominator without contributing to the numerator.

Player feature contributions below are arithmetic components of unit descriptors, not separable player point values, causal effects, talent grades or calibrated injury impacts. Position comes from frozen roster fields (OL/LB/DB are broad). The adapter cannot tell which guard is better at blocking, whether a corner is healthy, or how a rookie will perform. The failed historical screen and EXPERIMENTAL / HOLD status remain unchanged.

## Provenance

Current raw roster comes from the issued source directory, not the older current_roster:2026 cache item included in the broad run receipt. `train.py:diagnose_current` reads the issued `roster.csv.gz`. The latter cache item was not used for these current descriptor calculations.

| Evidence | SHA-256 |
| --- | --- |
| `docs\evidence\forecast-lab-2026\september-08-corrected\roster.csv.gz` | `2b2c39db80f1c9d9bf68b956a475cfba9ca19d4b456eefd2b4fa045f3a757965` |
| `docs\evidence\forecast-lab-2026\september-08-corrected\snapshot.json` | `b7064ca078f2ba317d34c3cdf7422c228f96daa6dcfb4d8d131878754ac11deb` |
| `research\pgo_corrected_roster_candidate\preflight-20260908-revised\historical-context.json` | `7e05aaff1254d9c951b1a5cdb8225dc50af0f47a894f86c2a4796fb0697811ac` |
| `research\pgo_corrected_roster_candidate\current-preflight-20260908\current-features.json` | `24cd7c95a46b736322715bba1d29890215c04a2e1f186ccad345d59a49c39512` |
| `research\pgo_corrected_roster_candidate\current-preflight-20260908\coverage.json` | `1995a0252f527d9b9db2541b053b26e4154147704f532f4d43d39629f5022ff4` |
| `research\pgo_corrected_roster_candidate\adapter.py` | `b287c33ce08995821f3aaf1dbab5d46e431ad624c72bac775b6ead5c16143bb2` |
| `pgo_challenger.py` | `f71712d88be59c1bc5f05f319277d1e9c9a76a719882455459317ecea2f28735` |

## Verified inherited fallback zeros and old carryovers

`pgo_challenger.py:_update_after_game` resolves snap rows by roster PFR ID, then exact normalized full name. `_normalize_player_name` only case-folds/collapses spaces. An unmatched ACT player receives `(0.0, 0.0)` in snap history. The adapter preserves that history. These examples are exact mismatches, not evidence of nonparticipation:

| Frozen ACT roster identity in 2025 | Raw snap identity | Last four ACT regular-season weeks and offense snaps | Saved role history |
| --- | --- | --- | --- |
| NE `00-0036198`, Mike Onwenu; PFR blank | Michael Onwenu; `OnweMi00` | W15 52; W16 74; W17 58; W18 59 | `[0,0,0,0]` |
| NYG `00-0036246`, Jon Runyan; PFR blank | Jon Runyan Jr.; `RunyJo00` | W13 55; W15 68; W17 64; W18 75 | `[0,0,0,0]` |

Both players therefore contribute zero to all three non-QB role-weighted offense descriptors, despite recorded snaps. They remain in the selected offense count (the rookie-capital denominator). No repair or counterfactual rating has been computed.

Vera-Tucker: all 17 regular-season 2025 NYJ roster rows are RES, so none update ACT-only role history. Last four 2024 ACT rows are W15-W18; raw snap offense counts are 58,69,63,64 and each share is 1.0. His frozen 2026 NE ACT record therefore carries `[1,1,1,1]` (median 1.0), contributes 0.025472 to NE offense draft prior, and uses present-date age with 2024 role.

Odell Beckham Jr.: no 2025 roster/snap rows; last four 2024 ACT rows are MIA W11-W14. Counts 16,17,14,10 normalize to `[0.23529411764705882,0.25,0.19718309859154928,0.1388888888888889]`. The frozen 2026 NYG ACT record carries median 0.21623860811930406 across the missing season.

Jake Briningstool (KC) and Gavin Bartholomew (MIN): their exact named 2025 regular-season roster rows are RES; no prior ACT roles exist in the saved context. In 2026 both are ACT and experience 1, so role descriptors omit them and rookie numerator is zero. They still count in the full unit denominator.

| Raw historical source | SHA-256 |
| --- | --- |
| `weekly_rosters:2025`: `D:\Postgame_Outlet-pgo-model\.cache\pgo_v1\c2f7a1ffebe06058400af1989d1cd2900cc5c9659f084623708a06d4e28de35b.csv` | `c2f7a1ffebe06058400af1989d1cd2900cc5c9659f084623708a06d4e28de35b` |
| `snap_counts:2025`: `D:\Postgame_Outlet-pgo-model\.cache\pgo_v1\80b02a6e511aa20283551cae622b29ba4d0a6f006c489a2d91591fcad33792e7.csv` | `80b02a6e511aa20283551cae622b29ba4d0a6f006c489a2d91591fcad33792e7` |
| `weekly_rosters:2024`: `D:\Postgame_Outlet-pgo-model\.cache\pgo_v1\074ecaeb9325de943c11f7bbc941425626985090ef8386f90cd837fa5cb5d4b3.csv` | `074ecaeb9325de943c11f7bbc941425626985090ef8386f90cd837fa5cb5d4b3` |
| `snap_counts:2024`: `D:\Postgame_Outlet-pgo-model\.cache\pgo_v1\a2aa58efe093f8aa0ad5aadf09f81d8ec690a1183bd2dde68d20e7f109a9c335.csv` | `a2aa58efe093f8aa0ad5aadf09f81d8ec690a1183bd2dde68d20e7f109a9c335` |

## Team descriptor and player tables

Notation: `role` is median prior role; `draft part` is role/sum(role)/sqrt(pick), so all known-role draft parts sum to the team role-weighted draft prior. `rookie part` is 1/sqrt(pick)/unit_count for experience zero. `young part` is role/sum(role) for age under 26. Missing role produces no contribution to these role-weighted descriptors. Ages use the frozen UTC date. All listed raw rows are ACT.

### PIT

Selected QB: **Aaron Rodgers**, GSIS `00-0023459`, DOB `1983-12-02`, age 42.768845356167, experience 21, draft pick 24. Other ACT QBs: Mason Rudolph, Will Howard, Drew Allar.

| Feature | Saved value |
| --- | --- |
| `qb_age_centered` | 15.768845356167 |
| `qb_age_squared` | 248.656483866725 |
| `offense_role_weighted_age` | 27.108266439405 |
| `offense_young_role_share` | 0.321275004957 |
| `offense_role_weighted_draft_prior` | 0.104135955186 |
| `offense_rookie_draft_capital` | 0.031814325887 |
| `defense_role_weighted_age` | 28.471372908927 |
| `defense_young_role_share` | 0.193646265495 |
| `defense_role_weighted_draft_prior` | 0.165147254317 |
| `defense_rookie_draft_capital` | 0.010178628972 |

Coverage: 53 resolved ACT rows; 0 unmapped positions; 0 unmatched current identities. Missing DOB/experience counts are zero in both units.

**Offense:** 22 players; 16 known-role; role mass 8.845654609492; 6 blank draft records representing 23.4189% of known role mass.

| Player / GSIS | Raw pos | DOB | Age | Exp | Pick | Saved prior roles | Role | Draft part | Young part | Rookie part |
| --- | --- | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| Troy Fautanu / `00-0039871` | OL | 2000-10-11 | 25.908814 | 2 | 20 | [1.000000, 1.000000, 1.000000, 1.000000] | 1.000000 | 0.025278717 | 0.113049858 | 0.000000000 |
| Michael Pittman / `00-0036252` | WR | 1997-10-05 | 28.925988 | 6 | 34 | [0.933333, 0.933333, 0.859649, 0.892308] | 0.912821 | 0.017697664 | 0.000000000 | 0.000000000 |
| Zach Frazier / `00-0039896` | OL | 2001-08-29 | 25.027208 | 2 | 51 | [1.000000, 1.000000, 1.000000, 1.000000] | 1.000000 | 0.015830147 | 0.113049858 | 0.000000000 |
| DK Metcalf / `00-0035640` | WR | 1997-12-14 | 28.734334 | 7 | 64 | [0.860465, 0.826923, 0.787879, 0.878378] | 0.843694 | 0.011922437 | 0.000000000 | 0.000000000 |
| Mason McCormick / `00-0039358` | OL | 2000-05-25 | 26.289383 | 2 | 119 | [1.000000, 1.000000, 1.000000, 1.000000] | 1.000000 | 0.010363264 | 0.000000000 | 0.000000000 |
| Pat Freiermuth / `00-0036894` | TE | 1998-10-25 | 27.871893 | 5 | 55 | [0.424242, 0.432432, 0.696970, 0.693333] | 0.562883 | 0.008580384 | 0.000000000 | 0.000000000 |
| Darnell Washington / `00-0038558` | TE | 2001-08-17 | 25.060063 | 3 | 93 | [0.288462, 0.727273, 0.675676, 0.136364] | 0.482069 | 0.005651157 | 0.054497788 | 0.000000000 |
| Roman Wilson / `00-0039739` | WR | 2001-06-19 | 25.221599 | 2 | 84 | [0.569231, 0.277778, 0.441860, 0.136364] | 0.359819 | 0.004438279 | 0.040677501 | 0.000000000 |
| Spencer Anderson / `00-0038645` | OL | 2000-06-07 | 26.253790 | 3 | 251 | [0.333333, 0.851351, 0.818182, 0.320000] | 0.575758 | 0.004108401 | 0.000000000 | 0.000000000 |
| Ben Skowronek / `00-0036862` | WR | 1997-06-27 | 29.199778 | 5 | 249 | [0.060606, 0.013514, 0.000000, 0.106667] | 0.037060 | 0.000265505 | 0.000000000 | 0.000000000 |
| Robert Tonyan / `00-0033757` | TE | 1994-04-30 | 32.359323 | 9 | blank | [0.049180, 0.044444, 0.000000, 0.031250] | 0.037847 | 0.000000000 | 0.000000000 | 0.000000000 |
| Rico Dowdle / `00-0036139` | RB | 1998-06-14 | 28.236035 | 6 | blank | [0.596491, 0.574074, 0.641509, 0.529412] | 0.585283 | 0.000000000 | 0.000000000 | 0.000000000 |
| Ryan McCollum / `00-0036783` | OL | 1998-03-04 | 28.515301 | 5 | blank | [0.060606, 0.000000, 0.000000, 0.000000] | 0.000000 | 0.000000000 | 0.000000000 | 0.000000000 |
| Jaylen Warren / `00-0037228` | RB | 1998-11-01 | 27.852728 | 4 | blank | [0.454545, 0.486486, 0.318182, 0.373333] | 0.413939 | 0.000000000 | 0.000000000 | 0.000000000 |
| Brock Hoffman / `00-0037336` | OL | 1999-07-02 | 27.187417 | 4 | blank | [0.000000, 0.068966, 0.000000, 1.000000] | 0.034483 | 0.000000000 | 0.000000000 | 0.000000000 |
| Dylan Cook / `00-0037480` | OL | 1998-01-11 | 28.657673 | 4 | blank | [1.000000, 1.000000, 1.000000, 0.960000] | 1.000000 | 0.000000000 | 0.000000000 | 0.000000000 |
| Gennings Dunker / `00-0041396` | OL | 2003-05-08 | 23.337919 | 0 | 96 | missing | missing | 0.000000000 | 0.000000000 | 0.004639185 |
| Kaden Wetjen / `00-0041397` | WR | 2002-03-09 | 24.501530 | 0 | 121 | missing | missing | 0.000000000 | 0.000000000 | 0.004132231 |
| Riley Nowakowski / `00-0041398` | TE | 2002-06-30 | 24.192146 | 0 | 169 | missing | missing | 0.000000000 | 0.000000000 | 0.003496503 |
| Max Iheanachor / `00-0041482` | OL | 2003-10-19 | 22.888903 | 0 | 21 | missing | missing | 0.000000000 | 0.000000000 | 0.009918995 |
| Germie Bernard / `00-0041489` | WR | 2003-12-02 | 22.768435 | 0 | 47 | missing | missing | 0.000000000 | 0.000000000 | 0.006630227 |
| Eli Heidenreich / `00-0041490` | RB | 2003-07-28 | 23.116149 | 0 | 230 | missing | missing | 0.000000000 | 0.000000000 | 0.002997184 |

**Defense:** 24 players; 20 known-role; role mass 12.138790752655; 1 blank draft records representing 0.0000% of known role mass.

| Player / GSIS | Raw pos | DOB | Age | Exp | Pick | Saved prior roles | Role | Draft part | Young part | Rookie part |
| --- | --- | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| Jalen Ramsey / `00-0033055` | DB | 1994-10-24 | 31.874713 | 10 | 5 | [1.000000, 1.000000, 0.961538, 0.980392] | 0.990196 | 0.036480499 | 0.000000000 | 0.000000000 |
| Patrick Queen / `00-0036323` | LB | 1999-08-13 | 27.072424 | 6 | 28 | [1.000000, 1.000000, 1.000000, 1.000000] | 1.000000 | 0.015568457 | 0.000000000 | 0.000000000 |
| Joey Porter Jr. / `00-0039167` | DB | 2000-07-26 | 26.119633 | 3 | 32 | [1.000000, 0.986486, 1.000000, 1.000000] | 1.000000 | 0.014562958 | 0.000000000 | 0.000000000 |
| T.J. Watt / `00-0033886` | LB | 1994-10-11 | 31.910306 | 9 | 30 | [0.815385, 0.824324, 0.875000, 0.843137] | 0.833731 | 0.012539776 | 0.000000000 | 0.000000000 |
| Jaquan Brisker / `00-0038135` | DB | 1999-04-20 | 27.387284 | 4 | 48 | [1.000000, 1.000000, 1.000000, 1.000000] | 1.000000 | 0.011890605 | 0.000000000 | 0.000000000 |
| Asante Samuel Jr. / `00-0036617` | DB | 1999-10-03 | 26.932791 | 5 | 47 | [1.000000, 0.972973, 0.961538, 0.411765] | 0.967256 | 0.011622966 | 0.000000000 | 0.000000000 |
| Derrick Harmon / `00-0040678` | DL | 2003-08-03 | 23.099721 | 1 | 21 | [0.476923, 0.581081, 0.692308, 0.705882] | 0.636694 | 0.011445795 | 0.052451220 | 0.000000000 |
| Cameron Heyward / `00-0027969` | DL | 1989-05-06 | 37.342314 | 15 | 31 | [0.740000, 0.608108, 0.711538, 0.725490] | 0.718514 | 0.010631123 | 0.000000000 | 0.000000000 |
| Jamel Dean / `00-0035699` | DB | 1996-10-15 | 29.897945 | 7 | 94 | [1.000000, 0.943662, 1.000000, 0.600000] | 0.971831 | 0.008257553 | 0.000000000 | 0.000000000 |
| Alex Highsmith / `00-0036333` | LB | 1997-08-07 | 29.087524 | 6 | 102 | [0.880000, 0.905405, 0.923077, 0.862745] | 0.892703 | 0.007281676 | 0.000000000 | 0.000000000 |
| Keeanu Benton / `00-0039110` | DL | 2001-07-17 | 25.144938 | 3 | 49 | [0.540000, 0.527027, 0.653846, 0.862745] | 0.596923 | 0.007024977 | 0.049174839 | 0.000000000 |
| Payton Wilson / `00-0039741` | LB | 2000-04-21 | 26.382472 | 2 | 98 | [0.420000, 0.702703, 0.442308, 0.215686] | 0.431154 | 0.003587929 | 0.000000000 | 0.000000000 |
| Nick Herbig / `00-0038577` | LB | 2001-11-21 | 24.797224 | 3 | 132 | [0.337500, 0.520000, 0.788462, 0.254902] | 0.428750 | 0.003074268 | 0.035320652 | 0.000000000 |
| Jack Sawyer / `00-0040160` | LB | 2002-05-06 | 24.342731 | 1 | 123 | [0.560000, 0.891892, 0.250000, 0.098039] | 0.405000 | 0.003008341 | 0.033364114 | 0.000000000 |
| Rayshawn Jenkins / `00-0033941` | DB | 1994-01-25 | 32.619424 | 9 | 113 | [0.090909, 0.080000, 0.545455, 0.529412] | 0.310160 | 0.002403653 | 0.000000000 | 0.000000000 |
| Sebastian Joseph-Day / `00-0034810` | DL | 1995-03-21 | 31.469503 | 8 | 195 | [0.594595, 0.266667, 0.444444, 0.245902] | 0.355556 | 0.002097562 | 0.000000000 | 0.000000000 |
| Brandin Echols / `00-0036504` | DB | 1997-10-16 | 28.895871 | 5 | 200 | [0.412500, 0.340000, 0.202703, 0.294118] | 0.317059 | 0.001846926 | 0.000000000 | 0.000000000 |
| Yahya Black / `00-0040188` | DL | 2002-04-21 | 24.383800 | 1 | 164 | [0.680000, 0.297297, 0.269231, 0.235294] | 0.283264 | 0.001822192 | 0.023335441 | 0.000000000 |
| Cole Holcomb / `00-0035286` | LB | 1996-07-30 | 30.108763 | 7 | 173 | [0.000000, 0.000000, 0.000000, 0.000000] | 0.000000 | 0.000000000 | 0.000000000 | 0.000000000 |
| Carson Bruener / `00-0040231` | LB | 2001-06-06 | 25.257192 | 1 | 226 | [0.000000, 0.000000, 0.000000, 0.000000] | 0.000000 | 0.000000000 | 0.000000000 | 0.000000000 |
| Kevin Jobity Jr. / `00-0041261` | DL | 2003-10-06 | 22.924495 | 0 | blank | missing | missing | 0.000000000 | 0.000000000 | 0.000000000 |
| Daylen Everette / `00-0041393` | DB | 2004-05-06 | 22.341321 | 0 | 85 | missing | missing | 0.000000000 | 0.000000000 | 0.004519385 |
| Gabe Rubio / `00-0041400` | DL | 2003-07-09 | 23.168169 | 0 | 210 | missing | missing | 0.000000000 | 0.000000000 | 0.002875273 |
| Robert Spears-Jennings / `00-0041401` | DB | 2004-01-25 | 22.620588 | 0 | 224 | missing | missing | 0.000000000 | 0.000000000 | 0.002783971 |

### DEN

Selected QB: **Bo Nix**, GSIS `00-0039732`, DOB `2000-02-25`, age 26.535794711733, experience 2, draft pick 12. Other ACT QBs: Jarrett Stidham, Sam Ehlinger.

| Feature | Saved value |
| --- | --- |
| `qb_age_centered` | -0.464205288267 |
| `qb_age_squared` | 0.215486549655 |
| `offense_role_weighted_age` | 28.712696034672 |
| `offense_young_role_share` | 0.173963234346 |
| `offense_role_weighted_draft_prior` | 0.146197013456 |
| `offense_rookie_draft_capital` | 0.011027862802 |
| `defense_role_weighted_age` | 27.778361225855 |
| `defense_young_role_share` | 0.113909881375 |
| `defense_role_weighted_draft_prior` | 0.102031399635 |
| `defense_rookie_draft_capital` | 0.004923659639 |

Coverage: 53 resolved ACT rows; 0 unmapped positions; 0 unmatched current identities. Missing DOB/experience counts are zero in both units.

**Offense:** 23 players; 20 known-role; role mass 11.798504435971; 3 blank draft records representing 10.9001% of known role mass.

| Player / GSIS | Raw pos | DOB | Age | Exp | Pick | Saved prior roles | Role | Draft part | Young part | Rookie part |
| --- | --- | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| Mike McGlinchey / `00-0034847` | OL | 1995-01-12 | 31.655681 | 8 | 9 | [1.000000, 1.000000, 1.000000, 1.000000] | 1.000000 | 0.028252168 | 0.000000000 | 0.000000000 |
| Jaylen Waddle / `00-0036613` | WR | 1998-11-25 | 27.787018 | 5 | 6 | [0.784615, 0.840000, 0.711864, 0.254545] | 0.748240 | 0.025890371 | 0.000000000 | 0.000000000 |
| Garett Bolles / `00-0033538` | OL | 1992-05-27 | 34.284072 | 9 | 20 | [0.970588, 1.000000, 1.000000, 0.864407] | 0.985294 | 0.018673423 | 0.000000000 | 0.000000000 |
| Courtland Sutton / `00-0034348` | WR | 1995-10-10 | 30.913708 | 8 | 40 | [0.882353, 0.939394, 0.819444, 0.779661] | 0.850899 | 0.011403047 | 0.000000000 | 0.000000000 |
| Quinn Meinerz / `00-0037001` | OL | 1998-11-15 | 27.814397 | 5 | 98 | [0.970588, 1.000000, 1.000000, 1.000000] | 1.000000 | 0.008561700 | 0.000000000 | 0.000000000 |
| RJ Harvey / `00-0040730` | RB | 2001-02-04 | 25.591217 | 1 | 60 | [0.676471, 0.590909, 0.652778, 0.559322] | 0.621843 | 0.006804222 | 0.052705276 | 0.000000000 |
| Luke Wattenberg / `00-0037278` | OL | 1997-09-10 | 28.994435 | 4 | 171 | [1.000000, 1.000000, 1.000000, 1.000000] | 1.000000 | 0.006481492 | 0.000000000 | 0.000000000 |
| Pat Bryant / `00-0040134` | WR | 2002-12-10 | 23.745867 | 1 | 74 | [0.700000, 0.472973, 0.636364, 0.661017] | 0.648690 | 0.006391379 | 0.054980722 | 0.000000000 |
| Evan Engram / `00-0033881` | TE | 1994-09-02 | 32.017085 | 9 | 23 | [0.279412, 0.439394, 0.305556, 0.389831] | 0.347693 | 0.006144763 | 0.000000000 | 0.000000000 |
| Ben Powers / `00-0034978` | OL | 1996-10-29 | 29.859614 | 7 | 123 | [1.000000, 0.348485, 0.569444, 1.000000] | 0.784722 | 0.005997033 | 0.000000000 | 0.000000000 |
| J.K. Dobbins / `00-0036158` | RB | 1998-12-17 | 27.726784 | 6 | 55 | [0.493827, 0.523810, 0.460317, 0.524590] | 0.508818 | 0.005815063 | 0.000000000 | 0.000000000 |
| Adam Trautman / `00-0036422` | TE | 1997-02-05 | 29.588561 | 6 | 105 | [0.617647, 0.575758, 0.722222, 0.576271] | 0.596959 | 0.004937680 | 0.000000000 | 0.000000000 |
| Troy Franklin / `00-0039868` | WR | 2003-02-06 | 23.587069 | 2 | 102 | [0.500000, 0.636364, 0.375000, 0.423729] | 0.461864 | 0.003876033 | 0.039146013 | 0.000000000 |
| Marvin Mims Jr. / `00-0038976` | WR | 2002-03-19 | 24.474151 | 3 | 63 | [0.308824, 0.318182, 0.472222, 0.322034] | 0.320108 | 0.003418213 | 0.027131223 | 0.000000000 |
| Alex Forsyth / `00-0038649` | OL | 1999-02-13 | 27.567986 | 3 | 257 | [0.029412, 0.000000, 1.000000, 0.932203] | 0.480808 | 0.002542013 | 0.000000000 | 0.000000000 |
| Tyler Badie / `00-0037085` | RB | 1999-02-07 | 27.584413 | 4 | 196 | [0.102941, 0.227273, 0.111111, 0.152542] | 0.131827 | 0.000798084 | 0.000000000 | 0.000000000 |
| Matt Peart / `00-0036392` | OL | 1997-06-11 | 29.243585 | 6 | 99 | [0.000000, 0.049383, 0.000000, 1.000000] | 0.024691 | 0.000210330 | 0.000000000 | 0.000000000 |
| Lil'Jordan Humphrey / `00-0035406` | WR | 1998-04-19 | 28.389358 | 7 | blank | [0.676471, 0.196970, 0.597222, 0.271186] | 0.434204 | 0.000000000 | 0.000000000 | 0.000000000 |
| Nate Adkins / `00-0038783` | TE | 1999-07-09 | 27.168251 | 3 | blank | [0.253968, 0.367647, 0.106061, 0.389831] | 0.310808 | 0.000000000 | 0.000000000 | 0.000000000 |
| Alex Palczewski / `00-0038796` | OL | 1999-08-03 | 27.099804 | 3 | blank | [0.970588, 0.651515, 0.430556, 0.000000] | 0.541035 | 0.000000000 | 0.000000000 | 0.000000000 |
| Dallen Bentley / `00-0041133` | TE | 2000-12-31 | 25.687044 | 0 | 256 | missing | missing | 0.000000000 | 0.000000000 | 0.002717391 |
| Jonah Coleman / `00-0041496` | RB | 2003-08-20 | 23.053177 | 0 | 108 | missing | missing | 0.000000000 | 0.000000000 | 0.004183698 |
| Kage Casey / `00-0041498` | OL | 2003-10-10 | 22.913544 | 0 | 111 | missing | missing | 0.000000000 | 0.000000000 | 0.004126774 |

**Defense:** 25 players; 24 known-role; role mass 10.697728680587; 7 blank draft records representing 23.5745% of known role mass.

| Player / GSIS | Raw pos | DOB | Age | Exp | Pick | Saved prior roles | Role | Draft part | Young part | Rookie part |
| --- | --- | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| Pat Surtain II / `00-0036874` | DB | 2000-04-14 | 26.401637 | 5 | 9 | [0.984848, 1.000000, 1.000000, 0.947368] | 0.992424 | 0.030923207 | 0.000000000 | 0.000000000 |
| Brandon Jones / `00-0036221` | DB | 1998-04-02 | 28.435902 | 6 | 70 | [1.000000, 0.988889, 0.920000, 0.515152] | 0.954444 | 0.010663752 | 0.000000000 | 0.000000000 |
| Riley Moss / `00-0038552` | DB | 2000-03-03 | 26.516629 | 3 | 83 | [1.000000, 0.985714, 1.000000, 1.000000] | 1.000000 | 0.010260520 | 0.000000000 | 0.000000000 |
| Zach Allen / `00-0035248` | DL | 1997-08-20 | 29.051931 | 7 | 65 | [0.757576, 0.657143, 0.627907, 0.666667] | 0.661905 | 0.007674450 | 0.000000000 | 0.000000000 |
| Jahdae Barron / `00-0040720` | DB | 2001-12-04 | 24.761631 | 1 | 20 | [0.227273, 0.257143, 0.488372, 0.456140] | 0.356642 | 0.007454619 | 0.033338068 | 0.000000000 |
| Nik Bonitto / `00-0037249` | LB | 1999-09-26 | 26.951957 | 4 | 64 | [0.681818, 0.471429, 0.744186, 0.561404] | 0.621611 | 0.007263351 | 0.000000000 | 0.000000000 |
| Talanoa Hufanga / `00-0036564` | DB | 2000-02-01 | 26.601504 | 5 | 180 | [1.000000, 0.985714, 0.930233, 0.947368] | 0.966541 | 0.006734302 | 0.000000000 | 0.000000000 |
| Eyioma Uwazurike / `00-0038106` | DL | 1998-05-06 | 28.342813 | 4 | 116 | [0.242424, 0.442857, 0.558140, 0.561404] | 0.500498 | 0.004343922 | 0.000000000 | 0.000000000 |
| Jonah Elliss / `00-0039809` | LB | 2003-04-03 | 23.433746 | 2 | 76 | [0.333333, 0.314286, 0.279070, 0.701754] | 0.323810 | 0.003472092 | 0.030268998 | 0.000000000 |
| D.J. Jones / `00-0033297` | DL | 1995-01-19 | 31.636515 | 9 | 198 | [0.303030, 0.442857, 0.465116, 0.333333] | 0.388095 | 0.002578185 | 0.000000000 | 0.000000000 |
| Justin Strnad / `00-0036428` | LB | 1996-08-21 | 30.048529 | 6 | 178 | [0.200000, 0.000000, 0.511628, 0.877193] | 0.355814 | 0.002492995 | 0.000000000 | 0.000000000 |
| Que Robinson / `00-0040168` | LB | 2001-05-12 | 25.325640 | 1 | 134 | [0.315068, 0.414286, 0.288889, 0.271429] | 0.301979 | 0.002438554 | 0.028228300 | 0.000000000 |
| Tycen Anderson / `00-0037752` | DB | 1999-06-13 | 27.239437 | 4 | 166 | [0.000000, 0.372093, 0.307692, 0.269231] | 0.288462 | 0.002092870 | 0.000000000 | 0.000000000 |
| Sai'vion Jones / `00-0040153` | DL | 2003-07-03 | 23.184597 | 1 | 101 | [0.125000, 0.200000, 0.298246] | 0.200000 | 0.001860277 | 0.018695557 | 0.000000000 |
| Jordan Jackson / `00-0037294` | DL | 1998-01-30 | 28.605652 | 4 | 194 | [0.253521, 0.244186, 0.163934, 0.438596] | 0.248854 | 0.001670135 | 0.000000000 | 0.000000000 |
| Kris Abrams-Draine / `00-0039371` | DB | 2001-10-04 | 24.928643 | 2 | 145 | [0.015152, 0.000000, 0.000000, 0.298246] | 0.007576 | 0.000058810 | 0.000708165 | 0.000000000 |
| JL Skinner / `00-0038605` | DB | 2001-04-16 | 25.396825 | 3 | 183 | [0.000000, 0.014286, 0.000000, 0.298246] | 0.007143 | 0.000049358 | 0.000667698 | 0.000000000 |
| Alex Singleton / `00-0031898` | LB | 1993-12-07 | 32.753582 | 11 | blank | [0.984848, 1.000000, 0.976744, 0.947368] | 0.980796 | 0.000000000 | 0.000000000 | 0.000000000 |
| Malcolm Roach / `00-0035763` | DL | 1998-06-09 | 28.249724 | 6 | blank | [0.363636, 0.442857, 0.581395, 0.596491] | 0.512126 | 0.000000000 | 0.000000000 | 0.000000000 |
| Devon Key / `00-0036683` | DB | 1997-10-28 | 28.863016 | 5 | blank | [0.030303, 0.028571, 0.069767, 0.929825] | 0.050035 | 0.000000000 | 0.000000000 | 0.000000000 |
| Ja'Quan McMillian / `00-0037384` | DB | 2000-06-04 | 26.262004 | 4 | blank | [0.742424, 0.500000, 0.511628, 0.842105] | 0.627026 | 0.000000000 | 0.000000000 | 0.000000000 |
| Dondrea Tillman / `00-0037799` | LB | 1998-04-30 | 28.359241 | 6 | blank | [0.318182, 0.342857, 0.255814, 0.666667] | 0.330519 | 0.000000000 | 0.000000000 | 0.000000000 |
| Karene Reid / `00-0040449` | LB | 2000-02-19 | 26.552222 | 1 | blank | [0.000000, 0.041667, 0.000000, 0.000000] | 0.000000 | 0.000000000 | 0.000000000 | 0.000000000 |
| Jordan Turner / `00-0040634` | LB | 2001-12-13 | 24.736990 | 1 | blank | [0.000000, 0.042857, 0.000000, 0.298246] | 0.021429 | 0.000000000 | 0.002003095 | 0.000000000 |
| Tyler Onyedim / `00-0041552` | DL | 2003-05-14 | 23.321492 | 0 | 66 | missing | missing | 0.000000000 | 0.000000000 | 0.004923660 |

### KC

Selected QB: **Patrick Mahomes**, GSIS `00-0033873`, DOB `1995-09-17`, age 30.976679877068, experience 9, draft pick 10. Other ACT QBs: Justin Fields, Garrett Nussmeier.

| Feature | Saved value |
| --- | --- |
| `qb_age_centered` | 3.976679877068 |
| `qb_age_squared` | 15.813982844677 |
| `offense_role_weighted_age` | 26.828027721162 |
| `offense_young_role_share` | 0.412527528729 |
| `offense_role_weighted_draft_prior` | 0.125596432376 |
| `offense_rookie_draft_capital` | 0.006703864207 |
| `defense_role_weighted_age` | 27.264297493528 |
| `defense_young_role_share` | 0.349984737269 |
| `defense_role_weighted_draft_prior` | 0.103950785290 |
| `defense_rookie_draft_capital` | 0.035326672507 |

Coverage: 53 resolved ACT rows; 0 unmapped positions; 0 unmatched current identities. Missing DOB/experience counts are zero in both units.

**Offense:** 23 players; 18 known-role; role mass 8.675868792846; 5 blank draft records representing 0.3646% of known role mass.

| Player / GSIS | Raw pos | DOB | Age | Exp | Pick | Saved prior roles | Role | Draft part | Young part | Rookie part |
| --- | --- | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| Josh Simmons / `00-0040116` | OL | 2002-12-26 | 23.702061 | 1 | 32 | [1.000000, 1.000000, 1.000000, 0.696970] | 1.000000 | 0.020375676 | 0.115262232 | 0.000000000 |
| Xavier Worthy / `00-0039894` | WR | 2003-04-27 | 23.368036 | 2 | 28 | [0.765625, 0.672131, 0.844444, 0.790698] | 0.778161 | 0.016950310 | 0.089692612 | 0.000000000 |
| Creed Humphrey / `00-0036623` | OL | 1999-06-28 | 27.198368 | 5 | 63 | [1.000000, 1.000000, 1.000000, 1.000000] | 1.000000 | 0.014521676 | 0.000000000 | 0.000000000 |
| Kingsley Suamataia / `00-0039844` | OL | 2003-01-18 | 23.639089 | 2 | 63 | [1.000000, 1.000000, 1.000000, 1.000000] | 1.000000 | 0.014521676 | 0.115262232 | 0.000000000 |
| Travis Kelce / `00-0030506` | TE | 1989-10-05 | 36.926152 | 13 | 63 | [0.983607, 0.777778, 0.976744, 0.796875] | 0.886810 | 0.012877962 | 0.000000000 | 0.000000000 |
| Rashee Rice / `00-0039067` | WR | 2000-04-22 | 26.379734 | 3 | 55 | [0.625000, 0.893939, 0.781250, 0.852459] | 0.816855 | 0.012695517 | 0.000000000 | 0.000000000 |
| Kenneth Walker III / `00-0038134` | RB | 2000-10-20 | 25.884173 | 4 | 41 | [0.416667, 0.441176, 0.469697, 0.420290] | 0.430733 | 0.007753600 | 0.049647266 | 0.000000000 |
| Trey Smith / `00-0036660` | OL | 1999-06-16 | 27.231223 | 5 | 226 | [1.000000, 0.406250, 1.000000, 1.000000] | 1.000000 | 0.007667130 | 0.000000000 | 0.000000000 |
| Tyquan Thornton / `00-0038104` | WR | 2000-08-07 | 26.086778 | 4 | 50 | [0.260417, 0.242424, 0.296875, 0.508197] | 0.278646 | 0.004542078 | 0.000000000 | 0.000000000 |
| Noah Gray / `00-0036637` | TE | 1999-04-30 | 27.359905 | 5 | 162 | [0.377049, 0.511111, 0.488372, 0.562500] | 0.499742 | 0.004525588 | 0.000000000 | 0.000000000 |
| Jaylon Moore / `00-0036557` | OL | 1998-01-09 | 28.663148 | 5 | 155 | [0.545455, 1.000000, 0.426230, 0.031250] | 0.485842 | 0.004497967 | 0.000000000 | 0.000000000 |
| Joshua Ezeudu / `00-0037807` | OL | 1999-09-19 | 26.971122 | 4 | 67 | [0.029412, 0.033898, 0.160714, 0.528302] | 0.097306 | 0.001370221 | 0.000000000 | 0.000000000 |
| Brashard Smith / `00-0040078` | RB | 2003-04-11 | 23.411843 | 1 | 228 | [0.049180, 0.177778, 0.139535, 0.531250] | 0.158656 | 0.001211092 | 0.018287083 | 0.000000000 |
| Jalen Royals / `00-0040646` | WR | 2003-02-18 | 23.554214 | 1 | 133 | [0.000000, 0.066667, 0.116279, 0.671875] | 0.091473 | 0.000914226 | 0.010543367 | 0.000000000 |
| Jared Wiley / `00-0039824` | TE | 2000-11-02 | 25.848580 | 2 | 131 | [0.000000, 0.044444, 0.116279, 0.187500] | 0.080362 | 0.000809284 | 0.009262675 | 0.000000000 |
| Hunter Nourzad / `00-0039827` | OL | 2000-11-26 | 25.782870 | 2 | 159 | [0.032787, 0.022222, 0.046512, 1.000000] | 0.039649 | 0.000362429 | 0.004570062 | 0.000000000 |
| Mike Caliendo / `00-0037207` | OL | 1997-10-21 | 28.882181 | 4 | blank | [1.000000, 0.000000, 0.000000, 0.046875] | 0.023438 | 0.000000000 | 0.000000000 | 0.000000000 |
| Nikko Remigio / `00-0038519` | WR | 1999-11-04 | 26.845178 | 3 | blank | [0.000000, 0.000000, 0.016393, 0.088889] | 0.008197 | 0.000000000 | 0.000000000 | 0.000000000 |
| Jake Briningstool / `00-0040081` | TE | 2002-12-09 | 23.748605 | 1 | blank | missing | missing | 0.000000000 | 0.000000000 | 0.000000000 |
| Cyrus Allen / `00-0040890` | WR | 2003-02-11 | 23.573379 | 0 | 176 | missing | missing | 0.000000000 | 0.000000000 | 0.003277297 |
| Diego Pounds / `00-0040987` | OL | 2002-12-12 | 23.740392 | 0 | blank | missing | missing | 0.000000000 | 0.000000000 | 0.000000000 |
| Emmett Johnson / `00-0041013` | RB | 2003-10-10 | 22.913544 | 0 | 161 | missing | missing | 0.000000000 | 0.000000000 | 0.003426567 |
| Kahlil Benson / `00-0041019` | OL | 2002-08-30 | 24.025134 | 0 | blank | missing | missing | 0.000000000 | 0.000000000 | 0.000000000 |

**Defense:** 24 players; 17 known-role; role mass 10.280521239278; 6 blank draft records representing 6.6898% of known role mass.

| Player / GSIS | Raw pos | DOB | Age | Exp | Pick | Saved prior roles | Role | Draft part | Young part | Rookie part |
| --- | --- | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| George Karlaftis / `00-0037192` | DL | 2001-04-03 | 25.432418 | 4 | 30 | [0.800000, 0.787879, 0.643836, 0.708333] | 0.748106 | 0.013285791 | 0.072769273 | 0.000000000 |
| Nick Bolton / `00-0036621` | LB | 2000-03-10 | 26.497464 | 5 | 58 | [0.909091, 1.000000, 0.986111, 1.000000] | 0.993056 | 0.012683655 | 0.000000000 | 0.000000000 |
| Nohl Williams / `00-0040670` | DB | 2002-09-23 | 23.959424 | 1 | 85 | [1.000000, 0.547945, 1.000000, 1.000000] | 1.000000 | 0.010550557 | 0.097271333 | 0.000000000 |
| Kristian Fulton / `00-0036416` | DB | 1998-09-03 | 28.014264 | 6 | 61 | [0.030303, 0.630137, 0.986111, 1.000000] | 0.808124 | 0.010064634 | 0.000000000 | 0.000000000 |
| Chamarri Conner / `00-0038982` | DB | 2000-07-11 | 26.160701 | 3 | 119 | [1.000000, 1.000000, 1.000000, 1.000000] | 1.000000 | 0.008916848 | 0.000000000 | 0.000000000 |
| Chris Jones / `00-0032762` | DL | 1994-07-03 | 32.184097 | 10 | 37 | [0.636364, 0.547945, 0.527778, 0.354839] | 0.537861 | 0.008601109 | 0.000000000 | 0.000000000 |
| L'Jarius Sneed / `00-0036374` | DB | 1997-01-21 | 29.629630 | 6 | 138 | [1.000000, 0.941176, 0.967213, 0.507692] | 0.954195 | 0.007901006 | 0.000000000 | 0.000000000 |
| Drue Tranquill / `00-0035262` | LB | 1995-08-15 | 31.067031 | 7 | 130 | [0.939394, 0.931507, 0.902778, 0.500000] | 0.917142 | 0.007824380 | 0.000000000 | 0.000000000 |
| Ashton Gillotte / `00-0040640` | DL | 2002-10-30 | 23.858122 | 1 | 66 | [0.500000, 0.616438, 0.625000, 0.741935] | 0.620719 | 0.007432040 | 0.060378182 | 0.000000000 |
| Alohi Gilman / `00-0036380` | DB | 1997-09-17 | 28.975270 | 6 | 186 | [1.000000, 0.986486, 1.000000, 0.960000] | 0.993243 | 0.007084089 | 0.000000000 | 0.000000000 |
| Felix Anudike-Uzomah / `00-0039006` | DL | 2002-01-24 | 24.621998 | 3 | 31 | [0.145161, 0.101695, 0.295775, 0.702703] | 0.220468 | 0.003851674 | 0.021445213 | 0.000000000 |
| Jaden Hicks / `00-0039825` | DB | 2002-08-16 | 24.063465 | 2 | 133 | [0.075758, 0.232877, 0.458333, 0.596774] | 0.345605 | 0.002915004 | 0.033617461 | 0.000000000 |
| Khyiris Tonga / `00-0036909` | DL | 1996-07-07 | 30.171735 | 5 | 250 | [0.543860, 0.184615, 0.614286, 0.309091] | 0.426475 | 0.002623667 | 0.000000000 | 0.000000000 |
| Jeffrey Bassa / `00-0040072` | LB | 2002-09-20 | 23.967638 | 1 | 156 | [0.000000, 0.000000, 0.055556, 0.354839] | 0.027778 | 0.000216332 | 0.002701981 | 0.000000000 |
| Jack Cochrane / `00-0037208` | LB | 1999-02-09 | 27.578937 | 4 | blank | [0.090909, 0.397260, 0.013889, 0.000000] | 0.052399 | 0.000000000 | 0.000000000 | 0.000000000 |
| Christian Roland-Wallace / `00-0039324` | DB | 2001-11-23 | 24.791748 | 2 | blank | [0.479167, 0.242424, 0.564516, 0.431373] | 0.455270 | 0.000000000 | 0.044284681 | 0.000000000 |
| Cooper McDonald / `00-0040118` | LB | 2001-08-07 | 25.087442 | 1 | blank | [0.000000, 0.068493, 0.291667, 0.419355] | 0.180080 | 0.000000000 | 0.017516613 | 0.000000000 |
| Xavier Nwankpa / `00-0040957` | DB | 2003-12-08 | 22.752007 | 0 | blank | missing | missing | 0.000000000 | 0.000000000 | 0.000000000 |
| Jack Pyburn / `00-0041256` | LB | 2003-09-03 | 23.014846 | 0 | blank | missing | missing | 0.000000000 | 0.000000000 | 0.000000000 |
| Bryson Eason / `00-0041358` | DL | 2002-01-21 | 24.630211 | 0 | blank | missing | missing | 0.000000000 | 0.000000000 | 0.000000000 |
| Jadon Canady / `00-0041497` | DB | 2003-05-01 | 23.357085 | 0 | 109 | missing | missing | 0.000000000 | 0.000000000 | 0.003990943 |
| R Mason Thomas / `00-0041501` | DL | 2004-08-25 | 22.037413 | 0 | 40 | missing | missing | 0.000000000 | 0.000000000 | 0.006588078 |
| Mansoor Delane / `00-0041543` | DB | 2003-12-15 | 22.732842 | 0 | 6 | missing | missing | 0.000000000 | 0.000000000 | 0.017010345 |
| Peter Woods / `00-0041545` | DL | 2005-03-05 | 21.511735 | 0 | 29 | missing | missing | 0.000000000 | 0.000000000 | 0.007737306 |

### LAR

Selected QB: **Matthew Stafford**, GSIS `00-0026498`, DOB `1988-02-07`, age 38.585323449489, experience 17, draft pick 1. Other ACT QBs: Stetson Bennett, Ty Simpson.

| Feature | Saved value |
| --- | --- |
| `qb_age_centered` | 11.585323449489 |
| `qb_age_squared` | 134.219719429281 |
| `offense_role_weighted_age` | 27.939211659928 |
| `offense_young_role_share` | 0.300778925491 |
| `offense_role_weighted_draft_prior` | 0.080113259639 |
| `offense_rookie_draft_capital` | 0.008303497080 |
| `defense_role_weighted_age` | 27.107183540266 |
| `defense_young_role_share` | 0.368064367775 |
| `defense_role_weighted_draft_prior` | 0.149322553523 |
| `defense_rookie_draft_capital` | 0.000000000000 |

Coverage: 52 resolved ACT rows; 0 unmapped positions; 0 unmatched current identities. Missing DOB/experience counts are zero in both units.

**Offense:** 24 players; 22 known-role; role mass 10.001190271082; 5 blank draft records representing 23.1761% of known role mass.

| Player / GSIS | Raw pos | DOB | Age | Exp | Pick | Saved prior roles | Role | Draft part | Young part | Rookie part |
| --- | --- | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| Steve Avila / `00-0039058` | OL | 1999-10-16 | 26.897198 | 3 | 36 | [1.000000, 1.000000, 1.000000, 1.000000] | 1.000000 | 0.016664683 | 0.000000000 | 0.000000000 |
| Terrance Ferguson / `00-0040737` | TE | 2003-03-07 | 23.507670 | 1 | 46 | [0.642857, 0.777778, 0.760870, 0.492308] | 0.701863 | 0.010347179 | 0.070177982 | 0.000000000 |
| Davante Adams / `00-0031381` | WR | 1992-12-24 | 33.706373 | 12 | 53 | [0.767857, 0.750000, 0.428571, 0.458333] | 0.604167 | 0.008297880 | 0.000000000 | 0.000000000 |
| Kevin Dotson / `00-0036339` | OL | 1996-09-18 | 29.971868 | 6 | 135 | [1.000000, 0.828571, 1.000000, 0.228261] | 0.914286 | 0.007867982 | 0.000000000 | 0.000000000 |
| Colby Parkinson / `00-0036244` | TE | 1999-01-07 | 27.669288 | 6 | 133 | [0.861111, 0.858696, 0.784615, 0.840000] | 0.849348 | 0.007363903 | 0.000000000 | 0.000000000 |
| Puka Nacua / `00-0039075` | WR | 2001-05-29 | 25.279095 | 3 | 177 | [0.555556, 0.782609, 0.738462, 0.693333] | 0.715897 | 0.005380374 | 0.071581223 | 0.000000000 |
| Kyren Williams / `00-0037840` | RB | 2000-08-26 | 26.034758 | 4 | 164 | [0.541667, 0.706522, 0.707692, 0.626667] | 0.666594 | 0.005204607 | 0.000000000 | 0.000000000 |
| Davis Allen / `00-0039074` | TE | 2001-02-03 | 25.593955 | 3 | 175 | [0.750000, 0.652174, 0.415385, 0.706667] | 0.679420 | 0.005135323 | 0.067933943 | 0.000000000 |
| Tyler Higbee / `00-0033110` | TE | 1993-01-01 | 33.684470 | 10 | 110 | [0.525000, 0.536232, 0.392157, 0.640000] | 0.530616 | 0.005058622 | 0.000000000 | 0.000000000 |
| Blake Corum / `00-0039738` | RB | 2000-11-25 | 25.785608 | 2 | 83 | [0.458333, 0.293478, 0.246154, 0.333333] | 0.313406 | 0.003439666 | 0.031336850 | 0.000000000 |
| Konata Mumpfield / `00-0040590` | WR | 2002-10-24 | 23.874549 | 1 | 242 | [0.444444, 0.456522, 0.661538, 0.480000] | 0.468261 | 0.003009737 | 0.046820514 | 0.000000000 |
| Tutu Atwell / `00-0036849` | WR | 1999-10-07 | 26.921840 | 5 | 57 | [0.055556, 0.086957, 0.200000, 0.133333] | 0.110145 | 0.001458732 | 0.000000000 | 0.000000000 |
| Jordan Whittington / `00-0039751` | WR | 2000-10-01 | 25.936193 | 2 | 213 | [0.055556, 0.163043, 0.200000, 0.000000] | 0.109300 | 0.000748819 | 0.010928651 | 0.000000000 |
| Beaux Limmer / `00-0039753` | OL | 2001-06-10 | 25.246241 | 2 | 217 | [0.121212, 0.000000, 0.000000, 0.040000] | 0.020000 | 0.000135753 | 0.001999762 | 0.000000000 |
| David Quessenberry / `00-0030097` | OL | 1990-08-24 | 36.041808 | 13 | 176 | [0.000000, 0.000000, 0.000000, 0.040000] | 0.000000 | 0.000000000 | 0.000000000 | 0.000000000 |
| Coleman Shelton / `00-0034114` | OL | 1995-07-28 | 31.116313 | 8 | blank | [1.000000, 1.000000, 1.000000, 0.960000] | 1.000000 | 0.000000000 | 0.000000000 | 0.000000000 |
| Bill Murray / `00-0036093` | OL | 1997-07-03 | 29.183351 | 6 | blank | [0.000000, 0.493333, 0.045455, 0.031746] | 0.038600 | 0.000000000 | 0.000000000 | 0.000000000 |
| Alaric Jackson / `00-0036603` | OL | 1998-07-14 | 28.153898 | 5 | blank | [0.828571, 0.986111, 1.000000, 0.960000] | 0.973056 | 0.000000000 | 0.000000000 | 0.000000000 |
| Ronnie Rivers / `00-0037557` | RB | 1999-01-31 | 27.603578 | 4 | blank | [0.000000, 0.000000, 0.046154, 0.040000] | 0.020000 | 0.000000000 | 0.000000000 | 0.000000000 |
| Xavier Smith / `00-0038359` | WR | 1997-09-21 | 28.964318 | 3 | blank | [0.041667, 0.239130, 0.507692, 0.333333] | 0.286232 | 0.000000000 | 0.000000000 | 0.000000000 |
| Warren McClendon Jr. / `00-0039077` | OL | 2001-04-11 | 25.410515 | 3 | 174 | [0.000000, 0.000000, 0.000000, 0.000000] | 0.000000 | 0.000000000 | 0.000000000 | 0.000000000 |
| Dylan McMahon / `00-0039830` | OL | 2001-01-22 | 25.626810 | 2 | 190 | [0.000000, 0.000000, 0.000000, 1.000000] | 0.000000 | 0.000000000 | 0.000000000 | 0.000000000 |
| CJ Daniels / `00-0041399` | WR | 2002-01-04 | 24.676756 | 0 | 197 | missing | missing | 0.000000000 | 0.000000000 | 0.002968627 |
| Max Klare / `00-0041510` | TE | 2003-07-08 | 23.170907 | 0 | 61 | missing | missing | 0.000000000 | 0.000000000 | 0.005334870 |

**Defense:** 22 players; 21 known-role; role mass 13.073337812377; 7 blank draft records representing 27.3777% of known role mass.

| Player / GSIS | Raw pos | DOB | Age | Exp | Pick | Saved prior roles | Role | Draft part | Young part | Rookie part |
| --- | --- | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| Myles Garrett / `00-0033868` | LB | 1995-12-29 | 30.694675 | 9 | 1 | [0.803030, 0.980000, 0.939394, 0.955882] | 0.947638 | 0.072486320 | 0.000000000 | 0.000000000 |
| Trent McDuffie / `00-0037191` | DB | 2000-09-13 | 25.985475 | 4 | 21 | [1.000000, 1.000000, 1.000000, 0.128571] | 1.000000 | 0.016691827 | 0.076491560 | 0.000000000 |
| Emmanuel Forbes / `00-0039151` | DB | 2001-01-13 | 25.651451 | 3 | 16 | [0.812500, 0.750000, 0.716981, 0.781818] | 0.765909 | 0.014646395 | 0.058585581 | 0.000000000 |
| Byron Young / `00-0039137` | LB | 1998-03-13 | 28.490660 | 3 | 77 | [0.812500, 0.852941, 0.811321, 0.600000] | 0.811910 | 0.007077441 | 0.000000000 | 0.000000000 |
| Kamren Kinchens / `00-0039834` | DB | 2002-09-29 | 23.942997 | 2 | 99 | [0.750000, 0.897059, 0.566038, 0.872727] | 0.811364 | 0.006237513 | 0.062062470 | 0.000000000 |
| Kobie Turner / `00-0039138` | DL | 1999-04-26 | 27.370856 | 3 | 89 | [0.765625, 0.838235, 0.716981, 0.581818] | 0.741303 | 0.006010551 | 0.000000000 | 0.000000000 |
| Quentin Lake / `00-0037841` | DB | 1999-01-29 | 27.609054 | 4 | 211 | [1.000000, 1.000000, 1.000000, 0.380952] | 1.000000 | 0.005265896 | 0.000000000 | 0.000000000 |
| Kam Curl / `00-0036349` | DB | 1999-03-03 | 27.518703 | 6 | 216 | [1.000000, 1.000000, 1.000000, 1.000000] | 1.000000 | 0.005204591 | 0.000000000 | 0.000000000 |
| Jaylen Watson / `00-0037195` | DB | 1998-09-17 | 27.975934 | 4 | 243 | [1.000000, 1.000000, 0.969697, 0.808219] | 0.984848 | 0.004832588 | 0.000000000 | 0.000000000 |
| Braden Fiske / `00-0039734` | DL | 2000-01-18 | 26.639835 | 2 | 39 | [0.437500, 0.308824, 0.245283, 0.436364] | 0.372594 | 0.004563695 | 0.000000000 | 0.000000000 |
| Tyler Davis / `00-0039749` | DL | 2000-11-01 | 25.851318 | 2 | 196 | [0.343750, 0.441176, 0.641509, 0.327273] | 0.392463 | 0.002144295 | 0.030020125 | 0.000000000 |
| Josaiah Stewart / `00-0040580` | LB | 2003-04-26 | 23.370774 | 1 | 90 | [0.187500, 0.161765, 0.207547, 0.490909] | 0.197524 | 0.001592617 | 0.015108887 | 0.000000000 |
| Ty Hamilton / `00-0040585` | DL | 2002-04-15 | 24.400227 | 1 | 148 | [0.218750, 0.147059, 0.226415, 0.236364] | 0.222583 | 0.001399503 | 0.017025686 | 0.000000000 |
| Desjuan Johnson / `00-0039061` | LB | 1999-09-02 | 27.017666 | 3 | 259 | [0.265625, 0.147059, 0.226415, 0.436364] | 0.246020 | 0.001169322 | 0.000000000 | 0.000000000 |
| Poona Ford / `00-0034234` | DL | 1995-11-19 | 30.804192 | 8 | blank | [0.562500, 0.632353, 0.622642, 0.400000] | 0.592571 | 0.000000000 | 0.000000000 | 0.000000000 |
| Grant Stuard / `00-0036672` | LB | 1998-10-15 | 27.899272 | 5 | 259 | [0.000000, 0.000000, 0.000000, 0.000000] | 0.000000 | 0.000000000 | 0.000000000 | 0.000000000 |
| Nate Landman / `00-0037587` | LB | 1998-11-19 | 27.803446 | 4 | blank | [1.000000, 0.985294, 0.962264, 0.727273] | 0.973779 | 0.000000000 | 0.000000000 | 0.000000000 |
| Josh Wallace / `00-0039772` | DB | 2000-07-05 | 26.177129 | 2 | blank | [0.390625, 0.725806, 0.750000, 0.455882] | 0.590844 | 0.000000000 | 0.000000000 | 0.000000000 |
| Omar Speights / `00-0039774` | LB | 2001-03-02 | 25.520031 | 2 | blank | [0.593750, 0.779412, 0.867925, 0.545455] | 0.686581 | 0.000000000 | 0.052517643 | 0.000000000 |
| Jaylen McCollough / `00-0039776` | DB | 2000-10-12 | 25.906076 | 2 | blank | [0.640625, 0.308824, 0.830189, 0.854545] | 0.735407 | 0.000000000 | 0.056252416 | 0.000000000 |
| Shaun Dolac / `00-0040613` | LB | 2001-09-14 | 24.983401 | 1 | blank | [0.000000, 0.000000, 0.000000, 0.000000] | 0.000000 | 0.000000000 | 0.000000000 | 0.000000000 |
| Wesley Bailey / `00-0041404` | LB | 2001-04-26 | 25.369446 | 0 | blank | missing | missing | 0.000000000 | 0.000000000 | 0.000000000 |

### NE

Selected QB: **Drake Maye**, GSIS `00-0039851`, DOB `2002-08-30`, age 24.025133986324, experience 2, draft pick 3. Other ACT QBs: Tommy DeVito, Behren Morton.

| Feature | Saved value |
| --- | --- |
| `qb_age_centered` | -2.974866013676 |
| `qb_age_squared` | 8.849827799324 |
| `offense_role_weighted_age` | 28.595347930094 |
| `offense_young_role_share` | 0.314668572980 |
| `offense_role_weighted_draft_prior` | 0.140786654276 |
| `offense_rookie_draft_capital` | 0.015125360131 |
| `defense_role_weighted_age` | 27.549065697506 |
| `defense_young_role_share` | 0.359022715982 |
| `defense_role_weighted_draft_prior` | 0.089337034561 |
| `defense_rookie_draft_capital` | 0.014317526752 |

Coverage: 53 resolved ACT rows; 0 unmapped positions; 0 unmatched current identities. Missing DOB/experience counts are zero in both units.

**Offense:** 24 players; 20 known-role; role mass 10.492320067169; 6 blank draft records representing 19.7493% of known role mass.

| Player / GSIS | Raw pos | DOB | Age | Exp | Pick | Saved prior roles | Role | Draft part | Young part | Rookie part |
| --- | --- | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| Will Campbell / `00-0040699` | OL | 2004-01-06 | 22.672608 | 1 | 4 | [1.000000, 1.000000, 0.605634, 0.762712] | 0.881356 | 0.042000050 | 0.084000100 | 0.000000000 |
| Alijah Vera-Tucker / `00-0036979` | OL | 1999-06-17 | 27.228485 | 5 | 14 | [1.000000, 1.000000, 1.000000, 1.000000] | 1.000000 | 0.025472082 | 0.000000000 | 0.000000000 |
| Hunter Henry / `00-0033090` | TE | 1994-12-07 | 31.754245 | 10 | 35 | [0.865385, 0.810811, 0.651515, 0.576271] | 0.731163 | 0.011779006 | 0.000000000 | 0.000000000 |
| A.J. Brown / `00-0035676` | WR | 1997-06-30 | 29.191565 | 7 | 51 | [0.724638, 0.871429, 0.888889, 0.000000] | 0.798033 | 0.010650360 | 0.000000000 | 0.000000000 |
| Jared Wilson / `00-0040147` | OL | 2003-06-05 | 23.261258 | 1 | 95 | [1.000000, 0.042254, 1.000000, 1.000000] | 1.000000 | 0.009778375 | 0.095307805 | 0.000000000 |
| Morgan Moses / `00-0031330` | OL | 1991-03-03 | 35.518868 | 12 | 66 | [1.000000, 0.729730, 0.878788, 0.762712] | 0.820750 | 0.009628693 | 0.000000000 | 0.000000000 |
| TreVeyon Henderson / `00-0040734` | RB | 2002-10-22 | 23.880025 | 1 | 38 | [0.480769, 0.189189, 0.515152, 0.406780] | 0.443774 | 0.006861182 | 0.042295169 | 0.000000000 |
| Mack Hollins / `00-0033555` | WR | 1993-09-16 | 32.978090 | 9 | 118 | [0.859155, 0.753846, 0.788462, 0.662162] | 0.771154 | 0.006765945 | 0.000000000 | 0.000000000 |
| Rhamondre Stevenson / `00-0036875` | RB | 1998-02-23 | 28.539943 | 5 | 120 | [0.673077, 0.837838, 0.484848, 0.474576] | 0.578963 | 0.005037191 | 0.000000000 | 0.000000000 |
| Romeo Doubs / `00-0037816` | WR | 2000-04-13 | 26.404375 | 4 | 132 | [0.757576, 0.625000, 0.574468, 0.000000] | 0.599734 | 0.004975082 | 0.000000000 | 0.000000000 |
| Kyle Williams / `00-0040131` | WR | 2002-11-13 | 23.819791 | 1 | 69 | [0.096154, 0.378378, 0.848485, 0.457627] | 0.418003 | 0.004796043 | 0.039838925 | 0.000000000 |
| Cameron Latu / `00-0038564` | TE | 2000-02-24 | 26.538533 | 3 | 101 | [0.070423, 0.275362, 0.111111, 0.296875] | 0.193237 | 0.001832557 | 0.000000000 | 0.000000000 |
| DeMario Douglas / `00-0038621` | WR | 2000-12-08 | 25.750015 | 3 | 210 | [0.192308, 0.175676, 0.136364, 0.254237] | 0.183992 | 0.001210088 | 0.017535844 | 0.000000000 |
| Greg Van Roten / `00-0029685` | OL | 1990-02-26 | 36.531893 | 14 | blank | [1.000000, 1.000000, 1.000000, 1.000000] | 1.000000 | 0.000000000 | 0.000000000 | 0.000000000 |
| Reggie Gilliam / `00-0036187` | RB | 1997-08-20 | 29.051931 | 6 | blank | [0.114286, 0.220000, 0.092105, 0.200000] | 0.157143 | 0.000000000 | 0.000000000 | 0.000000000 |
| Mike Onwenu / `00-0036198` | OL | 1997-12-10 | 28.745286 | 6 | 182 | [0.000000, 0.000000, 0.000000, 0.000000] | 0.000000 | 0.000000000 | 0.000000000 | 0.000000000 |
| Ben Brown / `00-0037413` | OL | 1998-05-19 | 28.307221 | 4 | blank | [0.000000, 0.081081, 1.000000, 1.000000] | 0.540541 | 0.000000000 | 0.000000000 | 0.000000000 |
| Walter Rouse / `00-0039828` | OL | 2001-03-09 | 25.500866 | 2 | 177 | [0.000000, 0.816327, 0.000000, 0.000000] | 0.000000 | 0.000000000 | 0.000000000 | 0.000000000 |
| Corey Kiner / `00-0040556` | RB | 2002-01-21 | 24.630211 | 1 | blank | [0.075758, 0.157895, 0.035088, 0.254545] | 0.116826 | 0.000000000 | 0.011134445 | 0.000000000 |
| Efton Chism III / `00-0040563` | WR | 2001-10-26 | 24.868409 | 1 | blank | [0.074627, 0.030769, 0.621212, 0.440678] | 0.257652 | 0.000000000 | 0.024556286 | 0.000000000 |
| Dametrious Crownover / `00-0041103` | OL | 2001-09-12 | 24.988877 | 0 | 196 | missing | missing | 0.000000000 | 0.000000000 | 0.002976190 |
| Tanner Arkin / `00-0041314` | TE | 2003-07-07 | 23.173645 | 0 | blank | missing | missing | 0.000000000 | 0.000000000 | 0.000000000 |
| Eli Raridon / `00-0041395` | TE | 2004-02-12 | 22.571305 | 0 | 95 | missing | missing | 0.000000000 | 0.000000000 | 0.004274910 |
| Caleb Lomu / `00-0041541` | OL | 2004-12-23 | 21.708865 | 0 | 28 | missing | missing | 0.000000000 | 0.000000000 | 0.007874260 |

**Defense:** 24 players; 18 known-role; role mass 10.787222397216; 9 blank draft records representing 32.3260% of known role mass.

| Player / GSIS | Raw pos | DOB | Age | Exp | Pick | Saved prior roles | Role | Draft part | Young part | Rookie part |
| --- | --- | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| Christian Gonzalez / `00-0039147` | DB | 2002-06-28 | 24.197622 | 3 | 17 | [1.000000, 1.000000, 0.846154, 0.938776] | 0.969388 | 0.021795329 | 0.089864445 | 0.000000000 |
| Kevin Byard / `00-0033132` | DB | 1993-08-17 | 33.060227 | 10 | 64 | [1.000000, 1.000000, 1.000000, 1.000000] | 1.000000 | 0.011587784 | 0.000000000 | 0.000000000 |
| Christian Barmore / `00-0036981` | DL | 1999-07-28 | 27.116231 | 5 | 38 | [0.728571, 0.800000, 0.769231, 0.693878] | 0.748901 | 0.011262195 | 0.000000000 | 0.000000000 |
| Carlton Davis III / `00-0034778` | DB | 1996-12-31 | 29.687126 | 8 | 63 | [0.642857, 0.981818, 0.846154, 0.938776] | 0.892465 | 0.010423441 | 0.000000000 | 0.000000000 |
| Craig Woodson / `00-0040716` | DB | 2001-02-20 | 25.547410 | 1 | 106 | [0.871429, 0.945455, 0.923077, 0.897959] | 0.910518 | 0.008198341 | 0.084407090 | 0.000000000 |
| Dre'Mont Jones / `00-0035678` | LB | 1997-01-05 | 29.673436 | 7 | 71 | [0.671053, 0.608108, 0.787234, 0.573333] | 0.639580 | 0.007036494 | 0.000000000 | 0.000000000 |
| Milton Williams / `00-0036916` | DL | 1999-04-06 | 27.425614 | 5 | 73 | [0.666667, 0.589286, 0.681159, 0.571429] | 0.627976 | 0.006813529 | 0.000000000 | 0.000000000 |
| Marcus Jones / `00-0037253` | DB | 1998-10-22 | 27.880107 | 4 | 85 | [0.685714, 0.345455, 0.615385, 0.387755] | 0.501570 | 0.005043271 | 0.000000000 | 0.000000000 |
| Darius Muasau / `00-0039829` | LB | 2001-02-10 | 25.574789 | 2 | 183 | [0.803279, 0.573770, 0.610169, 0.490909] | 0.591970 | 0.004056622 | 0.054876962 | 0.000000000 |
| Joshua Farmer / `00-0040171` | DL | 2003-01-17 | 23.641827 | 1 | 137 | [0.231884, 0.272727, 0.485714, 0.127273] | 0.252306 | 0.001998283 | 0.023389308 | 0.000000000 |
| Jaylen Reed / `00-0040204` | DB | 2003-01-29 | 23.608972 | 1 | 187 | [0.016129, 0.000000, 0.833333, 0.314815] | 0.165472 | 0.001121744 | 0.015339623 | 0.000000000 |
| Robert Spillane / `00-0034720` | LB | 1995-12-14 | 30.735744 | 8 | blank | [1.000000, 1.000000, 0.690909, 0.000000] | 0.845455 | 0.000000000 | 0.000000000 | 0.000000000 |
| Christian Elliss / `00-0036813` | LB | 1999-01-02 | 27.682978 | 5 | blank | [0.857143, 0.672727, 0.717949, 0.653061] | 0.695338 | 0.000000000 | 0.000000000 | 0.000000000 |
| Cory Durden / `00-0038653` | DL | 1999-01-26 | 27.617268 | 3 | blank | [0.528571, 0.636364, 0.794872, 0.714286] | 0.675325 | 0.000000000 | 0.000000000 | 0.000000000 |
| Leonard Taylor III / `00-0039289` | DL | 2002-05-29 | 24.279759 | 2 | blank | [0.305556, 0.071429, 0.564103, 0.510204] | 0.407880 | 0.000000000 | 0.037811385 | 0.000000000 |
| Dell Pettus / `00-0039692` | DB | 2001-06-02 | 25.268144 | 2 | blank | [0.000000, 0.145455, 0.743590, 0.244898] | 0.195176 | 0.000000000 | 0.018093282 | 0.000000000 |
| Charles Woods / `00-0039770` | DB | 2000-06-17 | 26.226411 | 2 | blank | [0.371429, 0.000000, 0.538462, 0.204082] | 0.287755 | 0.000000000 | 0.000000000 | 0.000000000 |
| Elijah Ponder / `00-0040574` | LB | 2002-08-29 | 24.027872 | 1 | blank | [0.142857, 0.290909, 0.871795, 0.469388] | 0.380148 | 0.000000000 | 0.035240622 | 0.000000000 |
| Karon Prunty / `00-0041088` | DB | 2001-12-24 | 24.706873 | 0 | 171 | missing | missing | 0.000000000 | 0.000000000 | 0.003186330 |
| Namdi Obiazor / `00-0041109` | LB | 2002-04-19 | 24.389276 | 0 | 212 | missing | missing | 0.000000000 | 0.000000000 | 0.002861678 |
| Channing Canada / `00-0041316` | DB | 2002-08-17 | 24.060727 | 0 | blank | missing | missing | 0.000000000 | 0.000000000 | 0.000000000 |
| Quintayvious Hutchins / `00-0041402` | LB | 2003-04-02 | 23.436484 | 0 | 247 | missing | missing | 0.000000000 | 0.000000000 | 0.002651187 |
| Erick Hunter / `00-0041455` | LB | 2003-02-26 | 23.532311 | 0 | blank | missing | missing | 0.000000000 | 0.000000000 | 0.000000000 |
| Gabe Jacas / `00-0041569` | LB | 2004-05-27 | 22.283825 | 0 | 55 | missing | missing | 0.000000000 | 0.000000000 | 0.005618332 |

### MIN

Selected QB: **Kyler Murray**, GSIS `00-0035228`, DOB `1997-08-07`, age 29.087524042246, experience 7, draft pick 1. Other ACT QBs: Carson Wentz, J.J. McCarthy.

| Feature | Saved value |
| --- | --- |
| `qb_age_centered` | 2.087524042246 |
| `qb_age_squared` | 4.357756626955 |
| `offense_role_weighted_age` | 27.905093151005 |
| `offense_young_role_share` | 0.214650627758 |
| `offense_role_weighted_draft_prior` | 0.153004901600 |
| `offense_rookie_draft_capital` | 0.010952464371 |
| `defense_role_weighted_age` | 28.466696609333 |
| `defense_young_role_share` | 0.112052520239 |
| `defense_role_weighted_draft_prior` | 0.077152670137 |
| `defense_rookie_draft_capital` | 0.027729295597 |

Coverage: 53 resolved ACT rows; 0 unmapped positions; 0 unmatched current identities. Missing DOB/experience counts are zero in both units.

**Offense:** 23 players; 19 known-role; role mass 9.144766383395; 5 blank draft records representing 5.8495% of known role mass.

| Player / GSIS | Raw pos | DOB | Age | Exp | Pick | Saved prior roles | Role | Draft part | Young part | Rookie part |
| --- | --- | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| T.J. Hockenson / `00-0035229` | TE | 1997-07-03 | 29.183351 | 7 | 8 | [0.788462, 0.562500, 0.800000, 0.754098] | 0.771280 | 0.029819093 | 0.000000000 | 0.000000000 |
| Donovan Jackson / `00-0040661` | OL | 2002-12-04 | 23.762295 | 1 | 24 | [1.000000, 1.000000, 1.000000, 1.000000] | 1.000000 | 0.022321417 | 0.109352165 | 0.000000000 |
| Justin Jefferson / `00-0036322` | WR | 1999-06-16 | 27.231223 | 6 | 22 | [0.963636, 0.950820, 0.981481, 0.761194] | 0.957228 | 0.022316776 | 0.000000000 | 0.000000000 |
| Christian Darrisaw / `00-0036616` | OL | 1999-06-02 | 27.269554 | 5 | 23 | [1.000000, 1.000000, 0.863636, 0.796875] | 0.931818 | 0.021246855 | 0.000000000 | 0.000000000 |
| Jordan Addison / `00-0038994` | WR | 2002-01-27 | 24.613784 | 3 | 23 | [0.636364, 0.672131, 0.777778, 0.925373] | 0.724954 | 0.016530051 | 0.079275340 | 0.000000000 |
| Brian O'Neill / `00-0034158` | OL | 1995-09-15 | 30.982156 | 8 | 62 | [0.953125, 0.818182, 1.000000, 0.865672] | 0.909398 | 0.012629486 | 0.000000000 | 0.000000000 |
| Josh Oliver / `00-0035249` | TE | 1997-03-21 | 29.468093 | 7 | 69 | [0.618182, 0.524590, 0.925926, 0.462687] | 0.571386 | 0.007521984 | 0.000000000 | 0.000000000 |
| Will Fries / `00-0036483` | OL | 1998-04-04 | 28.430426 | 5 | 248 | [1.000000, 1.000000, 1.000000, 1.000000] | 1.000000 | 0.006943869 | 0.000000000 | 0.000000000 |
| Jauan Jennings / `00-0036259` | WR | 1997-07-10 | 29.164185 | 6 | 217 | [0.810811, 0.818182, 0.902778, 0.880952] | 0.849567 | 0.006306599 | 0.000000000 | 0.000000000 |
| Aaron Jones / `00-0033293` | RB | 1994-12-02 | 31.767935 | 9 | 182 | [0.453125, 0.581818, 0.639344, 0.648148] | 0.610581 | 0.004949201 | 0.000000000 | 0.000000000 |
| Blake Brandel / `00-0036347` | OL | 1997-01-23 | 29.624154 | 6 | 203 | [0.200000, 0.000000, 1.000000, 0.134328] | 0.167164 | 0.001282988 | 0.000000000 | 0.000000000 |
| Tai Felton / `00-0040154` | WR | 2003-03-15 | 23.485766 | 1 | 102 | [0.018182, 0.114754, 0.000000, 0.134328] | 0.066468 | 0.000719680 | 0.007268415 | 0.000000000 |
| Trevor Keegan / `00-0039310` | OL | 2000-08-30 | 26.023806 | 2 | 172 | [0.514706, 0.000000, 0.100000, 0.000000] | 0.050000 | 0.000416901 | 0.000000000 | 0.000000000 |
| Ryan Van Demark / `00-0037404` | OL | 1998-03-22 | 28.466019 | 4 | blank | [0.000000, 0.040000, 0.026316, 1.000000] | 0.033158 | 0.000000000 | 0.000000000 | 0.000000000 |
| Jordan Mason / `00-0037525` | RB | 1999-05-24 | 27.294195 | 4 | blank | [0.296875, 0.363636, 0.065574, 0.402985] | 0.330256 | 0.000000000 | 0.000000000 | 0.000000000 |
| Nick Samac / `00-0039237` | OL | 2001-08-21 | 25.049111 | 2 | 228 | [0.000000, 0.000000, 0.000000, 0.000000] | 0.000000 | 0.000000000 | 0.000000000 | 0.000000000 |
| Gavin Bartholomew / `00-0040215` | TE | 2003-04-30 | 23.359823 | 1 | 202 | missing | missing | 0.000000000 | 0.000000000 | 0.000000000 |
| Joe Huber / `00-0040500` | OL | 2002-05-02 | 24.353683 | 1 | blank | [0.000000, 0.000000, 0.000000, 0.000000] | 0.000000 | 0.000000000 | 0.000000000 | 0.000000000 |
| Myles Price / `00-0040506` | WR | 2001-12-16 | 24.728776 | 1 | blank | [0.046875, 0.018182, 0.032787, 0.000000] | 0.025484 | 0.000000000 | 0.002786769 | 0.000000000 |
| Ben Yurosek / `00-0040509` | TE | 2002-03-17 | 24.479627 | 1 | blank | [0.018182, 0.032787, 0.259259, 0.388060] | 0.146023 | 0.000000000 | 0.015967939 | 0.000000000 |
| Caleb Tiernan / `00-0041053` | OL | 2003-01-23 | 23.625400 | 0 | 97 | missing | missing | 0.000000000 | 0.000000000 | 0.004414549 |
| Max Bredeson / `00-0041081` | RB | 2002-10-04 | 23.929307 | 0 | 159 | missing | missing | 0.000000000 | 0.000000000 | 0.003448050 |
| Demond Claiborne / `00-0041104` | RB | 2003-10-09 | 22.916282 | 0 | 198 | missing | missing | 0.000000000 | 0.000000000 | 0.003089865 |

**Defense:** 24 players; 18 known-role; role mass 10.076963527948; 9 blank draft records representing 25.9978% of known role mass.

| Player / GSIS | Raw pos | DOB | Age | Exp | Pick | Saved prior roles | Role | Draft part | Young part | Rookie part |
| --- | --- | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| Byron Murphy / `00-0035236` | DB | 1998-01-18 | 28.638507 | 7 | 33 | [1.000000, 1.000000, 1.000000, 1.000000] | 1.000000 | 0.017274813 | 0.000000000 | 0.000000000 |
| Dallas Turner / `00-0039924` | LB | 2003-02-02 | 23.598020 | 2 | 17 | [0.528571, 0.660714, 0.718750, 0.725490] | 0.689732 | 0.016600697 | 0.068446426 | 0.000000000 |
| Blake Cashman / `00-0035276` | LB | 1996-05-10 | 30.330534 | 7 | 157 | [1.000000, 1.000000, 1.000000, 0.882353] | 1.000000 | 0.007919914 | 0.000000000 | 0.000000000 |
| Andrew Van Ginkel / `00-0035272` | LB | 1995-07-01 | 31.190237 | 7 | 151 | [0.857143, 0.964286, 0.953125, 0.745098] | 0.905134 | 0.007309618 | 0.000000000 | 0.000000000 |
| Josh Metellus / `00-0036348` | DB | 1998-01-21 | 28.630294 | 6 | 205 | [0.873016, 0.925373, 1.000000, 0.985714] | 0.955544 | 0.006622835 | 0.000000000 | 0.000000000 |
| Isaiah Rodgers / `00-0036222` | DB | 1998-01-07 | 28.668624 | 6 | 211 | [0.957143, 0.910714, 0.953125, 1.000000] | 0.955134 | 0.006525193 | 0.000000000 | 0.000000000 |
| Jay Ward / `00-0038578` | DB | 2000-07-13 | 26.155226 | 3 | 134 | [0.157143, 0.785714, 0.609375, 0.882353] | 0.697545 | 0.005979845 | 0.000000000 | 0.000000000 |
| Levi Drake Rodriguez / `00-0039421` | DL | 2000-08-04 | 26.094992 | 2 | 232 | [0.314286, 0.571429, 0.500000, 0.568627] | 0.534314 | 0.003481149 | 0.000000000 | 0.000000000 |
| Theo Jackson / `00-0037301` | DB | 1998-10-02 | 27.934865 | 4 | 204 | [0.000000, 0.375000, 0.468750, 0.588235] | 0.421875 | 0.002931157 | 0.000000000 | 0.000000000 |
| Tyrion Ingram-Dawkins / `00-0040173` | DL | 2003-06-26 | 23.203762 | 1 | 139 | [0.242857, 0.428571, 0.062500, 0.352941] | 0.297899 | 0.002507449 | 0.029562393 | 0.000000000 |
| Eric Wilson / `00-0033336` | LB | 1994-09-26 | 31.951375 | 9 | blank | [0.971429, 1.000000, 1.000000, 0.882353] | 0.985714 | 0.000000000 | 0.000000000 | 0.000000000 |
| James Pierre / `00-0035795` | DB | 1996-09-16 | 29.977344 | 6 | blank | [0.984615, 0.513514, 0.862500, 0.588235] | 0.725368 | 0.000000000 | 0.000000000 | 0.000000000 |
| Jalen Redmond / `00-0038778` | DL | 1999-03-12 | 27.494062 | 3 | blank | [0.800000, 0.982143, 0.734375, 0.529412] | 0.767188 | 0.000000000 | 0.000000000 | 0.000000000 |
| Ivan Pace Jr. / `00-0038807` | LB | 2000-12-16 | 25.728112 | 3 | blank | [0.014286, 0.017857, 0.000000, 0.235294] | 0.016071 | 0.000000000 | 0.001594868 | 0.000000000 |
| Bo Richter / `00-0039718` | LB | 2000-08-13 | 26.070351 | 2 | blank | [0.000000, 0.000000, 0.000000, 0.117647] | 0.000000 | 0.000000000 | 0.000000000 | 0.000000000 |
| Chaz Chambliss / `00-0040496` | LB | 2002-10-25 | 23.871811 | 1 | blank | [0.000000, 0.000000, 0.000000, 0.039216] | 0.000000 | 0.000000000 | 0.000000000 | 0.000000000 |
| Zemaiah Vaughn / `00-0040507` | DB | 2002-04-02 | 24.435820 | 1 | blank | [0.000000] | 0.000000 | 0.000000000 | 0.000000000 | 0.000000000 |
| Elijah Williams / `00-0040624` | DL | 2002-09-09 | 23.997755 | 1 | blank | [0.062500, 0.157143, 0.178571, 0.093750] | 0.125446 | 0.000000000 | 0.012448832 | 0.000000000 |
| Caleb Banks / `00-0041033` | DL | 2003-03-12 | 23.493980 | 0 | 18 | missing | missing | 0.000000000 | 0.000000000 | 0.009820928 |
| Domonique Orange / `00-0041046` | DL | 2004-03-11 | 22.494644 | 0 | 82 | missing | missing | 0.000000000 | 0.000000000 | 0.004601314 |
| Jakobe Thomas / `00-0041054` | DB | 2003-06-30 | 23.192810 | 0 | 98 | missing | missing | 0.000000000 | 0.000000000 | 0.004208969 |
| Charles Demmings / `00-0041083` | DB | 2003-04-05 | 23.428270 | 0 | 163 | missing | missing | 0.000000000 | 0.000000000 | 0.003263585 |
| Jacob Thomas / `00-0041354` | DB | 2004-05-30 | 22.275611 | 0 | blank | missing | missing | 0.000000000 | 0.000000000 | 0.000000000 |
| Jake Golday / `00-0041495` | LB | 2003-05-23 | 23.296851 | 0 | 51 | missing | missing | 0.000000000 | 0.000000000 | 0.005834500 |

### NYG

Selected QB: **Jaxson Dart**, GSIS `00-0040691`, DOB `2003-05-13`, age 23.324229792535, experience 1, draft pick 25. Other ACT QBs: Jameis Winston.

| Feature | Saved value |
| --- | --- |
| `qb_age_centered` | -3.675770207465 |
| `qb_age_squared` | 13.511286618087 |
| `offense_role_weighted_age` | 27.655718745303 |
| `offense_young_role_share` | 0.306610746251 |
| `offense_role_weighted_draft_prior` | 0.157053561123 |
| `offense_rookie_draft_capital` | 0.021941051670 |
| `defense_role_weighted_age` | 27.160806356145 |
| `defense_young_role_share` | 0.307139025868 |
| `defense_role_weighted_draft_prior` | 0.197648935204 |
| `defense_rookie_draft_capital` | 0.030276708616 |

Coverage: 53 resolved ACT rows; 0 unmapped positions; 0 unmatched current identities. Missing DOB/experience counts are zero in both units.

**Offense:** 23 players; 20 known-role; role mass 10.679935996611; 4 blank draft records representing 7.6417% of known role mass.

| Player / GSIS | Raw pos | DOB | Age | Exp | Pick | Saved prior roles | Role | Draft part | Young part | Rookie part |
| --- | --- | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| Andrew Thomas / `00-0036386` | OL | 1999-01-22 | 27.628220 | 6 | 4 | [1.000000, 1.000000, 1.000000, 0.357143] | 1.000000 | 0.046816760 | 0.000000000 | 0.000000000 |
| Malik Nabers / `00-0039337` | WR | 2003-07-28 | 23.116149 | 2 | 6 | [0.941176, 0.985075, 0.924242, 0.328947] | 0.932709 | 0.035653494 | 0.087332869 | 0.000000000 |
| John Michael Schmitz / `00-0039019` | OL | 1999-04-19 | 27.390022 | 3 | 57 | [1.000000, 1.000000, 1.000000, 0.750000] | 1.000000 | 0.012402063 | 0.000000000 | 0.000000000 |
| Theo Johnson / `00-0039847` | TE | 2001-02-26 | 25.530983 | 2 | 107 | [0.780488, 0.890909, 0.867647, 0.964286] | 0.879278 | 0.007959132 | 0.082329901 | 0.000000000 |
| Jermaine Eluemunor / `00-0033290` | OL | 1994-12-13 | 31.737818 | 9 | 159 | [1.000000, 1.000000, 0.953125, 0.986667] | 0.993333 | 0.007376117 | 0.000000000 | 0.000000000 |
| Darius Slayton / `00-0035535` | WR | 1997-01-12 | 29.654271 | 7 | 171 | [0.867647, 0.785714, 0.875000, 0.866667] | 0.867157 | 0.006209133 | 0.000000000 | 0.000000000 |
| Marcus Mbow / `00-0040181` | OL | 2003-04-02 | 23.436484 | 1 | 154 | [0.000000, 0.642857, 1.000000, 1.000000] | 0.821429 | 0.006197846 | 0.076913249 | 0.000000000 |
| Cam Skattebo / `00-0040715` | RB | 2002-02-05 | 24.589143 | 1 | 105 | [0.684932, 0.710145, 0.597403, 0.211538] | 0.641167 | 0.005858790 | 0.060034728 | 0.000000000 |
| Odell Beckham Jr. / `00-0031235` | WR | 1992-11-05 | 33.840531 | 12 | 12 | [0.235294, 0.250000, 0.197183, 0.138889] | 0.216239 | 0.005844858 | 0.000000000 | 0.000000000 |
| Darnell Mooney / `00-0036309` | WR | 1997-10-29 | 28.860278 | 6 | 173 | [0.915493, 0.701299, 0.698113, 0.825397] | 0.763348 | 0.005434139 | 0.000000000 | 0.000000000 |
| Najee Harris / `00-0036893` | RB | 1998-03-09 | 28.501612 | 5 | 24 | [0.491803, 0.184615, 0.344828, 0.127907] | 0.264721 | 0.005059585 | 0.000000000 | 0.000000000 |
| Tyrone Tracy Jr. / `00-0039384` | RB | 1999-11-23 | 26.793158 | 2 | 166 | [0.764706, 0.625000, 0.656250, 0.693333] | 0.674792 | 0.004903961 | 0.000000000 | 0.000000000 |
| Isaiah Likely / `00-0037838` | TE | 2000-04-18 | 26.390686 | 4 | 139 | [0.512195, 0.400000, 0.697368, 0.490196] | 0.501196 | 0.003980441 | 0.000000000 | 0.000000000 |
| Devin Singletary / `00-0035250` | RB | 1997-09-03 | 29.013601 | 7 | 74 | [0.235294, 0.375000, 0.296875, 0.320000] | 0.308438 | 0.003357242 | 0.000000000 | 0.000000000 |
| Chris Manhertz / `00-0031484` | TE | 1992-04-10 | 34.412753 | 11 | blank | [0.058824, 0.464286, 0.234375, 0.306667] | 0.270521 | 0.000000000 | 0.000000000 | 0.000000000 |
| Patrick Ricard / `00-0033376` | RB | 1994-05-27 | 32.285399 | 9 | blank | [0.439024, 0.581818, 0.565789, 0.509804] | 0.537797 | 0.000000000 | 0.000000000 | 0.000000000 |
| Aaron Stinnie / `00-0034668` | OL | 1994-02-18 | 32.553714 | 8 | blank | [0.000000, 1.000000, 0.015625, 0.000000] | 0.007812 | 0.000000000 | 0.000000000 | 0.000000000 |
| Jon Runyan / `00-0036246` | OL | 1997-08-08 | 29.084786 | 6 | 192 | [0.000000, 0.000000, 0.000000, 0.000000] | 0.000000 | 0.000000000 | 0.000000000 | 0.000000000 |
| Bryan Hudson / `00-0039446` | OL | 2001-01-11 | 25.656927 | 2 | blank | [0.000000, 0.046875, 0.000000] | 0.000000 | 0.000000000 | 0.000000000 | 0.000000000 |
| Thomas Fidone II / `00-0040225` | TE | 2002-09-20 | 23.967638 | 1 | 219 | [0.000000, 0.192982, 0.000000, 0.000000] | 0.000000 | 0.000000000 | 0.000000000 | 0.000000000 |
| Malachi Fields / `00-0041042` | WR | 2003-08-26 | 23.036750 | 0 | 74 | missing | missing | 0.000000000 | 0.000000000 | 0.005054245 |
| J.C. Davis / `00-0041101` | OL | 2003-10-09 | 22.916282 | 0 | 192 | missing | missing | 0.000000000 | 0.000000000 | 0.003137773 |
| Francis Mauigoa / `00-0041505` | OL | 2005-06-04 | 21.262586 | 0 | 10 | missing | missing | 0.000000000 | 0.000000000 | 0.013749033 |

**Defense:** 25 players; 21 known-role; role mass 11.243407150933; 3 blank draft records representing 1.8857% of known role mass.

| Player / GSIS | Raw pos | DOB | Age | Exp | Pick | Saved prior roles | Role | Draft part | Young part | Rookie part |
| --- | --- | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| Abdul Carter / `00-0040677` | LB | 2003-10-03 | 22.932709 | 1 | 3 | [0.803279, 0.901639, 0.881356, 0.945455] | 0.891498 | 0.045778508 | 0.079290701 | 0.000000000 |
| Kayvon Thibodeaux / `00-0037611` | LB | 2000-12-15 | 25.730850 | 4 | 5 | [0.703704, 0.627119, 0.712121, 0.617647] | 0.665411 | 0.026467148 | 0.059182343 | 0.000000000 |
| Tremaine Edmunds / `00-0034673` | LB | 1998-05-02 | 28.353765 | 8 | 16 | [1.000000, 0.930556, 0.986111, 0.972603] | 0.979357 | 0.021776249 | 0.000000000 | 0.000000000 |
| Brian Burns / `00-0035713` | LB | 1998-04-23 | 28.378406 | 7 | 16 | [0.770492, 0.721311, 0.677966, 0.636364] | 0.699639 | 0.015556645 | 0.000000000 | 0.000000000 |
| Jevon Holland / `00-0036998` | DB | 2000-03-03 | 26.516629 | 5 | 36 | [1.000000, 1.000000, 1.000000, 0.423729] | 1.000000 | 0.014823502 | 0.000000000 | 0.000000000 |
| Greg Newsome II / `00-0036996` | DB | 2000-05-18 | 26.308548 | 5 | 26 | [0.846154, 0.575758, 1.000000, 0.708333] | 0.777244 | 0.013557279 | 0.000000000 | 0.000000000 |
| Paulson Adebo / `00-0036937` | DB | 1999-07-03 | 27.184679 | 5 | 76 | [1.000000, 1.000000, 1.000000, 0.981818] | 1.000000 | 0.010202234 | 0.000000000 | 0.000000000 |
| Tyler Nubin / `00-0039861` | DB | 2001-06-14 | 25.235289 | 2 | 47 | [0.926471, 0.646154, 0.688525, 0.819672] | 0.754098 | 0.009783204 | 0.067070271 | 0.000000000 |
| Deonte Banks / `00-0039000` | DB | 2001-04-03 | 25.432418 | 3 | 24 | [0.000000, 0.409836, 0.847458, 0.527273] | 0.468554 | 0.008506609 | 0.041673702 | 0.000000000 |
| Andru Phillips / `00-0039821` | DB | 2001-11-30 | 24.772583 | 2 | 70 | [0.540984, 0.459016, 0.661017, 0.727273] | 0.601000 | 0.006388924 | 0.053453572 | 0.000000000 |
| Darius Alexander / `00-0040694` | DL | 2000-08-26 | 26.034758 | 1 | 65 | [0.524590, 0.409836, 0.576271, 0.800000] | 0.550431 | 0.006072227 | 0.000000000 | 0.000000000 |
| Micah McFadden / `00-0037259` | LB | 2000-01-03 | 26.680904 | 4 | 146 | [1.000000, 1.000000, 0.454545, 0.157143] | 0.727273 | 0.005353317 | 0.000000000 | 0.000000000 |
| Shelby Harris / `00-0031270` | DL | 1991-08-11 | 35.078065 | 12 | 235 | [0.484848, 0.800000, 0.712121, 0.705882] | 0.709002 | 0.004113537 | 0.000000000 | 0.000000000 |
| DJ Reader / `00-0032424` | DL | 1994-07-01 | 32.189573 | 10 | 166 | [0.555556, 0.527027, 0.574074, 0.527273] | 0.541414 | 0.003737469 | 0.000000000 | 0.000000000 |
| Chauncey Golston / `00-0036982` | DL | 1998-02-10 | 28.575535 | 5 | 84 | [0.377049, 0.409836, 0.372881, 0.381818] | 0.379434 | 0.003682123 | 0.000000000 | 0.000000000 |
| Jason Pinnock / `00-0036502` | DB | 1999-06-30 | 27.192892 | 5 | 175 | [0.245283, 0.183333, 0.121212, 0.318841] | 0.214308 | 0.001440860 | 0.000000000 | 0.000000000 |
| Nic Jones / `00-0038986` | DB | 2001-10-15 | 24.898526 | 3 | 250 | [0.000000, 0.145455, 0.147059, 0.000000] | 0.072727 | 0.000409100 | 0.006468437 | 0.000000000 |
| Elijah Campbell / `00-0034248` | DB | 1995-08-24 | 31.042390 | 8 | blank | [0.000000, 0.000000, 0.000000, 0.000000] | 0.000000 | 0.000000000 | 0.000000000 | 0.000000000 |
| Ar'Darius Washington / `00-0036587` | DB | 1999-11-02 | 26.850654 | 5 | blank | [0.197368, 0.297297, 0.148936, 0.226667] | 0.212018 | 0.000000000 | 0.000000000 | 0.000000000 |
| Zaire Barnes / `00-0038399` | LB | 1999-09-03 | 27.014928 | 3 | 184 | [0.000000, 0.000000, 0.000000, 0.000000] | 0.000000 | 0.000000000 | 0.000000000 | 0.000000000 |
| Basil Okoye / `00-0039176` | DL | 2001-10-20 | 24.884837 | 3 | blank | [0.000000, 0.000000, 0.000000, 0.000000] | 0.000000 | 0.000000000 | 0.000000000 | 0.000000000 |
| Bobby Jamison-Travis / `00-0041095` | DL | 2001-04-28 | 25.363971 | 0 | 186 | missing | missing | 0.000000000 | 0.000000000 | 0.002932942 |
| Jack Kelly / `00-0041102` | LB | 2003-01-02 | 23.682896 | 0 | 193 | missing | missing | 0.000000000 | 0.000000000 | 0.002879263 |
| Colton Hood / `00-0041462` | DB | 2005-02-23 | 21.539114 | 0 | 37 | missing | missing | 0.000000000 | 0.000000000 | 0.006575959 |
| Arvell Reese / `00-0041509` | LB | 2005-08-30 | 21.024388 | 0 | 5 | missing | missing | 0.000000000 | 0.000000000 | 0.017888544 |

### DET

Selected QB: **Jared Goff**, GSIS `00-0033106`, DOB `1994-10-14`, age 31.902092445430, experience 10, draft pick 1. Other ACT QBs: Joshua Dobbs.

| Feature | Saved value |
| --- | --- |
| `qb_age_centered` | 4.902092445430 |
| `qb_age_squared` | 24.030510343543 |
| `offense_role_weighted_age` | 25.976114635765 |
| `offense_young_role_share` | 0.728831178051 |
| `offense_role_weighted_draft_prior` | 0.167723449487 |
| `offense_rookie_draft_capital` | 0.012765032897 |
| `defense_role_weighted_age` | 27.798308486960 |
| `defense_young_role_share` | 0.115153142470 |
| `defense_role_weighted_draft_prior` | 0.182215493167 |
| `defense_rookie_draft_capital` | 0.014535735263 |

Coverage: 51 resolved ACT rows; 0 unmapped positions; 0 unmatched current identities. Missing DOB/experience counts are zero in both units.

**Offense:** 19 players; 18 known-role; role mass 8.609843693622; 4 blank draft records representing 10.0268% of known role mass.

| Player / GSIS | Raw pos | DOB | Age | Exp | Pick | Saved prior roles | Role | Draft part | Young part | Rookie part |
| --- | --- | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| Penei Sewell / `00-0036880` | OL | 2000-10-09 | 25.914290 | 5 | 7 | [1.000000, 1.000000, 1.000000, 0.906250] | 1.000000 | 0.043899110 | 0.116146127 | 0.000000000 |
| Jameson Williams / `00-0037240` | WR | 2001-03-26 | 25.454321 | 4 | 12 | [0.906250, 0.945946, 0.828125, 0.945205] | 0.925728 | 0.031038261 | 0.107519692 | 0.000000000 |
| Jahmyr Gibbs / `00-0039139` | RB | 2002-03-20 | 24.471413 | 3 | 12 | [0.812500, 0.864865, 0.687500, 0.712329] | 0.762414 | 0.025562610 | 0.088551478 | 0.000000000 |
| Sam LaPorta / `00-0039065` | TE | 2001-01-12 | 25.654189 | 3 | 34 | [0.962963, 0.970588, 1.000000, 0.757143] | 0.966776 | 0.019257103 | 0.112287242 | 0.000000000 |
| Tate Ratledge / `00-0040728` | OL | 2001-04-26 | 25.369446 | 1 | 57 | [1.000000, 1.000000, 1.000000, 1.000000] | 1.000000 | 0.015383930 | 0.116146127 | 0.000000000 |
| Amon-Ra St. Brown / `00-0036963` | WR | 1999-10-24 | 26.875295 | 5 | 112 | [0.953125, 0.972973, 0.828125, 0.945205] | 0.949165 | 0.010416877 | 0.000000000 | 0.000000000 |
| Isaac TeSlaa / `00-0040669` | WR | 2002-02-20 | 24.548074 | 1 | 70 | [0.625000, 0.554054, 0.515625, 0.602740] | 0.578397 | 0.008029374 | 0.067178559 | 0.000000000 |
| Christian Mahogany / `00-0039408` | OL | 2000-10-11 | 25.908814 | 2 | 210 | [0.890625, 0.945946, 1.000000, 0.958904] | 0.952425 | 0.007633538 | 0.110620478 | 0.000000000 |
| Ben Bartch / `00-0036272` | OL | 1998-07-22 | 28.131994 | 6 | 116 | [0.444444, 0.566038, 0.500000, 0.313433] | 0.472222 | 0.005092396 | 0.000000000 | 0.000000000 |
| Larry Borom / `00-0036905` | OL | 1999-03-30 | 27.444780 | 5 | 151 | [0.107692, 0.000000, 0.000000, 1.000000] | 0.053846 | 0.000508945 | 0.000000000 | 0.000000000 |
| Miles Frazier / `00-0040193` | OL | 2001-09-12 | 24.988877 | 1 | 171 | [0.203125, 0.054054, 0.000000, 0.041096] | 0.047575 | 0.000422557 | 0.005525649 | 0.000000000 |
| Juice Scruggs / `00-0038936` | OL | 2000-01-19 | 26.637097 | 3 | 62 | [0.000000, 0.000000, 0.046154, 0.205882] | 0.023077 | 0.000340398 | 0.000000000 | 0.000000000 |
| Tyler Conklin / `00-0034270` | TE | 1995-07-30 | 31.110837 | 8 | 157 | [0.000000, 0.029851, 0.000000, 0.323944] | 0.014925 | 0.000138350 | 0.000000000 | 0.000000000 |
| Brock Wright / `00-0036754` | TE | 1998-11-27 | 27.781542 | 5 | blank | [0.546875, 0.385714, 0.830508, 0.882353] | 0.688692 | 0.000000000 | 0.000000000 | 0.000000000 |
| Tay Martin / `00-0037524` | WR | 1997-12-14 | 28.734334 | 4 | blank | [0.064516, 0.157895, 0.237288, 0.107692] | 0.132794 | 0.000000000 | 0.000000000 | 0.000000000 |
| Jacob Saylors / `00-0038896` | RB | 2000-03-08 | 26.502940 | 3 | blank | [0.000000, 0.000000, 0.000000, 0.000000] | 0.000000 | 0.000000000 | 0.000000000 | 0.000000000 |
| Sione Vaki / `00-0039364` | RB | 2001-07-30 | 25.109345 | 2 | 132 | [0.000000, 0.000000, 0.000000, 0.000000] | 0.000000 | 0.000000000 | 0.000000000 | 0.000000000 |
| Jackson Meeks / `00-0040390` | TE | 2003-03-24 | 23.461125 | 1 | blank | [0.066667, 0.016949] | 0.041808 | 0.000000000 | 0.004855827 | 0.000000000 |
| Blake Miller / `00-0041439` | OL | 2004-02-25 | 22.535713 | 0 | 17 | missing | missing | 0.000000000 | 0.000000000 | 0.012765033 |

**Defense:** 27 players; 21 known-role; role mass 11.570446363915; 5 blank draft records representing 10.6127% of known role mass.

| Player / GSIS | Raw pos | DOB | Age | Exp | Pick | Saved prior roles | Role | Draft part | Young part | Rookie part |
| --- | --- | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| Aidan Hutchinson / `00-0037236` | DL | 2000-08-09 | 26.081302 | 4 | 2 | [0.791667, 0.824324, 0.962963, 0.781818] | 0.807995 | 0.049379175 | 0.000000000 | 0.000000000 |
| Devin White / `00-0035707` | LB | 1998-02-17 | 28.556370 | 7 | 5 | [1.000000, 1.000000, 1.000000, 0.890625] | 1.000000 | 0.038651369 | 0.000000000 | 0.000000000 |
| Jack Campbell / `00-0039018` | LB | 2000-08-22 | 26.045709 | 3 | 18 | [1.000000, 1.000000, 1.000000, 1.000000] | 1.000000 | 0.020371060 | 0.000000000 | 0.000000000 |
| Rock Ya-Sin / `00-0035637` | DB | 1996-05-23 | 30.294941 | 7 | 34 | [0.888889, 0.972973, 0.981481, 0.963636] | 0.968305 | 0.014352331 | 0.000000000 | 0.000000000 |
| Levi Onwuzurike / `00-0036954` | DL | 1998-03-02 | 28.520777 | 5 | 41 | [0.757143, 0.625000, 0.718750, 0.738462] | 0.728606 | 0.009834461 | 0.000000000 | 0.000000000 |
| Alim McNeill / `00-0036624` | DL | 2000-05-11 | 26.327714 | 5 | 72 | [0.731707, 0.777778, 0.756757, 0.259259] | 0.744232 | 0.007580398 | 0.000000000 | 0.000000000 |
| Avonte Maddox / `00-0034377` | DB | 1996-03-31 | 30.440050 | 8 | 125 | [0.975610, 1.000000, 0.932432, 0.981818] | 0.978714 | 0.007565727 | 0.000000000 | 0.000000000 |
| Derrick Barnes / `00-0036964` | LB | 1999-05-29 | 27.280505 | 5 | 113 | [0.694444, 0.689189, 0.981481, 1.000000] | 0.837963 | 0.006812954 | 0.000000000 | 0.000000000 |
| D.J. Reed / `00-0034384` | DB | 1996-11-11 | 29.824021 | 8 | 142 | [0.722222, 0.905405, 0.981481, 0.600000] | 0.813814 | 0.005902429 | 0.000000000 | 0.000000000 |
| Tyleik Williams / `00-0040672` | DL | 2003-02-24 | 23.537787 | 1 | 28 | [0.263889, 0.310811, 0.425926, 0.363636] | 0.337224 | 0.005507935 | 0.029145253 | 0.000000000 |
| D.J. Wonnum / `00-0036335` | LB | 1997-10-31 | 28.854802 | 6 | 117 | [0.652174, 0.671875, 0.560606, 0.805970] | 0.662024 | 0.005289699 | 0.000000000 | 0.000000000 |
| Chuck Clark / `00-0033294` | DB | 1995-04-19 | 31.390104 | 9 | 186 | [0.000000, 0.581081, 0.576923, 0.352941] | 0.464932 | 0.002946341 | 0.000000000 | 0.000000000 |
| Tyler Lacy / `00-0038940` | DL | 1999-11-10 | 26.828751 | 3 | 130 | [0.666667, 0.263889, 0.243902, 0.309091] | 0.286490 | 0.002171638 | 0.000000000 | 0.000000000 |
| Mekhi Wingo / `00-0039396` | DL | 2003-04-17 | 23.395415 | 2 | 189 | [0.127273, 0.208955, 0.616667, 0.400000] | 0.304478 | 0.001914143 | 0.026315114 | 0.000000000 |
| Roger McCreary / `00-0038125` | DB | 2000-02-10 | 26.576863 | 4 | 35 | [0.000000, 0.014925, 0.207547, 0.472727] | 0.111236 | 0.001625033 | 0.000000000 | 0.000000000 |
| Malcolm Rodriguez / `00-0037289` | LB | 1999-03-29 | 27.447518 | 4 | 188 | [0.055556, 0.040541, 0.351852, 0.727273] | 0.203704 | 0.001284014 | 0.000000000 | 0.000000000 |
| Ennis Rakestraw Jr. / `00-0039862` | DB | 2002-06-05 | 24.260594 | 2 | 61 | [0.184211, 0.123077, 0.000000, 0.062500] | 0.092788 | 0.001026784 | 0.008019437 | 0.000000000 |
| Khalil Dorsey / `00-0036124` | DB | 1998-03-31 | 28.441378 | 6 | blank | [0.013889, 0.000000, 0.000000, 0.000000] | 0.000000 | 0.000000000 | 0.000000000 | 0.000000000 |
| Trevor Nowaske / `00-0038660` | LB | 1998-11-07 | 27.836301 | 3 | blank | [0.069444, 0.054054, 0.055556, 0.145455] | 0.062500 | 0.000000000 | 0.000000000 | 0.000000000 |
| Christian Izien / `00-0038820` | DB | 2000-06-08 | 26.251052 | 3 | blank | [1.000000, 0.000000, 0.527273, 0.607843] | 0.567558 | 0.000000000 | 0.000000000 | 0.000000000 |
| Thomas Harper / `00-0039660` | DB | 2000-11-05 | 25.840366 | 2 | blank | [0.936508, 0.024390, 0.972973, 0.259259] | 0.597884 | 0.000000000 | 0.051673339 | 0.000000000 |
| Ahmed Hassanein / `00-0040761` | DL | 2002-07-09 | 24.167505 | 1 | 196 | missing | missing | 0.000000000 | 0.000000000 | 0.000000000 |
| Derrick Moore / `00-0041441` | LB | 2002-12-06 | 23.756819 | 0 | 44 | missing | missing | 0.000000000 | 0.000000000 | 0.005583543 |
| Jimmy Rolder / `00-0041442` | LB | 2004-02-09 | 22.579519 | 0 | 118 | missing | missing | 0.000000000 | 0.000000000 | 0.003409536 |
| Keith Abney II / `00-0041445` | DB | 2005-01-11 | 21.656844 | 0 | 157 | missing | missing | 0.000000000 | 0.000000000 | 0.002955877 |
| Skyler Gill-Howard / `00-0041447` | DL | 2002-10-13 | 23.904666 | 0 | 205 | missing | missing | 0.000000000 | 0.000000000 | 0.002586779 |
| Eric O'Neill / `00-0041459` | DL | 2003-07-01 | 23.190072 | 0 | blank | missing | missing | 0.000000000 | 0.000000000 | 0.000000000 |


## Reproduce the independent checks

Run `python -B research/pgo_ranking_trace_20260909/check_player_inputs.py` from the repository root. It verifies saved source manifests, reconstructs all 320 current descriptor cells from the frozen roster and saved role history, and verifies the raw Onwenu/Runyan mismatches. Observed result: PASS, maximum absolute feature error 0.0. The helper performs no model fitting, history preparation, source retrieval or writes.
