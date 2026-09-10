"""One fixed penalty-history experiment; importing never reads sources or fits."""
import argparse
import copy
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
from itertools import groupby
import json
import math
from pathlib import Path

from pgo_sources import CURRENT_TEAMS, normalize_team

FEATURE = 'prior_penalty_yards_per_game'
DECAY = 0.5 ** (1 / 4)
IDENTITY = 'pgo-penalty-candidate-2026-09-10'
ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = Path(__file__).resolve().parent
BASELINE = ROOT / 'research/pgo_postseason_candidate/run-20260909-attempt01'
BASELINE_SHA256 = 'a58aeff835471182a555e4b926beafd0db01c7c5e3fe19827ddf56bd03f2514a'
CHARTER_SHA256 = '073a491cbe704b19934d7c9ab313bdd51eb32e2685124a53131a6d3f49ec3730'
HISTORY_TYPES = {'REG','WC','DIV','CON','SB'}
COMPARATORS = ('postseason','corrected','pgo_v0','constant')


def _require(ok, message):
    if not ok:
        raise ValueError(message)


def _utc(value):
    result = datetime.fromisoformat(str(value).replace('Z','+00:00'))
    _require(result.tzinfo is not None, 'Penalty history requires aware kickoff timestamps')
    return result.astimezone(timezone.utc)


def _count(value):
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError('Penalty counts and yards must be nonnegative integers') from error
    _require(not isinstance(value,bool) and math.isfinite(number) and number >= 0 and number.is_integer(),
             'Penalty counts and yards must be nonnegative integers')
    return int(number)


def penalty_history(games, team_rows, initial=None):
    """Emit prior rates before each kickoff batch, then update completed games only.

    The caller admits completed source games and enforces seed/source as-of times.
    Unrelated source rows are ignored; every requested team-game must match exactly.
    """
    states = {}
    for team, pair in (initial or {}).items():
        _require(team in CURRENT_TEAMS and isinstance(pair,(list,tuple)) and len(pair)==2, 'Invalid penalty seed team/state')
        _require(all(type(v) in (int,float) and math.isfinite(v) and v>=0 for v in pair)
                 and (pair[1]>0 or pair[0]==0), 'Invalid penalty seed accumulator')
        states[team] = list(pair)
    games = sorted((dict(g) for g in games),key=lambda g:(_utc(g['kickoff']),g['game_id']))
    wanted, ids = {}, set()
    for g in games:
        _require(g['game_type'] in HISTORY_TYPES and type(g['season']) is int and type(g['week']) is int
                 and g['week']>0 and g['game_id'] not in ids, 'Invalid or duplicate penalty history game')
        ids.add(g['game_id'])
        _require(g['home'] in CURRENT_TEAMS and g['away'] in CURRENT_TEAMS and g['home']!=g['away'], 'Invalid penalty game teams')
        for side in ('home','away'):
            key=(g['season'],g['week'],g[side])
            _require(key not in wanted, 'Duplicate penalty team-game period')
            wanted[key]=(g,side)
    observations = {}
    for r in team_rows:
        key=(_count(r['season']),_count(r['week']),normalize_team(r['team']))
        if key not in wanted:
            continue
        g,side=wanted[key];other='away' if side=='home' else 'home'
        _require(key not in observations and r['game_id']==g['game_id']
                 and normalize_team(r['opponent_team'])==g[other]
                 and r['season_type']==('REG' if g['game_type']=='REG' else 'POST'),
                 'Penalty source identity or membership differs')
        observations[key]=(_count(r['penalty_yards']),_count(r['penalties']))
    _require(set(observations)==set(wanted), 'Missing required penalty team-game source')
    pregame = {}
    for _, batch in groupby(games,key=lambda g:_utc(g['kickoff'])):
        batch=list(batch);seen=set()
        for g in batch:
            values={}
            for side in ('home','away'):
                team=g[side]
                _require(team not in seen,'Team plays twice in one kickoff batch')
                seen.add(team)
                n,d=states.get(team,(0.,0.));values[side]=n/d if d else None
            values['difference']=None if None in values.values() else values['home']-values['away']
            pregame[g['game_id']]=values
        for g in batch:
            for side in ('home','away'):
                team=g[side];n,d=states.get(team,(0.,0.))
                yards,_=observations[g['season'],g['week'],team]
                states[team]=[DECAY*n+yards,DECAY*d+1]
    return dict(pregame=pregame,states=dict(sorted(states.items())),coverage=dict(
        games=len(games),team_games=len(observations),zero_yards=sum(y==0 for y,_ in observations.values()),
        penalty_count=sum(n for _,n in observations.values()),penalty_yards=sum(y for y,_ in observations.values()),
        missing_pregame=sum(r['difference'] is None for r in pregame.values())))


def augment_rows(originals, pregame):
    from research.pgo_week1_corrected import train as corrected
    output=[]
    for old in originals:
        _require(old['game_id'] in pregame and FEATURE not in old['features'], 'Penalty feature inventory differs')
        value=pregame[old['game_id']]['difference']
        _require(value is None or type(value) in (int,float) and math.isfinite(value), 'Invalid prior penalty feature')
        row=corrected.audit.ch.FeatureRow(**copy.deepcopy(old))
        row.features[FEATURE]=value
        restored=asdict(row);restored['features'].pop(FEATURE)
        _require(restored==old,'Original baseline feature or metadata changed')
        output.append(row)
    return output


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _json(value):
    return (json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()


def _verified(directory, digest):
    raw=(directory/'manifest.json').read_bytes()
    _require(_sha(raw)==digest,'Pinned experiment manifest differs')
    manifest=json.loads(raw)
    for name,meta in manifest['files'].items():
        _require(Path(name).name==name and name not in ('.','..'),'Invalid experiment member')
        value=(directory/name).read_bytes()
        _require(_sha(value)==meta['sha256'] and len(value)==meta['bytes'],'Experiment member differs: '+name)
    return manifest


def load_baseline():
    """Read verified frozen baseline rows and replay its eight saved folds; no fit."""
    from research.pgo_week1_corrected import train as corrected
    audit=corrected.audit
    _verified(BASELINE,BASELINE_SHA256)
    originals=json.loads((BASELINE/'historical-features.json').read_bytes())
    rows=[audit.ch.FeatureRow(**r) for r in originals]
    saved=list(audit.pgo_sources.open_csv(BASELINE/'matched-predictions.csv'))
    matched={r['game_id']:r for r in saved}
    _require(len(rows)==3407 and len({r.game_id for r in rows})==3407
             and len(saved)==len(matched)==2127,'Frozen baseline cohort differs')
    fits=json.loads((BASELINE/'fold-fits.json').read_bytes())
    maximum=0.;counts=[];seen=set()
    for season,training,validation in audit.base.expanding_folds(rows):
        fit=next(f for f in fits if f.get('evaluation_season')==season)
        _require([r.game_id for r in training]==fit['training']['game_ids']
                 and [r.game_id for r in validation]==fit['validation']['game_ids'],'Frozen fold membership differs')
        for row,prediction in zip(validation,corrected.replay(validation,fit)):
            old=matched[row.game_id]
            _require(row.actual_margin==float(old['actual_margin']) and row.kickoff==old['kickoff']
                     and row.season==int(old['season']) and row.week==int(old['week']), 'Baseline evaluation identity differs')
            maximum=max(maximum,abs(prediction-float(old['candidate'])));seen.add(row.game_id)
        counts.append(len(validation))
    _require(counts==[256,256,256,272,271,272,272,272] and seen==set(matched)
             and maximum<=1e-10,'Frozen baseline replay differs')
    return dict(originals=originals,matched=matched,replay=dict(status='PASS',games=len(seen),maximum_error=maximum,fold_counts=counts))


def _pins():
    _require(_sha((DIRECTORY/'charter.md').read_bytes())==CHARTER_SHA256,'Penalty charter differs')
    _verified(BASELINE,BASELINE_SHA256)
    names=['research/pgo_penalty_candidate/candidate.py','tests/test_pgo_penalty_candidate.py',
           'research/pgo_penalty_candidate/charter.md','research/pgo_week1_corrected/train.py',
           'research/pgo_input_audit/audit_model.py','pgo_challenger.py','pgo_opponent_evaluation.py',
           'pgo_sources.py','pgo_model.py','pgo_prospective.py']
    code={name:_sha((ROOT/name).read_bytes()) for name in names}
    inventory=json.loads((BASELINE/'run-start.json').read_bytes())['sources']
    sources={k:v for k,v in inventory.items() if k=='schedule_results:None' or k.startswith('team_weekly_stats:')}
    _require(len(sources)==14,'Penalty historical source inventory differs')
    for name,meta in sources.items():
        raw=Path(meta['path']).read_bytes()
        _require(_sha(raw)==meta['sha256'] and len(raw)==meta['bytes'],'Pinned penalty source differs: '+name)
    return dict(code_sha256=code,sources=sources,baseline_manifest_sha256=BASELINE_SHA256,charter_sha256=CHARTER_SHA256)


def _start(output, kind, **bindings):
    output=Path(output).resolve()
    _require(output.parent==DIRECTORY and not output.exists(),'Use a new exclusive penalty attempt directory')
    pins=_pins()
    protected={str(p.relative_to(ROOT)):_sha(p.read_bytes()) for p in (ROOT/'docs/evidence').rglob('*') if p.is_file()}
    receipt=dict(identity=IDENTITY,status='STARTED_INCOMPLETE',kind=kind,started_at=datetime.now(timezone.utc).isoformat(),
                 pins=pins,issued_before_sha256=protected,**bindings)
    output.mkdir()
    (output/'run-start.json').write_bytes(_json(receipt))
    return output,receipt


def _finish(output,receipt,artifacts):
    _require(_pins()==receipt['pins'],'Penalty source or code changed during attempt')
    _require(all(_sha((ROOT/p).read_bytes())==h for p,h in receipt['issued_before_sha256'].items()),'Issued evidence changed during penalty attempt')
    receipt=dict(receipt,status='EXPERIMENTAL / HOLD',completed_at=datetime.now(timezone.utc).isoformat(),
                 protected_before_after='PASS',historical_source_vintage='REVIEW REQUIRED')
    artifacts=dict(artifacts,**{'run-receipt.json':_json(receipt)})
    for name,raw in artifacts.items():
        with (output/name).open('xb') as handle:handle.write(raw)
    artifacts['run-start.json']=(output/'run-start.json').read_bytes()
    with (output/'manifest.json').open('xb') as handle:
        handle.write(_json(dict(identity=IDENTITY,files={n:dict(sha256=_sha(raw),bytes=len(raw)) for n,raw in artifacts.items()})))
    return dict(output=str(output),manifest_sha256=_sha((output/'manifest.json').read_bytes()),status=receipt['status'])


def prepare(output):
    from pgo_sources import open_csv
    output,receipt=_start(output,'FEATURE_PREPARATION_NO_FIT')
    baseline=load_baseline();sources=receipt['pins']['sources']
    games=[]
    for r in open_csv(Path(sources['schedule_results:None']['path'])):
        if r['game_type'] not in HISTORY_TYPES or not 2013<=int(r['season'])<=2025 or not r['home_score'] or not r['away_score']:continue
        # Use the same schedule normalizer as the pinned history constructor.
        from pgo_prospective import _normalize_row
        normalized=_normalize_row(r)
        games.append(dict(game_id=r['game_id'],season=int(r['season']),week=int(r['week']),game_type=r['game_type'],
                          kickoff=normalized['kickoff'],home=normalize_team(r['home_team']),away=normalize_team(r['away_team'])))
    team_rows=[r for k,v in sources.items() if k.startswith('team_weekly_stats:') for r in open_csv(Path(v['path']))]
    history=penalty_history(games,team_rows)
    _require(len(games)==3562 and history['coverage']['team_games']==7124 and set(history['states'])==set(CURRENT_TEAMS),'Historical penalty coverage differs')
    by_id={g['game_id']:g for g in games}
    _require({g['game_id'] for g in games if g['game_type']=='REG'}=={r['game_id'] for r in baseline['originals']},'REG penalty cohort differs')
    for r in baseline['originals']:
        g=by_id[r['game_id']]
        _require((g['season'],g['week'],_utc(g['kickoff']))==(r['season'],r['week'],_utc(r['kickoff'])),'Penalty versus baseline game time differs')
    rows=augment_rows(baseline['originals'],history['pregame'])
    seed=dict(schema_version=1,feature=FEATURE,states=history['states'],season=2025,
              history_through=max(_utc(g['kickoff']) for g in games).isoformat(),history_games=len(games),half_life_games=4)
    receipt.update(training_games=len(rows),model_fits=0)
    return _finish(output,receipt,{'historical-features.json':_json([asdict(r) for r in rows]),
        'penalty-seed.json':_json(seed),'coverage.json':_json(history['coverage']),'baseline-replay.json':_json(baseline['replay'])})


def screen(metrics, interval):
    candidate,baseline=metrics['candidate'],metrics['postseason']
    cs={r['season']:r['mae'] for r in candidate['seasons']};bs={r['season']:r['mae'] for r in baseline['seasons']}
    _require(set(cs)==set(bs)==set(range(2018,2026)),'Penalty screen requires eight locked seasons')
    wins=sum(cs[s]<bs[s] for s in cs)
    improvement=baseline['overall']['mae']-candidate['overall']['mae']
    checks=dict(mae_improvement_at_least_005=improvement>=.05,at_least_five_seasons=wins>=5,positive_interval_lower=interval['lower']>0)
    return dict(status='PASS' if all(checks.values()) else 'FAIL',scientific_status='EXPERIMENTAL / HOLD',
                checks=checks,season_wins=wins,mae_improvement=improvement)


def raw_yard_weight(fit):
    index=fit['preprocessor']['feature_names'].index(FEATURE)
    return fit['coefficients'][index+1]/fit['preprocessor']['scales'][index]


def fit(output, prepared, digest):
    from research.pgo_week1_corrected import train as corrected
    audit=corrected.audit;prepared=Path(prepared).resolve()
    _require(prepared.parent==DIRECTORY,'Preparation must be in penalty research')
    _verified(prepared,digest)
    prior=json.loads((prepared/'run-receipt.json').read_bytes())
    _require(prior['kind']=='FEATURE_PREPARATION_NO_FIT' and prior['pins']==_pins(),'Prepared code/source pins differ')
    output,receipt=_start(output,'FIXED_DIAGNOSTIC_FIT',prepared_manifest_sha256=digest)
    baseline=load_baseline()
    raw_rows=json.loads((prepared/'historical-features.json').read_bytes())
    _require(len(raw_rows)==len(baseline['originals']),'Penalty training count differs')
    for row,old in zip(raw_rows,baseline['originals']):
        check=copy.deepcopy(row);value=check['features'].pop(FEATURE)
        _require(check==old and (value is None or type(value) in (int,float) and math.isfinite(value)),'Prepared original fields or penalty value differ')
    rows=[audit.ch.FeatureRow(**r) for r in raw_rows]
    matched={k:{**{n:r[n] for n in ('game_id','kickoff','home_team','away_team')},
                'season':int(r['season']),'week':int(r['week']),'neutral_site':r['neutral_site']=='True',
                'actual_margin':float(r['actual_margin']),'postseason':float(r['candidate']),
                **{n:float(r[n]) for n in COMPARATORS if n!='postseason'}} for k,r in baseline['matched'].items()}
    folds=[(s,training,testing) for s,training,testing in audit.base.expanding_folds(rows)]+[(None,rows,[])]
    fits=[];maximum=0.
    for season,training,testing in folds:
        values=[r.features[FEATURE] for r in training if r.features[FEATURE] is not None]
        _require(values and min(values)<max(values),'No penalty variation in training fold')
        pp,coefficients,mirrored=corrected.fit_combined(training)
        fitted=audit._fit_receipt(pp,coefficients,training,testing,4,name='active4_symmetric',fit_training=mirrored)
        fitted['evaluation_season']=season
        fitted['penalty_coefficient_per_raw_yard']=raw_yard_weight(fitted)
        probes=testing if season is not None else training
        predictions=audit.base._predict_rows(probes,pp,coefficients)
        replayed=corrected.replay(probes,json.loads(_json(fitted)))
        error=max(abs(a-b) for a,b in zip(predictions,replayed))
        _require(all(math.isfinite(v) for v in predictions+replayed) and error<=1e-10,'Penalty serialized replay differs')
        maximum=max(maximum,error)
        if season is not None:
            for row,value in zip(testing,predictions):matched[row.game_id]['candidate']=value
        fits.append(fitted)
    values=sorted(matched.values(),key=lambda r:(r['season'],r['week'],r['kickoff'],r['game_id']))
    metrics={name:audit.metric_views(values,name) for name in (*COMPARATORS,'candidate')}
    intervals={f'vs_{name}':audit.base.season_block_bootstrap(values,'candidate',name,samples=10000,seed=20260910) for name in COMPARATORS}
    result=screen(metrics,intervals['vs_postseason'])
    _verified(prepared,digest)
    final=dict(schema_version=1,identity=IDENTITY,status='EXPERIMENTAL / HOLD',feature=FEATURE,
               charter_sha256=CHARTER_SHA256,prepared_manifest_sha256=digest,**fits[-1])
    receipt.update(training_games=len(rows),evaluation_games=len(values),model_fits=len(fits),maximum_serialized_replay_error=maximum,further_study_screen=result)
    artifacts={n:(prepared/n).read_bytes() for n in ('penalty-seed.json','coverage.json','baseline-replay.json','historical-features.json')}
    artifacts.update({'final-fit.json':_json(final),'fold-fits.json':_json(fits),
                      'matched-predictions.csv':audit.base._csv_bytes(values),
                      'metrics.json':_json(dict(metrics=metrics,paired_bootstrap=intervals,further_study_screen=result,
                          penalty_coefficients=[dict(evaluation_season=f['evaluation_season'],coefficient_per_raw_yard=f['penalty_coefficient_per_raw_yard']) for f in fits]))})
    return _finish(output,receipt,artifacts)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='operation',required=True)
    pre=sub.add_parser('prepare');pre.add_argument('--output',type=Path,required=True)
    run=sub.add_parser('fit');run.add_argument('--output',type=Path,required=True)
    run.add_argument('--prepared',type=Path,required=True);run.add_argument('--manifest-sha256',required=True)
    args=parser.parse_args()
    result=prepare(args.output) if args.operation=='prepare' else fit(args.output,args.prepared,args.manifest_sha256)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
