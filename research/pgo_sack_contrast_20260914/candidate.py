"""One sealed historical contrast experiment; no live inputs or serving hooks."""
import argparse
import copy
import csv
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import platform
import subprocess
import sys
import traceback

import numpy as np

from research.pgo_postseason_candidate import pinned_challenger as ch
from research.pgo_input_audit import audit_model as audit

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
BASE = ROOT / 'research/pgo_postseason_candidate/run-20260909-attempt01'
PUBLICATION = Path('D:/CodexWorktrees/Postgame_Outlet-publication-20260909/output')
DESIGN = PUBLICATION / 'overnight-20260914/weight-plan'
IDENTITY = 'pgo-qb-team-sack-contrast4-v1-20260914'
ARM = 'sack_contrast4'
Q, T = 'qb_sack_avoidance', 'sack_avoidance_rate'
CHARTER_SHA = '87004c8e946118a2f70c89d04d4aba8aecc5ab8a7e67cdfddb311bee2778e273'
DESIGN_SHA = '86a29440310dd3635a5dcd6d86bdf1db5be340959b6517037cfd334620f67d42'
FEATURE_SHA = '5b0aa4ac3d06ff37314c71984003651434f0df1cb2f17c6a74e7b26c44f20365'
PACKAGES = (
    (BASE, 'a58aeff835471182a555e4b926beafd0db01c7c5e3fe19827ddf56bd03f2514a'),
    (ROOT / 'research/pgo_weights_candidate_20260910/run-attempt01',
     '481d64fec1512934da21066c5a5c40b3f43dc4ad45ef7295d243948deba9e814'),
    (PUBLICATION / 'week2-readiness-20260914/weights',
     '9afafdc69b409bf0da5c18f9c8849d439f2e7dc7063545c4a688412429166bd6'),
)
LABELS = tuple(str(s) for s in range(2018, 2026)) + ('final',)


def require(condition, message):
    if not condition: raise ValueError(message)


def raw_json(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()


def write(path, value):
    with Path(path).open('xb') as out: out.write(value if isinstance(value, bytes) else raw_json(value))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pin(path):
    path = Path(path).resolve()
    require(path.is_file() and not path.is_symlink(), 'Missing or linked source: ' + str(path))
    return dict(path=str(path), sha256=sha(path), bytes=path.stat().st_size)


def clock(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(parsed.tzinfo is not None, 'Missing timestamp zone')
    return parsed


def finite(value):
    return type(value) in (float, int) and math.isfinite(value)


def validate_rows(rows, names):
    require(rows and len({r.game_id for r in rows}) == len(rows), 'Empty or duplicate rows')
    for row in rows:
        require(sorted(row.features) == list(names), 'Feature inventory differs')
        require(type(row.season) is int and 2013 <= row.season <= 2025, 'Unplanned season')
        require(finite(row.actual_margin), 'Invalid target')
        require(all(v is None or finite(v) for v in row.features.values()), 'Invalid feature value')


def preprocessor(meta):
    names, missing = meta['feature_names'], meta['missing_features']
    require(names == sorted(set(names)) and set(missing) <= set(names)
            and missing == [n for n in names if n in missing], 'Preprocessor inventory differs')
    require(len(meta['medians']) == len(meta['scales']) == len(names), 'Preprocessor lengths differ')
    require(all(finite(v) for v in meta['medians']), 'Invalid saved medians')
    require(all(finite(v) and v > 0 for v in meta['scales']), 'Invalid saved scales')
    return ch.Preprocessor(tuple(names), np.asarray(meta['medians']), np.asarray(meta['scales']), tuple(missing))


def metadata(pp):
    return dict(feature_names=list(pp.feature_names), medians=pp.medians.tolist(),
                scales=pp.scales.tolist(), missing_features=list(pp.missing_features))


def reconstructed(rows, training_ids, names):
    by_id = {r.game_id:r for r in rows}
    require(len(by_id) == len(rows) and len(set(training_ids)) == len(training_ids), 'Duplicate training IDs')
    training = [by_id[key] for key in training_ids]
    validate_rows(training, names)
    return metadata(ch.fit_preprocessor(audit.symmetric_rows(training), names))


def transformation(meta):
    names = meta['feature_names']
    require(Q in names and T in names, 'Missing contrast pair')
    return dict(name=ARM, feature_names=list(names), missing_features=list(meta['missing_features']),
                common_slot=Q, contrast_slot=T, contrast_factor=2., restandardize=False,
                pair_matrix=[[1/math.sqrt(2), 1/math.sqrt(2)],
                             [1/(2*math.sqrt(2)), -1/(2*math.sqrt(2))]])


def transform(matrix, meta, declaration):
    require(declaration == transformation(meta), 'Transformation inventory or specification differs')
    names = meta['feature_names']
    x = np.asarray(matrix, dtype=float)
    require(x.ndim == 2 and x.shape[1] == len(names)+len(meta['missing_features'])
            and np.isfinite(x).all(), 'Invalid standardized matrix')
    q, t = names.index(Q), names.index(T)
    output = x.copy()
    output[:, q] = (x[:, q] + x[:, t]) / math.sqrt(2)
    output[:, t] = (x[:, q] - x[:, t]) / (2*math.sqrt(2))
    return output


def replay(rows, fit):
    """Scalar serialized replay, independent of NumPy preprocessing/transform."""
    p = fit['preprocessor']; preprocessor(p)
    changed = 'transformation' in fit
    if changed: require(fit['transformation'] == transformation(p), 'Serialized transformation differs')
    names = p['feature_names']; q, t = names.index(Q), names.index(T)
    beta = fit['coefficients']
    require(len(beta) == 1+len(names)+len(p['missing_features']) and all(finite(v) for v in beta),
            'Invalid serialized coefficients')
    values = []
    for row in rows:
        x = [0. if row.features[name] is None else (row.features[name]-median)/scale
             for name, median, scale in zip(names, p['medians'], p['scales'])]
        if changed:
            x[q], x[t] = (x[q]+x[t])/math.sqrt(2), (x[q]-x[t])/(2*math.sqrt(2))
        x += [float(row.features[name] is None) for name in p['missing_features']]
        values.append(math.fsum([beta[0], *(a*b for a,b in zip(x, beta[1:]))]))
    require(all(finite(v) for v in values), 'Nonfinite replay')
    return values


def symmetry(fit, row):
    names = fit['preprocessor']['feature_names']
    zero = replace(row, features={name:0. for name in names}, actual_margin=0.)
    probes = []
    for missing in ((), (Q,), (T,), (Q,T), tuple(fit['preprocessor']['missing_features'])):
        features = dict(row.features)
        for name in missing: features[name] = None
        probe = replace(row, features=features)
        probes.extend(audit.symmetric_rows([probe]))
    predictions = replay(probes, fit)
    values = dict(neutral_self_absolute=abs(replay([zero], fit)[0]),
                  maximum_reversal_absolute=max(abs(a+b) for a,b in zip(predictions[::2], predictions[1::2])))
    values.update(tolerance=1e-8, passed=all(v <= 1e-8 for v in values.values()))
    require(values['passed'], 'Symmetry check failed')
    return values


def protected():
    require(sha(DESIGN/'proposed-charter.md') == CHARTER_SHA, 'Sealed charter differs')
    require(sha(DESIGN/'manifest.json') == DESIGN_SHA, 'Sealed design manifest differs')
    pins = [pin(DESIGN/'manifest.json')]
    # Preserve the original design package, including its already reviewed source pins.
    design = json.loads((DESIGN/'manifest.json').read_bytes())
    for old in design['files'] + design['source_pins']:
        actual = pin(old['path'])
        require(actual == old, 'Sealed design source differs: ' + old['path'])
        pins.append(actual)
    packages = []
    for directory, expected in PACKAGES:
        require(sha(directory/'manifest.json') == expected, 'Protected manifest differs')
        manifest = json.loads((directory/'manifest.json').read_bytes())
        pins.append(pin(directory/'manifest.json'))
        for name, member in manifest['files'].items():
            path = (directory/name).resolve()
            require(path.is_relative_to(directory.resolve()) and not path.is_symlink(), 'Unsafe package member')
            actual = pin(path)
            require(actual['sha256'] == member['sha256'] and actual['bytes'] == member['bytes'],
                    'Protected package member differs: ' + str(path))
            pins.append(actual)
        packages.append(dict(directory=str(directory), manifest_sha256=expected, members=len(manifest['files'])))
    require(sha(BASE/'historical-features.json') == FEATURE_SHA, 'Historical feature bytes differ')
    # The helper is bound to the historical fit package, not merely today's checkout.
    old = json.loads((BASE/'run-start.json').read_bytes())['code_and_issued_sha256']
    for name in ('pgo_opponent_evaluation.py', 'research/pgo_postseason_candidate/pinned_challenger.py'):
        matches = [value for key,value in old.items()
                   if key.replace('\\', '/') == name or key.replace('\\', '/').endswith('/'+name)]
        require(len(matches) == 1 and sha(ROOT/name) == matches[0], 'Inherited helper changed: ' + name)
    for module in tuple(sys.modules.values()):
        location = getattr(module, '__file__', None)
        if location and Path(location).resolve().is_relative_to(ROOT) and str(location).endswith('.py'):
            pins.append(pin(location))
    pins += [pin(HERE/'candidate.py'), pin(ROOT/'tests/test_pgo_sack_contrast.py')]
    return list({p['path']:p for p in pins}.values()), packages


def environment():
    return dict(python=platform.python_version(), numpy=np.__version__, executable=str(Path(sys.executable).resolve()),
                platform=platform.platform(), machine=platform.machine())


def load_inputs():
    rows = [ch.FeatureRow(**r) for r in json.loads((BASE/'historical-features.json').read_bytes())]
    fits = json.loads((BASE/'fold-fits.json').read_bytes())
    names = sorted(rows[0].features)
    validate_rows(rows, names)
    require(len(rows) == 3407 and len(names) == 24 and len(fits) == 9, 'Cohort or fit count differs')
    matched = list(csv.DictReader(io.StringIO((BASE/'matched-predictions.csv').read_text())))
    require(len(matched) == len({r['game_id'] for r in matched}) == 2127, 'Matched control count differs')
    return rows, fits, matched


def preflight_checks():
    pins, packages = protected()
    rows, fits, matched = load_inputs()
    by_id = {r.game_id:r for r in rows}; saved = {r['game_id']:r for r in matched}
    names = sorted(rows[0].features); maximum_pp = maximum_control = 0.
    fold_table, ids = [], []
    for index, fit in enumerate(fits):
        season = 2018+index if index < 8 else None
        require(fit.get('evaluation_season') == season, 'Evaluation season differs')
        train = fit['training']['game_ids']; test = fit['validation']['game_ids']
        require(train == [r.game_id for r in rows if season is None or r.season < season]
                and test == ([] if season is None else [r.game_id for r in rows if r.season == season]),
                'Locked fold membership or order differs')
        require(len(train) == fit['training']['count'] and len(train)*2 == fit['training']['augmented_row_count'],
                'Mirrored training count differs')
        require(fit['parameters'] == dict(alpha=200., delta=1., half_life_games=4), 'Inherited parameters differ')
        pp = preprocessor(fit['preprocessor'])
        reconstructed_pp = reconstructed(rows, train, names)
        require(reconstructed_pp['feature_names'] == fit['preprocessor']['feature_names']
                and reconstructed_pp['missing_features'] == fit['preprocessor']['missing_features'], 'Training inventory differs')
        difference = max(abs(a-b) for key in ('medians','scales')
                         for a,b in zip(reconstructed_pp[key], fit['preprocessor'][key]))
        require(difference <= 1e-12, 'Training-only preprocessor differs')
        maximum_pp = max(maximum_pp, difference)
        if test:
            require(max(clock(by_id[k].kickoff) for k in train) < min(clock(by_id[k].kickoff) for k in test),
                    'Chronological split overlap')
            require(len(test) == (256,256,256,272,271,272,272,272)[index], 'Test count differs')
            testing = [by_id[k] for k in test]
            control = replay(testing, fit)
            for row, prediction in zip(testing, control):
                old = saved[row.game_id]
                require((row.season,row.week,row.kickoff,row.actual_margin) ==
                        (int(old['season']),int(old['week']),old['kickoff'],float(old['actual_margin'])), 'Control identity differs')
                maximum_control = max(maximum_control, abs(prediction-float(old['candidate'])))
            require(maximum_control <= 1e-10, 'Saved control replay differs')
            ids.extend(test)
        symmetry(fit, by_id[train[0]])
        fold_table.append(dict(label=LABELS[index], evaluation_season=season,
                               training_ids=train, test_ids=test, preprocessor=fit['preprocessor'],
                               transformation=transformation(fit['preprocessor']),
                               training_preprocessor_maximum_error=difference))
    require(len(ids) == len(set(ids)) == 2127 and set(ids) == set(saved), 'Evaluation IDs differ')
    require(all(pin(p['path']) == p for p in pins), 'Protected input changed during preflight')
    return dict(identity=IDENTITY, status='PREFLIGHT PASS / NO CANDIDATE FITS', environment=environment(),
                protected_pins=pins, packages=packages, original_games=3407, evaluation_games=2127,
                evaluation_folds=8, final_historical_fits=1, maximum_control_replay_error=maximum_control,
                maximum_preprocessor_error=maximum_pp, planned_candidate_fits=9, executed_candidate_fits=0,
                folds=fold_table, historical_source_vintage='REVIEW REQUIRED',
                prospective_phase='NOT STARTED', charter_sha256=CHARTER_SHA)


def seal(output):
    files = {p.name:dict(sha256=sha(p), bytes=p.stat().st_size) for p in sorted(output.iterdir())
             if p.is_file() and p.name != 'manifest.json'}
    write(output/'manifest.json', dict(identity=IDENTITY, files=files))


def prepare(output):
    output = Path(output).resolve(); output.mkdir(parents=True, exist_ok=False)
    write(output/'start.json', dict(started_at=datetime.now(timezone.utc).isoformat(), operation='PREFLIGHT_NO_FIT'))
    try:
        result = preflight_checks()
        tests = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'tests.test_pgo_sack_contrast'],
                               cwd=ROOT, capture_output=True)
        write(output/'tests.log', tests.stdout+tests.stderr)
        require(tests.returncode == 0, 'No-fit tests failed')
        write(output/'charter.md', (DESIGN/'proposed-charter.md').read_bytes())
        write(output/'candidate.used.py.txt', Path(__file__).read_bytes())
        write(output/'tests.used.py.txt', (ROOT/'tests/test_pgo_sack_contrast.py').read_bytes())
        write(output/'preflight.json', result)
        seal(output)
        print(json.dumps(dict(status=result['status'], protected_pins=len(result['protected_pins']),
                              maximum_control_replay_error=result['maximum_control_replay_error'],
                              maximum_preprocessor_error=result['maximum_preprocessor_error'],
                              output=str(output), manifest_sha256=sha(output/'manifest.json'))), flush=True)
    except BaseException:
        write(output/'failure.json', dict(failed_at=datetime.now(timezone.utc).isoformat(), traceback=traceback.format_exc(),
                                         candidate_fits=0))
        seal(output)
        raise


def fit_once(label, x, y, called):
    require(label in LABELS and label not in called and len(called) < 9, 'Unplanned or repeated fit')
    require(label == LABELS[len(called)], 'Fit order differs')
    called.add(label)
    return ch.fit_huber_ridge(x, y, alpha=200., delta=1., max_iter=50, tolerance=1e-8)


def coefficient_report(fit, probes):
    p = fit['preprocessor']; names = p['feature_names']; beta = list(fit['coefficients'][1:])
    q,t = names.index(Q),names.index(T)
    if 'transformation' in fit:
        beta[q],beta[t] = (beta[q]+beta[t]/2)/math.sqrt(2), (beta[q]-beta[t]/2)/math.sqrt(2)
    raw = {name:beta[i]/p['scales'][i] for i,name in enumerate(names)}
    x = preprocessor(p).transform(probes)
    common = (x[:,q]+x[:,t])/math.sqrt(2); contrast = (x[:,q]-x[:,t])/(2*math.sqrt(2))
    if 'transformation' in fit:
        common_beta, contrast_beta = fit['coefficients'][q+1], fit['coefficients'][t+1]
    else:
        common_beta = (beta[q]+beta[t])/math.sqrt(2)
        contrast_beta = math.sqrt(2)*(beta[q]-beta[t])
    return dict(intercept=fit['coefficients'][0], effective_raw_coefficients=raw,
                standardized_original_coefficients=dict(zip(names,beta)),
                missing_indicator_terms=dict(zip(p['missing_features'],beta[len(names):])),
                pair_d_per_percentage_point=.01*(raw[Q]-raw[T]),
                pair_signs={name:int(np.sign(raw[name])) for name in (Q,T)},
                common_coefficient=common_beta, contrast_coefficient=contrast_beta,
                common_contribution_mean=float(np.mean(common*common_beta)),
                common_contribution_mean_absolute=float(np.mean(np.abs(common*common_beta))),
                contrast_contribution_mean=float(np.mean(contrast*contrast_beta)),
                contrast_contribution_mean_absolute=float(np.mean(np.abs(contrast*contrast_beta))),
                contribution_games=len(probes), sample_sizes={name:sum(r.features[name] is not None for r in probes) for name in (Q,T)})


def screen(metrics, interval, stability):
    baseline, candidate = metrics['control'], metrics[ARM]
    improvement = baseline['overall']['mae']-candidate['overall']['mae']
    a,b = candidate['seasons'],baseline['seasons']
    require([v['season'] for v in a] == [v['season'] for v in b] == list(range(2018,2026)), 'Screen seasons differ')
    season_wins = sum(x['mae'] < y['mae'] for x,y in zip(a,b))
    checks = dict(improvement_at_least_005=improvement >= .05, at_least_five_seasons=season_wins >= 5,
                  positive_interval_lower=interval['lower'] > 0)
    stable = stability['candidate_drift'] <= stability['control_drift']+1e-12
    return dict(status='PASS' if all(checks.values()) and stable else 'FAIL', checks=checks,
                pooled_improvement=improvement, improved_seasons=season_wins,
                primary_screen_passed=all(checks.values()), stability_screen_passed=stable,
                meaning='Further-study screen only; reused history and source vintage remain experimental')


def independent_metrics(rows, key):
    errors = [float(r[key])-float(r['actual_margin']) for r in rows]
    return dict(count=len(rows), mae=math.fsum(map(abs,errors))/len(rows),
                rmse=math.sqrt(math.fsum(e*e for e in errors)/len(rows)),
                bias_predicted_minus_actual=math.fsum(errors)/len(rows))


def run(output, prepared, expected):
    prepared=Path(prepared).resolve(); output=Path(output).resolve()
    require(sha(prepared/'manifest.json') == expected, 'Reviewed preflight manifest differs')
    for name, p in json.loads((prepared/'manifest.json').read_bytes())['files'].items():
        require(Path(name).name == name and sha(prepared/name) == p['sha256']
                and (prepared/name).stat().st_size == p['bytes'], 'Preflight member differs')
    preflight=json.loads((prepared/'preflight.json').read_bytes())
    require(preflight['identity'] == IDENTITY and preflight['executed_candidate_fits'] == 0, 'Wrong preflight')
    require(preflight['environment'] == environment(), 'Reviewed environment differs')
    require(all(pin(p['path']) == p for p in preflight['protected_pins']), 'Reviewed source changed')
    output.mkdir(parents=True, exist_ok=False)
    write(output/'run-start.json', dict(identity=IDENTITY, started_at=datetime.now(timezone.utc).isoformat(),
                                      preflight_manifest_sha256=expected, preflight_directory=str(prepared),
                                      planned_candidate_fits=9, environment=environment(), charter_sha256=CHARTER_SHA))
    called=set()
    try:
        # Re-audit without fitting; source and split failures consume no optimizer calls.
        check=preflight_checks()
        require(check == preflight, 'Preflight replay differs')
        originals, controls, saved = load_inputs(); by_id={r.game_id:r for r in originals}
        values={r['game_id']:{**{k:r[k] for k in ('game_id','kickoff','home_team','away_team')},
                             **{k:int(r[k]) for k in ('season','week')}, 'neutral_site':r['neutral_site']=='True',
                             'actual_margin':float(r['actual_margin']), 'control':float(r['candidate']),
                             **{k:float(r[k]) for k in ('corrected','pgo_v0','constant')}} for r in saved}
        reports=[]; max_replay=0.
        for index, bound in enumerate(preflight['folds']):
            label=bound['label']; training=[by_id[k] for k in bound['training_ids']]
            testing=[by_id[k] for k in bound['test_ids']]; mirrored=audit.symmetric_rows(training)
            pp=preprocessor(bound['preprocessor'])
            x=transform(pp.transform(mirrored),bound['preprocessor'],bound['transformation'])
            y=np.asarray([r.actual_margin for r in mirrored])
            write(output/f'fit-{label}-start.json', dict(label=label, started_at=datetime.now(timezone.utc).isoformat(),
                                                       original_training_games=len(training), mirrored_rows=len(mirrored),
                                                       fit_call_number=len(called)+1))
            print('Fitting sealed candidate '+label, flush=True)
            beta=fit_once(label,x,y,called)
            fitted=dict(identity=IDENTITY, label=label, evaluation_season=bound['evaluation_season'],
                        preprocessor=bound['preprocessor'], transformation=bound['transformation'], coefficients=beta.tolist(),
                        training_ids=bound['training_ids'], test_ids=bound['test_ids'],
                        parameters=dict(alpha=200., delta=1., max_iter=50, tolerance=1e-8, unpenalized_intercept=True))
            fitted['symmetry']=symmetry(fitted,training[0])
            write(output/f'fit-{label}.json',fitted)
            # Read actual serialized bytes before independent replay.
            restored=json.loads((output/f'fit-{label}.json').read_bytes()); probes=testing or training
            predictions=ch.predict(transform(pp.transform(probes),bound['preprocessor'],bound['transformation']),beta).tolist()
            replayed=replay(probes,restored)
            error=max(abs(a-b) for a,b in zip(predictions,replayed)); max_replay=max(max_replay,error)
            require(error <= 1e-10 and all(finite(v) for v in predictions), 'Candidate serialized replay differs')
            for row,value in zip(testing,predictions): values[row.game_id][ARM]=value
            reports.append(dict(label=label, evaluation_season=bound['evaluation_season'],
                                training_games=len(training), mirrored_rows=len(mirrored), test_games=len(testing),
                                contribution_scope='held_out_games' if testing else 'final_training_games_not_evaluation',
                                control=coefficient_report(controls[index],probes),
                                candidate=coefficient_report(restored,probes), maximum_serialized_replay_error=error))
        require(called == set(LABELS), 'Candidate fit count differs')
        matched=[values[r['game_id']] for r in saved]
        require(len(matched)==2127 and all(ARM in r for r in matched), 'Missing candidate predictions')
        write(output/'matched-predictions.json',matched)
        metrics={key:audit.metric_views(matched,key) for key in (ARM,'control','corrected','pgo_v0','constant')}
        interval=audit.base.season_block_bootstrap(matched,ARM,'control',samples=10000,seed=20260914)
        write(output/'coefficient-report.json',reports)
        stability={key+'_drift':math.fsum(abs(a[key]['pair_d_per_percentage_point']-b[key]['pair_d_per_percentage_point'])
                                         for a,b in zip(reports[:7],reports[1:8]))/7 for key in ('candidate','control')}
        result=dict(metrics=metrics, paired_season_block_bootstrap=interval, coefficient_stability=stability,
                    further_study_screen=screen(metrics,interval,stability))
        write(output/'metrics.json',result)
        # Independent stdlib arithmetic reads saved rows; no second fit or feature changes.
        reread=json.loads((output/'matched-predictions.json').read_bytes())
        verified={key:independent_metrics(reread,key) for key in metrics}
        require(all(abs(value-metrics[key]['overall'][field]) <= 1e-10
                    for key,row in verified.items() for field,value in row.items()), 'Independent metric replay differs')
        write(output/'independent-metrics.json',dict(status='PASS',overall=verified,method='stdlib math.fsum from saved predictions'))
        require(all(pin(p['path']) == p for p in preflight['protected_pins']), 'Protected source changed during run')
        write(output/'run-receipt.json',dict(identity=IDENTITY, status='EXPERIMENTAL / HOLD',
              completed_at=datetime.now(timezone.utc).isoformat(), executed_candidate_fits=len(called),
              evaluation_fits=8, final_historical_fits=1, evaluation_games=2127,
              maximum_serialized_replay_error=max_replay, protected_source_integrity='PASS',
              historical_source_vintage='REVIEW REQUIRED', prospective_phase='NOT STARTED',
              production_changed=False, further_study_screen=result['further_study_screen']))
        seal(output)
        print(json.dumps(dict(output=str(output), manifest_sha256=sha(output/'manifest.json'),
                              screen=result['further_study_screen'], stability=stability, interval=interval)),flush=True)
    except BaseException:
        write(output/'failure.json',dict(failed_at=datetime.now(timezone.utc).isoformat(),
                                         fit_calls_started=sorted(called),traceback=traceback.format_exc()))
        seal(output)
        raise


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='operation',required=True)
    prep=sub.add_parser('preflight'); prep.add_argument('--output',type=Path,required=True)
    fit=sub.add_parser('run'); fit.add_argument('--output',type=Path,required=True)
    fit.add_argument('--prepared',type=Path,required=True); fit.add_argument('--manifest-sha256',required=True)
    args=parser.parse_args()
    if args.operation=='preflight': prepare(args.output)
    else: run(args.output,args.prepared,args.manifest_sha256)
