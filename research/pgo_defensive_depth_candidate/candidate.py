"""Prepare four fixed prior-season defensive fields; deliberately no fitting."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

import pgo_challenger as ch
import pgo_forecast_corrected as issued
import pgo_sources
from research.pgo_defensive_depth_candidate import evidence as ev
from research.pgo_opening_night_20260909.identity import source_package
from research.pgo_week1_corrected import train as corrected

ROOT = ev.ROOT
DIRECTORY = Path(__file__).resolve().parent
FEATURES = ('defense_prior_qb_hits_per_100_snaps',
            'defense_prior_pass_defended_per_100_snaps',
            'defense_prior_effective_contributors', 'defense_prior_history_coverage')
CORRECTED = ROOT/'research/pgo_week1_corrected/run-20260908'
BASE_MANIFEST_SHA = '7530b3199f8a17ffec34f9e5351919ea67cb45df66e16befd655ab4e746f7a4c'


def team_features(rows, profiles, target_season, colliding_ids=()):
    """Same ACT/prior-season construction for historical and current rosters."""
    players, seen = [], set()
    for row in rows:
        if row['status'].strip() != 'ACT':
            raise ValueError('Only ACT roster rows are accepted')
        if int(row['season']) != target_season:
            raise ValueError('Roster target season differs')
        pid = ch._roster_player_id(row, colliding_ids)
        if not pid or pid in seen:
            raise ValueError('Duplicate or missing ACT player identity')
        seen.add(pid)
        if row['position'].strip().upper() in ev.DEFENSE:
            players.append(pid)
    values = {name:None for name in FEATURES}
    coverage = {'active_defenders':len(players), 'observed_history':0,
                'without_observed_history':len(players), 'exposure':{}}
    if profiles is None:
        return values, {**coverage, 'status':'PRIOR_SEASON_SOURCE_UNAVAILABLE'}
    known = []
    for pid in players:
        profile = profiles.get(pid)
        if profile is None:
            continue
        if not profile['observations'] or any(o['season'] != target_season-1 for o in profile['observations']):
            raise ValueError('Production must be strictly from the prior season')
        known.append(profile)
    coverage.update(observed_history=len(known), without_observed_history=len(players)-len(known),
                    status='AVAILABLE' if players else 'NO_DEFENDERS_ON_ACT_ROSTER')
    for name, statistic in zip(FEATURES[:2], ('def_qb_hits','def_pass_defended')):
        numerator = denominator = excluded = 0.0
        missing_rows = 0
        for profile in known:
            for row in profile['observations']:
                snaps = ev.number(row['defensive_snaps'])
                if snaps is None or snaps <= 0:
                    raise ValueError('Prior observed snaps must be positive')
                value = ev.number(row['stats'][statistic])
                if value is None:
                    excluded += snaps; missing_rows += 1
                else:
                    numerator += value; denominator += snaps
        values[name] = 100*numerator/denominator if denominator else None
        coverage['exposure'][statistic] = {
            'numerator':numerator, 'matched_defensive_snaps':denominator,
            'excluded_defensive_snaps':excluded, 'missing_stat_rows':missing_rows,
            'matched_exposure_fraction':denominator/(denominator+excluded) if denominator+excluded else None}
    shares = [ev.number(p['prior_role_share']) for p in known]
    if any(q is None or not 0 < q <= 1 for q in shares):
        raise ValueError('Invalid prior positive role share')
    values[FEATURES[2]] = sum(shares)**2/sum(q*q for q in shares) if shares else None
    values[FEATURES[3]] = len(known)/len(players) if players else None
    return values, coverage


def difference(home, away):
    return {k:None if home[k] is None or away[k] is None else home[k]-away[k] for k in FEATURES}


def source_inventory():
    corrected.audit._verified_manifest(CORRECTED,BASE_MANIFEST_SHA)
    prior=json.loads((corrected.audit.PRIOR_RUN/'run-receipt.json').read_bytes())
    paths=corrected.audit._paths_from_prior(prior)
    paths.update(source_package.load_sources(ev.IDENTITY_MANIFEST,ev.IDENTITY_SHA))
    return paths


def code_pins():
    paths=[DIRECTORY/name for name in ('candidate.py','evidence.py','predictive-charter.md',
                                      'test_candidate.py','test_evidence.py')]
    return {str(p.relative_to(ROOT)):ev.digest(p) for p in paths}


def prepare(capture_dir,output):
    """Append only four fields to saved corrected rows, preserving every base cell."""
    capture_dir,output=Path(capture_dir).resolve(),Path(output).resolve()
    if output.exists():
        raise ValueError('Preparation output already exists')
    paths=source_inventory()
    pins=code_pins()
    sources={f'{name}:{season}':{'path':str(path),'sha256':ev.digest(path),'bytes':path.stat().st_size}
             for (name,season),path in paths.items() if name in {'schedule_results','weekly_rosters','snap_counts','player_weekly_stats'}}
    output.mkdir(parents=True)
    ev.write_json(output/'run-start.json',{'kind':'FEATURE_PREPARATION_NO_FIT','status':'STARTED_INCOMPLETE',
                                         'started_at':datetime.now(timezone.utc).isoformat(),'code_sha256':pins,
                                         'source_inventory':sources,'corrected_manifest_sha256':BASE_MANIFEST_SHA})
    collision_path=ROOT/'research/pgo_snap_identity_repair_20260909/source-conflict-inventory.json'
    if ev.digest(collision_path)!='c3f721962886ba77fd1ff8d45637508d2050fd294c0f3185dff77f3561a66a29':
        raise ValueError('Collision inventory changed')
    collisions=set(json.loads(collision_path.read_bytes())['colliding_gsis'])
    groups={};history={};coverage={}
    schedule=list(pgo_sources.open_csv(paths['schedule_results',None]))
    games={r['game_id']:r for r in schedule}
    for season in range(2013,2026):
        rr=list(pgo_sources.open_csv(paths['weekly_rosters',season]))
        ss=list(pgo_sources.open_csv(paths['snap_counts',season]))
        pp=list(pgo_sources.open_csv(paths['player_weekly_stats',season]))
        if any(int(r['season'])!=season for rows in (rr,ss,pp) for r in rows):
            raise ValueError('Historical source contains a different season')
        for r in rr:
            if r['status'].strip()=='ACT':
                key=(season,int(r['week']),pgo_sources.normalize_team(r['team']))
                groups.setdefault(key,[]).append(r)
        for r in ss:
            if r['game_type'] not in ev.GAME_TYPES:
                continue
            game=games.get(r['game_id'])
            if game is None or (int(game['season']),int(game['week']),game['game_type'])!=(season,int(r['week']),r['game_type']):
                raise ValueError('Snap record is not bound to its scheduled game')
            if pgo_sources.normalize_team(r['team']) not in {pgo_sources.normalize_team(game[k]) for k in ('home_team','away_team')}:
                raise ValueError('Snap team is not in its scheduled game')
        history[season],coverage[str(season)]=ev.build_history(rr,ss,pp,season,collisions)
        print(json.dumps({'prior_season':season,'profiles':len(history[season]),
                          'resolved_rows':coverage[str(season)].get('resolved_positive_snap_rows',0),
                          'unresolved_rows':coverage[str(season)].get('unresolved_positive_snap_rows',0)}),flush=True)
    saved=json.loads((CORRECTED/'historical-features.json').read_bytes())
    prepared=[];by_team=[]
    for old in saved:
        game=games[old['game_id']];season=old['season'];week=old['week']
        if game['game_type']!='REG' or (int(game['season']),int(game['week']))!=(season,week):
            raise ValueError('Corrected historical game identity differs')
        home,away=(pgo_sources.normalize_team(game[k]) for k in ('home_team','away_team'))
        feature_views={}
        for team in (home,away):
            roster=groups.get((season,week,team),[])
            if not roster:
                raise ValueError('Missing historical ACT team roster')
            view,receipt=team_features(roster,history.get(season-1),season,collisions)
            feature_views[team]=view
            by_team.append({'game_id':old['game_id'],'season':season,'week':week,'team':team,**receipt})
        added=difference(feature_views[home],feature_views[away])
        prepared.append({**old,'features':{**old['features'],**added},'subgroup_flags':{
            'weeks_1_4':week<=4,'weeks_5_18':week>=5}})
    if len(prepared)!=3407 or len({r['game_id'] for r in prepared})!=3407:
        raise ValueError('Corrected training cohort differs')
    for new,old in zip(prepared,saved):
        if {k:v for k,v in new['features'].items() if k not in FEATURES}!=old['features']:
            raise ValueError('Base corrected features changed')
    # No current-season production is consumed. The fresh QB selection merely
    # supplies the unchanged corrected constructor with current source metadata.
    from research.pgo_postseason_candidate.sources import qualify
    qualified=qualify(capture_dir)
    context=json.loads((CORRECTED/'historical-context.json').read_bytes())
    base=issued.current_features(context,qualified['selected_roster'],qualified['inputs_as_of'])
    fresh=defaultdict(list)
    for r in pgo_sources.open_csv(capture_dir/'roster.csv.gz'):
        if r['status'].strip()=='ACT':fresh[pgo_sources.normalize_team(r['team'])].append(r)
    current={};current_coverage={}
    for team in sorted(pgo_sources.CURRENT_TEAMS):
        view,receipt=team_features(fresh[team],history[2025],2026,collisions)
        current[team]={**base[team],**view};current_coverage[team]=receipt
    if code_pins()!=pins:
        raise ValueError('Candidate implementation changed during preparation')
    corrected.audit._verified_manifest(CORRECTED,BASE_MANIFEST_SHA)
    for source in sources.values():
        if ev.digest(source['path'])!=source['sha256']:
            raise ValueError('Historical source changed during preparation')
    artifacts={'historical-features.json':prepared,'current-features.json':current,
               'coverage.json':{'prior_season_identity':coverage,'historical_team_games':by_team,
                                'current_teams':current_coverage,'warmup_season_all_missing':2013,
                                'history_source_publication_vintage':'REVIEW REQUIRED',
                                'interpretation':'Per-stat rates describe exact matched exposure, not all snaps or pass-rush opportunities.'},
               'current-source-qualification.json':qualified,
               'run-receipt.json':{'kind':'FEATURE_PREPARATION_NO_FIT','status':'READY_FOR_INDEPENDENT_REVIEW',
                   'completed_at':datetime.now(timezone.utc).isoformat(),'model_fits':0,'training_games':3407,
                   'feature_names':list(FEATURES),'base_parity':'EXACT','code_sha256':pins,
                   'charter_sha256':ev.digest(DIRECTORY/'predictive-charter.md'),
                   'source_inventory':sources,'current_inputs_as_of':qualified['inputs_as_of'],
                   'capture_manifest_sha256':ev.digest(capture_dir/'capture.json')}}
    for name,value in artifacts.items():ev.write_json(output/name,value)
    ev.write_json(output/'manifest.json',{'schema_version':1,'identity':'pgo-defensive-production-20260909',
                   'files':{p.name:{'sha256':ev.digest(p),'bytes':p.stat().st_size} for p in output.iterdir() if p.is_file()}})
    return {'path':str(output),'manifest_sha256':ev.digest(output/'manifest.json'),
            'games':len(prepared),'current_teams':len(current),'features':list(FEATURES)}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(prepare(args.capture,args.output)))
