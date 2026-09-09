"""Prepare evidenced prior-role proxies; does not fit or change a forecast."""
import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import pgo_challenger as ch
import pgo_sources
from research.pgo_opening_night_20260909.identity import source_package

SOURCE_MANIFEST = ROOT / 'research/pgo_opening_night_20260909/identity/package-complete-20260909/source-manifest.json'
SOURCE_SHA = '17f1dec348ad4992dbe32c6e5d54461ef8bd858e7e9d1775e37951385c492f2a'


def role_observations(rosters, snaps, colliding_ids):
    groups, observations = defaultdict(list), defaultdict(list)
    for row in rosters:
        if row['status'].strip() == 'ACT' and int(row['season']) == 2025:
            groups[int(row['week']), pgo_sources.normalize_team(row['team'])].append(row)
    snap_groups = defaultdict(list)
    for row in snaps:
        if row['game_type'] == 'REG' and int(row['season']) == 2025:
            snap_groups[int(row['week']), pgo_sources.normalize_team(row['team'])].append(row)
    for key, rows in sorted(snap_groups.items()):
        roster = groups.get(key, [])
        metadata = ch._roster_identity_maps(roster, colliding_ids)
        by_id = {ch._roster_player_id(r, colliding_ids): r for r in roster}
        if len(by_id) != len(roster):
            raise ValueError('Duplicate historical ACT identity')
        totals = {unit: max(float(r[unit + '_snaps']) for r in rows) for unit in ('offense', 'defense')}
        if any(not math.isfinite(v) or v < 0 for v in totals.values()):
            raise ValueError('Invalid unit snap denominator')
        seen = set()
        for row in rows:
            player_id, method = ch._snap_identity(row, metadata)
            if not player_id:
                continue
            if player_id in seen:
                raise ValueError('Duplicate historical snap identity')
            seen.add(player_id)
            for unit, denominator in totals.items():
                value = float(row[unit + '_snaps'])
                if not math.isfinite(value) or value < 0 or value > denominator:
                    raise ValueError('Invalid observed snap count')
                if value > 0:
                    observations[player_id, unit].append({
                        'season': 2025, 'week': key[0], 'team': key[1],
                        'game_id': row['game_id'], 'share': value / denominator,
                        'unit_snaps': value, 'team_unit_denominator': denominator,
                        'identity_method': method, 'snap_row': row,
                        'roster_row': by_id[player_id],
                    })
    return observations


def prepare(evidence, roster_path, depth_path=None):
    paths = source_package.load_sources(SOURCE_MANIFEST, SOURCE_SHA)
    inventory_raw = (ROOT / 'research/pgo_snap_identity_repair_20260909/source-conflict-inventory.json').read_bytes()
    if hashlib.sha256(inventory_raw).hexdigest() != 'c3f721962886ba77fd1ff8d45637508d2050fd294c0f3185dff77f3561a66a29':
        raise ValueError('Historical collision inventory changed')
    inventory = json.loads(inventory_raw)
    colliding = inventory['colliding_gsis']
    histories = role_observations(pgo_sources.open_csv(paths['weekly_rosters', 2025]),
                                 pgo_sources.open_csv(paths['snap_counts', 2025]), colliding)
    fresh = defaultdict(list)
    for row in pgo_sources.open_csv(roster_path):
        if row['season'] == '2026' and row['week'] == '1':
            fresh[pgo_sources.normalize_team(row['team']), row['gsis_id']].append(row)
    depth = defaultdict(list)
    if depth_path is not None:
        from datetime import datetime
        stamp = datetime.fromisoformat(evidence['depth_as_of'])
        for row in pgo_sources.open_csv(depth_path):
            if datetime.fromisoformat(row['dt'].replace('Z', '+00:00')) == stamp:
                depth[pgo_sources.normalize_team(row['team']), row['gsis_id']].append(row)
    result = []
    for player in evidence['players']:
        key = player['team'], player['gsis_id']
        rows = fresh[key]
        if len(rows) != 1:
            raise ValueError(f'Current roster identity missing or duplicate: {key}')
        row = rows[0]
        aliases = {ch._normalize_player_name(row.get('full_name'))}
        aliases |= {ch._normalize_player_name(f"{row.get(given, '')} {row.get('last_name', '')}")
                    for given in ('first_name', 'football_name')}
        if ch._normalize_player_name(player['name']) not in aliases:
            raise ValueError(f'Current roster name disagrees: {key}')
        position = row['position'].strip().upper()
        group = ch.ROLE_POSITION_GROUPS.get(position)
        unit = 'defense' if group == 'defense' else 'offense'
        player_id = ch._roster_player_id(row, colliding)
        history = histories.get((player_id, unit), [])
        selected = history[-4:]
        share = statistics.median(r['share'] for r in selected) if selected else None
        reason = None if selected else 'No positive observed 2025 unit role; expected playing time is unknown.'
        if group is None or position == 'QB':
            share = None
            reason = 'Quarterback or unsupported non-QB unit; no adjustment.'
        source_note = 'Median of last four positive observed 2025 regular-season unit snap shares; historical playing-role proxy, not a current depth-chart or replacement-quality estimate.'
        ranks = sorted({f"{r['pos_abb']} {r['pos_rank']}" for r in depth[key]})
        if ranks:
            source_note += ' Fresh depth listing: ' + ', '.join(ranks) + '.'
            if all(int(r['pos_rank']) > 1 for r in depth[key] if r['pos_rank']):
                source_note += ' Current backup listing: prior usage can overstate current lost playing time.'
        else:
            source_note += ' No current role is established by a depth listing.'
        result.append({
            'team': key[0], 'gsis_id': key[1], 'position': position,
            'snap_share': share, 'sample_count': len(selected),
            'last_observed': f"2025 Week {selected[-1]['week']}" if selected else None,
            'previous_team': selected[-1]['team'] if selected else None,
            'source_note': source_note, 'current_depth_rows': depth[key],
            'reason': reason, 'observations': selected, 'current_roster_row': row,
            'historical_identity_manifest_sha256': SOURCE_SHA,
            'source_hashes': {name: hashlib.sha256(paths[name, 2025].read_bytes()).hexdigest()
                              for name in ('weekly_rosters', 'snap_counts')},
            'current_roster_sha256': hashlib.sha256(Path(roster_path).read_bytes()).hexdigest(),
        })
    if len({(r['team'], r['gsis_id']) for r in result}) != len(result):
        raise ValueError('Duplicate current injury role')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--roster', type=Path, required=True)
    parser.add_argument('--depth', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output already exists')
    result = prepare(json.loads(args.evidence.read_bytes()), args.roster, args.depth)
    with args.output.open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(result, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write('\n')
    print(json.dumps([{'team': r['team'], 'name': r['current_roster_row']['full_name'],
                       'share': r['snap_share'], 'samples': r['sample_count'], 'reason': r['reason']}
                      for r in result], indent=2))


if __name__ == '__main__':
    main()
