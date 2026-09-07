# PGO Rating Explanations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let readers inspect the actual saved contribution groups behind every PGO team rating while making the rating's meaning, age, and audit limits clear.

**Architecture:** Extend the existing comparison renderer and shared team drawer. Derive display contributions from the immutable 32-team ratings CSV; do not run a model. The existing protected refresh must retain the explanations while updating only McCabe's comparison fields.

**Tech Stack:** Existing Python, unittest, HTML/CSS, browser JavaScript. No new dependencies.

## Global Constraints

- McCabe Ratings remains the first/default board; McCabe and statistical PGO remain separate products.
- Preserve every PGO rating, rank, availability value, historical receipt, source lock, and Fantasy panel. Preserve `Experimental model — HOLD`.
- No model refit, tuning, evaluation, new source capture, new forecast lock, promotion, or publication in this implementation task.
- Show only the saved performance and roster/coaching groups. Do not invent offense/defense/QB percentiles, confidence, probabilities, scores, or individual feature contributions.
- McCabe: human-set roster ratings in neutral-field points; QB + non-QB offense + defense sum to the total. PGO: independent model outputs fitted to game margins and centered across 32 teams; its neutral-field point interpretation remains experimental. Do not describe PGO as a calibrated price, generic index, Super Bowl probability, or a current injury report.
- Remove the public raw `Rating gap` column. PGO minus McCabe is not an established point-price disagreement. Use rank comparisons only, with both snapshot dates visible.
- Title the comparison `PGO vs McCabe` and provide concise rank-based highlights for closest agreements, biggest disagreements, PGO higher, and McCabe higher. Explicitly label them rank comparisons across the shown dated snapshots. No consensus blending or tuning.
- The snapshot is July 21, 2026. The current frozen forecast fit does not exactly match the public rating fit; it cannot provide feature-level attribution for this table.
- Include a concise open-audit note that starting-QB/depth assumptions need review; group contributions do not establish predictive quality.
- Preserve existing keyboard, focus restoration, sorting, and mobile behavior. Reuse `openDrawer(content, trigger)`.
- Worktree: `D:/CodexWorktrees/Postgame_Outlet-league-profiles`; base e2d80ac7b6302367470241dff3bfac34ad5d00e9. No theme edits in this task.

### Task 1: Source-backed team explanations and dated labels

**Files:** Modify `pgo_comparison.py`; extend `tests/test_pgo_comparison.py`; write a local preview under `output/pgo-explain-lab-20260907/`. Keep `docs/index.html` untouched until the parent integrates the reviewed change.

**Interface:** Add `add_rating_explanations(page, model_path=MODEL_PATH, backtest_path=BACKTEST_PATH)` returning HTML. The function verifies the model source/receipt and that the existing comparison's 32 PGO numeric rows match the same saved snapshot before adding/replacing its own marked explanation block and team triggers. It must be idempotent. Call it from the real CLI after normal rendering/refresh so ordinary refreshes retain the feature. Existing generic test fixtures can still exercise `refresh_mccabe_page` without private/model lookups.

- [x] Add focused tests that reject nonfinite/invalid component algebra and a mismatched public row, demonstrate exact source identities and centered contributions for all 32 teams, prove idempotence and preservation through McCabe refresh, and ensure source-backed explanatory labels.
- [x] Use existing `load_model_rows` and `validate_receipt`. Explicitly validate both component columns before use. The arithmetic is:

```python
roster_mean = sum(row['roster_coaching_points'] for row in rows) / len(rows)
roster = row['roster_coaching_points'] - roster_mean
performance = row['full_strength_rating'] - roster
assert math.isclose(performance + roster, row['full_strength_rating'], abs_tol=1e-6)
```

The saved groups use different offsets; this centers the roster group across all 32 and places only CSV rounding residual in performance. These are model contribution groups, not independent football grades.

- [x] Add team-name buttons in the existing comparison row header. Store safe escaped details in HTML templates within the same panel. In `COMPARISON_SCRIPT`, bind them to the existing global `openDrawer` using template content. Avoid nested sections inside the comparison panel because its protected extractor intentionally ends at the first `</section>`.
- [x] Each drawer identifies the team, experimental HOLD, original as-of time, full-strength model output, centered performance group, centered roster/coaching group, availability adjustment and lineup output at that snapshot. Explain the common league-average baseline, experimental scale interpretation, correlated inputs, and absent feature-level receipt. Use the full group labels and values; no percentage bars masquerading as percentile scores.
- [x] Add visible introductory meaning/date text and an expandable audit explanation. Replace misleading `PGO today` labels with `PGO lineup`, explicitly tied to the snapshot date. Don't claim a July zero adjustment establishes September health.
- [x] Keep future McCabe refresh safe: templates must not contain table rows that match its comparison-row patcher; use paragraphs or a description list. All 32 original PGO values and the Fantasy panel must remain byte-identical outside approved markup additions and labels.
- [x] Support migration from the existing 10-column comparison to the new 9-column comparison with no raw rating gap. In the shared refresh, distinguish exactly 9 versus 8 `td` cells, reject other counts, and update McCabe rank/value plus rank gap in both formats. Deriving an old headline model value from the raw rating gap is needed only for the legacy format. Never manufacture a replacement numerical rating-gap field. Regenerate rank highlights from fresh McCabe data during normal enrichment; add a focused legacy/current refresh regression.
- [x] Run `python -m unittest tests.test_pgo_comparison -v` and relevant `tests.test_ratings_release` checks; inspect `git diff --check`. Use existing source data for the local preview only; no fit or evaluation.
- [x] Commit only source/test/plan files with `Explain saved PGO rating contributions and snapshot limits`. Write a report at `output/pgo-explain-lab-20260907/explanations-report.md` with tests, commit, preservation evidence, and concerns.

The parent will review the diff, test the real drawer in desktop/mobile browsers, and integrate the reviewed HTML separately.
