"""Independent raw-schedule totals check; no production/evaluator function calls."""
from pathlib import Path
import csv,hashlib,json,math
from collections import defaultdict
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
RUN=ROOT/'research/pgo_input_audit/totals-20260908-corrected'
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
manifest=json.loads((RUN/'manifest.json').read_bytes())
for name,digest in manifest.items(): assert sha(RUN/name)==digest
receipt=json.loads((RUN/'metrics.json').read_bytes())
assert sha(ROOT/'research/pgo_input_audit/charter.md')==receipt['charter_sha256']=='4be3031146e6f7f58347a7139a8c249b5bbb40a69876b86547ddaca4b45f52fd'
assert sha(ROOT/'research/pgo_input_audit/check_totals.py')==receipt['code_sha256']
lock_path=ROOT/'research/pgo_v1/sources.lock.json'
assert sha(lock_path)=='3a7673ac4617d57954cb56954f2216226a358c7b187b1e3ce62994a6f2b3fd29'
lock=json.loads(lock_path.read_bytes())
entry=next(e for e in lock['sources'] if e['name']=='schedule_results')
recovery=json.loads((ROOT/'output/pgo-snapshot-review-20260907/public-fit-recovery/recovered-fit.json').read_bytes())
source=next(e for e in recovery['original_raw_sources'] if e['source']=='schedule_results')
schedule=Path(source['path'])
assert sha(schedule)==entry['sha256']==source['sha256']==receipt['schedule_sha256']
assert len(schedule.read_bytes())==entry['bytes']==source['bytes']
with schedule.open(newline='',encoding='utf-8') as stream: raw=list(csv.DictReader(stream))
ALIASES={'OAK':'LV','SD':'LAC','STL':'LAR','LA':'LAR','JAC':'JAX','WSH':'WAS'}

def independently_predict(raw):
    team_totals=defaultdict(list); league_totals=defaultdict(list); observed={}
    for row in raw:
        if row['game_type']!='REG' or not row['home_score'].strip() or not row['away_score'].strip(): continue
        game=row['game_id']
        if game in observed: raise ValueError('Duplicate raw game identity')
        year=int(row['season']); total=float(row['home_score'])+float(row['away_score'])
        home=ALIASES.get(row['home_team'],row['home_team']); away=ALIASES.get(row['away_team'],row['away_team'])
        observed[game]=(year,int(row['week']),home,away,total)
        team_totals[year,home].append(total);team_totals[year,away].append(total)
        league_totals[year].append(total)
    def avg(values): return math.fsum(values)/len(values)
    result={}
    for game,(year,week,home,away,total) in observed.items():
        if 2018<=year<=2025:
            result[game]=dict(game_id=game,season=year,week=week,home=home,away=away,actual_total=total,
                pf_pa_total=(avg(team_totals[year-1,home])+avg(team_totals[year-1,away]))/2,
                league_total=avg(league_totals[year-1]))
    return result
rows=independently_predict(raw)
assert len(rows)==2127
with (RUN/'predictions.csv').open(newline='') as stream: saved=list(csv.DictReader(stream))
assert len(saved)==2127 and {r['game_id'] for r in saved}==set(rows)
checks=0
for row in saved:
    expected=rows[row['game_id']]
    for key,value in expected.items():
        if isinstance(value,(int,float)):
            assert math.isclose(float(row[key]),value,rel_tol=0,abs_tol=1e-10),(row['game_id'],key)
        else: assert row[key]==value
        checks+=1
with (ROOT/'research/pgo_current_strength/run-20260908/matched-predictions.csv').open(newline='') as stream:
    matched=list(csv.DictReader(stream))
assert {r['game_id'] for r in matched}==set(rows)
views={'overall':list(rows.values()),'week_1':[r for r in rows.values() if r['week']==1],
       'weeks_1_4':[r for r in rows.values() if 1<=r['week']<=4],
       'weeks_5_18':[r for r in rows.values() if 5<=r['week']<=18]}
views.update({str(year):[r for r in rows.values() if r['season']==year] for year in range(2018,2026)})
for label,group in views.items():
    for arm in ('pf_pa_total','league_total'):
        errors=[r[arm]-r['actual_total'] for r in group]
        metrics=dict(count=len(group),mae=math.fsum(map(abs,errors))/len(group),
                     rmse=math.sqrt(math.fsum(e*e for e in errors)/len(group)),bias=math.fsum(errors)/len(group))
        for key,value in metrics.items():
            assert math.isclose(value,receipt['metrics'][label][arm][key],rel_tol=0,abs_tol=1e-10),(label,arm,key)
            checks+=1
sums=[];counts=[]
for year in range(2018,2026):
    group=views[str(year)]
    sums.append(math.fsum(abs(r['actual_total']-r['league_total'])-abs(r['actual_total']-r['pf_pa_total']) for r in group))
    counts.append(len(group))
draws=np.random.default_rng(20260908).integers(0,8,(10000,8))
weights=np.array([np.bincount(draw,minlength=8) for draw in draws])
distribution=(weights@np.array(sums))/(weights@np.array(counts))
bootstrap=dict(mean=math.fsum(sums)/sum(counts),lower=float(np.quantile(distribution,.025)),
               upper=float(np.quantile(distribution,.975)),blocks=8,samples=10000,seed=20260908)
for key,value in bootstrap.items():
    assert math.isclose(value,receipt['improvement_vs_league_total'][key],rel_tol=0,abs_tol=1e-10),key
assert bootstrap['mean']>0 and bootstrap['lower']<0<bootstrap['upper']
# Falsify accidental current-season use, for every evaluated year independently.
for year in range(2018,2026):
    changed=[{**r,'home_score':'99','away_score':'0'} if r['season']==str(year) else r for r in raw]
    perturbed=independently_predict(changed)
    affected=0
    for game,row in rows.items():
        if row['season']<=year:
            assert row['pf_pa_total']==perturbed[game]['pf_pa_total']
            assert row['league_total']==perturbed[game]['league_total']
        if row['season']==year and row['actual_total']!=perturbed[game]['actual_total']: affected+=1
    assert affected>0
first=next(r for r in raw if r['game_type']=='REG' and r['home_score'] and r['away_score'])
try: independently_predict(raw+[first])
except ValueError: pass
else: raise AssertionError('Independent duplicate rejection failed')
initial=ROOT/'research/pgo_input_audit/totals-20260908'
assert (initial/'predictions.csv').read_bytes()==(RUN/'predictions.csv').read_bytes()
old=json.loads((initial/'metrics.json').read_bytes())
assert old['metrics']==receipt['metrics']
assert old['improvement_vs_league_total']['seed']==20260907
assert math.isclose(old['improvement_vs_league_total']['mean'],-bootstrap['mean'],abs_tol=1e-10)
result=dict(status='PASS',raw_schedule_sha256=sha(schedule),source_lock_sha256=sha(lock_path),
    charter_sha256=receipt['charter_sha256'],code_sha256=receipt['code_sha256'],
    corrected_manifest_sha256=sha(RUN/'manifest.json'),game_count=len(rows),
    independently_recomputed_prediction_fields=checks,metric_views=len(views),improvement_control_minus_candidate=bootstrap,
    future_perturbations=dict(every_evaluated_season=True,changed_actuals_confirmed=True),
    duplicate_guard_meaningful=True,original_predictions_and_metrics_preserved=True,
    initial_bootstrap_superseded=dict(wrong_seed=20260907,reversed_direction=True),
    check_totals_or_evaluator_functions_called=False,
    findings=[],limits=['Historical source vintage remains REVIEW REQUIRED.','Totals-only verification does not validate exact scores, margins, or fixed-season strength.'])
Path(__file__).with_name('totals-independent-verification.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
