# McCabe dashboard mock v2 review

Recommendation: carry this visual direction into the existing PGO renderer after
a responsive, accessible preview. The dark slate surfaces, restrained Cobalt
accents, compact ratings board, team color markers and expandable plain-language
analysis fit the product. The submitted file is a useful theme reference.

Reviewed input: `C:\Users\Alex\Downloads\pgo_dashboard_mock_v2.html` (77,938 bytes),
SHA-256 `164f9b55a42064ef3107f4e089cb32cd99acec93ac8dd20342d9afd37ca8dae7`.
Review date: 2026-09-09. Comparison checkout: `275289e` plus the existing isolated
snap repair. The mock and public site were not edited.

## What works

- The palette specifies dark slate (`#0e1116` / `#171c24`), light text
  (`#e6edf3`), muted secondary text (`#93a1b0`) and blue (`#3b82f6`). This fits
  the already selected Cobalt direction.
- A single 32-team board gives the ratings a clear focal point. Monospaced,
  tabular numbers and a stronger total-rating weight support comparison.
- Team markers and a signed, zero-centered bar provide useful secondary cues.
  Numerical signs remain visible, so color is not the only above/below signal.
- The writing follows an understandable pattern: the case for the team,
  quarterback, what moved the number, and risk or concluding assessment.
- The implementation uses ordinary HTML/CSS and a small disclosure function.
  No new framework or dependency is needed to use this direction.

## Changes needed before adopting the theme

1. **Keep the current mobile behavior.** The mock has eight table columns, a
   nominal 230-pixel scale column, no media rules, and no deliberate horizontal
   table-scrolling treatment. Its card clips overflow. Use rank, team and rating
   as the narrow-screen essentials; expose component columns and the scale
   through the existing all-columns control. Actual narrow-screen clipping and
   wrapping remain to be measured in a rendered preview.
2. **Use accessible disclosure controls.** All 32 rows use `onclick`; there are
   no buttons, focus targets, keyboard handlers or expanded-state attributes.
   Preserve the existing keyboard interaction and focus behavior. Team names
   should activate a real button with a visible focus indicator and
   `aria-expanded` / `aria-controls`. Lighten the small green update-badge text:
   its declared foreground/background colors calculate to only 4.10:1 contrast,
   versus 6.49:1 for muted table text and 16.00:1 for body text.
3. **Retain sorting, navigation and context.** The mock contains no sort
   controls, links, model switch, methodology links or source links. Keep the
   existing McCabe/PGO distinction and forecast/fantasy navigation. Keep PGO's
   experimental status visible in its own view and detailed evidence available
   behind its disclosure.
4. **Tighten hierarchy.** Give the brand a semantic `h1`; align its content with
   the board's maximum width. Put the quarterback below the team name on narrow
   screens. Expand Off/Def to Offense/Defense where space permits. Put the zero
   reference and scale meaning close to the bars, rather than only below row 32.
5. **Edit the expanded copy for scanning.** Keep a short opening assessment and
   two or three drivers prominent. Several long writeups make extensive use of
   bold text, reducing its usefulness as emphasis. Put detailed injury context,
   dated sources and methodological caveats in secondary disclosure.
6. **Generate freshness labels from the edition.** Week 1, Updated Sep 8 and
   the Rams leader badge are hard-coded in this mock. Reuse the renderer's saved
   edition metadata so a theme revision cannot silently claim a fresh update.

## The file also proposes data and editorial changes

All 32 displayed component sums equal their displayed totals. That establishes
internal arithmetic only; the injury and roster statements were not fact-checked
as part of this theme review.

Compared with `data/ratings.csv`, 19 teams have at least one different displayed
component: 18 substantive revisions plus San Francisco's source offense value
of 0.25 displayed as 0.2. Examples:

| Team | Current source total | Mock total | Component change |
| --- | ---: | ---: | --- |
| Los Angeles Rams | +7.3 | +7.6 | Defense +0.9 to +1.2 |
| Buffalo | +7.0 | +6.6 | Offense +1.0 to +0.6 |
| Baltimore | +5.5 | +6.0 | Defense +0.5 to +1.0 |
| Kansas City | +4.0 | +3.0 | QB +4.5 to +3.5 |
| Denver | +1.5 | +2.2 | Changes to all three components |

These are proposed McCabe grades and prose, not PGO model outputs. Preserve the
file as supplied. A theme change should use reviewed source data; adoption of
these revised grades and writeups should be explicit and retain edition history.
The McCabe sum `QB + Offense + Defense` must not be presented as a validated
decomposition of PGO's separate statistical model.

## Review limits and next preview

The browser security policy blocked opening the local file URL. This review
therefore covers the actual HTML, CSS, interaction code, table arithmetic and
source-data differences; it does not claim visual approval or rendered desktop,
mobile, contrast or browser interaction validation. No alternate browser path
was used to circumvent that block.

The next design step is an isolated preview applying these visual tokens to the
existing renderer while retaining its functional and evidence controls. Verify
desktop, 375-pixel mobile and the narrower Shopify embed; then obtain visual
approval before publication. The user's request in this turn is a review, and
no theme implementation, data adoption or publication was performed.
