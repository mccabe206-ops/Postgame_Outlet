"""All-team postseason history on the unchanged corrected construction.

Run construction in a dedicated process: the existing research constructor uses
scoped module hooks. True source game types remain in the coverage receipt.
"""
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
import math

from research.pgo_week1_corrected import train as corrected
from research.pgo_postseason_candidate import pinned_challenger as pinned

audit = corrected.audit
ch = audit.ch
IDENTITY = 'pgo-postseason-candidate-2026-09-09'
HISTORY_TYPES = frozenset(('REG', 'WC', 'DIV', 'CON', 'SB'))
PINNED_CORE_SHA256 = 'f71712d88be59c1bc5f05f319277d1e9c9a76a719882455459317ecea2f28735'


@contextmanager
def historical_construction(paths):
    """Retain the exact issued constructor's role semantics, including its limits."""
    if audit.sha256(Path(pinned.__file__).read_bytes()) != PINNED_CORE_SHA256:
        raise ValueError('Pinned corrected historical core differs')
    original_audit, original_current = audit.ch, audit.current.ch
    audit.ch = audit.current.ch = pinned
    try:
        with audit.construction_scope(paths, active_only=True, half_life_games=4, exposure_fix=True):
            yield
    finally:
        audit.ch, audit.current.ch = original_audit, original_current


def history_schedule(paths):
    rows, seen, periods = [], set(), set()
    for raw in audit.pgo_sources.open_csv(paths['schedule_results', None]):
        if raw.get('game_type') not in HISTORY_TYPES:
            continue
        if not ch.FIRST_SEASON <= int(raw['season']) <= ch.LAST_SEASON:
            continue
        if not raw.get('home_score', '').strip() or not raw.get('away_score', '').strip():
            continue
        if raw['game_id'] in seen:
            raise ValueError('Duplicate history game')
        seen.add(raw['game_id'])
        for side in ('home', 'away'):
            score = float(raw[side + '_score'])
            if not math.isfinite(score) or score < 0:
                raise ValueError('Invalid historical score')
            key = (int(raw['season']), int(raw['week']), ch.normalize_team(raw[side + '_team']))
            if key in periods:
                raise ValueError('Duplicate team history period')
            periods.add(key)
        rows.append(dict(raw))
    return rows


def build_rows(paths, *, include_postseason=True):
    schedule = history_schedule(paths)
    if not include_postseason:
        schedule = [r for r in schedule if r['game_type'] == 'REG']
    by_id = {r['game_id']: r for r in schedule}
    schedule_path = Path(paths['schedule_results', None]).resolve()
    # ponytail: reuse the pinned walker without altering its default REG policy.
    # Only its schedule membership view changes; targets are filtered by the
    # retained, true source type immediately after the chronological walk.
    with historical_construction(paths):
        original_open = pinned.open_csv

        def inclusive_open(path):
            if Path(path).resolve() == schedule_path:
                for row in schedule:
                    yield {**row, 'game_type': 'REG'}
            else:
                yield from original_open(path)

        pinned.open_csv = inclusive_open
        try:
            rows, context, inputs = audit.current.build_rows(paths, 'starter_recency')
        finally:
            pinned.open_csv = original_open
    if {r.game_id for r in rows} != set(by_id):
        raise ValueError('Postseason history walk membership differs')
    postseason = []
    for row in rows:
        game = by_id[row.game_id]
        if game['game_type'] == 'REG':
            continue
        teams = {}
        for side in ('home', 'away'):
            team = ch.normalize_team(game[side + '_team'])
            key = (row.season, row.week, team)
            team_row = inputs['team_rows'].get(key)
            qbs = [r for r in inputs['players'].get(key, ()) if r.get('position', '').strip() == 'QB']
            if team_row is None or not qbs:
                raise ValueError(f'Missing postseason team/QB production: {row.game_id} {team}')
            teams[team] = {'team_rows': 1, 'qb_rows': len(qbs),
                           'active_roster_rows': len(inputs['rosters'].get(key, ())),
                           'snap_rows': len(inputs['snaps'].get(key, ()))}
        postseason.append({'game_id': row.game_id, 'season': row.season, 'week': row.week,
                           'game_type': game['game_type'], 'kickoff': row.kickoff,
                           'neutral': game.get('location', '').casefold() == 'neutral', 'teams': teams})
    regular = audit.drop_features([r for r in rows if by_id[r.game_id]['game_type'] == 'REG'], audit.ROSTER_COACH)
    report = {'history_games': len(rows), 'regular_targets': len(regular),
              'postseason_games': len(postseason),
              'game_types': dict(Counter(r['game_type'] for r in schedule)),
              'postseason': postseason, 'starter_coverage': context['current_strength']['coverage'],
              'historical_core_sha256': PINNED_CORE_SHA256,
              'historical_role_policy': 'Exact corrected constructor; inherited role identity/zero-fill limits retained',
              'historical_source_vintage': 'REVIEW REQUIRED',
              'policy': 'REG+WC+DIV+CON+SB update history; REG-only fitting/evaluation targets'}
    return regular, context, inputs, report


def portable_context(context, inputs):
    result = corrected.portable_context(context, inputs)
    result['identity'] = IDENTITY
    return result


def _score_rates(rows):
    points, allowed, counts, posts, totals, seen = Counter(), Counter(), Counter(), Counter(), [], set()
    for row in rows:
        if row['game_id'] in seen:
            raise ValueError('Duplicate scoring-history game')
        seen.add(row['game_id'])
        home, away = (ch.normalize_team(row[k]) for k in ('home_team', 'away_team'))
        hs, aws = float(row['home_score']), float(row['away_score'])
        if home == away or min(hs, aws) < 0 or not all(map(math.isfinite, (hs, aws))):
            raise ValueError('Invalid scoring history')
        points[home] += hs
        points[away] += aws
        allowed[home] += aws
        allowed[away] += hs
        counts.update((home, away))
        if row['game_type'] != 'REG':
            posts.update((home, away))
        totals.append(hs + aws)
    if not totals:
        raise ValueError('Empty scoring history')
    return ({team: {'pf': points[team] / n, 'pa': allowed[team] / n, 'games': n,
                    'postseason_games': posts[team]} for team, n in sorted(counts.items())},
            sum(totals) / len(totals))


def scoring_rates(paths):
    """Unfitted 2025 REG+POST PF/PA heuristic, with separate team denominators."""
    rows = [r for r in history_schedule(paths) if r['season'] == '2025']
    regular = Counter(ch.normalize_team(r[side + '_team']) for r in rows
                      if r['game_type'] == 'REG' for side in ('home', 'away'))
    types = Counter(r['game_type'] for r in rows)
    if (set(regular) != set(audit.pgo_model.CURRENT_TEAMS) or set(regular.values()) != {17}
            or types != Counter(REG=272, WC=6, DIV=4, CON=2, SB=1)):
        raise ValueError('Scoring requires complete 2025 REG+postseason history')
    return _score_rates(rows)
