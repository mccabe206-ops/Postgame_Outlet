"""Independent arithmetic/provenance check of the seven-arm saved audit.

Uses stdlib/NumPy only. Never imports the evaluator, constructs model inputs,
fits a model, fetches sources, or changes a run artifact.
"""
import argparse
import csv
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUN = Path(__file__).with_name('run-20260908-eligibility-attempt02')
DEFAULT_OUTPUT = Path(__file__).with_name('verification.json')
PRIOR = ROOT / 'research/pgo_current_strength/run-20260908'
PRIOR_SHA = '6682197b16fcc0974fef19e6c704ef238d4d2a30ba0db066e3e86a6bad35ee4a'
SNAPSHOT = ROOT / 'docs/evidence/forecast-lab-2026/september-07'
SNAPSHOT_SHA = '43bdeee73a2d3301eedbcecc7d291dc9ebe68cf196860e7217326570e4fe2f42'
ARMS = ('reference4', 'active4', 'active4_clean', 'active8_clean',
        'active4_compact', 'active4_exposure', 'active4_symmetric')
BASELINES = ('prior_raw', 'prior_starter', 'pgo_v0', 'constant')
TEAMS = tuple(sorted('ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LAC LAR LV MIA MIN NE NO NYG NYJ PHI PIT SEA SF TB TEN WAS'.split()))
TOLERANCE = 1e-10


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def csv_rows(path):
    with Path(path).open(newline='', encoding='utf-8') as stream:
        return list(csv.DictReader(stream))


def manifest(directory, expected=None):
    directory = Path(directory)
    if expected is not None:
        assert sha(directory / 'manifest.json') == expected
    value = read(directory / 'manifest.json')
    for name, entry in value['files'].items():
        path = directory / name
        assert path.stat().st_size == entry['bytes'] and sha(path) == entry['sha256'], name
    return value


def summary(rows, key, team=None):
    actual, predicted = [], []
    for row in rows:
        sign = -1 if team is not None and row['away_team'] == team else 1
        actual.append(sign * float(row['actual_margin']))
        predicted.append(sign * float(row[key]))
    count = len(actual)
    errors = [p-a for a,p in zip(actual,predicted)]
    denominator = sum(a != 0 for a in actual)
    correct = sum(a*p > 0 for a,p in zip(actual,predicted) if a != 0)
    return {'count': count,
            'mae': math.fsum(abs(e) for e in errors)/count if count else None,
            'rmse': math.sqrt(math.fsum(e*e for e in errors)/count) if count else None,
            'bias_predicted_minus_actual': math.fsum(errors)/count if count else None,
            'winner': {'correct': correct, 'denominator': denominator,
                       'accuracy': correct/denominator if denominator else None,
                       'actual_ties': sum(a == 0 for a in actual),
                       'predicted_ties': sum(p == 0 for p in predicted)}}


def views(rows, key):
    groups = {'overall': rows,
              'weeks_1_4': [r for r in rows if int(r['week']) <= 4],
              'weeks_5_18': [r for r in rows if int(r['week']) >= 5],
              'week_1': [r for r in rows if int(r['week']) == 1],
              'large_predicted_margin_abs_ge_7': [r for r in rows if abs(float(r[key])) >= 7],
              'neutral_site': [r for r in rows if r['neutral_site'] == 'True']}
    output = {name: summary(selected, key) for name,selected in groups.items()}
    output['seasons'] = [{'season': s, **summary([r for r in rows if int(r['season']) == s], key)}
                         for s in range(2018,2026)]
    output['teams'] = [{'team': t, **summary([r for r in rows if t in (r['home_team'],r['away_team'])],key,t)}
                       for t in TEAMS]
    return output


def bootstrap(rows, candidate, control):
    sums, counts = [], []
    for season in range(2018,2026):
        selected = [r for r in rows if int(r['season']) == season]
        gains = [abs(float(r[control])-float(r['actual_margin']))-
                 abs(float(r[candidate])-float(r['actual_margin'])) for r in selected]
        sums.append(math.fsum(gains)); counts.append(len(gains))
    # Each sampled season contributes all its games, preserving the unequal
    # original season sizes. This is a paired game-weighted block bootstrap.
    selections = np.random.default_rng(20260908).integers(0,8,size=(10000,8))
    totals = np.asarray(sums)[selections].sum(axis=1)
    numbers = np.asarray(counts)[selections].sum(axis=1)
    values = totals/numbers
    low,high = np.quantile(values,[.025,.975])
    return {'mean': math.fsum(sums)/sum(counts), 'lower': float(low), 'upper': float(high),
            'blocks': 8, 'samples': 10000, 'seed': 20260908}


def transform(features, fit):
    p=fit['preprocessor'];names=p['feature_names'];missing_names=p['missing_features']
    rows=[]
    for feature in features:
        missing=[feature.get(k) is None for k in names]
        row=[((p['medians'][i] if missing[i] else feature[names[i]])-p['medians'][i])/p['scales'][i]
             for i in range(len(names))]
        row += [float(feature.get(k) is None) for k in missing_names]
        rows.append(row)
    output=np.asarray(rows,dtype=float)
    assert np.isfinite(output).all()
    return output


def predict(features,fit):
    x=transform(features,fit)
    return fit['coefficients'][0]+x@np.asarray(fit['coefficients'][1:])


def neutral_difference(a,b,names):
    return {name: 0.0 if name in ('home_field','rest_difference') else
            (None if a.get(name) is None or b.get(name) is None else a[name]-b[name])
            for name in names}


def verify(run=DEFAULT_RUN, output=DEFAULT_OUTPUT):
    run,output=Path(run),Path(output)
    if output.exists():
        raise ValueError('Verification output must be new')
    members=manifest(run);manifest(PRIOR,PRIOR_SHA);manifest(SNAPSHOT,SNAPSHOT_SHA)
    receipt=read(run/'run-receipt.json');prior_receipt=read(PRIOR/'run-receipt.json')
    for name,digest in receipt['code_sha256'].items():
        assert sha(ROOT/name)==digest,name
    for filename,key in (('charter.md','charter_sha256'),('charter-v2-addendum.md','addendum_sha256'),
                         ('charter-v3-symmetry.md','symmetry_charter_sha256')):
        assert sha(Path(__file__).with_name(filename))==receipt[key]
    for name,entry in prior_receipt['source_inventory_before_after'].items():
        path=Path(entry['path'])
        assert path.stat().st_size==entry['bytes'] and sha(path)==entry['sha256'],name
        assert receipt['source_inventory_before_after'][name]=={k:entry[k] for k in ('bytes','sha256')}
    rows=csv_rows(run/'matched-predictions.csv');prior_rows={r['game_id']:r for r in csv_rows(PRIOR/'matched-predictions.csv')}
    assert len(rows)==len({r['game_id'] for r in rows})==2127
    assert {r['game_id'] for r in rows}==set(prior_rows)
    assert set(receipt['arms'])==set(ARMS)
    for row in rows:
        old=prior_rows[row['game_id']]
        for k in ('season','week','kickoff','actual_margin'):
            assert row[k]==old[k],(row['game_id'],k)
        for key,oldkey in (('reference4','starter_recency'),('prior_raw','raw'),('prior_starter','starter'),
                           ('pgo_v0','pgo_v0'),('constant','constant')):
            assert math.isclose(float(row[key]),float(old[oldkey]),abs_tol=1e-12,rel_tol=0)
    fits=read(run/'fold-fits.json');prior_fits=read(PRIOR/'fold-fits.json')['starter_recency']
    assert fits['reference4']==prior_fits
    for arm in ARMS:
        assert len(fits[arm])==9
        for i,fit in enumerate(fits[arm]):
            reference=fits['reference4'][i];training=fit['training'];validation=fit['validation']
            assert training['game_ids']==reference['training']['game_ids']
            assert validation==reference['validation']
            assert training['count']==len(training['game_ids'])==len(set(training['game_ids']))
            assert not set(training['game_ids'])&set(validation['game_ids'])
            if i<8:
                season=fit['evaluation_season'];assert season==2018+i
                assert max(int(g.split('_')[0]) for g in training['game_ids'])<season
                assert all(int(g.split('_')[0])==season for g in validation['game_ids'])
            else:
                assert training['count']==3407 and fit['fit']=='final_2013_2025'
            assert fit['parameters']=={'half_life_games':8 if arm=='active8_clean' else 4,
                                        'alpha':200.0 if arm=='active4_symmetric' else 100.0,'delta':1.0}
            if arm=='active4_symmetric':
                assert training['augmented_row_count']==2*training['unique_game_count']==2*training['count']
                assert fit['symmetry_invariants']['passed']

    numeric_checks=0
    max_difference=0.0
    def compare(actual,expected,path=''):
        nonlocal numeric_checks,max_difference
        if isinstance(expected,dict):
            assert set(actual)==set(expected),path
            for k in expected:compare(actual[k],expected[k],path+'/'+k)
        elif isinstance(expected,list):
            assert len(actual)==len(expected),path
            for i,(a,b) in enumerate(zip(actual,expected)):compare(a,b,path+'/'+str(i))
        elif isinstance(expected,(int,float)) and not isinstance(expected,bool):
            assert isinstance(actual,(int,float)) and math.isfinite(actual),path
            error=abs(actual-expected);max_difference=max(max_difference,error);numeric_checks+=1
            assert error<=TOLERANCE,(path,actual,expected)
        else:assert actual==expected,(path,actual,expected)
    saved=read(run/'metrics.json');calculated={name:views(rows,name) for name in (*BASELINES,*ARMS)}
    compare(saved['metrics'],calculated,'metrics')
    controls={'active4':'reference4','active4_clean':'active4','active8_clean':'active4_clean',
              'active4_compact':'active4_clean','active4_exposure':'active4_clean','active4_symmetric':'active4_clean'}
    boot={};screens={}
    for arm,control in controls.items():
        boot[arm]={f'vs_{key}':bootstrap(rows,arm,key) for key in ('reference4',control)}
        old=calculated['reference4'];new=calculated[arm]
        wins=sum(a['mae']<b['mae'] for a,b in zip(new['seasons'],old['seasons']))
        checks={'pooled_mae_improves':new['overall']['mae']<old['overall']['mae'],
                'interval_vs_reference_above_zero':boot[arm]['vs_reference4']['lower']>0,
                'at_least_five_seasons_improve':wins>=5,
                'weeks_1_4_not_worse':new['weeks_1_4']['mae']<=old['weeks_1_4']['mae']}
        screens[arm]={'season_mae_wins':wins,'checks':checks,
                     'merits_future_prospective_comparison':all(checks.values()),'promotion_status':'HOLD'}
    compare(saved['paired_bootstrap'],boot,'bootstrap');compare(saved['screening'],screens,'screens')

    details=read(run/'rating-details.json');assert len(details)==32*len(ARMS)
    detailmap={(r['variant'],r['team']):r for r in details};assert len(detailmap)==len(details)
    prior_details={r['team']:r for r in read(PRIOR/'rating-details.json') if r['variant']=='starter_recency'}
    for team in TEAMS:
        assert {k:v for k,v in detailmap['reference4',team].items() if k!='variant'}=={
            k:v for k,v in prior_details[team].items() if k!='variant'}
    ratings=csv_rows(run/'ratings.csv');ratingmap={r['team']:r for r in ratings};assert set(ratingmap)==set(TEAMS)
    contribution_error=0.0
    for arm in ARMS:
        final=fits[arm][-1];p=final['preprocessor'];names=p['feature_names']+[k+'_missing' for k in p['missing_features']]
        armrows=[detailmap[arm,t] for t in TEAMS]
        features=[{**r['features'],'home_field':0.0,'rest_difference':0.0} for r in armrows]
        x=transform(features,final);raw=final['coefficients'][0]+x@np.array(final['coefficients'][1:]);centered=raw-raw.mean()
        terms=(x-x.mean(axis=0))*np.array(final['coefficients'][1:])
        ranks={TEAMS[i]:rank for rank,i in enumerate(sorted(range(32),key=lambda i:(-centered[i],TEAMS[i])),1)}
        for i,row in enumerate(armrows):
            assert abs(centered[i]-row['rating'])<=TOLERANCE
            assert row['rank']==ranks[row['team']]==int(ratingmap[row['team']][arm+'_rank'])
            assert abs(float(ratingmap[row['team']][arm+'_rating'])-row['rating'])<=TOLERANCE
            assert set(row['centered_contributions'])==set(names)
            for name,value in zip(names,terms[i]):
                error=abs(value-row['centered_contributions'][name]);contribution_error=max(contribution_error,error)
                assert error<=TOLERANCE
            assert abs(math.fsum(row['centered_contributions'].values())-row['rating'])<=TOLERANCE

    # All current inputs in symmetric and clean arms must match; coefficient
    # changes are then attributable to the declared fitting constraint.
    for t in TEAMS:
        assert detailmap['active4_symmetric',t]['features']==detailmap['active4_clean',t]['features']
    symmetry=[]
    for fold in fits['active4_symmetric']:
        p=fold['preprocessor'];names=p['feature_names'];pairs=[]
        for a in TEAMS:
            for b in TEAMS:
                pairs.append(neutral_difference(detailmap['active4_symmetric',a]['features'],
                                                detailmap['active4_symmetric',b]['features'],names))
        largest=0.0
        patterns=[set(),*({n} for n in names),set(names)]
        for pattern in patterns:
            positive=[{k:None if k in pattern else v for k,v in row.items()} for row in pairs]
            negative=[{k:None if v is None else -v for k,v in row.items()} for row in positive]
            residual=np.abs(predict(positive,fold)+predict(negative,fold))
            largest=max(largest,float(residual.max()))
        assert largest<=1e-8
        symmetry.append({'training_through':fold['training']['season_max'],
                         'team_pairs':1024,'missing_patterns':len(patterns),'maximum_swap_sum':largest})

    ne_changes={}
    baseline=detailmap['active4_clean','NE']
    for arm in ('reference4','active4','active8_clean','active4_compact','active4_exposure','active4_symmetric'):
        candidate=detailmap[arm,'NE'];keys=set(candidate['centered_contributions'])|set(baseline['centered_contributions'])
        terms={k:candidate['centered_contributions'].get(k,0)-baseline['centered_contributions'].get(k,0) for k in keys}
        ne_changes[arm]={'control':'active4_clean','rank':candidate['rank'],'rating':candidate['rating'],
                         'control_rank':baseline['rank'],'control_rating':baseline['rating'],
                         'rating_delta':candidate['rating']-baseline['rating'],
                         'largest_term_deltas':sorted(terms.items(),key=lambda kv:-abs(kv[1]))[:10]}
        assert abs(math.fsum(terms.values())-(candidate['rating']-baseline['rating']))<TOLERANCE

    # Recheck immutable reads after verification, including actual configured
    # source paths rather than assuming the cache inventory was unchanged.
    manifest(run);manifest(PRIOR,PRIOR_SHA);manifest(SNAPSHOT,SNAPSHOT_SHA)
    for name,entry in prior_receipt['source_inventory_before_after'].items():assert sha(entry['path'])==entry['sha256']
    for name,digest in receipt['code_sha256'].items():assert sha(ROOT/name)==digest
    result={'status':'PASS','run_manifest_sha256':sha(run/'manifest.json'),
            'verifier_sha256':sha(Path(__file__)),'no_fit_or_evaluator_helpers':True,
            'games':2127,'arms':list(ARMS),'manifest_members':len(members['files']),
            'sources_verified':len(prior_receipt['source_inventory_before_after']),
            'numeric_metric_bootstrap_checks':numeric_checks,'maximum_metric_bootstrap_difference':max_difference,
            'maximum_contribution_difference':contribution_error,'current_ratings_verified':224,
            'fold_reference_and_chronology':'PASS','symmetry_checks':symmetry,
            'NE_changes_against_active4_clean':ne_changes,
            'promotion_status':'HOLD','historical_source_vintage':'REVIEW REQUIRED'}
    with output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2,sort_keys=True,allow_nan=False)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,default=DEFAULT_RUN)
    parser.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    args=parser.parse_args()
    result=verify(args.run,args.output)
    print(json.dumps({k:v for k,v in result.items() if k not in ('NE_changes_against_active4_clean','symmetry_checks')},indent=2))
