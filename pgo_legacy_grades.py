"""Isolate immutable legacy kickoff conflicts without weakening current grading."""
import copy
import re

import pgo_season as season
from pgo_season import record, require, utc

COUNTS = ('wins', 'losses', 'ties', 'no_pick', 'pending')
POINTER_FIELDS = ('path', 'manifest_sha256', 'checked_at')


def kickoff_conflicts(model, results):
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
    return sorted(set(held))


def _rows(state):
    rows = (state or {}).get('model_records', [])
    require(isinstance(rows, list) and all(isinstance(row, dict) for row in rows), 'Invalid model records')
    indexed = {row['edition']: row for row in rows}
    require(len(indexed) == len(rows), 'Duplicate model record edition')
    return indexed


def _models():
    models = season.legacy_models()
    require(len({model['edition'] for model in models}) == len(models)
            and all(model['edition'] != 'pgo-weekly-2026' for model in models), 'Invalid legacy editions')
    return models


def _pointer(pointer):
    require(isinstance(pointer, dict) and all(key in pointer for key in POINTER_FIELDS), 'Invalid held source pointer')
    require(isinstance(pointer['path'], str)
            and re.fullmatch(r'runs(?:-v2)?/\d{8}T\d{12}Z', pointer['path']) is not None
            and isinstance(pointer['manifest_sha256'], str)
            and re.fullmatch(r'[0-9a-f]{64}', pointer['manifest_sha256']) is not None, 'Invalid held source pointer')
    utc(pointer['checked_at'])
    return {key: pointer[key] for key in POINTER_FIELDS}


def records(state, results, previous, previous_pointer):
    prior_rows = _rows(previous)
    prior_holds = ((previous or {}).get('legacy_grading_check') or {}).get('models', {})
    rows, holds = [], {}
    for model in _models():
        edition = model['edition']; conflicts = kickoff_conflicts(model, results)
        if not conflicts:
            rows.append(dict(name=model['name'], edition=edition, **record(model['games'], results)))
            continue
        reason = 'Legacy kickoff differs from the verified final: ' + ', '.join(conflicts) + '.'
        source = checked = None
        row = prior_rows.get(edition) if previous_pointer is not None else None
        if row is not None:
            prior_hold = prior_holds.get(edition)
            if prior_hold:
                source = copy.deepcopy(prior_hold['record_source'])
                checked = prior_hold['record_checked_at']
            else:
                require({key: row[key] for key in COUNTS} == record(model['games'], previous['results']),
                        'Previous legacy record does not replay')
                source = _pointer(previous_pointer); checked = previous['checked_at']
                require(source['checked_at'] == checked, 'Held record clock differs')
            row = copy.deepcopy(row)
        else:
            row = dict(name=model['name'], edition=edition, **dict.fromkeys(COUNTS))
        rows.append(row)
        holds[edition] = dict(game_ids=conflicts, blocked_reason=reason,
            record_source=source, record_checked_at=checked)
    return rows, dict(status='BLOCKED' if holds else 'READY', checked_at=state['checked_at'],
        blocked_reason='Legacy grading needs review; retained records are historical or unavailable.' if holds else None,
        models=holds)


def validate(state, root, previous_pointer, *, durable=None):
    """Authenticate retention against the preceding state and original source archive."""
    try:
        _validate(state, root, previous_pointer, durable)
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError('Malformed legacy grading component') from error


def _validate(state, root, previous_pointer, durable):
    from pgo_season_rollover import check_preserved, load_archive
    cache = {}
    def archive(pointer):
        pointer = _pointer(pointer)
        key = tuple(pointer[key] for key in POINTER_FIELDS)
        if key not in cache:
            cache[key] = load_archive(root, pointer)
        saved, manifest = cache[key]
        require(saved['checked_at'] == pointer['checked_at'], 'Held record clock differs')
        require(utc(manifest['created_at']) >= utc(saved['checked_at']), 'Archive durable clock precedes check')
        return saved, manifest

    component = state.get('legacy_grading_check')
    require('legacy_grading_check' not in state or isinstance(component, dict), 'Malformed legacy grading component')
    previous = archive(previous_pointer)[0] if previous_pointer is not None and component is not None else None
    if component is None:
        if state.get('results'):
            require(not any(kickoff_conflicts(model, state['results']) for model in _models()),
                    'Legacy grading component omitted for kickoff conflict')
        if previous_pointer is not None:
            previous = load_archive(root, previous_pointer)[0]
            require('legacy_grading_check' not in previous, 'Legacy grading component omitted')
        return  # Historical states predating this optional component remain readable.
    require(isinstance(component, dict)
            and set(component) == {'status', 'checked_at', 'blocked_reason', 'models'}
            and isinstance(component['models'], dict), 'Malformed legacy grading component')
    require(component['checked_at'] == state['checked_at'], 'Legacy grading check clock differs')
    if durable is not None:
        require(utc(durable) >= utc(state['checked_at']), 'Legacy grading durable clock precedes check')
    if previous is not None:
        require(utc(previous['checked_at']) < utc(state['checked_at']), 'Previous legacy record is not historical')
        check_preserved(previous, state, durable)
    rows = _rows(state); models = _models()
    require(set(rows) == {'pgo-weekly-2026', *(model['edition'] for model in models)}, 'Unknown or absent model record edition')
    holds = component['models']
    for edition, row in rows.items():
        unavailable = edition in holds and holds[edition].get('record_source') is None
        require(all(row[key] is None if unavailable else type(row[key]) is int and row[key] >= 0 for key in COUNTS),
                'Invalid model record counts')
    require({key:rows['pgo-weekly-2026'][key] for key in COUNTS}
            == record([g for w in state['weeks'] for g in w['games']], state['results']), 'Weekly record differs')
    expected_rows, expected_check = records(state, state['results'], previous, previous_pointer)
    require(component == expected_check, 'Legacy grading hold differs from previous verified state')
    for row in expected_rows:
        require(rows[row['edition']] == row, 'Held legacy record differs from previous verified row')
    for model in models:
        edition = model['edition']; hold = component['models'].get(edition)
        if hold is None:
            continue
        retained = rows[edition]
        if hold['record_source'] is None:
            require(hold['record_checked_at'] is None and all(retained[key] is None for key in COUNTS),
                    'Unavailable legacy record claims verified counts')
            continue
        source, _ = archive(hold['record_source'])
        require(source['checked_at'] == hold['record_checked_at'], 'Held record clock differs')
        require(utc(hold['record_checked_at']) < utc(state['checked_at'])
                and previous is not None and utc(hold['record_checked_at']) <= utc(previous['checked_at']),
                'Held record is not historical')
        require(edition not in ((source.get('legacy_grading_check') or {}).get('models', {})),
                'Held record source is itself held')
        require(retained == _rows(source)[edition], 'Held legacy record differs from verified archive')
        require(all(type(retained[key]) is int and retained[key] >= 0 for key in COUNTS)
                and {key:retained[key] for key in COUNTS} == record(model['games'], source['results']),
                'Held legacy record does not replay')
