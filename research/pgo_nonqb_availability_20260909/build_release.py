"""Issue a separate non-QB scenario from reviewed local captures, never refit."""
import argparse
from collections import defaultdict
from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import pgo_forecast_corrected as corrected
import pgo_sources
from research.pgo_nonqb_availability_20260909.prepare_roles import prepare, SOURCE_MANIFEST, SOURCE_SHA
from research.pgo_opening_night_20260909.identity.source_package import load_sources


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def time(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('A source timestamp requires timezone')
    return result


def prepare_evidence(path, base):
    evidence = deepcopy(json.loads(path.read_bytes()))
    source_root = path.parent.resolve()
    sources = {}
    path_map = {}
    for source in evidence['sources']:
        original = source['source_file']
        filename = (ROOT / original).resolve()
        relative = filename.relative_to(source_root).as_posix()
        if source['status'] != 200 or source['sha256'] != digest(filename) or source['bytes'] != filename.stat().st_size:
            raise ValueError(f'Raw source differs: {relative}')
        source['source_file'] = relative
        if source.get('final_url'):
            parts = urlsplit(source['final_url'])
            source['final_url'] = urlunsplit((parts.scheme, parts.netloc, parts.path, '', ''))
        path_map[original] = relative
        sources[relative] = source
    for row in [*evidence['players'], *evidence['teams'], *evidence.get('excluded', [])]:
        row['source_file'] = path_map[row['source_file']]
    for key in ('roster_source', 'depth_source'):
        evidence[key] = sources[path_map[evidence[key]['source_file']]]
    evidence['as_of'] = max(evidence['sources'], key=lambda r: time(r['captured_at']))['captured_at']
    for team in evidence['teams']:
        team['source_kind'] = team.pop('report_kind')
        reports = [r['report_date'] for r in evidence['players']
                   if r['team'] == team['team'] and r['source_kind'] == team['source_kind']]
        team['report_date'] = max(reports) if reports else None

    # Fresh source observations must still support the old conditional QB inputs.
    rosters = defaultdict(list)
    for row in pgo_sources.open_csv(source_root / evidence['roster_source']['source_file']):
        if row['season'] == '2026' and row['week'] == '1':
            rosters[pgo_sources.normalize_team(row['team']), row['gsis_id']].append(row)
    depth = list(pgo_sources.open_csv(source_root / evidence['depth_source']['source_file']))
    depth_time = time(evidence['depth_source']['captured_at'])
    eligible = [r for r in depth if time(r['dt']) <= depth_time]
    latest = max(time(r['dt']) for r in eligible)
    starters = [r for r in eligible if time(r['dt']) == latest and r['pos_abb'] == 'QB' and r['pos_rank'] == '1']
    if len(starters) != 32:
        raise ValueError('Fresh QB1 depth does not uniquely cover 32 teams')
    checks = []
    for team in base['teams']:
        matching = [r for r in starters if pgo_sources.normalize_team(r['team']) == team['team']]
        if len(matching) != 1 or matching[0]['gsis_id'] != team['qb_gsis_id']:
            raise ValueError(f'Fresh expected QB changed: {team["team"]}')
        rows = rosters[team['team'], team['qb_gsis_id']]
        if len(rows) != 1 or rows[0]['status'] != 'ACT' or rows[0]['position'] != 'QB':
            raise ValueError(f'Fresh expected QB not ACT: {team["team"]}')
        checks.append({'team': team['team'], 'gsis_id': team['qb_gsis_id'],
                       'depth_row': matching[0], 'roster_row': rows[0]})
    evidence['qb_checks'] = checks
    evidence['depth_as_of'] = latest.isoformat()
    historical = load_sources(SOURCE_MANIFEST, SOURCE_SHA)
    history_dir = source_root / 'history'
    history_dir.mkdir(exist_ok=True)
    evidence['role_sources'] = []
    for name in ('weekly_rosters', 'snap_counts'):
        original = historical[name, 2025]
        raw = original.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        relative = f'history/{name}-2025-{sha}.csv'
        copied = source_root / relative
        if copied.exists():
            if copied.read_bytes() != raw:
                raise ValueError('Prior source copy differs')
        else:
            with copied.open('xb') as handle:
                handle.write(raw)
        evidence['role_sources'].append(dict(
            source_file=relative, sha256=sha, bytes=len(raw),
            kind='qualified_local_source', name=name, season=2025,
            qualification_manifest_sha256=SOURCE_SHA,
            note='Previously qualified historical identity source; corrected roster is derived, not a fresh HTTP capture.'))
    return evidence, source_root


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output directory already exists')
    base = corrected.load_snapshot(corrected.DEFAULT_OUTPUT)
    fit_path = ROOT / 'research/pgo_week1_corrected/run-20260908/final-fit.json'
    fit = json.loads(fit_path.read_bytes())
    evidence, source_root = prepare_evidence(args.evidence, base)
    roles = prepare(evidence, source_root / evidence['roster_source']['source_file'],
                    source_root / evidence['depth_source']['source_file'])
    protected = [*sorted((ROOT / 'docs/evidence/forecast-lab-2026').rglob('*')), fit_path]
    before = {str(p.relative_to(ROOT)): digest(p) for p in protected if p.is_file()}
    import pgo_nonqb_availability as availability
    availability.save_package(base, fit, evidence, roles, args.output, source_root=source_root)
    availability.load_package(args.output)
    after = {str(p.relative_to(ROOT)): digest(p) for p in protected if p.is_file()}
    if before != after:
        raise ValueError('An issued forecast or fitted model changed')
    print(json.dumps({'status': 'PASS', 'output': str(args.output),
                      'preserved_files': len(before), 'model_fits': 0,
                      'players': len(roles), 'missing_roles': sum(r['snap_share'] is None for r in roles),
                      'fresh_qbs_verified': len(evidence['qb_checks'])}, indent=2))


if __name__ == '__main__':
    main()
