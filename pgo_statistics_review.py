"""Compare later statistics with an issued edition; never recalculate its picks."""
from collections import defaultdict
import copy
from datetime import timedelta
import re

import pgo_season as season
import pgo_season_model as model
from pgo_season_rollover import source_bytes

TEAM_FIELDS = (*model.TEAM_COUNTS, 'passing_epa', 'rushing_epa')
QB_FIELDS = (*model.QB_COUNTS, 'passing_epa', 'passing_cpoe', 'rushing_epa')


def project(games, team_rows, player_rows):
    """Canonical model-input values on exactly the saved completed-game cohort."""
    periods = {}
    for game in games:
        model._game_identity(game, season.SEASON)
        for team, opponent in ((game['home'],game['away']),(game['away'],game['home'])):
            key=(game['season'],game['week'],team)
            season.require(key not in periods, 'Duplicate statistics-review game or team')
            periods[key]=(game,opponent)
    season.require(periods, 'Statistics review has no completed games')
    cohorts={key[:2] for key in periods}
    # Later games cannot become apparent corrections to an earlier edition.
    team_rows=[r for r in team_rows if model._period(r)[:2] in cohorts]
    player_rows=[r for r in player_rows if (model._integer(r['season']),model._integer(r['week'])) in cohorts]
    player_rows,pools=model.partition_player_rows(team_rows,player_rows,games)
    teams={};players=defaultdict(list);seen=set();output={}
    colliding=model._context()['inputs']['colliding_gsis']
    def label(row,key):
        season.require(key in periods and row.get('season_type')=='REG', 'Statistics row is outside saved cohort')
        game,opponent=periods[key]
        season.require(row.get('game_id')==game['game_id'] and
                       season.pgo_sources.normalize_team(row.get('opponent_team'))==opponent,
                       'Statistics game or opponent identity differs')
    def save(kind,key,pid,row,fields):
        values={name:model._number(row.get(name),nullable=True) for name in fields}
        if kind=='player':values['position']=row['position'].strip().upper()
        output['|'.join((kind,str(key[0]),str(key[1]),key[2],pid))]=dict(
            kind=kind,game_id=periods[key][0]['game_id'],team=key[2],player_id=pid or None,values=values)
    for row in team_rows:
        key=model._period(row);label(row,key)
        season.require(key not in teams, 'Duplicate team production')
        teams[key]=dict(row,**{name:model._number(row.get(name),nullable=name not in model.TEAM_COUNTS) for name in TEAM_FIELDS})
        save('team',key,'',row,TEAM_FIELDS)
    for row in player_rows:
        key=model._period(row);label(row,key);pid=row.get('player_id')
        season.require(isinstance(pid,str) and re.fullmatch(r'00-\d{7}',pid) is not None
                       and isinstance(row.get('position'),str) and row['position'].strip(), 'Missing player identity')
        season.require(pid not in colliding, 'Ambiguous historical player ID requires identity review')
        season.require((*key,pid) not in seen, 'Duplicate player production');seen.add((*key,pid))
        players[key].append(row)
        fields=QB_FIELDS if row['position'].strip().upper()=='QB' else ('attempts','sacks_suffered')
        save('player',key,pid,row,fields)
    for game in games:model._validate_production(game,teams,players)
    # Pools remain unattributed evidence, never a fabricated player contribution.
    return dict(rows=output,unattributed_penalties=pools)


def differences(before,after):
    changed=[]
    for key in sorted(set(before['rows'])|set(after['rows'])):
        old=before['rows'].get(key);new=after['rows'].get(key);identity=new or old
        a=old['values'] if old else {};b=new['values'] if new else {}
        for field in sorted(set(a)|set(b)):
            if field not in a or field not in b or a[field]!=b[field]:
                changed.append(dict(**{k:identity[k] for k in ('kind','game_id','team','player_id')},
                                    field=field,before=a.get(field),after=b.get(field),
                                    change='added_row' if old is None else 'removed_row' if new is None else 'changed_value'))
    if before['unattributed_penalties']!=after['unattributed_penalties']:
        changed.append(dict(kind='unattributed_penalties',game_id=None,team=None,player_id=None,
                            field='penalty_reconciliation',before=before['unattributed_penalties'],
                            after=after['unattributed_penalties'],change='changed_evidence'))
    return changed


def _feeds(refs,root,deadline):
    data={}
    for kind in ('team','player'):
        matches=[r for r in refs if r.get('url')==season.URLS[kind]]
        season.require(len(matches)==1, 'Missing or ambiguous saved '+kind+' statistics source')
        data[kind]=season.csv_rows(source_bytes(root,matches[0],deadline))
    return data


def verify_saved(payload,root,deadline,*,state=None):
    """Replay a retained comparison from its hashed captures before displaying it."""
    season.require(season.utc(payload['checked_at'])<=season.utc(deadline), 'Statistics check is from the future')
    for ref in payload.get('attempt_sources',[]):source_bytes(root,ref,payload['checked_at'])
    report=payload.get('report')
    if not report:return
    season.require(season.utc(report['basis_inputs_as_of'])<=season.utc(report['compared_at'])<=season.utc(payload['checked_at']),
                   'Statistics comparison clock differs')
    completed=report['completed_week']
    season.require(type(completed) is int and 1<=completed<=18 and
                   {g['week'] for g in report['games']}==set(range(1,completed+1)) and
                   all(season.utc(g['kickoff'])<season.utc(report['basis_inputs_as_of']) for g in report['games']),
                   'Statistics comparison completed-week cohort differs')
    if state is not None:
        expected={g['game_id']:{k:g[k] for k in model.GAME_IDENTITY} for g in state['schedule'] if g['week']<=completed}
        saved={g['game_id']:{k:g[k] for k in model.GAME_IDENTITY} for g in report['games']}
        season.require(saved==expected and len(saved)==len(report['games']), 'Statistics comparison differs from saved schedule')
        if report['basis_edition']==state['rankings']['edition']:
            season.require(completed==state['rankings']['completed_week'] and
                           report['basis_inputs_as_of']==state['rankings']['inputs_as_of'], 'Statistics comparison edition differs')
            refs=state['rankings'].get('source_captures') or state.get('edition_sources',{}).get(report['basis_edition'],[])
        else:
            refs=state.get('edition_sources',{}).get(report['basis_edition'],[])
        issued=[r for r in refs if r.get('url') in (season.URLS['team'],season.URLS['player'])]
        season.require(len(issued)==2 and sorted(issued,key=lambda r:r['url'])==sorted(report['basis_sources'],key=lambda r:r['url']),
                       'Statistics comparison basis differs from issued edition sources')
    before=_feeds(report['basis_sources'],root,report['basis_inputs_as_of'])
    after=_feeds(report['latest_sources'],root,report['compared_at'])
    for ref in report['latest_sources']:
        season.require(season.utc(ref['captured_at'])>=season.utc(report['basis_inputs_as_of']), 'Later statistics precede edition')
    old=project(report['games'],before['team'],before['player']);new=project(report['games'],after['team'],after['player'])
    season.require(differences(old,new)==report['changes'], 'Saved statistics comparison differs from its sources')
    season.require(report['input_rows']==dict(before=len(old['rows']),after=len(new['rows'])), 'Statistics row counts differ')
    if payload['status'] in ('CLEAR','REVIEW'):
        season.require((payload['status']=='REVIEW')==bool(report['changes']), 'Statistics review status differs')


def refresh_review(state,previous,root,checked_at):
    old=copy.deepcopy((previous or {}).get('statistics_review',{}))
    rankings=state.get('rankings') or {};edition=rankings.get('edition')
    if rankings.get('completed_week',0)==0:
        return dict(status='WAITING',checked_at=checked_at,blocked_reason=None,
                    reason='Starts after the first ranking edition using a completed 2026 week.',report=None)
    if old.get('attempt_edition')==edition and old.get('checked_at'):
        elapsed=season.utc(checked_at)-season.utc(old['checked_at'])
        season.require(elapsed>=timedelta(0), 'Statistics review clock moved backwards')
        if elapsed<timedelta(hours=6):return old
    payload=dict(old,status='BLOCKED',checked_at=checked_at,attempt_edition=edition,
                 attempt_sources=[],blocked_reason=None)
    try:
        refs=rankings.get('source_captures') or state.get('edition_sources',{}).get(edition,[])
        before=_feeds(refs,root,rankings['inputs_as_of'])
        completed=rankings['completed_week']
        games=[g for g in state['schedule'] if g['week']<=completed]
        finals={r['game_id']:r for r in state['results']}
        season.require(games and all(g['game_id'] in finals and
                       season.utc(finals[g['game_id']]['finalized_at'])<=season.utc(rankings['inputs_as_of']) for g in games),
                       'Ranking statistics cohort is not fully final before the edition')
        baseline=project(games,before['team'],before['player'])
        latest={}
        for kind in ('team','player'):
            raw,ref=season.fetch_source(season.URLS[kind],root)
            payload['attempt_sources'].append(ref);latest[kind]=season.csv_rows(raw)
        current=project(games,latest['team'],latest['player'])
        compared=season.now();changes=differences(baseline,current)
        payload.update(status='REVIEW' if changes else 'CLEAR',checked_at=compared,
            report=dict(basis_edition=edition,basis_inputs_as_of=rankings['inputs_as_of'],completed_week=completed,
                        compared_at=compared,games=copy.deepcopy(games),
                        basis_sources=[r for r in refs if r.get('url') in (season.URLS['team'],season.URLS['player'])],
                        latest_sources=copy.deepcopy(payload['attempt_sources']),changes=changes,
                        input_rows=dict(before=len(baseline['rows']),after=len(current['rows']))))
        verify_saved(payload,root,compared,state=state)
    except (ValueError,KeyError,TypeError,OSError) as error:
        payload.update(status='BLOCKED',checked_at=season.now(),blocked_reason=str(error))
        # An incomplete attempt cannot replace the last successful comparison.
        payload['report']=old.get('report')
    return payload
