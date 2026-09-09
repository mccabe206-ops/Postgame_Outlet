"""Qualify one fresh, byte-pinned Week 1 capture for the new edition."""
from collections import Counter
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import html
import json
from pathlib import Path
import re
import unicodedata

import generate_site
import pgo_forecast_corrected as base
import pgo_model
import pgo_prospective
import pgo_sources
from research.pgo_week1_corrected.qualify_sources import official_games

TEAMS = set(pgo_model.CURRENT_TEAMS)
CHARTER = Path(__file__).with_name('charter.md')


def name_key(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', value).casefold() if c.isalnum())


def injury_tables(raw):
    """Read the NFL's labeled five-column injury tables, preserving empty cells."""
    result = {}
    clean = lambda s: ' '.join(html.unescape(re.sub(r'<[^>]*>', ' ', s)).split())
    pattern = r'd3-o-section-sub-title[^>]*>\s*<span>(.*?)</span>.*?<table\b[^>]*>(.*?)</table>'
    for label, table in re.findall(pattern, raw, re.S):
        label = clean(label)
        if label in result:
            raise ValueError('Duplicate official injury team')
        headers = [clean(s) for s in re.findall(r'<th\b[^>]*>(.*?)</th>', table, re.S)]
        if headers != ['Player', 'Position', 'Injuries', 'Practice Status', 'Game Status']:
            raise ValueError('Official injury table schema changed')
        rows = []
        for tr in re.findall(r'<tr\b[^>]*>(.*?)</tr>', table, re.S):
            values = [clean(s) for s in re.findall(r'<td\b[^>]*>(.*?)</td>', tr, re.S)]
            if values:
                if len(values) != 5 or not values[0] or values[4] not in ('', 'Out', 'Doubtful', 'Questionable'):
                    raise ValueError('Invalid official injury row')
                rows.append(dict(zip(('player_name', 'position', 'injury', 'practice_status', 'game_status'), values)))
        result[label] = rows
    if not result:
        raise ValueError('No official injury tables found')
    return result


def qualify(directory):
    directory = Path(directory)
    capture = base._read(directory / 'capture.json')
    sources = {s['file']: s for s in capture['sources']}
    if len(sources) != len(capture['sources']) or len(sources) != 13:
        raise ValueError('Fresh capture must have 13 distinct sources')
    for name, s in sources.items():
        if Path(name).name != name or (directory / name).is_symlink():
            raise ValueError('Invalid source member')
        raw = (directory / name).read_bytes()
        if len(raw) != s['bytes'] or base._hash(raw) != s['sha256'] or s['status'] != 200:
            raise ValueError('Fresh capture hash, size or status differs')
        if not s['url'].startswith('https://'):
            raise ValueError('Source requires HTTPS')
        if not base.current._utc(s['started_at']) <= base.current._utc(s['captured_at']) <= base.current._utc(capture['captured_at']):
            raise ValueError('Capture timestamps are out of order')
        if s.get('last_modified') and parsedate_to_datetime(s['last_modified']) > base.current._utc(s['captured_at']):
            raise ValueError('Source modification timestamp is in the future')
    for tag, filename, asset_name in (
            ('rosters', 'roster.csv.gz', 'roster_2026.csv.gz'),
            ('depth_charts', 'depth.csv.gz', 'depth_charts_2026.csv.gz'),
            ('schedules', 'schedule.csv.gz', 'games.csv.gz')):
        release = base._read(directory / (tag + '-release.json'))
        if release['tag_name'] != tag or release['draft'] or release['prerelease']:
            raise ValueError('Source release identity differs')
        for asset, member in ((asset_name, filename), ('timestamp.json', tag + '-timestamp.json')):
            matches = [a for a in release['assets'] if a['name'] == asset]
            if len(matches) != 1 or matches[0]['digest'] != 'sha256:' + sources[member]['sha256'] or matches[0]['size'] != sources[member]['bytes']:
                raise ValueError('Provider asset digest differs')
    roster = list(pgo_sources.open_csv(directory / 'roster.csv.gz'))
    indexed, unresolved_roster = {}, []
    for row in roster:
        if (row['season'], row['week'], row['game_type']) != ('2026', '1', 'REG'):
            raise ValueError('Current roster period differs')
        team = pgo_sources.normalize_team(row['team'])
        key = (team, row['gsis_id'])
        if not row['gsis_id'] and row['status'] != 'ACT':
            unresolved_roster.append({k: row[k] for k in ('team', 'full_name', 'status')})
            continue
        if not row['gsis_id'] or key in indexed:
            raise ValueError('Missing or duplicate current roster identity')
        indexed[key] = row
    if {t for t, _ in indexed} != TEAMS:
        raise ValueError('Current roster does not cover all 32 teams')
    depth = list(pgo_sources.open_csv(directory / 'depth.csv.gz'))
    depth_clock = base.current._utc(sources['depth.csv.gz']['captured_at'])
    eligible = [r for r in depth if base.current._utc(r['dt']) <= depth_clock]
    latest = max(base.current._utc(r['dt']) for r in eligible)
    current = [r for r in eligible if base.current._utc(r['dt']) == latest]
    if {pgo_sources.normalize_team(r['team']) for r in current} != TEAMS:
        raise ValueError('Latest coherent depth does not cover 32 teams')
    selected = {}
    for d in current:
        if d['pos_abb'] != 'QB' or d['pos_rank'] != '1':
            continue
        team = pgo_sources.normalize_team(d['team'])
        row = indexed.get((team, d['gsis_id']))
        if team in selected or not row or row['status'] != 'ACT' or row['position'] != 'QB' or row['espn_id'] != d['espn_id']:
            raise ValueError('Expected QB identity or ACT eligibility differs')
        selected[team] = row
    if set(selected) != TEAMS or len({r['gsis_id'] for r in selected.values()}) != 32:
        raise ValueError('Expected QBs must uniquely cover 32 teams')
    prior = base.load_snapshot(base.DEFAULT_OUTPUT)
    old_games = {g['game_id']: g for g in prior['games']}
    games = []
    for raw in pgo_sources.open_csv(directory / 'schedule.csv.gz'):
        if (raw['season'], raw['game_type'], raw['week']) != ('2026', 'REG', '1'):
            continue
        value = pgo_prospective._normalize_row(raw)
        game = {k: value[k] for k in base.IDENTITY if k not in ('home', 'away')}
        game.update(home=value['home_team'], away=value['away_team'])
        if value['home_score'] or value['away_score'] or game != {k: old_games[game['game_id']][k] for k in base.IDENTITY}:
            raise ValueError('Current schedule conflicts with issued identity or has results')
        games.append(game)
    counts = Counter(t for g in games for t in (g['home'], g['away']))
    if len(games) != 16 or len({g['game_id'] for g in games}) != 16 or set(counts) != TEAMS or set(counts.values()) != {1}:
        raise ValueError('Week 1 must have 16 unique games and all 32 teams')
    official = official_games((directory / 'nfl-week-1.html').read_text(encoding='utf-8'))
    identity = lambda g: (g['away'], g['home'], base.current._utc(g['kickoff']))
    if len(official) != 16 or {identity(g) for g in official} != {identity(g) for g in games}:
        raise ValueError('Official schedule disagrees with provider')
    injury_page = (directory / 'nfl-injuries.html').read_text(encoding='utf-8')
    title = re.search(r'<title>(.*?)</title>', injury_page, re.S)
    if title is None or 'Week 1 of the 2026 Season' not in html.unescape(title[1]):
        raise ValueError('Official injury page season/week differs')
    tables = injury_tables(injury_page)
    coverage = {}
    for team in sorted(TEAMS):
        label = next(name.split()[-1] for name, colors in generate_site.TEAM.items() if colors[0] == team)
        observations = []
        for r in tables.get(label, []):
            matches = [p for (t, _), p in indexed.items() if t == team and name_key(p['full_name']) == name_key(r['player_name'])]
            observations.append({**r, 'gsis_id': matches[0]['gsis_id'] if len(matches) == 1 else None,
                                 'source_url': sources['nfl-injuries.html']['url']})
        known = [r for r in observations if r['game_status'] == 'Out']
        qb_name = name_key(selected[team]['full_name'])
        blocked = any(r['game_status'] == 'Out' and (r['gsis_id'] == selected[team]['gsis_id'] or name_key(r['player_name']) == qb_name) for r in observations)
        coverage[team] = dict(status='BLOCKED_EXPECTED_QB_UNAVAILABLE' if blocked else 'DATED_REPORT_UNADJUSTED' if label in tables else 'UNKNOWN',
                              source_kind='formal_injury_report' if label in tables else 'no_formal_report',
                              source_url=sources['nfl-injuries.html']['url'],
                              captured_at=sources['nfl-injuries.html']['captured_at'], report_date=None,
                              observations=observations, known_unavailable=known,
                              notes=['Captured official NFL table; retrieval time is not the report publication time.',
                                     'Non-QB injuries are not priced in this edition. ACT eligibility does not establish health.'])
    return dict(schema_version=1, status='PASS', charter_sha256=base._hash(CHARTER.read_bytes()),
                capture_manifest_sha256=base._hash((directory / 'capture.json').read_bytes()),
                inputs_as_of=capture['captured_at'], depth_as_of=latest.isoformat(),
                selected_roster=selected, games=sorted(games, key=lambda g: (g['kickoff'], g['game_id'])),
                coverage=coverage, formal_report_teams=sum(v['source_kind'] == 'formal_injury_report' for v in coverage.values()),
                unresolved_nonactive_roster=unresolved_roster,
                qualification_time=datetime.now(timezone.utc).isoformat())


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    result = qualify(args.directory)
    with (args.directory / 'postseason-qualification.json').open('xb') as f:
        f.write(base._json(result))
    print(json.dumps({k: result[k] for k in ('status', 'inputs_as_of', 'depth_as_of', 'formal_report_teams')}))
