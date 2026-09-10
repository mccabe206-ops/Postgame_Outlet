"""Bounded, in-memory source-correction diagnostic; never adopt or rewrite sources."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import verify_sources as audit

PROVIDER_SHA256 = 'a48acc5cd40d598a41b1a247ff6e1dbeb2af03c3ec647d4e6a59b953b0e86799'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def row_key(row):
    return (int(row['season']), int(row['week']), audit.normalize_team(row['team']),
            row['gsis_id'], row['status'])


def row_hash(row):
    return hashlib.sha256(json.dumps(row, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def apply_rows(rows, corrections, source_sha256):
    indexed = {}
    for correction in corrections:
        key = row_key(correction)
        require(key not in indexed, f'Duplicate correction: {key}')
        require(correction['source_sha256'] == source_sha256, f'Correction source hash: {key}')
        require(row_key(correction['original_row']) == key, f'Correction row key: {key}')
        require(row_hash(correction['original_row']) == correction['original_row_sha256'],
                f'Correction original row hash: {key}')
        require(correction['status'] == 'ACT' and
                correction['original_row']['pfr_id'] == correction['old_pfr_id'] and
                correction['old_pfr_id'] != correction['verified_pfr_id'], f'Correction old value: {key}')
        indexed[key] = correction
    result, seen = [], set()
    for row in rows:
        key = row_key(row)
        correction = indexed.get(key)
        if correction:
            require(key not in seen, f'Duplicate source roster key: {key}')
            require(row == correction['original_row'], f'Unexpected full source row: {key}')
            seen.add(key)
            result.append({**row, 'pfr_id': correction['verified_pfr_id']})
        else:
            result.append(dict(row))
    require(seen == set(indexed), f'Missing correction rows: {sorted(set(indexed) - seen)}')
    return result


def load_inputs():
    inventory_path = HERE.parent / 'source-conflict-inventory.json'
    provider_path = HERE / 'provider-evidence.json'
    preservation_path = HERE / 'preservation-before.json'
    ledger_path = HERE / 'corrections.json'
    inventory, evidence, preservation, ledger = [json.loads(p.read_bytes()) for p in
                                               (inventory_path, provider_path, preservation_path, ledger_path)]
    require(audit.digest(provider_path) == PROVIDER_SHA256 == ledger['provider_evidence_sha256'],
            'Provider evidence SHA-256 differs from reviewed seven-identity evidence')
    require(audit.digest(inventory_path) == ledger['inventory_sha256'] ==
            preservation['files'][str(inventory_path)], 'Original inventory SHA-256 changed')
    require(audit.digest(preservation_path) == ledger['preservation_before_sha256'],
            'Preservation manifest SHA-256 changed')
    require(inventory['inventory_complete'] and inventory['source_qualification'] == 'STOP',
            'Expected complete, unadopted STOP inventory')
    require(audit.digest(audit.ROOT / 'pgo_challenger.py') == inventory['audited_code_sha256'],
            'Final production resolver hash changed')
    require(audit.digest(Path(audit.__file__)) == inventory['audit_script_sha256'],
            'Original audit script hash changed')
    selected = evidence['players_crosswalk']['selected_rows']
    identities = {row['gsis_id']: row for row in selected}
    require(len(selected) == len(identities) == 7, 'Provider evidence must have seven unique GSIS rows')
    require(evidence['not_model_source_package'] is True and
            evidence['players_crosswalk']['response_sha256'] and
            evidence['players_crosswalk']['url'], 'Incomplete provider provenance')
    corrections = ledger['corrections']
    require(len(corrections) == len(inventory['resolver_conflicts']) == 115,
            'Expected exactly 115 corrections and original conflicts')
    indexed = {}
    for correction in corrections:
        key = row_key(correction)
        require(key not in indexed, f'Duplicate correction: {key}')
        indexed[key] = correction
    expected_keys, conflicts = set(), {}
    for conflict in inventory['resolver_conflicts']:
        require(len(conflict['named_roster_rows']) == 1 and not conflict['direct_roster_rows'],
                'Expected one named roster row and no direct roster owner')
        original = conflict['named_roster_rows'][0]
        key = row_key(original)
        require(key not in expected_keys, f'Duplicate inventory roster key: {key}')
        expected_keys.add(key)
        require(key in indexed, f'Missing inventory correction: {key}')
        correction = indexed[key]
        provider = identities.get(original['gsis_id'])
        require(provider is not None, f'Missing provider GSIS evidence: {key}')
        require(provider['gsis_id'] == conflict['named_player_id'] and
                provider['pfr_id'] == conflict['pfr_id'] == correction['verified_pfr_id'] and
                provider['birth_date'] == original['birth_date'], f'Provider ID/birthdate mismatch: {key}')
        roster_colleges = {v.strip() for v in original['college'].split(';') if v.strip()}
        provider_colleges = {v.strip() for v in provider['college_name'].split(';') if v.strip()}
        require(roster_colleges and roster_colleges <= provider_colleges,
                f'Provider college mismatch: {key}')
        source = inventory['verified_sources'][f'weekly_rosters:{key[0]}']
        raw_original = correction['original_row']
        require(correction['source_sha256'] == source['sha256'] and
                {**raw_original, 'team': audit.normalize_team(raw_original['team'])} == original and
                correction['original_row_sha256'] == row_hash(raw_original) and
                correction['old_pfr_id'] == original['pfr_id'] and
                correction['provider_row'] == provider, f'Ledger differs from pinned evidence: {key}')
        snap_key = (conflict['season'], conflict['week'], conflict['team'], conflict['pfr_id'])
        require(snap_key not in conflicts, f'Duplicate conflict snap: {snap_key}')
        conflicts[snap_key] = conflict
    require(set(indexed) == expected_keys, 'Unexpected correction outside original inventory')
    require({key[3] for key in expected_keys} == set(identities), 'Unexpected provider identity scope')
    protected = dict(preservation['files'])
    for path in (inventory_path, provider_path, preservation_path, ledger_path, Path(__file__)):
        protected[str(path)] = audit.digest(path)
    return inventory, corrections, conflicts, protected


def legacy_identity(row, maps):
    pfr, names, ambiguous = maps
    name = audit.old_normalize(row['player'])
    direct = pfr.get(row['pfr_player_id'].strip())
    player = direct or names.get(name)
    return player, 'pfr' if direct else 'name' if player else 'ambiguous' if name in ambiguous else 'unmatched'


def run_diagnostic(inventory, corrections, conflicts, report):
    sources, collisions = inventory['verified_sources'], inventory['colliding_gsis']
    original_reader, strict_resolver = audit.source_rows, audit.ch._snap_identity
    original_maps, original_legacy, corrected_legacy = {}, {}, {}
    correction_groups = defaultdict(list)
    for correction in corrections:
        correction_groups[correction['season']].append(correction)
    roster_sources = {entry['path']: int(name.split(':')[1]) for name, entry in sources.items()
                      if name.startswith('weekly_rosters:')}
    seen_conflicts, seen_other, applied_rows = set(), 0, 0
    team_deltas = defaultdict(Counter)
    correction_keys = {row_key(c) for c in corrections}
    disputed_pairs = {(c['gsis_id'], c['old_pfr_id']) for c in corrections}
    outside_scope = Counter()

    def corrected_reader(entry):
        nonlocal applied_rows
        rows = original_reader(entry)
        if entry['path'] not in roster_sources:
            return rows
        season = roster_sources[entry['path']]
        corrected = apply_rows(rows, correction_groups[season], entry['sha256'])
        applied_rows += sum(a != b for a, b in zip(rows, corrected))
        raw_groups, corrected_groups = defaultdict(list), defaultdict(list)
        for raw, changed in zip(rows, corrected):
            if (raw['gsis_id'], raw['pfr_id']) in disputed_pairs and row_key(raw) not in correction_keys:
                outside_scope[season, raw['gsis_id'], raw['pfr_id'], raw['status']] += 1
            if raw['status'].strip() == 'ACT':
                key = (season, int(raw['week']), audit.normalize_team(raw['team']))
                raw_groups[key].append(raw)
                corrected_groups[key].append(changed)
        for key, group in raw_groups.items():
            original_maps[key] = audit.ch._roster_identity_maps(group, collisions)
            original_legacy[key] = audit.old_maps(group, collisions)
            corrected_legacy[key] = audit.old_maps(corrected_groups[key], collisions)
        return corrected

    def checked_resolver(row, metadata):
        nonlocal seen_other
        key = (int(row['season']), int(row['week']), audit.normalize_team(row['team']))
        snap_key = (*key, row['pfr_player_id'].strip())
        result = strict_resolver(row, metadata)  # No exception suppression or relaxed resolver.
        empty = audit.ch._roster_identity_maps([], collisions)
        old_before = legacy_identity(row, original_legacy.get(key, ({}, {}, set())))
        old_after = legacy_identity(row, corrected_legacy.get(key, ({}, {}, set())))
        conflict = conflicts.get(snap_key)
        if not conflict:
            require(result == strict_resolver(row, original_maps.get(key, empty)),
                    f'Unlisted strict resolver result changed: {snap_key}')
            require(old_before == old_after, f'Unlisted legacy resolver result changed: {snap_key}')
            seen_other += 1
            return result
        require(snap_key not in seen_conflicts and row == conflict['snap_row'],
                f'Duplicate or changed former-conflict snap: {snap_key}')
        require(result == (conflict['named_player_id'], 'pfr'), f'Incorrect corrected GSIS: {snap_key}')
        require(old_before[0] == conflict['old_player_id'] and old_after[0] == result[0],
                f'Unexpected legacy assignment for correction: {snap_key}')
        seen_conflicts.add(snap_key)
        volume = float(row['offense_snaps']) + float(row['defense_snaps'])
        delta = team_deltas[key[0], key[2]]
        for unit, value in [('rows', 1), ('volume', volume)]:
            delta['conflict_' + unit] -= value
            delta['new_resolution_conflict_' + unit] -= value
            delta['new_matched_' + unit] += value
            delta['new_resolution_pfr_' + unit] += value
            if old_before[0]:
                delta['old_match_conflict_' + unit] -= value
            else:
                delta['old_matched_' + unit] += value
                delta['old_unmatched_' + unit] -= value
        delta[f'old_resolution_{old_before[1]}_rows'] -= 1
        delta[f'old_resolution_{old_after[1]}_rows'] += 1
        report['resolved_conflicts'].append(dict(season=key[0], week=key[1], team=key[2],
             pfr_id=snap_key[-1], expected_gsis_id=result[0], player_id=result[0],
             offense_snaps=float(row['offense_snaps']), defense_snaps=float(row['defense_snaps'])))
        return result

    with patch.object(audit, 'source_rows', corrected_reader), patch.object(audit.ch, '_snap_identity', checked_resolver):
        for season in [2025, *range(2013, 2025)]:
            actual = audit.audit_season(season, sources, collisions, report)
            baseline = inventory['seasons'][str(season)]
            for team in audit.TEAMS:
                delta = team_deltas[season, team]
                before, after = baseline['teams'][team], actual['teams'][team]
                for name in set(before) | set(after) | set(delta):
                    require(after.get(name, 0) == before.get(name, 0) + delta[name],
                            f'Unexpected team metric change: {season}/{team}/{name}')
            season_delta = Counter()
            for team in audit.TEAMS:
                season_delta.update(team_deltas[season, team])
            for name in set(baseline['totals']) | set(actual['totals']) | set(season_delta):
                require(actual['totals'].get(name, 0) == baseline['totals'].get(name, 0) + season_delta[name],
                        f'Unexpected season metric change: {season}/{name}')
            for field in ('newly_matched_examples', 'newly_rejected_examples'):
                require(actual[field] == baseline[field], f'Unexpected named example change: {season}/{field}')
            report['seasons'][str(season)] = actual
            print(json.dumps({'season': season, 'matched_rows': actual['totals']['new_matched_rows'],
                              'conflict_rows': actual['totals']['conflict_rows']}), file=sys.stderr, flush=True)
    require(seen_conflicts == set(conflicts) and applied_rows == 115, 'Missing or excess applied/resolved corrections')
    require(seen_other == inventory['all_seasons']['REG_snap_rows'] - len(conflicts),
            'Unchanged row comparison denominator differs')
    require(report['eight_named_examples'] == inventory['eight_named_examples'], 'Eight Onwenu/Runyan examples changed')
    totals = {name: sum(s['totals'].get(name, 0) for s in report['seasons'].values())
              for name in inventory['all_seasons'] if name != 'team_seasons'}
    totals['team_seasons'] = sum(s['totals']['teams'] for s in report['seasons'].values())
    require(totals['REG_snap_rows'] == 310475 and totals['team_seasons'] == 416, 'Full source denominator differs')
    require(totals['new_matched_rows'] == inventory['all_seasons']['new_matched_rows'] + len(conflicts) and
            totals['new_matched_volume'] == inventory['all_seasons']['new_matched_volume'] +
            sum(float(c['snap_row']['offense_snaps']) + float(c['snap_row']['defense_snaps']) for c in conflicts.values()),
            'Corrected match count or volume differs from derived original inventory delta')
    require(totals['conflict_rows'] == totals['duplicate_snap_assignments'] ==
            totals['old_resolved_identities_reassigned'] == 0, 'Residual conflict, duplicate, or reassignment')
    require(totals['newly_rejected_rows'] == 16 and totals['newly_rejected_volume'] == 109,
            'CIN ambiguous-row rejection changed')
    report.update(all_seasons=totals, corrected_roster_rows=applied_rows,
                  former_conflicts_resolved=len(seen_conflicts), unchanged_strict_and_legacy_rows=seen_other,
                  unexpected_reassignments=0, eight_named_examples_preserved=True,
                  CIN_ambiguous_rows_preserved=16, per_team_and_season_metrics_verified=True)
    report['uncorrected_disputed_roster_rows_outside_115'] = [
        dict(season=season, gsis_id=gsis, pfr_id=pfr, status=status, rows=count)
        for (season, gsis, pfr, status), count in sorted(outside_scope.items())]
    report['uncorrected_disputed_roster_row_counts'] = dict(
        ACT=sum(count for (_, _, _, status), count in outside_scope.items() if status == 'ACT'),
        other_statuses=sum(count for (_, _, _, status), count in outside_scope.items() if status != 'ACT'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--output', type=Path, help='New nonexistent receipt inside this diagnostic directory')
    mode.add_argument('--stdout', action='store_true', help='Read-only replay; emit receipt without creating files')
    mode.add_argument('--self-check', action='store_true', help='Exercise exact-row guards only')
    args = parser.parse_args()
    require(not sys.flags.optimize, 'Run without -O: original audit assertions must remain enabled')
    if args.self_check:
        print(json.dumps(self_check()))
        return 0
    output = args.output.resolve() if args.output else None
    if output and (output.parent != HERE or output.exists()):
        parser.error('Output must be a new nonexistent path inside the source-resolution directory')
    report = dict(status='STOP', kind='BOUNDED_IN_MEMORY_SOURCE_CORRECTION_DIAGNOSTIC',
                  original_source_qualification='STOP', source_adoption='UNADOPTED', model_status='EXPERIMENTAL / HOLD',
                  policy='Only 115 exact ACT roster rows: replace PFR in copied dictionaries; strict final audit, no conflict collection',
                  source_fetches=0, source_writes=0, history_walks=0, model_fits=0,
                  started_at=datetime.now(timezone.utc).isoformat(), resolved_conflicts=[], resolver_conflicts=[],
                  eight_named_examples=[], seasons={})
    protected = {}
    try:
        inventory, corrections, conflicts, protected = load_inputs()
        observed_before = {path: audit.digest(Path(path)) for path in protected}
        require(observed_before == protected, 'Protected pre-existing file differs from preservation-before manifest')
        report['row_guard_self_check'] = self_check()
        report['input_pins'] = dict(inventory_sha256=audit.digest(HERE.parent / 'source-conflict-inventory.json'),
                                  provider_evidence_sha256=PROVIDER_SHA256,
                                  corrections_sha256=audit.digest(HERE / 'corrections.json'),
                                  verifier_sha256=audit.digest(Path(__file__)),
                                  audited_code_sha256=inventory['audited_code_sha256'],
                                  reused_audit_sha256=inventory['audit_script_sha256'])
        run_diagnostic(inventory, corrections, conflicts, report)
        report.update(status='PASS', diagnostic_complete=True)
    except (AssertionError, ValueError, KeyError, OSError, TypeError) as error:
        report.update(status='STOP', diagnostic_complete=False, error=f'{type(error).__name__}: {error}')
    finally:
        if protected:
            after = {path: audit.digest(Path(path)) if Path(path).is_file() else None for path in protected}
            report.update(protected_hashes_before=protected, protected_hashes_after=after,
                          protected_hashes_unchanged=protected == after, protected_file_count=len(protected))
            if protected != after:
                report.update(status='STOP', diagnostic_complete=False, error='Protected file changed or missing')
        report['completed_at'] = datetime.now(timezone.utc).isoformat()
        encoded = json.dumps(report, indent=2, sort_keys=True) + '\n'
        if output:
            with output.open('x', encoding='utf-8') as handle:
                handle.write(encoded)
            print(json.dumps({'status': report['status'], 'error': report.get('error'), 'output': str(output)}))
        else:
            print(encoded, end='')
    return 0 if report['status'] == 'PASS' else 1


def self_check():
    row = dict(season='2025', week='1', team='NO', gsis_id='example', status='ACT',
               pfr_id='old', full_name='Example Player')
    correction = dict(season=2025, week=1, team='NO', gsis_id='example', status='ACT',
                      original_row=row, original_row_sha256=row_hash(row),
                      old_pfr_id='old', verified_pfr_id='new', source_sha256='source')
    result = apply_rows([row], [correction], 'source')
    assert result == [{**row, 'pfr_id': 'new'}] and row['pfr_id'] == 'old'
    cases = [([row, row], [correction], 'source'), ([], [correction], 'source'),
             ([row], [correction, correction], 'source'),
             ([{**row, 'full_name': 'Unexpected'}], [correction], 'source'),
             ([{**row, 'pfr_id': 'unexpected'}], [correction], 'source'),
             ([row], [correction], 'changed-source'),
             ([{**row, 'status': 'INA'}], [correction], 'source'),
             ([row], [{**correction, 'original_row_sha256': 'wrong'}], 'source')]
    for args in cases:
        try:
            apply_rows(*args)
        except ValueError:
            continue
        raise AssertionError('Row guard accepted unexpected input')
    assert apply_rows([row], [], 'source') == [row]
    return {'status': 'PASS', 'positive_cases': 2, 'negative_cases': len(cases)}


if __name__ == '__main__':
    raise SystemExit(main())
