"""Read-only reconstruction of frozen roster descriptors and two snap ID gaps.

Run: python -B research/pgo_ranking_trace_20260909/check_player_inputs.py
No model imports, fits, history preparation, source capture, or file writes.
"""
import csv
from datetime import date
import gzip
import hashlib
import json
import math
from pathlib import Path
import statistics


ROOT = Path(__file__).resolve().parents[2]
CANDIDATE = ROOT / 'research/pgo_corrected_roster_candidate'
ISSUED = ROOT / 'docs/evidence/forecast-lab-2026/september-08-corrected'
ALIASES = dict(HB='RB', OT='T', OG='G', MLB='LB', FS='S', SS='S', SAF='S')
UNITS = {'offense': set('RB FB WR TE C G T OL'.split()),
         'defense': set('DE DT DL NT LB ILB OLB EDGE CB S DB'.split())}


def read_json(path):
    return json.loads(path.read_bytes())


def read_csv(path):
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', newline='', encoding='utf-8-sig') as handle:
        return list(csv.DictReader(handle))


def check():
    for directory in (CANDIDATE / 'current-preflight-20260908',
                      CANDIDATE / 'preflight-20260908-revised', ISSUED):
        for name, entry in read_json(directory / 'manifest.json')['files'].items():
            raw = (directory / name).read_bytes()
            assert len(raw) == entry['bytes'], (directory, name)
            assert hashlib.sha256(raw).hexdigest() == entry['sha256'], (directory, name)

    context = read_json(CANDIDATE / 'preflight-20260908-revised/historical-context.json')
    snapshot = read_json(ISSUED / 'snapshot.json')
    features = read_json(CANDIDATE / 'current-preflight-20260908/current-features.json')
    coverage = read_json(CANDIDATE / 'current-preflight-20260908/coverage.json')
    clock = date.fromisoformat(snapshot['inputs_as_of'][:10])
    teams = {}
    for row in read_csv(ISSUED / 'roster.csv.gz'):
        if row['status'].strip() != 'ACT':
            continue
        team = {'LA': 'LAR', 'SD': 'LAC', 'OAK': 'LV'}.get(row['team'], row['team'])
        pid = row['gsis_id'] or ('pfr:' + row['pfr_id'] if row['pfr_id'] else '')
        if row['gsis_id'] in context['inputs']['colliding_gsis']:
            pid += ':' + row['smart_id']
        assert pid and row['birth_date'] and row['years_exp'], row
        position = row['position'].strip().upper().split('/')[0]
        position = ALIASES.get(position, position)
        unit = next((key for key, positions in UNITS.items() if position in positions), None)
        history = context['snap_history'].get(pid, {}).get(unit, [])
        pick = int(row['draft_number']) if row['draft_number'] else None
        teams.setdefault(team, []).append(dict(
            pid=pid, gsis=row['gsis_id'], position=position, unit=unit,
            age=(clock - date.fromisoformat(row['birth_date'])).days / 365.2425,
            experience=int(row['years_exp']), draft=1 / math.sqrt(pick) if pick else 0,
            role=statistics.median(history) if history else None))

    checked, maximum_error = 0, 0.0
    assert set(teams) == set(features)
    for team, players in teams.items():
        assert len({p['pid'] for p in players}) == len(players)
        selected = next(t['qb_gsis_id'] for t in snapshot['teams'] if t['team'] == team)
        qbs = [p for p in players if p['gsis'] == selected and p['position'] == 'QB']
        assert len(qbs) == 1
        values = {'qb_age_centered': qbs[0]['age'] - 27,
                  'qb_age_squared': (qbs[0]['age'] - 27) ** 2}
        for unit in UNITS:
            members = [p for p in players if p['unit'] == unit]
            known = [p for p in members if p['role'] is not None]
            mass = sum(p['role'] for p in known)
            assert len(members) == coverage[team][unit]['players']
            assert len(known) == coverage[team][unit]['known_role_players']
            assert abs(mass - coverage[team][unit]['known_role_mass']) < 1e-12
            values.update({
                unit + '_role_weighted_age': sum(p['role'] * p['age'] for p in known) / mass,
                unit + '_young_role_share': sum(p['role'] * (p['age'] < 26) for p in known) / mass,
                unit + '_role_weighted_draft_prior': sum(p['role'] * p['draft'] for p in known) / mass,
                unit + '_rookie_draft_capital': sum(p['draft'] for p in members if p['experience'] == 0) / len(members),
            })
        for name, value in values.items():
            error = abs(value - features[team][name])
            assert error <= 1e-12, (team, name, value, features[team][name])
            maximum_error = max(maximum_error, error)
            checked += 1

    receipt = read_json(CANDIDATE / 'current-preflight-20260908/run-receipt.json')
    historical = {}
    for key in ('weekly_rosters:2025', 'snap_counts:2025'):
        source = receipt['sources'][key]
        path = Path(source['path'])
        assert hashlib.sha256(path.read_bytes()).hexdigest() == source['sha256']
        historical[key] = read_csv(path)
    gaps = []
    for team, pid, snap_name, weeks, counts in (
        ('NE', '00-0036198', 'Michael Onwenu', [15, 16, 17, 18], [52, 74, 58, 59]),
        ('NYG', '00-0036246', 'Jon Runyan Jr.', [13, 15, 17, 18], [55, 68, 64, 75]),
    ):
        for week, count in zip(weeks, counts):
            roster = [r for r in historical['weekly_rosters:2025']
                      if r['team'] == team and int(r['week']) == week and r['status'] == 'ACT']
            player = [r for r in roster if r['gsis_id'] == pid]
            assert len(player) == 1 and not player[0]['pfr_id']
            snap = next(r for r in historical['snap_counts:2025']
                        if r['team'] == team and int(r['week']) == week and r['player'] == snap_name)
            assert int(snap['offense_snaps']) == count
            assert snap['pfr_player_id'] not in {r['pfr_id'] for r in roster}
            assert ' '.join(snap_name.casefold().split()) not in {
                ' '.join(r['full_name'].casefold().split()) for r in roster}
        assert context['snap_history'][pid]['offense'] == [0.0] * 4
        gaps.append(dict(team=team, gsis_id=pid, snap_name=snap_name,
                         weeks=weeks, observed_offense_snaps=counts, saved_roles=[0.0] * 4))
    return dict(status='PASS', team_feature_cells=checked, maximum_absolute_error=maximum_error,
                input_clock=snapshot['inputs_as_of'], verified_fallback_zero_examples=gaps)


if __name__ == '__main__':
    print(json.dumps(check(), indent=2))
