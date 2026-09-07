# PGO Forecast Lab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a reviewable experimental 2026 forecast archive with honest interim tracking, using already frozen predictions.

**Architecture:** One Python generator verifies exact-byte archived evidence and renders a separate static page. Reuse existing prospective validators and exclusive output helper; no service, database, client data fetch, model run, or new dependency.

**Tech Stack:** Python stdlib plus existing PGO modules; HTML, native details, small browser script; unittest.

## Global Constraints

- Keep McCabe first/default and separate from statistical PGO and editorial Staff Picks.
- Preserve every original source, research receipt, lock and forecast. No fit, tuning, development evaluation, canonical grade, new forecast lock, source/network capture, or publication in this task.
- Source cutoff July 21, 2026; exact forecasts publicly attested August 26, 2026 in commit `8aae9438d251c645509d3df15a31bb86d50059b9` at `2026-08-26T16:07:24-04:00`. Do not call July 21 the verified creation date.
- This frozen track uses 75% PGO v0 and 25% archived challenger. It is a different fit from the public PGO v1 ratings table. Preserve that distinction and say `Experimental` prominently.
- Margin forecasts are model estimates of home score minus away score, not calibrated market prices. No win probabilities, confidence tiers, predicted final scores, season records, playoff odds, award outputs, staff picks, or wagering claims. A winner accuracy diagnostic derived explicitly from margin signs is permitted because the user requested that metric; it is not a calibrated probability or a separate human pick.
- Do not load or display McCabe numeric ratings in this Lab, or compute a PGO-minus-McCabe numerical gap. A link to the separate McCabe board is appropriate.
- All 272 forecasts remain available regardless of outcome. Data is the frozen schedule, not a claim about the current schedule. Changed kickoff/identity requires review; never alter the original forecast.
- Any subset metrics are `Interim tracking — not a validation result`. Do not emit a canonical receipt or PASS. Leave the existing full-season scientific gate unchanged.
- No fabricated results or staff picks. All example records in tests are synthetic only.
- No palette publication; the user is choosing among actual-homepage previews. Use the current shared board styles so a later reviewed palette carries across.

### Task 1: Archive reader and interim tracker

**Files:** Create `pgo_forecast_lab.py`, `tests/test_pgo_forecast_lab.py`, exact-byte copies under `docs/evidence/forecast-lab-2026/` and `docs/forecast-lab.html`; update `.gitattributes` only for the copied immutable files. Do not edit `pgo_comparison.py` or theme files (parent integrates links).

**Inputs:**

- Existing `research/pgo_stability_blend/prospective_attestation.json`.
- Exact derived lock and CSV from `D:/Claude Context/Postgame_Outlet/prospective_evidence/2026-08-26-stability-blend/`. SHA lock `d6ebf73188c41046f945a54653bdb89eadc2dc18d917276a47c0166b9ada98e9`; CSV `8b17ab8c4744586e5386a7755ceaf63ccf8a8438533e8c904de68b5bc25dca6f`.
- Existing `generate_site.TEMPLATE` CSS/fonts can supply shared presentation. Do not embed the whole rankings app or assume unknown placeholders are safe. Extract the existing `<style>` block for this static page and use its CSS variables, hero, wrap, table-shell classes.

**Interfaces:** `load_archive(lock_path, csv_path, attestation_path)` validates and returns the lock. `load_results(capture_root, lock)` validates append-only captures and returns unique finalized rows plus audit provenance. `render_lab(lock, results, provenance)` returns escaped standalone HTML. A small CLI builds the page and optionally records a reviewed results CSV; it never fetches or grades.

- [ ] Write focused tests for exact attestation/CSV agreement and tampering; 272-row archive coverage; empty/interim counts; subset identity/score/timestamp validation; known MAE/RMSE; existing-target/correction refusal; escaping and honest labels. Use the real frozen archive for verification and small synthetic result subsets for logic, with no fitting or canonical grading.
- [ ] Copy the two original artifacts byte-for-byte with `shutil.copyfile`; verify the stated hashes before and after. Set `-text` for their `.gitattributes` entries to preserve exact bytes.
- [ ] Verify using existing `pgo_prospective._verify_lock` and `_verify_grade_attestation`, plus the actual CSV's SHA and equality to `_prediction_csv(lock)`. Reject a mismatch before writing HTML. Don't substitute the public board fit.
- [ ] Render an answer-first page: `PGO Forecast Lab`, `Can PGO predict football?`, experimental status, source cutoff/attestation date, frozen/recorded counts, and a link back to McCabe's ratings. One native details block per week keeps all 272 rows available; Week 1 open initially. Show matchup, frozen kickoff with timezone, blend margin, PGO v0 margin, actual result/error if present. A diagnostic disclosure may show archived unblended margins; do not label the blend as the live ratings model.
- [ ] Include clear concise method/record copy, exact downloadable evidence links, immutable attestation-commit link, and a separate `Staff Picks` note saying no editorial picks are published in this model archive. Use human-readable dates without losing timezone meaning.
- [ ] Freeze naive diagnostics now, before kickoff, outside every promotion gate: constant zero margin and venue-only +2.5 for `Home` / 0 for `Neutral` (the existing v0 home-field constant). Label these diagnostic margin baselines, not simulated coin flips or market prices. Show the 50/50 winner benchmark as a theoretical 50% reference only; no invented observed record. McCabe game-pick and market comparisons are unavailable because they were not captured. Do not retrospectively fill them from end-season data.
- [ ] Interim metrics on the identical accepted results for blend, v0, zero, and venue baselines: count, MAE, RMSE. A winner accuracy diagnostic may be computed for blend/v0 from sign, excluding actual ties and reporting zero-margin forecasts as abstentions; state the denominator. No confidence calibration claims.
- [ ] Results capture uses a reviewed local CSV with the existing grader identity/final columns and an explicit HTTPS source URL. Captures are incremental newly finalized games, not cumulative replacements. Record current UTC capture time and the archived CSV's actual SHA. The exclusive helper writes text, so require UTF-8 round-trip preservation or canonicalize and hash the exact stored UTF-8 bytes. Write a new timestamped directory containing the CSV and a JSON metadata receipt via `_write_new_outputs`; refuse existing destinations. No real result capture now. Rendering verifies stored CSV hashes, exact lock identities (including kickoff, week/season if supplied), unique game IDs, nonnegative integer scores (reject bool/fraction/nonfinite), and kickoff < finalized_at <= captured_at. Reject duplicate/conflicting outcomes across captures; an explicit correction-policy extension can be designed if a real correction arises. Do not overwrite a result, silently select a later correction, or write canonical `prospective_receipt.json`.
- [ ] Label results provenance as a reviewed transcription: the CSV digest verifies that archived transcription, not the remote source's contents. Do not imply automatic source acquisition or verification. Add a focused check that no McCabe numeric data is read/rendered/subtracted, and fail if shared CSS markers are missing/ambiguous.
- [ ] Use source URLs only as provenance, never as executable content; escape HTML and restrict to HTTPS. Reject traversal/invalid capture metadata and any source path outside the individual capture directory. Use fixed filenames to avoid needing arbitrary path support.
- [ ] Build `docs/forecast-lab.html` with no outcomes. Run `python -m unittest tests.test_pgo_forecast_lab -v`, `python -m py_compile pgo_forecast_lab.py`, and `git diff --check`. Confirm original lock/CSV/attestation/model bytes unchanged. Commit only this task's files and plan.
- [ ] Write `output/pgo-explain-lab-20260907/forecast-lab-report.md` with commit, tests, exact input/output hashes, and limitations. Return a short result. Parent reviews and publishes separately.

No new weekly forecast generation or real result acquisition is needed for this archive. The public record can grow through explicitly captured finalized results; scientific certification remains the separate existing full-season process.
