"""Source-bound defensive production and current depth; no model fitting."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import shutil
import statistics

import pgo_challenger as ch
import pgo_model
import pgo_sources

ROOT = Path(__file__).resolve().parents[2]
STATS = ('def_sacks', 'def_qb_hits', 'def_tackles_for_loss',
         'def_pass_defended', 'def_interceptions')
DEFENSE = frozenset('DE DT DL NT EDGE LB ILB MLB OLB CB DB S FS SS SAF'.split())
DEPTH_GROUPS = frozenset(('defense','def','defensive','base 3-4 d','base 4-3 d'))
GAME_TYPES = frozenset(('REG', 'WC', 'DIV', 'CON', 'SB'))
IDENTITY_MANIFEST = ROOT / 'research/pgo_opening_night_20260909/identity/package-complete-20260909/source-manifest.json'
IDENTITY_SHA = '17f1dec348ad4992dbe32c6e5d54461ef8bd858e7e9d1775e37951385c492f2a'
DEFAULT = ROOT / 'docs/evidence/defensive-depth-2026/september-09'


def utc(value):
    clock = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if clock.tzinfo is None:
        raise ValueError('Source clock must include UTC offset')
    return clock.astimezone(timezone.utc)


def number(value):
    if value is None or str(value).strip() == '':
        return None
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError('Negative or nonfinite defensive count')
    return result


def aliases(row):
    return {ch._normalize_player_name(row.get('full_name'))} | {
        ch._normalize_player_name(f"{row.get(k, '')} {row.get('last_name', '')}")
        for k in ('first_name', 'football_name')}


def build_history(rosters, snaps, player_stats, season, colliding_ids):
    """Strict prior-season joins; unmatched exposure is never an observed zero."""
    groups, stats = defaultdict(list), {}
    for row in rosters:
        if int(row['season']) != season or row['status'].strip() != 'ACT':
            continue
        groups[int(row['week']), pgo_sources.normalize_team(row['team'])].append(row)
    for row in player_stats:
        if int(row['season']) != season or row.get('season_type') not in {'REG', 'POST'}:
            continue
        key = (int(row['week']), pgo_sources.normalize_team(row['team']), row['player_id'])
        if key in stats:
            raise ValueError('Duplicate player statistic identity')
        stats[key] = row
    snap_groups = defaultdict(list)
    for row in snaps:
        if int(row['season']) == season and row['game_type'] in GAME_TYPES:
            snap_groups[int(row['week']), pgo_sources.normalize_team(row['team'])].append(row)
    histories, audit = defaultdict(list), Counter()
    unmatched = []
    for (week, team), rows in sorted(snap_groups.items()):
        rr = groups.get((week, team), [])
        by_id = {ch._roster_player_id(r, colliding_ids): r for r in rr}
        if len(by_id) != len(rr) or '' in by_id:
            raise ValueError('Missing or duplicate historical ACT identity')
        metadata = ch._roster_identity_maps(rr, colliding_ids)
        denominator = max(number(r['defense_snaps']) or 0 for r in rows)
        seen = set()
        for row in rows:
            count = number(row['defense_snaps'])
            if count is None:
                raise ValueError('Missing observed snap count')
            if count == 0:
                continue
            audit['positive_defensive_snap_rows'] += 1
            pid, method = ch._snap_identity(row, metadata)
            if not pid or pid in colliding_ids or ':' in pid:
                audit['unresolved_positive_snap_rows'] += 1
                audit['unresolved_defensive_snaps'] += count
                unmatched.append({'team': team, 'week': week, 'player': row['player'],
                                  'pfr_player_id': row['pfr_player_id'], 'snaps': count,
                                  'reason': method if not pid else 'COLLIDING_GSIS'})
                continue
            if pid in seen:
                raise ValueError('Duplicate resolved defensive snap identity')
            seen.add(pid)
            source = stats.get((week, team, pid))
            if source is not None and (source['season_type'] == 'REG') != (row['game_type'] == 'REG'):
                raise ValueError('Statistic/snap game type differs')
            values = {k: number(source.get(k)) if source else None for k in STATS}
            histories[pid].append({'season': season, 'week': week, 'team': team,
                                   'game_id': row['game_id'], 'game_type': row['game_type'],
                                   'defensive_snaps': count, 'share': count / denominator,
                                   'identity_method': method, 'stats': values})
            audit['resolved_positive_snap_rows'] += 1
            audit['resolved_postseason_rows' if row['game_type'] != 'REG' else 'resolved_regular_rows'] += 1
            audit['identity_' + method] += 1
            if source is None:
                audit['missing_stat_rows'] += 1
                audit['missing_stat_defensive_snaps'] += count
    profiles = {}
    for pid, obs in histories.items():
        snaps_total = sum(r['defensive_snaps'] for r in obs)
        values = {k: sum(r['stats'][k] for r in obs) if all(r['stats'][k] is not None for r in obs) else None for k in STATS}
        profiles[pid] = {
            'defensive_snaps': snaps_total, **values,
            'observed_games': len(obs), 'previous_teams': sorted({r['team'] for r in obs}),
            'matched_stat_defensive_snaps': sum(r['defensive_snaps'] for r in obs if all(v is not None for v in r['stats'].values())),
            'rates_per_100_defensive_snaps': {k: 100*v/snaps_total if v is not None else None for k,v in values.items()},
            'history_status': 'OBSERVED' if all(v is not None for v in values.values()) else 'PARTIAL_STAT_COVERAGE',
            'prior_role_share': statistics.median(r['share'] for r in obs[-4:]),
            'observations': obs,
        }
    return profiles, {**audit, 'unresolved_rows': unmatched}


def current_teams(roster, depth, histories, captured_at, teams=None):
    teams = set(pgo_model.CURRENT_TEAMS if teams is None else teams)
    current, latest, eligible = defaultdict(list), {}, []
    seen = set()
    for row in roster:
        if row['position'].strip().upper() not in DEFENSE or row['status'] not in {'ACT', 'RES', 'DEV', 'EXE'}:
            continue
        team = pgo_sources.normalize_team(row['team'])
        if team not in teams:
            continue
        key = (team, row['gsis_id'])
        if not key[1] or key in seen or row['season'] != '2026' or row['week'] != '1':
            raise ValueError('Missing/duplicate current identity or wrong current period')
        seen.add(key); current[team].append(row)
    cutoff = utc(captured_at)
    for row in depth:
        team = pgo_sources.normalize_team(row['team'])
        clock = utc(row['dt'])
        if team in teams and clock <= cutoff:
            latest[team] = max(latest.get(team, clock), clock)
            eligible.append((team, clock, row))
    depth_by_player = defaultdict(list)
    for team, clock, row in eligible:
        if clock == latest[team] and str(row.get('pos_grp', '')).casefold() in DEPTH_GROUPS:
            depth_by_player[team, row['gsis_id']].append(row)
    result = []
    for team in sorted(teams):
        players = []
        for row in sorted(current[team], key=lambda r: (r['status'] != 'ACT', r['position'], r['full_name'])):
            pid = row['gsis_id']; profile = histories.get(pid)
            rows = depth_by_player[team, pid]
            valid = all(ch._normalize_player_name(r['player_name']) in aliases(row) for r in rows)
            depth_status = 'LISTED' if rows and valid else 'NAME_MISMATCH' if rows else 'UNLISTED'
            ranks = []
            if valid:
                for r in rows:
                    rank = number(r['pos_rank'])
                    if rank is None or rank < 1 or not rank.is_integer():
                        raise ValueError('Invalid depth rank')
                    ranks.append({'position': r['pos_abb'], 'rank': int(rank)})
            record = {'gsis_id': pid, 'name': row['full_name'], 'position': row['position'],
                      'roster_status': row['status'], 'depth_status': depth_status,
                      'depth_rows': sorted(ranks, key=lambda r:(r['position'], r['rank'])),
                      'prior_season': 2025}
            if profile:
                record.update({k:v for k,v in profile.items() if k != 'observations'})
            else:
                record.update({'defensive_snaps': None, **{k:None for k in STATS},
                               'observed_games': 0, 'previous_teams': [], 'matched_stat_defensive_snaps': 0,
                               'rates_per_100_defensive_snaps': {k:None for k in STATS},
                               'prior_role_share': None, 'history_status': 'NO_OBSERVED_PRIOR_DEFENSIVE_SNAPS'})
            players.append(record)
        active = [p for p in players if p['roster_status'] == 'ACT']
        starters = [p for p in active if any(r['rank'] == 1 for r in p['depth_rows'])]
        backups = [p for p in active if p['depth_rows'] and all(r['rank'] > 1 for r in p['depth_rows'])]
        result.append({'team': team, 'coverage_status': 'AVAILABLE' if active and team in latest else 'UNKNOWN',
                       'depth_snapshot_at': latest[team].isoformat() if team in latest else None,
                       'active_defenders': len(active), 'listed_starters': len(starters),
                       'listed_backups': len(backups), 'unlisted_defenders': sum(not p['depth_rows'] for p in active),
                       'backups_with_prior_defensive_snaps': sum(p['defensive_snaps'] is not None for p in backups),
                       'backups_without_prior_defensive_snaps': sum(p['defensive_snaps'] is None for p in backups),
                       'players': players})
    return result


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as f:
        json.dump(value, f, indent=2, sort_keys=True, allow_nan=False); f.write('\n')


def prepare(capture_dir, output):
    capture_dir, output = Path(capture_dir), Path(output)
    if output.exists():
        raise ValueError('Output already exists')
    capture = json.loads((capture_dir/'capture.json').read_bytes())
    source_info = {s['file']:s for s in capture['sources']}
    for name in ('roster.csv.gz', 'depth.csv.gz'):
        entry = source_info[name]; path = capture_dir/name
        if entry['status'] != 200 or not entry['url'].startswith('https://') or digest(path) != entry['sha256'] or path.stat().st_size != entry['bytes']:
            raise ValueError('Current source bytes differ')
        utc(entry['captured_at'])
    if digest(IDENTITY_MANIFEST) != IDENTITY_SHA:
        raise ValueError('Historical identity manifest differs')
    identity = json.loads(IDENTITY_MANIFEST.read_bytes())
    paths = {}
    for entry in identity['sources']:
        if entry['season'] != 2025:
            continue
        path = ROOT/'docs/evidence/nonqb-availability-2026/september-09/raw/history'/f"{entry['name']}-2025-{entry['sha256']}.csv"
        if digest(path) != entry['sha256']:
            raise ValueError('Historical identity file differs')
        paths[entry['name']] = path
    receipt = json.loads((ROOT/'research/pgo_week1_corrected/run-20260908/run-receipt.json').read_bytes())
    pin = receipt['source_inventory']['player_weekly_stats:2025']
    player_path = Path(r'D:\Postgame_Outlet-pgo-model\.cache\pgo_v1')/(pin['sha256']+'.csv.gz')
    if digest(player_path) != pin['sha256']:
        raise ValueError('Pinned player source differs')
    inventory_path = ROOT/'research/pgo_snap_identity_repair_20260909/source-conflict-inventory.json'
    if digest(inventory_path) != 'c3f721962886ba77fd1ff8d45637508d2050fd294c0f3185dff77f3561a66a29':
        raise ValueError('Identity collision inventory differs')
    colliding = set(json.loads(inventory_path.read_bytes())['colliding_gsis'])
    history, audit = build_history(pgo_sources.open_csv(paths['weekly_rosters']),
                                   pgo_sources.open_csv(paths['snap_counts']),
                                   pgo_sources.open_csv(player_path), 2025, colliding)
    rows = current_teams(pgo_sources.open_csv(capture_dir/'roster.csv.gz'),
                         pgo_sources.open_csv(capture_dir/'depth.csv.gz'), history,
                         source_info['depth.csv.gz']['captured_at'])
    sources = []
    for name in ('roster.csv.gz','depth.csv.gz'):
        s = source_info[name]
        sources.append({k:s[k] for k in ('file','url','captured_at','sha256','bytes')})
    for name,path,url in [('weekly_rosters',paths['weekly_rosters'],'https://github.com/nflverse/nflverse-data/releases/download/weekly_rosters/roster_weekly_2025.csv'),
                          ('snap_counts',paths['snap_counts'],'https://github.com/nflverse/nflverse-data/releases/download/snap_counts/snap_counts_2025.csv'),
                          ('player_stats',player_path,'https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_2025.csv.gz')]:
        sources.append({'file':name, 'url':url,'captured_at':None,'sha256':digest(path),'bytes':path.stat().st_size})
    value = {'schema_version':1,'generated_at':datetime.now(timezone.utc).isoformat(),
             'inputs_as_of':capture['captured_at'],'status':'DESCRIPTIVE / NOT IN MODEL',
             'forecast_adjustment':None,'historical_window':'2025 REG + POST',
             'sources':sources,'teams':rows,'history_coverage':audit,
             'limitations':['Production and prior playing time do not measure replacement quality.',
                            'No calibrated availability probability or forecast adjustment is applied.',
                            'Active roster and provider depth do not establish final game-day availability.',
                            'No observed prior defensive snaps means unknown demonstrated production, not bad player quality.',
                            'Historical source publication vintage is not verified; qualified identity audit covered REG and this build also checks POST.',
                            'Unique roster-name fallback is counted; unresolved snap identities remain excluded.',
                            'Current roster includes provider reserve/practice-squad labels that can lag official transactions.']}
    output.mkdir(parents=True)
    write_json(output/'defensive-depth.json',value)
    write_json(output/'history-witness.json',history)
    write_json(output/'manifest.json',{'schema_version':1,'files':{p.name:{'sha256':digest(p),'bytes':p.stat().st_size} for p in output.iterdir() if p.is_file()}})
    return load_verified(output)


def load_verified(directory=DEFAULT, optional=False):
    directory = Path(directory)
    if not directory.exists() and optional:
        return None
    try:
        manifest=json.loads((directory/'manifest.json').read_bytes())
        if set(manifest['files']) != {'defensive-depth.json','history-witness.json'}:
            raise ValueError('Unexpected defensive evidence members')
        for name,pin in manifest['files'].items():
            path=directory/name
            if digest(path)!=pin['sha256'] or path.stat().st_size!=pin['bytes']:
                raise ValueError('Defensive evidence bytes differ')
        value=json.loads((directory/'defensive-depth.json').read_bytes())
        if value['status']!='DESCRIPTIVE / NOT IN MODEL' or value['forecast_adjustment'] is not None:
            raise ValueError('Defensive evidence has unsupported model claim')
        if {t['team'] for t in value['teams']}!=set(pgo_model.CURRENT_TEAMS) or len(value['teams'])!=32:
            raise ValueError('Defensive evidence must cover all32 teams')
        return value
    except (OSError,KeyError,TypeError,json.JSONDecodeError) as error:
        raise ValueError('Invalid defensive evidence package') from error


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();value=prepare(args.capture,args.output)
    print(json.dumps({'teams':len(value['teams']),'history_coverage':{k:v for k,v in value['history_coverage'].items() if k!='unresolved_rows'},'output':str(args.output)}))


if __name__=='__main__':main()
