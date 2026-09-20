"""Three source-backed names for Week 2 context only; frozen v6 evidence."""
import gzip
import hashlib
from datetime import datetime
from pathlib import Path
from pgo_challenger import _normalize_player_name

BINDINGS = [{'id': 'car-2026-week2',
  'game_id': '2026_02_CAR_ATL',
  'team': 'CAR',
  'names': ['Pat Jones'],
  'canonical_name': 'Patrick Jones II',
  'gsis_id': '00-0037007',
  'roster_position': 'LB',
  'file': 'car-patrick-jones.html.gz',
  'sha256': '68dc56ece6d7c0a83a888d99fa885a226d047344dac6a2e868debe4fa15e4d3b',
  'source_url': 'https://www.panthers.com/news/week-2-inactives-at-atlanta-pat-jones-out-for-falcons-game-bobby-brown-panthers-falcons',
  'captured_at': '2026-09-20T15:46:03.327453+00:00',
  'evidence': 'Same official inactive article list says OLB Pat Jones; narrative says Outside linebacker '
              'Patrick Jones II, who was questionable with a back injury, was among the inactives for Week '
              '2; full name links exact official Patrick Jones II roster profile.',
  'source_positions': ['OLB', 'LB']},
 {'id': 'hou-2026-week2',
  'game_id': '2026_02_CIN_HOU',
  'team': 'HOU',
  'names': ['Nate Thomas'],
  'canonical_name': 'Nathan Thomas',
  'gsis_id': '00-0039422',
  'roster_position': 'OL',
  'file': 'hou-nathan-thomas.html.gz',
  'sha256': '7d9ec1e702d4db78178e3e3f3cd62cd387eac341273314e2293a706c0f31b16c',
  'source_url': 'https://www.houstontexans.com/team/players-roster/nathan-thomas/',
  'captured_at': '2026-09-20T16:14:54.336690+00:00',
  'evidence': 'Same official roster profile /nathan-thomas/: HTML title and roster selector use Nate Thomas; '
              'H1 and JSON-LD Person use Nathan Thomas; position T jersey78 matches inactive list T No.78.',
  'source_positions': ['T', 'OT']},
 {'id': 'ten-2026-week2',
  'game_id': '2026_02_PHI_TEN',
  'team': 'TEN',
  'names': ['Cor’Dale Flott', "Cor'Dale Flott"],
  'canonical_name': 'Cordale Flott',
  'gsis_id': '00-0037758',
  'roster_position': 'DB',
  'file': 'ten-cordale-flott.html.gz',
  'sha256': '8b29ee4fd843aee4569f9c6609a8ecd9aef796fc46bd22ab4d037f6790ffb488',
  'source_url': 'https://www.tennesseetitans.com/team/players-roster/cor-dale-flott/',
  'captured_at': '2026-09-20T16:15:55.574739+00:00',
  'evidence': 'Same official /cor-dale-flott/ profile H1 and JSON-LD Person name Cordale Flott; biography '
              "states Born Cor'Dale Flott on Aug. 24, 2001 in Saraland, Ala.; position CB matches inactive "
              'row.',
  'source_positions': ['CB']}]
EVIDENCE_ROOT = Path(__file__).resolve().parent/'docs/evidence/season-2026/context-name-evidence'


def capture_evidence(games):
    ids = {game['game_id'] for game in games}
    return {b['id']:gzip.decompress((EVIDENCE_ROOT/b['file']).read_bytes()).decode('utf-8')
            for b in BINDINGS if b['game_id'] in ids}


def apply_context_names(games, indexed, names, evidence, checked_at):
    games = {game['game_id']:game for game in games}
    bindings = [b for b in BINDINGS if b['game_id'] in games]
    if not isinstance(evidence,dict) or set(evidence) != {b['id'] for b in bindings}:
        raise ValueError('Context name evidence inventory differs')
    provenance = {}
    for b in bindings:
        body = evidence[b['id']]
        if not isinstance(body,str) or hashlib.sha256(body.encode('utf-8')).hexdigest() != b['sha256']:
            raise ValueError('Context name evidence bytes differ')
        if datetime.fromisoformat(b['captured_at']) > checked_at:
            raise ValueError('Context identity evidence was captured after this check')
        game = games[b['game_id']]
        roster = indexed.get(b['gsis_id'])
        if (game['season'] != 2026 or game['week'] != 2 or b['team'] not in (game['away'],game['home'])
                or not roster or roster['team'] != b['team'] or roster['full_name'] != b['canonical_name']
                or roster['position'] != b['roster_position'] or roster.get('status') != 'ACT'):
            raise ValueError('Context name binding differs from current game or roster identity')
        if sum(r['team'] == b['team'] and r['full_name'] == b['canonical_name'] for r in indexed.values()) != 1:
            raise ValueError('Context canonical roster name is ambiguous')
        for alias in b['names']:
            key = _normalize_player_name(alias)
            for r in indexed.values():
                possible = [r['full_name']] + [r.get(k,'')+' '+r.get('last_name','') for k in ('first_name','football_name')]
                if r['team'] == b['team'] and r['gsis_id'] != b['gsis_id'] and key in {_normalize_player_name(n) for n in possible}:
                    raise ValueError('Context alias is ambiguous in the roster')
            existing = names[b['team']].get(key)
            if existing is not None and existing != b['gsis_id']:
                raise ValueError('Context name conflicts with another roster identity')
            names[b['team']][key] = b['gsis_id']
            provenance[(b['team'],key)] = dict(identity_binding=b['id'],identity_source_sha256=b['sha256'],
                                               identity_source_url=b['source_url'],identity_source_positions=b['source_positions'],identity_source_names=b['names'])
    return provenance
