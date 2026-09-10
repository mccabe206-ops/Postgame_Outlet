"""Issue fixed, separately paired penalty forecasts and describe verified finals."""
import copy
import csv
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import re

import pgo_challenger as ch
import pgo_forecast_corrected as scoring
import pgo_season_model as model
import pgo_sources

PACKAGE_DIR = Path(__file__).resolve().parent / 'docs/evidence/penalty-model-2026'
PACKAGE_MANIFEST_SHA256 = '298b6f9d7624d3589763ab78ecb80583c1b8e43097e5da8adc1f0ba5f2faa628'
SOURCE_HREF = 'evidence/penalty-model-2026/manifest.json'
IDENTITY = 'pgo-penalty-shadow-2026'
TEAM_URL = 'https://github.com/nflverse/nflverse-data/releases/download/stats_team/stats_team_week_2026.csv.gz'
MUTABLE = {'grade', 'result'}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _utc(value):
    result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    _require(result.tzinfo is not None, 'Candidate clock needs a timezone')
    return result.astimezone(timezone.utc)


def _verified(path, digest, size=None):
    path = Path(path)
    _require(not path.is_symlink() and path.is_file(), 'Candidate source is missing or a symlink')
    raw = path.read_bytes()
    _require(hashlib.sha256(raw).hexdigest() == digest and (size is None or len(raw) == size),
             'Candidate source hash or size differs: ' + path.name)
    return raw


def _package(path, digest):
    _require(re.fullmatch('[0-9a-f]{64}', digest or '') is not None, 'Candidate package has no reviewed manifest pin')
    path = Path(path); _require(not path.is_symlink(), 'Candidate package is a symlink')
    manifest = json.loads(_verified(path / 'manifest.json', digest))
    names = {'final-fit.json', 'penalty-seed.json', 'metrics.json'}
    _require(set(manifest['files']) == names, 'Candidate package inventory differs')
    package = {name: json.loads(_verified(path / name, manifest['files'][name]['sha256'],
                                         manifest['files'][name]['bytes'])) for name in names}
    baseline = json.loads(_verified(model.SOURCE_DIR / 'final-fit.json', model.FIT_SHA256))
    from research.pgo_penalty_candidate.candidate import FEATURE
    fit = package['final-fit.json']; seed = package['penalty-seed.json']
    _require(set(fit['preprocessor']['feature_names']) == set(baseline['preprocessor']['feature_names']) | {FEATURE},
             'Candidate fitted feature inventory differs')
    _require(seed['season'] == 2025 and seed['feature'] == FEATURE and seed['half_life_games'] == 4
             and set(seed['states']) == set(pgo_sources.CURRENT_TEAMS),
             'Candidate seed season or team inventory differs')
    return fit, seed, package['metrics.json'], baseline


def _penalty_states(state, root, checked, seed):
    from research.pgo_penalty_candidate.candidate import penalty_history
    rankings = state['rankings']; completed = rankings['completed_week']
    _require(type(completed) is int and 0 <= completed <= 18, 'Candidate completed-week boundary differs')
    games, rows = [], []
    if completed:
        games = [g for g in state['schedule'] if g['week'] <= completed]
        _require(set(g['week'] for g in games) == set(range(1, completed + 1)), 'Candidate completed weeks are missing')
        completed_results = [r for r in state['results'] if r['week'] <= completed]
        finals = {r['game_id']: r for r in completed_results}
        _require(len(finals) == len(completed_results) and set(finals) == {g['game_id'] for g in games},
                 'Candidate completed-game final inventory differs')
        for game in games:
            result = finals[game['game_id']]
            _require(result['home_team'] == game['home'] and result['away_team'] == game['away']
                     and _utc(result['kickoff']) == _utc(game['kickoff'])
                     and _utc(game['kickoff']) < _utc(result['finalized_at']) <= _utc(rankings['inputs_as_of']) <= checked,
                     'Candidate final identity or clock differs')
        refs = [r for r in rankings['source_captures'] if r.get('url') == TEAM_URL]
        _require(len(refs) == 1, 'Candidate needs one captured team-stat source')
        ref = refs[0]
        _require(re.fullmatch(r'(?:sources|source-archive)/[0-9a-f]{64}\.csv\.gz', ref['path']) is not None,
                 'Candidate team-stat path differs')
        _require(_utc(ref['captured_at']) <= _utc(rankings['inputs_as_of']) <= checked, 'Candidate source clock is from the future')
        raw = _verified(Path(root) / ref['path'], ref['sha256'], ref['bytes'])
        periods = {(str(g['season']), str(g['week'])) for g in games}
        rows = [r for r in csv.DictReader(io.StringIO(gzip.decompress(raw).decode('utf-8-sig')))
                if (r.get('season'), r.get('week')) in periods]
    history_through = max((_utc(g['kickoff']) for g in games), default=_utc(seed['history_through']))
    _require(_utc(rankings['history_through']) == history_through, 'Candidate and ranking history clocks differ')
    return penalty_history(games, rows, initial=seed['states'])['states']


def _historical(metrics):
    values = metrics.get('metrics', {}); base = values.get('postseason', {}).get('overall', {})
    candidate = values.get('candidate', {}).get('overall', {}); screen = metrics.get('further_study_screen', {})
    interval = metrics.get('paired_bootstrap', {}).get('vs_postseason', {})
    return dict(games=candidate.get('games', candidate.get('count')), baseline_mae=base.get('mae'),
                candidate_mae=candidate.get('mae'),
                mae_improvement=base['mae'] - candidate['mae'] if 'mae' in base and 'mae' in candidate else None,
                interval={k: interval.get(k) for k in ('lower', 'upper')},
                season_wins=screen.get('season_wins'), status=screen.get('status', screen.get('passed')))


def _grade(games, results, checked):
    finals = {r['game_id']: r for r in results}
    _require(len(finals) == len(results), 'Duplicate candidate grading result')
    updated = copy.deepcopy(games)
    for game in updated:
        result = finals.get(game['game_id'])
        if result is None:
            _require(game.get('result') is None, 'Previously graded candidate final is missing')
            continue
        _require(result['home_team'] == game['home'] and result['away_team'] == game['away']
                 and result['season'] == game['season'] and result['week'] == game['week']
                 and result['game_type'] == 'REG' and _utc(result['kickoff']) == _utc(game['kickoff'])
                 and _utc(game['kickoff']) < _utc(result['finalized_at']) <= checked,
                 'Candidate result identity or final clock differs')
        _require(all(type(result[k]) is int and result[k] >= 0 for k in ('home_score', 'away_score')),
                 'Candidate final scores must be nonnegative integers')
        margin = result['home_score'] - result['away_score']
        _require(result['actual_margin'] == margin, 'Candidate final margin differs')
        saved = {k: result[k] for k in ('home_score', 'away_score', 'actual_margin', 'finalized_at')}
        _require(game.get('result') in (None, saved), 'Accepted candidate final changed')
        game['result'] = saved
        game['grade'] = {name: 'NO_PICK' if game[name + '_margin'] == 0 else 'T' if margin == 0
                         else 'W' if (game[name + '_margin'] > 0) == (margin > 0) else 'L'
                         for name in ('candidate', 'control')}
    return updated


def _metrics(games):
    paired = [g for g in games if g.get('result') is not None]
    metrics = dict(paired_games=len(paired), paired_weeks=len({g['week'] for g in paired}),
                   bias_definition='predicted_margin_minus_actual_margin',
                   formal_review='After the 2026 regular season; at least 150 paired games across 12 weeks. Interim results are descriptive.')
    for name in ('candidate', 'control'):
        errors = [g[name + '_margin'] - g['result']['actual_margin'] for g in paired]
        counts = {key: sum(g['grade'][name] == label for g in paired)
                  for key, label in (('wins', 'W'), ('losses', 'L'), ('ties', 'T'), ('no_pick', 'NO_PICK'))}
        metrics[name] = dict(**counts, mae=math.fsum(abs(v) for v in errors) / len(errors) if errors else None,
                            rmse=math.sqrt(math.fsum(v * v for v in errors) / len(errors)) if errors else None,
                            bias=math.fsum(errors) / len(errors) if errors else None)
    metrics['mae_improvement'] = metrics['control']['mae'] - metrics['candidate']['mae'] if paired else None
    return metrics


def refresh_shadow(state, previous, root, checked_at, *, package_path=PACKAGE_DIR, package_manifest_sha256=None):
    """Return detached candidate state; source failure never mutates the primary model."""
    old = (previous or {}).get('penalty_shadow', {})
    pin = package_manifest_sha256 or PACKAGE_MANIFEST_SHA256
    payload = dict(identity=IDENTITY, status='READY', blocked_reason=None, checked_at=checked_at,
                   package_manifest_sha256=old.get('package_manifest_sha256') or pin, source_href=SOURCE_HREF,
                   games=copy.deepcopy(old.get('games', [])), excluded=copy.deepcopy(old.get('excluded', [])),
                   historical=copy.deepcopy(old.get('historical', {})))
    try:
        checked = _utc(checked_at)
        payload['games'] = _grade(payload['games'], state['results'], checked)
        fit, seed, metrics, baseline = _package(package_path, pin)
        _require(not old.get('package_manifest_sha256') or old['package_manifest_sha256'] == pin,
                 'Candidate package changed after prospective issuance')
        payload['historical'] = _historical(metrics)
        history = _penalty_states(state, root, checked, seed)
        rankings = state['rankings']; teams = {r['team']: r for r in rankings['teams']}
        _require(len(teams) == len(rankings['teams']) == 32, 'Candidate ranking team inventory differs')
        issued = {g['game_id'] for g in payload['games']}
        _require(len(issued) == len(payload['games']), 'Duplicate saved candidate game')
        excluded = {r['game_id']: r for r in payload['excluded']}
        from research.pgo_penalty_candidate.candidate import FEATURE
        for week in state['weeks']:
            for game in week['games']:
                key = game['game_id']
                if key in issued:
                    continue
                cutoff = _utc(game['kickoff']) - timedelta(minutes=60)
                if checked >= cutoff or any(r['game_id'] == key for r in state['results']):
                    excluded[key] = dict(game_id=key, reason='Not issued before the real T-60 cutoff')
                    continue
                if game.get('blocked_reason') or game.get('margin') is None:
                    excluded[key] = dict(game_id=key, reason='Primary game is unavailable: ' + str(game.get('blocked_reason')))
                    continue
                try:
                    selected = {team: teams[team] for team in (game['home'], game['away'])}
                    _require(game['season'] == 2026 and game['game_type'] == 'REG'
                             and game['week'] == rankings['completed_week'] + 1,
                             'Candidate game is not in the eligible ranking week')
                    _require(game['source_edition'] == rankings['edition']
                             and _utc(game['inputs_as_of']) == _utc(rankings['inputs_as_of'])
                             and _utc(game['inputs_as_of']) <= _utc(game['issued_at']) <= checked
                             and _utc(rankings['inputs_as_of']) <= _utc(rankings['generated_at']) <= checked,
                             'Candidate game and ranking feature clocks differ')
                    _require(game['expected_qbs'] == {t: r['qb_name'] for t, r in selected.items()}
                             and all(r.get('qb_gsis_id') for r in selected.values()), 'Candidate expected QB identity differs')
                    vector = ch._matchup_features(selected[game['home']]['features'], selected[game['away']]['features'],
                                                  dict(game, neutral=game['location'] == 'Neutral'))
                    control = scoring.score(vector, baseline)
                    _require(math.isclose(control, game['margin'], abs_tol=1e-8, rel_tol=0.), 'Candidate matched-control baseline margin differs')
                    rates = {t: history[t][0] / history[t][1] if history[t][1] > 0 else None for t in selected}
                    vector[FEATURE] = rates[game['home']] - rates[game['away']] if all(v is not None for v in rates.values()) else None
                    candidate = scoring.score(vector, fit)
                    pair = {k: game[k] for k in ('game_id', 'season', 'week', 'game_type', 'kickoff', 'home', 'away', 'location', 'home_rest', 'away_rest')}
                    pair.update(issued_at=checked_at, inputs_as_of=game['inputs_as_of'], source_edition=game['source_edition'],
                                ranking_edition=rankings['edition'], feature_clock=rankings['inputs_as_of'],
                                penalty_history_through=rankings['history_through'], penalty_feature=vector[FEATURE],
                                expected_qbs=copy.deepcopy(game['expected_qbs']), qb_gsis_ids={t: r['qb_gsis_id'] for t, r in selected.items()},
                                package_manifest_sha256=pin, lock_at=cutoff.isoformat(), control_margin=control, candidate_margin=candidate,
                                grade={'control': 'PENDING', 'candidate': 'PENDING'}, result=None)
                    payload['games'].append(pair); issued.add(key); excluded.pop(key, None)
                except (ValueError, KeyError, TypeError, OverflowError) as error:
                    payload.update(status='BLOCKED', blocked_reason=str(error))
                    excluded[key] = dict(game_id=key, reason=str(error))
        payload['excluded'] = list(excluded.values())
    except (ValueError, KeyError, TypeError, OSError, OverflowError, ImportError) as error:
        payload.update(status='BLOCKED', blocked_reason=str(error))
    payload['metrics'] = _metrics(payload['games'])
    return payload


def check_durable_shadow(state, previous, durable):
    """Old pairs never change; newly saved forecasts must beat their real cutoff."""
    old = (previous or {}).get('penalty_shadow', {}).get('games', [])
    current = state.get('penalty_shadow', {}).get('games', [])
    before = {g['game_id']: g for g in old}; after = {g['game_id']: g for g in current}
    _require(len(before) == len(old) and len(after) == len(current), 'Duplicate immutable candidate game')
    _require(set(before) <= set(after), 'An immutable candidate forecast was removed')
    for key, game in after.items():
        if key in before:
            _require({k: v for k, v in game.items() if k not in MUTABLE}
                     == {k: v for k, v in before[key].items() if k not in MUTABLE}, 'An immutable candidate forecast changed')
        else:
            cutoff = _utc(game['kickoff']) - timedelta(minutes=60)
            _require(_utc(game['inputs_as_of']) <= _utc(game['issued_at']) <= _utc(durable) < cutoff
                     and _utc(game['lock_at']) == cutoff, 'Candidate durable-write cutoff deadline crossed')
            _require(all(type(game[k]) in (int, float) and math.isfinite(game[k]) for k in ('control_margin', 'candidate_margin')),
                     'Candidate margins must be finite')
