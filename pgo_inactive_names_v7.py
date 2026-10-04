"""Pinned Week 4 context aliases; frozen v6 names remain in their own module."""

from datetime import datetime
import gzip
import hashlib
from pathlib import Path

from pgo_challenger import _normalize_player_name
import pgo_inactive_names as legacy


EVIDENCE_ROOT = Path(__file__).resolve().parent / 'docs/evidence/season-2026'
BINDINGS = [
    dict(id='nyg-2026-week4', game_id='2026_04_ARI_NYG', away='ARI', home='NYG',
         team='NYG', names=['Ar\u2019Darius Washington'], canonical_name="Ar'Darius Washington",
         gsis_id='00-0036587', roster_position='DB', source_positions=['S'],
         file='availability-v2/20261004T165040655301Z/raw/005.html.gz',
         sha256='fafdb8619c8ad36370dddc2b562d520834167d68173c8332a5eb6d30ad258ce6',
         source_url='https://www.nfl.com/news/nfl-week-4-inactives-players-ruled-out-sunday-14-games-2026',
         captured_at='2026-10-04T16:50:41.122261+00:00',
         evidence='NFL lists S Ar\u2019Darius Washington; the same-game Giants list and '
                  "unique current ACT DB roster say Ar'Darius Washington. Only the apostrophe differs."),
    dict(id='hou-2026-week4', game_id='2026_04_DAL_HOU', away='DAL', home='HOU',
         team='HOU', names=['Nate Thomas'], canonical_name='Nathan Thomas',
         gsis_id='00-0039422', roster_position='OL', source_positions=['T', 'OT'],
         file='context-name-evidence/hou-nathan-thomas.html.gz',
         sha256='7d9ec1e702d4db78178e3e3f3cd62cd387eac341273314e2293a706c0f31b16c',
         source_url='https://www.houstontexans.com/team/players-roster/nathan-thomas/',
         captured_at='2026-09-20T16:14:54.336690+00:00',
         evidence='Official profile title says Nate Thomas; H1 and Person metadata say '
                  'Nathan Thomas. T jersey 78 matches the Week 4 club inactive row.'),
    dict(id='jax-2026-week4', game_id='2026_04_JAX_CIN', away='JAX', home='CIN',
         team='JAX', names=['CJ Williams'], canonical_name='C.J. Williams',
         gsis_id='00-0041106', roster_position='WR', source_positions=['WR'],
         file='availability-v2/20261004T165043757132Z/raw/005.html.gz',
         sha256='13a9b5f15670b4a8e076de4bb18e28ce68f76e880d3be3b25f89d5d4601187f9',
         source_url='https://www.jaguars.com/news/in-and-out-2026-week-4-montaric-brown-inactive-for-jaguars-vs-bengals',
         captured_at='2026-10-04T16:50:44.653508+00:00',
         evidence='Official club list says Rookie wide receiver CJ Williams; current '
                  'ACT WR roster names C.J. Williams with football name C.J. Only '
                  'the periods differ; the other Williams is Wesley, a DL.'),
    dict(id='nyj-2026-week4', game_id='2026_04_NYJ_CHI', away='NYJ', home='CHI',
         team='NYJ', names=['Kiko Mauigoa'], canonical_name='Francisco Mauigoa',
         gsis_id='00-0040186', roster_position='LB', source_positions=['LB'],
         file='availability-v2/20261004T165047724375Z/raw/004.html.gz',
         sha256='812abb4b4d8aab267ebbae44f0398d864dd83bac6e8aa9f4996997b8ac9e08c9',
         source_url='https://www.newyorkjets.com/news/jets-vs-bears-game-inactives-10-04-2026',
         captured_at='2026-10-04T16:50:48.239437+00:00',
         evidence='Official club inactive row LB Kiko Mauigoa links directly to '
                  '/team/players-roster/francisco-mauigoa/; current ACT LB roster '
                  'identity is Francisco Mauigoa.'),
]


def _legacy_games(games):
    ids = {binding['game_id'] for binding in legacy.BINDINGS}
    return [game for game in games if game['game_id'] in ids]


def capture_evidence(games):
    """Embed pinned bytes so later replay never depends on current source files."""
    ids = {game['game_id'] for game in games}
    evidence = legacy.capture_evidence(_legacy_games(games))
    evidence.update({binding['id']: gzip.decompress(
        (EVIDENCE_ROOT / binding['file']).read_bytes()).decode('utf-8')
        for binding in BINDINGS if binding['game_id'] in ids})
    return evidence


def apply_context_names(games, indexed, names, evidence, checked_at):
    """Resolve only the evidenced alias, game, team, GSIS ID and current roster."""
    old_games = _legacy_games(games)
    game_map = {game['game_id']: game for game in games}
    bindings = [binding for binding in BINDINGS if binding['game_id'] in game_map]
    old_ids = {binding['id'] for binding in legacy.BINDINGS
               if binding['game_id'] in {game['game_id'] for game in old_games}}
    expected = old_ids | {binding['id'] for binding in bindings}
    if not isinstance(evidence, dict) or set(evidence) != expected:
        raise ValueError('Context name evidence inventory differs')
    provenance = legacy.apply_context_names(
        old_games, indexed, names, {key: evidence[key] for key in old_ids}, checked_at)
    for binding in bindings:
        body = evidence[binding['id']]
        if not isinstance(body, str) or hashlib.sha256(body.encode('utf-8')).hexdigest() != binding['sha256']:
            raise ValueError('Context name evidence bytes differ')
        if datetime.fromisoformat(binding['captured_at']) > checked_at:
            raise ValueError('Context identity evidence was captured after this check')
        game = game_map[binding['game_id']]
        roster = indexed.get(binding['gsis_id'])
        if (game.get('season') != 2026 or game.get('week') != 4
                or game.get('away') != binding['away'] or game.get('home') != binding['home']
                or not roster or roster.get('gsis_id') != binding['gsis_id']
                or roster.get('team') != binding['team']
                or roster.get('full_name') != binding['canonical_name']
                or roster.get('position') != binding['roster_position'] or roster.get('status') != 'ACT'):
            raise ValueError('Context name binding differs from current game or roster identity')
        if sum(row['team'] == binding['team'] and row['full_name'] == binding['canonical_name']
               for row in indexed.values()) != 1:
            raise ValueError('Context canonical roster name is ambiguous')
        for alias in binding['names']:
            key = _normalize_player_name(alias)
            for row in indexed.values():
                possible = [row['full_name']] + [row.get(field, '') + ' ' + row.get('last_name', '')
                                                for field in ('first_name', 'football_name')]
                if (row['team'] == binding['team'] and row['gsis_id'] != binding['gsis_id']
                        and key in {_normalize_player_name(name) for name in possible}):
                    raise ValueError('Context alias is ambiguous in the roster')
            existing = names[binding['team']].get(key)
            if existing is not None and existing != binding['gsis_id']:
                raise ValueError('Context name conflicts with another roster identity')
            names[binding['team']][key] = binding['gsis_id']
            provenance[(binding['team'], key)] = dict(
                identity_binding=binding['id'], identity_source_sha256=binding['sha256'],
                identity_source_url=binding['source_url'],
                identity_source_positions=binding['source_positions'], identity_source_names=binding['names'])
    return provenance
