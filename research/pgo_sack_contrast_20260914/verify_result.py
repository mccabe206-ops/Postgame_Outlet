"""Read-only independent verification. No model import and no fitting."""
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ARM = 'sack_contrast4'
Q, T = 'qb_sack_avoidance', 'sack_avoidance_rate'


def require(value, message):
    if not value: raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def verify_manifest(folder, expected):
    require(sha(folder/'manifest.json') == expected, 'Manifest changed')
    for name, meta in read(folder/'manifest.json')['files'].items():
        require(Path(name).name == name and sha(folder/name) == meta['sha256']
                and (folder/name).stat().st_size == meta['bytes'], 'Manifest member changed: '+name)


def coefficients(fit):
    p = fit['preprocessor']; beta = list(fit['coefficients'][1:])
    q,t = p['feature_names'].index(Q),p['feature_names'].index(T)
    if 'transformation' in fit:
        common,contrast=beta[q],beta[t]
        beta[q]=(common+contrast/2)/math.sqrt(2)
        beta[t]=(common-contrast/2)/math.sqrt(2)
    return beta


def raw_prediction(row, fit):
    # Reconstruct the original raw-feature basis, never candidate.transform.
    p=fit['preprocessor']; beta=coefficients(fit)
    terms=[fit['coefficients'][0]]
    for name,median,scale,b in zip(p['feature_names'],p['medians'],p['scales'],beta):
        value=row['features'][name]
        if value is not None: terms.append((value-median)*(b/scale))
    terms += [beta[len(p['feature_names'])+i] for i,name in enumerate(p['missing_features'])
              if row['features'][name] is None]
    return math.fsum(terms)


def summary(rows,key):
    actual=[r['actual_margin'] for r in rows]; predictions=[r[key] for r in rows]
    errors=[b-a for a,b in zip(actual,predictions)]
    decisions=sum(a!=0 for a in actual)
    correct=sum(a*b>0 for a,b in zip(actual,predictions) if a!=0)
    return dict(count=len(rows),mae=math.fsum(map(abs,errors))/len(rows) if rows else None,
                rmse=math.sqrt(math.fsum(e*e for e in errors)/len(rows)) if rows else None,
                bias_predicted_minus_actual=math.fsum(errors)/len(rows) if rows else None,
                winner=dict(correct=correct,denominator=decisions,accuracy=correct/decisions if decisions else None,
                            actual_ties=sum(a==0 for a in actual),predicted_ties=sum(p==0 for p in predictions)))


def compare(actual,expected):
    require(type(actual) is type(expected) or isinstance(actual,(int,float)) and isinstance(expected,(int,float)),
            'Metric type differs')
    if isinstance(actual,dict):
        require(set(actual)==set(expected),'Metric keys differ')
        for key in actual: compare(actual[key],expected[key])
    elif isinstance(actual,(int,float)):
        require(math.isfinite(actual) and math.isfinite(expected) and abs(actual-expected)<=1e-10,'Metric number differs')
    else: require(actual==expected,'Metric value differs')


def percentile(sorted_values,q):
    index=(len(sorted_values)-1)*q
    lower=math.floor(index); upper=math.ceil(index)
    return sorted_values[lower]*(upper-index)+sorted_values[upper]*(index-lower) if lower!=upper else sorted_values[lower]


def main():
    prep=HERE/'preflight-attempt02'; run=HERE/'run-attempt01'
    verify_manifest(prep,'02d9fad8015c64203c329079394cb28b9eced94f597d577d697c3e16efd53bb1')
    verify_manifest(run,'b402573ba466c571fd826d77c67a27fae548c6231cf0fb46c4be0ea6437f6786')
    preflight=read(prep/'preflight.json'); receipt=read(run/'run-receipt.json')
    for pin in preflight['protected_pins']:
        require(sha(pin['path'])==pin['sha256'] and Path(pin['path']).stat().st_size==pin['bytes'],'Protected source changed')
    rows=read(run/'matched-predictions.json'); result=read(run/'metrics.json')
    original=read(ROOT/'research/pgo_postseason_candidate/run-20260909-attempt01/historical-features.json')
    baseline=read(ROOT/'research/pgo_postseason_candidate/run-20260909-attempt01/fold-fits.json')
    by_id={r['game_id']:r for r in original}; saved={r['game_id']:r for r in rows}
    require(len(by_id)==len(original)==3407 and len(saved)==len(rows)==2127,'Original or evaluated cohort differs')
    reports=read(run/'coefficient-report.json'); drifts={'candidate':[],'control':[]}
    errors=[]; all_ids=[]; final_replay=[]
    for index,label in enumerate([str(s) for s in range(2018,2026)]+['final']):
        fit=read(run/f'fit-{label}.json'); bound=preflight['folds'][index]
        start=read(run/f'fit-{label}-start.json')
        require(start['fit_call_number']==index+1 and fit['training_ids']==bound['training_ids']
                and fit['test_ids']==bound['test_ids'] and fit['preprocessor']==baseline[index]['preprocessor'],
                'Fit identity or cohort differs')
        require(fit['transformation']==bound['transformation'],'Transformation differs')
        require(fit['parameters']==dict(alpha=200.,delta=1.,max_iter=50,tolerance=1e-8,unpenalized_intercept=True),
                'Optimizer parameters differ')
        for key in fit['test_ids']:
            errors.append(abs(raw_prediction(by_id[key],fit)-saved[key][ARM]))
            errors.append(abs(raw_prediction(by_id[key],baseline[index])-saved[key]['control']))
        all_ids.extend(fit['test_ids'])
        for arm,model in (('candidate',fit),('control',baseline[index])):
            names=model['preprocessor']['feature_names']; betas=coefficients(model)
            raw={name:betas[i]/model['preprocessor']['scales'][i] for i,name in enumerate(names)}
            compare(raw,reports[index][arm]['effective_raw_coefficients'])
            compare(dict(zip(names,betas)),reports[index][arm]['standardized_original_coefficients'])
            compare(dict(zip(model['preprocessor']['missing_features'],betas[len(names):])),
                    reports[index][arm]['missing_indicator_terms'])
            delta=.01*(raw[Q]-raw[T]); compare(delta,reports[index][arm]['pair_d_per_percentage_point'])
            if label!='final': drifts[arm].append(delta)
        if label=='final':
            final_replay=[raw_prediction(row,fit) for row in original]
            require(all(math.isfinite(x) for x in final_replay),'Nonfinite final fit replay')
    require(len(all_ids)==len(set(all_ids))==2127 and set(all_ids)==set(saved),'Evaluation membership differs')
    require(max(errors)<=1e-10,'Independent raw-basis replay differs')
    require(len(list(run.glob('fit-*-start.json')))==9 and receipt['executed_candidate_fits']==9,'Fit call count differs')
    views=0
    for key,metrics in result['metrics'].items():
        subsets={'overall':rows,'week_1':[r for r in rows if r['week']==1],
                 'weeks_1_4':[r for r in rows if 1<=r['week']<=4],
                 'weeks_5_18':[r for r in rows if 5<=r['week']<=18],
                 'large_predicted_margin_abs_ge_7':[r for r in rows if abs(r[key])>=7],
                 'neutral_site':[r for r in rows if r['neutral_site']]}
        for name,subset in subsets.items(): compare(summary(subset,key),metrics[name]); views+=1
        for season in metrics['seasons']:
            compare({'season':season['season'],**summary([r for r in rows if r['season']==season['season']],key)},season)
            views+=1
        for team in metrics['teams']:
            subset=[]
            for row in rows:
                if row['home_team']==team['team']: subset.append(row)
                elif row['away_team']==team['team']:
                    subset.append({**row,'actual_margin':-row['actual_margin'],key:-row[key]})
            compare({'team':team['team'],**summary(subset,key)},team); views+=1
    # Same declared RNG, independent season aggregation and quantile arithmetic.
    blocks=[[abs(r['actual_margin']-r['control'])-abs(r['actual_margin']-r[ARM])
             for r in rows if r['season']==season] for season in range(2018,2026)]
    sums=[math.fsum(block) for block in blocks]; counts=list(map(len,blocks))
    draws=np.random.default_rng(20260914).integers(0,8,size=(10000,8))
    distribution=sorted(math.fsum(sums[int(i)] for i in draw)/sum(counts[int(i)] for i in draw) for draw in draws)
    interval=dict(mean=math.fsum(sums)/sum(counts),lower=percentile(distribution,.025),
                  upper=percentile(distribution,.975),blocks=8,samples=10000,seed=20260914)
    compare(interval,result['paired_season_block_bootstrap'])
    stability={arm+'_drift':math.fsum(abs(a-b) for a,b in zip(values,values[1:]))/7 for arm,values in drifts.items()}
    compare(stability,result['coefficient_stability'])
    wins=sum(math.fsum(block)>0 for block in blocks)
    primary=interval['mean']>=.05 and wins>=5 and interval['lower']>0
    stable=stability['candidate_drift']<=stability['control_drift']+1e-12
    require(result['further_study_screen']['primary_screen_passed']==primary
            and result['further_study_screen']['stability_screen_passed']==stable
            and result['further_study_screen']['improved_seasons']==wins
            and result['further_study_screen']['status']==('PASS' if primary and stable else 'FAIL'),'Locked gate differs')
    evidence=dict(status='PASS',verified_at=datetime.now(timezone.utc).isoformat(),model_imports=0,model_fits=0,
                  protected_pins_verified=len(preflight['protected_pins']),evaluation_games=2127,
                  fit_calls_verified=9,final_training_predictions_checked=len(final_replay),
                  maximum_raw_basis_prediction_error=max(errors),metric_views_independently_verified=views,
                  bootstrap=interval,stability=stability,primary_screen_passed=primary,stability_screen_passed=stable,
                  further_study_screen='PASS' if primary and stable else 'FAIL',
                  historical_source_vintage='REVIEW REQUIRED',prospective_phase='NOT STARTED',
                  verifier_sha256=sha(__file__),run_manifest_sha256=sha(run/'manifest.json'))
    target=Path(sys.argv[1]) if len(sys.argv)>1 else None
    if target:
        with target.open('x',encoding='utf-8',newline='\n') as handle:
            json.dump(evidence,handle,indent=2,sort_keys=True,allow_nan=False); handle.write('\n')
    print(json.dumps(evidence,indent=2,sort_keys=True))


if __name__=='__main__': main()
