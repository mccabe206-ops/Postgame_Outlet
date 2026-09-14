"""Create immutable completed-week reviews from archived forecasts and finals."""
import argparse
import copy
import html
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

import pgo_ats
import pgo_market_benchmark
import pgo_season as season
import pgo_season_accuracy
from pgo_season_rollover import index, load_archive, source_bytes

FOLDER = 'docs/analysis/weekly'
PATTERN = r'docs/analysis/weekly/2026-week([1-9]|1[0-8])-final\.(html|json)'


def summarize_week(state, week):
    """Pure, metric-specific review; None until the exact scheduled week is final."""
    season.require(state['season'] == 2026 and type(week) is int and 1 <= week <= 18,
                   'Invalid weekly review season or week')
    schedule = index(state['schedule']); finals = index(state['results'])
    season.require(finals.keys() <= schedule.keys(), 'Unknown final game')
    for key, final in finals.items():
        season.require(final['week'] == schedule[key]['week'], 'Final week differs from schedule')
    expected = {key:g for key,g in schedule.items() if g['week'] == week}
    if not expected or not expected.keys() <= finals.keys():
        return None
    games = index([g for w in state['weeks'] for g in w['games'] if g['week'] == week])
    season.require(games.keys() == expected.keys() and all(season.identity(games[k], expected[k]) for k in games),
                   'Completed-week forecast inventory differs from schedule')
    selected = copy.deepcopy(state)
    selected.update(weeks=[dict(week=week, games=list(games.values()))],
                    schedule=list(expected.values()), results=[finals[k] for k in expected], accuracy_models=[])
    selected['ats'] = dict(state.get('ats') or {})
    for key in ('games', 'unavailable'):
        selected['ats'][key] = [g for g in selected['ats'].get(key, []) if g['game_id'] in expected]
    accuracy = pgo_season_accuracy.summarize(selected)['primary']
    market = pgo_market_benchmark.summarize(selected)
    return dict(season=2026, week=week, checked_at=state['checked_at'], games_total=len(games),
                accuracy=accuracy, market=market, games=sorted(games.values(), key=lambda g:(g['kickoff'],g['game_id'])),
                results={k:finals[k] for k in expected}, quotes=index(selected['ats']['games']))


def verify_sources(state, week, root):
    """Reconcile the whole target slate and finals with the captured provider bytes."""
    refs = [r for r in state.get('source_captures', []) if r.get('url') == season.URLS['schedule']]
    season.require(len(refs) == 1, 'Missing or ambiguous weekly schedule source')
    used = {refs[0]['path']}
    captured = index([g for g in season.parse_schedule(source_bytes(root, refs[0], state['checked_at'])) if g['week'] == week])
    scheduled = index([g for g in state['schedule'] if g['week'] == week])
    season.require(captured.keys() == scheduled.keys() and all(season.identity(captured[k], scheduled[k])
                   and str(captured[k]['espn_id']) == str(scheduled[k]['espn_id']) for k in captured),
                   'Weekly slate differs from captured schedule')
    parsed = {}
    for final in state['results']:
        if final['week'] != week:
            continue
        ref = final['source']
        used.add(ref['path'])
        if ref['path'] not in parsed:
            payload = json.loads(source_bytes(root, ref, state['checked_at']))
            parsed[ref['path']] = index(season.parse_scoreboard(payload, state['schedule'], ref['captured_at'])['results'])
        replay = parsed[ref['path']].get(final['game_id'])
        season.require(replay is not None and all(final.get(k) == v for k,v in replay.items()),
                       'Saved final differs from explicit provider FINAL')
    for quote in (state.get('ats') or {}).get('games', []):
        if quote['game_id'] not in scheduled:
            continue
        payload = pgo_ats._read(quote['source'], root, season.utc(state['checked_at']))
        used.add(quote['source']['path'])
        season.parse_scoreboard(payload, state['schedule'], quote['source']['captured_at'])
        events = [e for e in payload['events'] if str(e['id']) == str(quote['event_id'])]
        season.require(len(events) == 1 and pgo_ats._quote(events[0], scheduled[quote['game_id']]) == quote['home_handicap'],
                       'Saved sportsbook line differs from its captured source')
    return sorted(used)


def _text(value):
    return html.escape(str(value), quote=True)


def _number(value, digits=2):
    return 'Unavailable' if value is None else f'{value:.{digits}f}'


def _record(row):
    return f'{row["wins"]} W / {row["losses"]} L / {row.get("ties", 0)} T'


def render(report, source):
    """Version 1 deterministic HTML. Its content freezes with the source archive."""
    accuracy = report['accuracy']; market = report['market']; ats = market['ats']
    pool = accuracy['confidence']; probability = accuracy['probabilities']; benchmark = market['benchmark']
    checked = season.utc(report['checked_at']).astimezone(ZoneInfo('America/New_York')).strftime('%B %d, %Y at %I:%M %p %Z')
    cards = [('Winner picks', _record(accuracy['record']), f'{accuracy["record"]["n"]} eligible games'),
             ('Against saved sportsbook spread', f'{ats["wins"]} W / {ats["losses"]} L',
              f'{ats["pushes"]} pushes; {ats["no_edge"]} no edge; {ats["unavailable"]} unavailable'),
             ('Average margin error', _number(accuracy['margin_mae']['value']) + ' NFL points', f'{accuracy["margin_mae"]["n"]} eligible games'),
             ('Average combined-score error', _number(accuracy['total_mae']['value']) + ' NFL points', f'{accuracy["total_mae"]["n"]} eligible games')]
    card_html = ''.join(f'<article><h2>{_text(label)}</h2><strong>{_text(value)}</strong><p>{_text(note)}</p></article>' for label,value,note in cards)
    market_rows = {r['game_id']:r for r in market['rows']}; rows = []; late = []
    for game in report['games']:
        key = game['game_id']; final = report['results'][key]
        values, reasons = pgo_season_accuracy._evaluate(game, final, None, season.utc(report['checked_at']))
        record = dict(wins='Correct', losses='Incorrect', ties='Tie').get(values.get('record'), 'Not eligible')
        margin, total = game.get('margin'), game.get('total')
        forecast = ('Unavailable' if margin is None or total is None else
                    f'{game["away"]} {(total-margin)/2:.1f}, {game["home"]} {(total+margin)/2:.1f}')
        m = market_rows[key]; spread = dict(W='Covered', L='Did not cover', PUSH='Push', NOPICK='No edge', UNAVAILABLE='Unavailable')[m['ats_grade']]
        quote = report['quotes'].get(key)
        if quote and m['ats_grade'] not in ('UNAVAILABLE', 'NOPICK'):
            side = 'home' if quote['ats_pick'] == game['home'] else 'away'
            spread = f'{quote["ats_pick"]} {quote[side+"_handicap"]:+g}: {spread}'
        if values.get('record'):
            picked = game['home'] if margin > 0 else game['away']
            record = picked + ': ' + record
        confidence = game.get('confidence') or {}; pool_value = values.get('confidence')
        earned = 'Unavailable' if pool_value is None else f'{pool_value[0]} / {pool_value[2]}'
        if confidence.get('added_after_lock') is True:
            earned += ' (late entry)'; late.append(game['away'] + ' @ ' + game['home'])
        elif confidence and confidence.get('added_after_lock') is None:
            earned += ' (timing unknown)'
        fields = [game['away'] + ' @ ' + game['home'], forecast, f'{game["away"]} {final["away_score"]}, {game["home"]} {final["home_score"]}',
                  record, _number(values.get('margin_mae')), _number(values.get('total_mae')), spread, earned]
        rows.append('<tr>' + ''.join('<td>' + _text(value) + '</td>' for value in fields) + '</tr>')
    exclusions = []
    labels = dict(record='Winner picks', margin_mae='Margin error', total_mae='Combined-score error', probabilities='Probability accuracy', confidence='Confidence pool')
    reasons = dict(no_verified_final='No verified final', blocked_forecast='Forecast withheld', unknown_forecast_time='Forecast time unknown',
                   late_forecast='Forecast saved after lock', missing_margin='Margin missing', missing_total='Total missing', no_pick='No selected team',
                   late_confidence='Probability added after lock', unknown_confidence_time='Probability timing unknown',
                   incomplete_probabilities='Full probabilities missing', missing_confidence='Pool allocation incomplete')
    for key,label in labels.items():
        excluded = '; '.join(f'{reasons.get(k,k)}: {v}' for k,v in accuracy[key]['reasons'].items()) or 'None'
        exclusions.append(f'<li>{label}: {_text(excluded)}.</li>')
    excluded_market = '; '.join(f'{market["reason_labels"].get(k,k)}: {v}' for k,v in benchmark['reasons'].items()) or 'None'
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="data:,">
<title>PGO 2026 Week {report['week']} completed review</title><link rel="stylesheet" href="../../pgo-theme.css">
<style>*{{box-sizing:border-box}}body{{margin:0;background:var(--bg,#0e1116);color:var(--ink,#e6edf3);font:16px/1.55 system-ui,sans-serif}}main{{max-width:1180px;margin:auto;padding:28px 18px 60px}}h1,h2{{line-height:1.2}}a{{color:var(--teal,#60a5fa)}}p{{max-width:950px}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px;margin:24px 0}}article,details{{background:var(--panel,#171c24);border:1px solid var(--border,#273040);padding:18px;border-radius:10px}}article h2{{font-size:1rem;margin:0 0 10px}}article strong{{font-size:1.3rem;color:var(--teal,#60a5fa)}}article p{{margin-bottom:0;color:var(--mut,#b2bfcc)}}.table-shell{{overflow:auto;border:1px solid var(--border,#273040);border-radius:10px}}table{{border-collapse:collapse;width:100%;min-width:950px;font-variant-numeric:tabular-nums}}th,td{{text-align:left;vertical-align:top;padding:10px;border-bottom:1px solid var(--border,#273040)}}th{{background:var(--panel,#171c24)}}caption{{text-align:left;padding:12px}}th:first-child,td:first-child{{white-space:nowrap}}details{{margin:20px 0}}summary{{cursor:pointer;font-weight:700}}code{{overflow-wrap:anywhere}}@media(max-width:600px){{main{{padding:20px 12px 45px}}h1{{font-size:1.9rem}}}}</style></head>
<body><main><p><a href="../../index.html#season-accuracy">Back to PGO rankings and accuracy</a></p>
<h1>Week {report['week']} completed review</h1><p>All {report['games_total']} scheduled games have accepted final scores. Saved {_text(checked)}.
This report preserves the original picks and lines. Later updates appear on the current board; this dated report stays unchanged.</p>
<section class="cards" aria-label="Week {report['week']} results">{card_html}</section>
<p>Winner picks grade who won the game. ATS picks grade a separate suggested side against the saved sportsbook spread. A push is an exact tie against that line.
Margin error measures the difference between the predicted and actual scoring margin. Combined-score error compares both teams' total points. Lower error is better.</p>
<h2>Game-by-game results</h2><p>On smaller screens, scroll the table sideways to see every column.</p><div class="table-shell" tabindex="0" role="region" aria-label="Scrollable game results"><table><caption>Original score averages, accepted finals and separately eligible grades</caption>
<thead><tr><th>Matchup</th><th>Predicted score averages</th><th>Final score</th><th>Winner pick</th><th>Margin error<br>NFL points</th><th>Total error<br>NFL points</th><th>ATS suggestion</th><th>Pool points<br>earned / assigned</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<h2>Same-game sportsbook comparison</h2><p>On the same {benchmark['n']} eligible games, PGO's average margin error was {_number(benchmark['pgo_margin_mae'])} NFL points and the saved sportsbook line's error was {_number(benchmark['sportsbook_margin_mae'])} NFL points.
PGO winner picks: {_record(benchmark['pgo_record'])}; saved sportsbook favorites: {_record(benchmark['sportsbook_record'])}.
No-pick games: PGO {benchmark['pgo_record']['no_pick']}, sportsbook {benchmark['sportsbook_record']['no_pick']}.</p>
<h2>Confidence pool accounting</h2><p>{pool['earned_points'] if pool['earned_points'] is not None else 'Unavailable'} earned of {pool['available_points'] if pool['available_points'] is not None else 'unavailable'} assigned pool points across {pool['n']} eligible completed picks.
Expected pool points: {_number(pool['expected_points'])}. These are fixed confidence points times the saved win chances, separate from NFL scoreboard points.</p>
<p>Late pool entries: {pool['late_count']} ({_text(', '.join(late) or 'none')}); unknown timing: {pool['unknown_timing_count']}.
Late entries remain in pool accounting and are excluded from probability accuracy.</p>
<details><summary>Probability accuracy and eligibility</summary><p>Probability accuracy uses {probability['n']} games with full home, away and tie chances saved before the prediction cutoff.
Brier score: {_number(probability['brier'],3)}; log loss: {_number(probability['log_loss'],3)}. Lower is better. Brier measures the squared difference between the saved chances and the actual outcome (0 to 2); log loss penalizes assigning little chance to the outcome that occurred.</p>
<p>Games excluded from each measure:</p><ul>{''.join(exclusions)}<li>Sportsbook comparison: {_text(excluded_market)}.</li></ul></details>
<h2>What these results mean</h2><p>A completed week is a useful record, but a small sample cannot prove accuracy, reliable win chances or a betting advantage. These are descriptive results. They do not establish the football cause of any miss or justify changing model weights.</p>
<details><summary>Frozen source evidence</summary><p><a href="{_text(source['state_url'])}">Saved state archive</a> SHA-256: <code>{source['state_sha256']}</code>.</p>
<p><a href="{_text(source['manifest_url'])}">State verification manifest</a> SHA-256: <code>{source['manifest_sha256']}</code>.</p>
<p>The scheduled slate, accepted finals and saved sportsbook quotes were checked against their captured provider bytes. Report format version 1.</p></details>
</main></body></html>
'''.encode('utf-8')


def build(root, pointer, week):
    archive = Path(root) / 'docs/evidence/season-2026'
    state, manifest = load_archive(archive, pointer)
    season.require(state.get('schema_version') == 1, 'Weekly review state schema differs')
    report = summarize_week(state, week)
    season.require(report is not None, 'Cannot publish an incomplete week')
    sources = list(verify_sources(state, week, archive) or [])
    filename, meta = next(iter(manifest['files'].items()))
    prefix = 'https://raw.githubusercontent.com/walshja9/Postgame_Outlet/main/docs/evidence/season-2026/'
    source = dict(state_url=prefix + pointer['path'] + '/' + filename, state_sha256=meta['sha256'],
                  manifest_url=prefix + pointer['path'] + '/manifest.json', manifest_sha256=pointer['manifest_sha256'])
    raw = render(report, source)
    receipt = dict(schema_version=1, season=2026, week=week, checked_at=state['checked_at'],
                   source_pointer=dict(path=pointer['path'], manifest_sha256=pointer['manifest_sha256']),
                   source_paths=['docs/evidence/season-2026/' + p for p in sorted(set(sources + [pointer['path'] + '/manifest.json', pointer['path'] + '/' + filename]))],
                   html_sha256=season.sha(raw), html_bytes=len(raw))
    return raw, season.canonical(receipt)


def verify_publication(root, paths):
    """Admission requires complete, exact replayed pairs; no general HTML allowlist."""
    root = Path(root); selected = set(paths)
    season.require(len(selected) == len(paths) and all(re.fullmatch(PATTERN, p) for p in selected), 'Invalid weekly report paths')
    weeks = {int(re.fullmatch(PATTERN, p)[1]) for p in selected}
    required = set(selected)
    for week in weeks:
        stem = f'{FOLDER}/2026-week{week}-final'
        season.require({stem + '.html', stem + '.json'} <= selected, 'Weekly report pair is incomplete')
        for suffix in ('.html', '.json'):
            path = root / (stem + suffix)
            season.require(not path.is_symlink() and path.resolve().is_relative_to(root.resolve()), 'Invalid weekly report symlink')
        receipt = season.read_json(root / (stem + '.json'))
        raw, evidence = build(root, receipt['source_pointer'], week)
        season.require((root/(stem+'.html')).read_bytes() == raw and (root/(stem+'.json')).read_bytes() == evidence,
                       'Saved weekly report differs from exact source replay')
        required.update(receipt['source_paths'])
    return sorted(required)


def publish(root=season.ROOT):
    root = Path(root); archive = root/'docs/evidence/season-2026'
    existing = sorted(p.relative_to(root).as_posix() for p in (root/FOLDER).glob('*'))
    verify_publication(root, existing)
    if not (archive/'current.json').exists():
        return []
    pointer = season.read_json(archive/'current.json'); state, _ = load_archive(archive, pointer)
    written = []
    for week in range(1,19):
        stem = f'{FOLDER}/2026-week{week}-final'
        if (root/(stem+'.json')).exists() or summarize_week(state, week) is None:
            continue
        raw, receipt = build(root, pointer, week)
        (root/FOLDER).mkdir(parents=True, exist_ok=True)
        for suffix, payload in (('.html', raw), ('.json', receipt)):
            with (root/(stem+suffix)).open('xb') as handle:
                handle.write(payload)
            written.append(stem+suffix)
    return written


def links(root=season.ROOT):
    root = Path(root)
    paths = sorted(p.relative_to(root).as_posix() for p in (root/FOLDER).glob('*'))
    verify_publication(root, paths)
    return [dict(href=p.removeprefix('docs/'), label=f'Week {int(re.fullmatch(PATTERN,p)[1])}: completed review')
            for p in sorted(paths, key=lambda p:int(re.fullmatch(PATTERN,p)[1])) if p.endswith('.html')]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=season.ROOT)
    args = parser.parse_args()
    print(json.dumps(dict(created=publish(args.root)), indent=2))


if __name__ == '__main__':
    main()
