# PGO Legacy Grading Holds Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep a legacy kickoff conflict visible and ungraded while verified independent current updates continue.

**Architecture:** Add one focused legacy-record component, called by the existing season decorator and durable save/load checks. Keep ordinary grading strict; authenticated previous records supply held counts, while shared views and health consumers disclose held editions.

**Tech Stack:** Existing Python standard library, unittest, current PGO archive readers and GitHub Actions. No new dependency.

## Global Constraints

- Never revise previously accepted final scores or grades; pending forecasts may earn new grades from verified finals.
- Retain original issue clocks, margins, QB assumptions, confidence allocations and archived bytes.
- Current calculations remain excluded from locked grading. Keep experimental labels.
- Only an earlier-edition kickoff mismatch with matching game/team identity is isolatable; wrong-team, malformed identity, changed accepted final, corrupt archive and unverified starter cases remain rejected.
- A held edition retains its entire last verified record and its authenticated saved-check clock; otherwise counts are unavailable. Repeated holds retain that source and record.
- Held-edition accuracy and comparisons are explicitly unavailable; no recalculated partial record may look current.
- No dependency, refit, automatic rescheduling approval, publication-queue change or Shopify-content change is part of this patch.
- Parent owns Git commits, source admission, real refresh and publication. Implementer writes only named source/tests/docs and ignored task artifacts, and reports exact tests; do not commit or run live source capture.

## Task 1: Isolate, validate and disclose legacy grading holds

**Files:**
- Create: `pgo_legacy_grades.py`, `tests/test_pgo_legacy_grades.py`.
- Modify as required: `pgo_season.py`, `pgo_season_view.py`, `pgo_season_accuracy.py`, `pgo_workflow_status.py`, `pgo_alerts.py`, `docs/pgo-season-operations.md`.
- Extend tests as required: `tests/test_pgo_season.py`, `tests/test_pgo_season_boundaries.py`, `tests/test_pgo_season_storage.py`, `tests/test_pgo_season_view.py`, `tests/test_pgo_season_accuracy.py`, `tests/test_pgo_workflow_status.py`, `tests/test_pgo_alerts.py`.
- Workflow scope: add `tests.test_pgo_legacy_grades` to the season verification command in `.github/workflows/update-season.yml`; retain all existing tests and workflow behavior.

**Interfaces:**
- Consumes: strict `pgo_season.record(games, results)`, immutable `legacy_models()`, actual verified previous season state/pointer and `pgo_season_rollover.load_archive(root, pointer)`.
- Produces: a focused module with `records(state, results, previous, previous_pointer)` returning `(legacy_record_rows, legacy_grading_check)` and `validate(state, root, previous_pointer, *, durable=None)`.
- Update `decorate(state, results, *, previous=None, previous_pointer=None)` compatibly. All three production refresh calls pass the verified previous state and actual previous pointer. Existing callers without a prior source can produce an explicitly unavailable held legacy record.
- Component shape: `legacy_grading_check = {'status': 'READY' or 'BLOCKED', 'checked_at': state['checked_at'], 'blocked_reason': None or a plain explanation, 'models': {edition: hold}}`.
- A hold contains `game_ids` (sorted unique actual kickoff-conflict IDs), `blocked_reason`, `record_source` (minimal pointer `{path, manifest_sha256, checked_at}` or `None`) and `record_checked_at` (authenticated source-state check time or `None`). Healthy models are absent from `models`. Unavailable record rows have the existing five count fields set to `None`, never fabricated zeros.
- First hold uses the immediately preceding verified row and pointer, after verifying its count replay. Repeated holds carry that prior hold's source/counts; they do not substitute the newer overall refresh time for the retained record's time.

- [ ] **Step 1: Reproduce the existing failure before implementation.**

Use real decorator/record logic with a detached CHI–GB fixture; patch only immutable model loading and external source I/O. A representative red case is:

```python
game = dict(game_id='2026_05_CHI_GB', season=2026, week=5, home='GB', away='CHI',
            kickoff='2026-10-11T17:00:00+00:00', margin=3, total=48,
            home_points=25.5, away_points=22.5, issued_at='2026-10-06T14:27:10+00:00',
            source_edition='weekly', inputs_as_of='2026-10-06T14:27:10+00:00', confidence=None)
final = dict(game_id=game['game_id'], season=2026, week=5, game_type='REG',
             home_team='GB', away_team='CHI', kickoff=game['kickoff'],
             home_score=24, away_score=20, actual_margin=4)
legacy_game = dict(game, kickoff='2026-10-11T20:25:00+00:00')
```

Assert that strict direct legacy `record([legacy_game], [final])` still raises, while the new decorator eventually preserves the prior legacy row and grades the weekly model. Before code, run the new regression and record the actual `Grade identity differs` failure in the task report.

- [ ] **Step 2: Implement the exact conflict boundary and retention.**

Use this strict classification in the new component; do not catch arbitrary grading exceptions:

```python
def kickoff_conflicts(model, results):
    from pgo_season import require, utc
    finals = {row['game_id']: row for row in results}
    require(len(finals) == len(results), 'Duplicate grades result')
    held = []
    for game in model['games']:
        result = finals.get(game['game_id'])
        if result is None:
            continue
        require(result['home_team'] == game['home'] and result['away_team'] == game['away'],
                'Grade identity differs')
        if utc(result['kickoff']) != utc(game['kickoff']):
            held.append(game['game_id'])
    return sorted(held)
```

Healthy legacy rows use unchanged `record()`. Held rows copy the prior verified edition row exactly or use `None` counts when no verified record exists. Supply the metadata contract above. The weekly record and weekly game grading remain strict. Preserve the final decorator after locked forecast restoration.

- [ ] **Step 3: Validate custody at save/load and repeated refresh.**

Call `validate()` before durable pointer advancement in `save_state()` and before returning the loaded state in `load_current()`. In saving, the previous pointer is the current verified pointer; in reading it is the current manifest's `previous` pointer. Use the existing archive reader, deduplicating identical source-pointer reads within one validation call. Recompute exact conflict IDs and compare the retained row to the immediately preceding row and the authenticated source row; replay the source record with strict original model inputs and source finals. Verify actual source-state check clock, check-clock ordering and source-pointer carry-forward. Reject modified held counts, changed retained source, future/self references, absent or fabricated holds, unknown/duplicate editions, malformed component data and unavailable rows claiming verified counts. Old states without this optional component remain readable.

Concrete custody assertion:

```python
source_state, source_manifest = load_archive(root, hold['record_source'])
require(source_state['checked_at'] == hold['record_checked_at'], 'Held record clock differs')
require(utc(hold['record_checked_at']) < utc(state['checked_at']), 'Held record is not historical')
source_row = next(row for row in source_state['model_records'] if row['edition'] == edition)
require(retained_row == source_row, 'Held legacy record differs from verified archive')
require({key: retained_row[key] for key in ('wins','losses','ties','no_pick','pending')}
        == record(model['games'], source_state['results']), 'Held legacy record does not replay')
```

- [ ] **Step 4: Make all consumers honest about the hold.**

The existing record table displays a plain held reason and authenticated saved-check date under the affected edition; no-source counts display unavailable. `pgo_season_accuracy.summarize()` excludes held legacy editions from current metric/comparison calculations and returns their hold information for the view to disclose. Other valid models keep their metrics. The current weekly model cannot be marked held by this legacy component. Extend existing workflow health and alert assessment with a separate legacy-grading review condition, without setting overall ready updates to blocked and without sending manual notifications. Describe this behavior in season operations.

- [ ] **Step 5: Complete the meaningful regression set and self-review.**

Cover: healthy unchanged records; first/repeated hold with exact row/time/source preservation; unavailable prior record; weekly grades continuing; wrong-team legacy and primary conflicts still raising; malformed/forged counts/pointers/clocks and omitted holds rejected; valid save/load; held accuracy/comparisons unavailable; both renderer disclosures; health separates the hold from current updates; original accepted finals/grades/locked forecast inputs unchanged. Keep source fixtures offline and do not modify real season archives.

Run: `python -B -m unittest tests.test_pgo_legacy_grades tests.test_pgo_season tests.test_pgo_season_boundaries tests.test_pgo_season_storage tests.test_pgo_season_view tests.test_pgo_season_accuracy tests.test_pgo_workflow_status tests.test_pgo_alerts tests.test_public_board_workflow`.

Expected: all tests pass with the direct strict mismatch case still rejected. Write `output/pgo-legacy-grade-holds-20261011/task-1-report.md` with red/green output, commands, changed files and concerns. Do not run the hour-long full suite: parent runs required full CI on the final reviewed source.

- [ ] **Step 6: Parent verification, commit and task review.**

Parent inspects the diff and independent test evidence, commits only scoped files, produces `scripts/review-package BASE HEAD`, and requests spec-compliance plus quality review using the task brief/report/diff. Fix important findings with covering tests before moving to release.

## Task 2: Verify real recovery and publish the reviewed patch

**Owner:** Parent. **Files:** ignored `output/pgo-legacy-grade-holds-20261011/` evidence; legitimate newly captured append-only season files if admitted; generated pages through the tested publisher only.

- [ ] Record immutable forecast/accepted-result/grade/archive preservation before real refresh.
- [ ] Run actual season refresh with reviewed code; retain new source clocks and distinct blocked legacy records. Replay saved state and verify both real pages, current ranking consistency and held record/accuracy labels. Never bypass source or clock checks to finish a release.
- [ ] Complete broad whole-branch review using the approved spec, implementation report and full range diff.
- [ ] Push the reviewed branch and dispatch `update-board.yml` for its exact SHA. Require the full Python 3.12 suite plus both 14-test research suites to pass before source integration/publication.
- [ ] Integrate by non-rebasing fast-forward only after the exact source test job passes. Allow the existing guarded publisher to commit both pages; if necessary retry only the publisher using the same passed source gate.
- [ ] Verify successful Pages deployment, exact public bytes and actual Opera Shopify embed, including held historical editions and current verified updates. Save a JPEG proof and release receipt, update the progress ledger, and report remaining queue/homepage work separately.
