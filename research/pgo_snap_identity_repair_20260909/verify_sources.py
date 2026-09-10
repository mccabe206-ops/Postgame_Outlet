"""Audit pinned raw snap identity joins only; never walk history or fit a model.

Run: python -B research/pgo_snap_identity_repair_20260909/verify_sources.py --output NEW.json
The output must not exist. No prior audit receipt is overwritten.
"""
import argparse
import csv
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import pgo_challenger as ch
from pgo_sources import CURRENT_TEAMS, normalize_team

CANDIDATE = ROOT / 'research/pgo_corrected_roster_candidate'
TEAMS = sorted(CURRENT_TEAMS)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen_json(directory, name):
    path = directory / name
    entry = json.loads((directory / 'manifest.json').read_bytes())['files'][name]
    assert path.stat().st_size == entry['bytes'] and digest(path) == entry['sha256'], str(path)
    return path, json.loads(path.read_bytes())


def old_normalize(value):
    return ' '.join((value or '').casefold().split())


def old_maps(rows, collisions):
    pfr, names, ambiguous = {}, {}, set()
    for row in rows:
        pid = ch._roster_player_id(row, collisions)
        if not pid:
            continue
        if row['pfr_id'].strip():
            pfr[row['pfr_id'].strip()] = pid
        name = old_normalize(row['full_name'])
        if not name or name in ambiguous:
            continue
        if name in names and names[name] != pid:
            del names[name]
            ambiguous.add(name)
        else:
            names[name] = pid
    return pfr, names, ambiguous


def source_rows(entry):
    path = Path(entry['path'])
    assert path.stat().st_size == entry['bytes'] and digest(path) == entry['sha256'], str(path)
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def audit_season(season, sources, collisions, report, collect_conflicts=False):
    totals = Counter()
    teams = {team: Counter() for team in TEAMS}
    for counter in teams.values():
        for metric in ('newly_matched', 'newly_rejected', 'old_matched', 'old_unmatched',
                       'new_matched', 'new_unmatched', 'old_reassigned', 'conflict',
                       'old_match_conflict'):
            counter[metric + '_rows'] = counter[metric + '_volume'] = 0
        for method in ('pfr', 'name', 'ambiguous', 'unmatched', 'conflict'):
            counter[f'new_resolution_{method}_rows'] = 0
            counter[f'new_resolution_{method}_volume'] = 0
    groups, seen = defaultdict(list), {}
    roster_rows = source_rows(sources[f'weekly_rosters:{season}'])
    snap_rows = source_rows(sources[f'snap_counts:{season}'])
    for row in roster_rows:
        totals['raw_roster_rows'] += 1
        if row['status'].strip() != 'ACT':
            continue
        totals['ACT_roster_rows_before_dedup'] += 1
        team, week = normalize_team(row['team']), int(row['week'])
        row = {**row, 'team': team}
        raw_id = row['gsis_id'].strip() or ('pfr:' + row['pfr_id'].strip() if row['pfr_id'].strip() else '')
        key = (week, team, raw_id)
        if raw_id and key in seen:
            prior = {k: v for k, v in seen[key].items() if k != 'status'}
            current = {k: v for k, v in row.items() if k != 'status'}
            if current != prior:
                raise ValueError(f'Conflicting ACT roster rows: {season}/{key}')
            totals['identical_ACT_roster_rows_collapsed'] += 1
            continue
        if raw_id:
            seen[key] = row
        groups[week, team].append(row)
    maps, legacy, assignments, raw_snaps = {}, {}, defaultdict(set), set()
    examples, rejected = {}, {}
    for row in snap_rows:
        totals['raw_snap_rows'] += 1
        if row['game_type'] != 'REG':
            continue
        team, week = normalize_team(row['team']), int(row['week'])
        key = (week, team)
        detail = dict(season=season, week=week, team=team,
                      snap_name=row['player'], pfr_id=row['pfr_player_id'])
        report['last_examined_snap'] = detail
        if key not in maps:
            maps[key] = ch._roster_identity_maps(groups[key], collisions)
            legacy[key] = old_maps(groups[key], collisions)
            teams[team]['team_weeks'] += 1
            teams[team]['ACT_roster_rows_in_snap_weeks'] += len(groups[key])
            teams[team]['ambiguous_roster_aliases'] += len(maps[key]['ambiguous_names'])
            teams[team]['team_weeks_without_ACT_roster'] += int(not groups[key])
        raw_key = (*key, row['pfr_player_id'].strip())
        if raw_key[-1]:
            if raw_key in raw_snaps:
                raise ValueError(f'Duplicate raw snap PFR identity: {season}/{raw_key}')
            raw_snaps.add(raw_key)
        pfr, names, ambiguous = legacy[key]
        old = pfr.get(row['pfr_player_id'].strip()) or names.get(old_normalize(row['player']))
        try:
            new, method = ch._snap_identity(row, maps[key])
        except ValueError as error:
            if not collect_conflicts or not str(error).startswith('Conflicting snap PFR/name identity:'):
                raise
            # Diagnostic marker only: production still raises for this source row.
            new, method = None, 'conflict'
            named = maps[key]['name_ids'].get(ch._normalize_player_name(row['player']))
            direct = maps[key]['pfr_ids'].get(row['pfr_player_id'].strip())
            report['resolver_conflicts'].append(dict(
                **detail, error=str(error), old_player_id=old,
                named_player_id=named, direct_player_id=direct, snap_row=dict(row),
                named_roster_rows=[dict(r) for r in groups[key]
                                   if ch._roster_player_id(r, collisions) == named],
                direct_roster_rows=[dict(r) for r in groups[key]
                                    if ch._roster_player_id(r, collisions) == direct]))
        if old and new and new != old:
            raise ValueError(f'Old match changed: {detail}; old={old}; new={new}')
        if new:
            if new in assignments[key]:
                raise ValueError(f'Duplicate resolved snap identity: {detail}; player={new}')
            assignments[key].add(new)
        offense, defense = float(row['offense_snaps']), float(row['defense_snaps'])
        assert offense >= 0 and defense >= 0, detail
        volume = offense + defense
        counter = teams[team]
        counter['REG_snap_rows'] += 1
        counter['REG_snap_volume'] += volume
        counter['old_matched_rows' if old else 'old_unmatched_rows'] += 1
        counter['old_matched_volume' if old else 'old_unmatched_volume'] += volume
        old_method = 'pfr' if pfr.get(row['pfr_player_id'].strip()) else (
            'name' if old else 'ambiguous' if old_normalize(row['player']) in ambiguous else 'unmatched')
        counter[f'old_resolution_{old_method}_rows'] += 1
        counter[f'new_resolution_{method}_rows'] += 1
        counter[f'new_resolution_{method}_volume'] += volume
        category = 'conflict' if method == 'conflict' else 'new_matched' if new else 'new_unmatched'
        counter[category + '_rows'] += 1
        counter[category + '_volume'] += volume
        if method == 'conflict' and old:
            counter['old_match_conflict_rows'] += 1
            counter['old_match_conflict_volume'] += volume
        if new and not old:
            counter['newly_matched_rows'] += 1
            counter['newly_matched_volume'] += volume
            exkey = (team, new, row['player'])
            example = examples.setdefault(exkey, dict(team=team, player_id=new,
                snap_name=row['player'], pfr_id=row['pfr_player_id'], weeks=[], volume=0))
            example['weeks'].append(week)
            example['volume'] += volume
        if old and not new and method != 'conflict':
            counter['newly_rejected_rows'] += 1
            counter['newly_rejected_volume'] += volume
            exkey = (team, old, row['player'], row['pfr_player_id'], method)
            example = rejected.setdefault(exkey, dict(team=team, old_player_id=old,
                snap_name=row['player'], pfr_id=row['pfr_player_id'], rejection=method,
                weeks=[], volume=0))
            example['weeks'].append(week)
            example['volume'] += volume
        if season == 2025:
            expected = {
                ('NE', 15): ('00-0036198', 'OnweMi00', 52),
                ('NE', 16): ('00-0036198', 'OnweMi00', 74),
                ('NE', 17): ('00-0036198', 'OnweMi00', 58),
                ('NE', 18): ('00-0036198', 'OnweMi00', 59),
                ('NYG', 13): ('00-0036246', 'RunyJo00', 55),
                ('NYG', 15): ('00-0036246', 'RunyJo00', 68),
                ('NYG', 17): ('00-0036246', 'RunyJo00', 64),
                ('NYG', 18): ('00-0036246', 'RunyJo00', 75),
            }.get((team, week))
            if expected and row['pfr_player_id'] == expected[1]:
                assert old is None and new == expected[0] and offense == expected[2], detail
                report['eight_named_examples'].append({**detail, 'player_id': new, 'offense_snaps': offense})
    assert len(teams) == 32 and all(c['REG_snap_rows'] > 0 for c in teams.values()), season
    for counter in teams.values():
        assert counter['old_matched_volume'] + counter['old_unmatched_volume'] == counter['REG_snap_volume'], ('old volume', season, dict(counter))
        assert counter['new_matched_volume'] + counter['new_unmatched_volume'] + counter['conflict_volume'] == counter['REG_snap_volume'], ('new volume', season, dict(counter))
        totals.update(counter)
    totals['old_resolved_identities_reassigned'] = 0
    totals['duplicate_snap_assignments'] = 0
    totals['teams'] = len(teams)
    totals['newly_matched_players'] = len({(e['team'], e['player_id']) for e in examples.values()})
    totals['newly_rejected_players'] = len({(e['team'], e['old_player_id']) for e in rejected.values()})
    return dict(totals=dict(totals), teams={k: dict(v) for k, v in teams.items()},
                newly_matched_examples=sorted(examples.values(), key=lambda e: (e['team'], e['player_id'])),
                newly_rejected_examples=sorted(rejected.values(), key=lambda e: (e['team'], e['old_player_id'])))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New receipt path; existing files are refused')
    parser.add_argument('--collect-conflicts', action='store_true',
                        help='Inventory resolver PFR/name errors only; any conflict retains STOP status')
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        parser.error(f'Output already exists: {output}')
    receipt_path, receipt = frozen_json(CANDIDATE / 'current-preflight-20260908', 'run-receipt.json')
    context_path, context = frozen_json(CANDIDATE / 'preflight-20260908-revised', 'historical-context.json')
    sources = {k: v for k, v in receipt['sources'].items()
               if k.startswith(('weekly_rosters:', 'snap_counts:'))}
    protected = [receipt_path, context_path, *[Path(v['path']) for v in sources.values()]]
    before = {str(p): digest(p) for p in protected}
    report = dict(status='RUNNING', kind='RAW_IDENTITY_JOIN_ONLY',
                  started_at=datetime.now(timezone.utc).isoformat(),
                  history_walks=0, model_fits=0, source_fetches=0,
                  receipt_sha256=before[str(receipt_path)],
                  historical_context_sha256=before[str(context_path)],
                  audited_code_sha256=digest(ROOT / 'pgo_challenger.py'),
                  audit_script_sha256=digest(Path(__file__)),
                  policy='ACT before exact/status-only roster dedup; REG snaps; same season/week/team only',
                  ambiguity_policy='Reject competing aliases even for a former exact full-name match; quantify old-to-missing transitions; stop on reassignment to a different player',
                  collect_conflicts=args.collect_conflicts, inventory_complete=False,
                  source_qualification='UNDETERMINED', resolver_conflicts=[],
                  colliding_gsis=context['inputs']['colliding_gsis'],
                  eight_named_examples=[], seasons={}, verified_sources=sources)
    try:
        for season in [2025, *range(2013, 2025)]:
            report['seasons'][str(season)] = audit_season(season, sources, report['colliding_gsis'], report, args.collect_conflicts)
            if season == 2025:
                assert len(report['eight_named_examples']) == 8
            print(json.dumps({'season': season, **report['seasons'][str(season)]['totals']}), flush=True)
        report['all_seasons'] = {
            name: sum(season['totals'][name] for season in report['seasons'].values())
            for name in ('REG_snap_rows', 'REG_snap_volume', 'old_matched_rows', 'old_matched_volume',
                         'new_matched_rows', 'new_matched_volume', 'new_unmatched_rows', 'new_unmatched_volume',
                         'newly_matched_rows', 'newly_matched_volume', 'newly_rejected_rows', 'newly_rejected_volume',
                         'old_resolved_identities_reassigned', 'duplicate_snap_assignments',
                         'conflict_rows', 'conflict_volume', 'old_match_conflict_rows', 'old_match_conflict_volume')}
        report['all_seasons']['team_seasons'] = sum(season['totals']['teams'] for season in report['seasons'].values())
        report['inventory_complete'] = True
        report['status'] = 'STOP' if report['resolver_conflicts'] else 'PASS'
        report['source_qualification'] = report['status']
        if report['resolver_conflicts']:
            report['error'] = 'Resolver PFR/name conflicts inventoried; production resolver remains blocked'
    except (AssertionError, ValueError) as error:
        report.update(status='STOP', source_qualification='STOP', error=str(error), stopped_conflicts_or_assertions=1)
    finally:
        after = {str(p): digest(p) for p in protected}
        report['protected_hashes_before'] = before
        report['protected_hashes_after'] = after
        report['protected_hashes_unchanged'] = before == after
        if before != after:
            report.update(status='STOP', error='Protected source or frozen evidence hash changed')
        report['completed_at'] = datetime.now(timezone.utc).isoformat()
        with output.open('x', encoding='utf-8') as handle:
            handle.write(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'status': report['status'], 'error': report.get('error'), 'output': str(output)}))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
