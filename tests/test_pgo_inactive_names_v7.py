import copy
from datetime import datetime
import gzip
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import pgo_inactive_names as legacy
import pgo_inactive_names_v7 as names_v7
from pgo_challenger import _normalize_player_name, _unique_roster_name_ids


ROOT = Path(__file__).resolve().parents[1]
ARCHIVES = ROOT / 'docs/evidence/season-2026/availability-v2'


def inputs(capture):
    return json.loads(gzip.decompress((ARCHIVES / capture / 'inputs.json.gz').read_bytes()))


def identity_maps(roster):
    indexed = {row['gsis_id']: dict(row) for row in roster if row.get('gsis_id')}
    names = {team: _unique_roster_name_ids(
        [row for row in indexed.values() if row['team'] == team], [])[0]
        for team in {row['team'] for row in indexed.values()}}
    return indexed, names


class InactiveV7NamesTests(unittest.TestCase):
    def setUp(self):
        saved = [inputs(capture) for capture in (
            '20261004T165041499152Z', '20261004T165043757132Z',
            '20261004T165047724375Z')]
        self.games = [game for item in saved for game in item['games']]
        self.indexed, self.names = identity_maps(
            [row for item in saved for row in item['roster']])
        self.evidence = names_v7.capture_evidence(self.games)
        self.now = datetime.fromisoformat('2026-10-04T17:00:00+00:00')

    def apply(self, **changes):
        kwargs = dict(games=self.games, indexed=self.indexed, names=self.names,
                      evidence=self.evidence, checked_at=self.now)
        kwargs.update(changes)
        return names_v7.apply_context_names(**kwargs)

    def test_saved_official_evidence_and_current_rosters_bind_only_exact_names(self):
        provenance = self.apply()
        expected = [
            ('HOU', 'Nate Thomas', '00-0039422', ['T', 'OT']),
            ('JAX', 'CJ Williams', '00-0041106', ['WR']),
            ('NYJ', 'Kiko Mauigoa', '00-0040186', ['LB']),
        ]
        self.assertEqual(set(self.evidence), {
            'hou-2026-week4', 'jax-2026-week4', 'nyj-2026-week4'})
        self.assertEqual(len(provenance), 3)
        for team, alias, gsis, positions in expected:
            key = _normalize_player_name(alias)
            self.assertEqual(self.names[team][key], gsis)
            record = provenance[(team, key)]
            self.assertEqual(record['identity_source_names'], [alias])
            self.assertEqual(record['identity_source_positions'], positions)
            self.assertEqual(record['identity_source_sha256'], hashlib.sha256(
                self.evidence[record['identity_binding']].encode()).hexdigest())
        self.assertIn('<title>Nate Thomas</title>', self.evidence['hou-2026-week4'])
        self.assertIn('>Nathan Thomas</h1>', self.evidence['hou-2026-week4'])
        self.assertIn('Rookie wide receiver CJ Williams', self.evidence['jax-2026-week4'])
        self.assertIn('href="/team/players-roster/francisco-mauigoa/" title="Kiko Mauigoa"',
                      self.evidence['nyj-2026-week4'])
        self.assertNotIn('nate tomas', self.names['HOU'])
        self.assertFalse(any(key[1] == 'rabbit taylor-demerson' for key in provenance))

    def test_evidence_inventory_bytes_and_capture_clock_fail_closed(self):
        cases = [None, {}, dict(self.evidence, unexpected='extra')]
        for key in self.evidence:
            altered = dict(self.evidence)
            altered[key] += 'tampered'
            cases.append(altered)
            altered = dict(self.evidence)
            altered[key] = b'wrong type'
            cases.append(altered)
        for evidence in cases:
            with self.subTest(evidence_type=type(evidence).__name__), self.assertRaises(ValueError):
                self.apply(evidence=evidence)
        with self.assertRaisesRegex(ValueError, 'captured after'):
            self.apply(checked_at=datetime.fromisoformat('2026-10-04T16:50:44+00:00'))

    def test_nyg_curly_apostrophe_alias_requires_unique_current_game_identity(self):
        saved = inputs('20261004T165040655301Z')
        indexed, names = identity_maps(saved['roster'])
        alias = 'Ar\u2019Darius Washington'
        canonical = "Ar'Darius Washington"
        key = _normalize_player_name(alias)
        self.assertNotEqual(key, _normalize_player_name(canonical))
        self.assertNotIn(key, names['NYG'])
        evidence = names_v7.capture_evidence(saved['games'])
        self.assertEqual(set(evidence), {'nyg-2026-week4'})
        self.assertTrue(alias in evidence['nyg-2026-week4'])
        club = gzip.decompress((ARCHIVES / '20261004T165040655301Z/raw/004.html.gz').read_bytes())
        self.assertEqual(hashlib.sha256(club).hexdigest(),
                         '580254bcb6a18d52253042c22d52c594fad893e2f326784bdbd4e70b579aa957')
        self.assertTrue(b"<li>S Ar'Darius Washington</li>" in club)
        provenance = names_v7.apply_context_names(saved['games'], indexed, names, evidence, self.now)
        self.assertEqual(names['NYG'][key], '00-0036587')
        self.assertEqual(provenance[('NYG', key)]['identity_source_names'], [alias])
        self.assertEqual(provenance[('NYG', key)]['identity_source_positions'], ['S'])
        for duplicate in (canonical, alias):
            ambiguous = copy.deepcopy(indexed)
            ambiguous['00-9999999'] = dict(indexed['00-0036587'],
                gsis_id='00-9999999', full_name=duplicate)
            with self.subTest(duplicate=duplicate), self.assertRaisesRegex(ValueError, 'ambiguous'):
                names_v7.apply_context_names(saved['games'], ambiguous, names, evidence, self.now)
        games = [dict(saved['games'][0], week=5)]
        with self.assertRaisesRegex(ValueError, 'current game or roster identity'):
            names_v7.apply_context_names(games, indexed, names, evidence, self.now)

    def test_game_and_current_roster_identity_must_match(self):
        for field, value in [('season', 2025), ('week', 3), ('away', 'TEN'), ('home', 'ARI')]:
            games = copy.deepcopy(self.games)
            games[0][field] = value
            with self.subTest(game_field=field), self.assertRaises(ValueError):
                self.apply(games=games)
        for gsis in ('00-0039422', '00-0041106', '00-0040186'):
            for field, value in [('team', 'ARI'), ('position', 'QB'), ('status', 'CUT'),
                                 ('full_name', 'Different Player'), ('gsis_id', '00-9999999')]:
                indexed = copy.deepcopy(self.indexed)
                indexed[gsis][field] = value
                with self.subTest(gsis=gsis, field=field), self.assertRaises(ValueError):
                    self.apply(indexed=indexed)
            indexed = copy.deepcopy(self.indexed)
            del indexed[gsis]
            with self.subTest(missing=gsis), self.assertRaises(ValueError):
                self.apply(indexed=indexed)

    def test_roster_or_existing_map_ambiguity_never_selects_an_alias(self):
        for canonical, alias in [('Nathan Thomas', 'Nate Thomas'),
                                 ('C.J. Williams', 'CJ Williams'),
                                 ('Francisco Mauigoa', 'Kiko Mauigoa')]:
            source = next(row for row in self.indexed.values() if row['full_name'] == canonical)
            for name in (canonical, alias):
                indexed = copy.deepcopy(self.indexed)
                indexed['00-9999999'] = dict(source, gsis_id='00-9999999', full_name=name)
                with self.subTest(alias=alias, duplicate=name), self.assertRaises(ValueError):
                    self.apply(indexed=indexed)
            current_names = copy.deepcopy(self.names)
            current_names[source['team']][_normalize_player_name(alias)] = '00-9999999'
            with self.subTest(map_conflict=alias), self.assertRaises(ValueError):
                self.apply(names=current_names)

    def test_unrelated_game_does_not_receive_bindings_or_accept_extra_evidence(self):
        games = [dict(self.games[0], game_id='2026_05_DAL_HOU', week=5)]
        self.assertEqual(names_v7.capture_evidence(games), {})
        self.assertEqual(self.apply(games=games, evidence={}), {})
        with self.assertRaisesRegex(ValueError, 'inventory'):
            self.apply(games=games)

    def test_replay_uses_embedded_evidence_without_reading_files(self):
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('no replay file reads')):
            self.assertEqual(len(self.apply()), 3)

    def test_legacy_week2_delegation_preserves_original_results(self):
        saved = inputs('20260920T154557557012Z')
        games = saved['games']
        indexed, old_names = identity_maps(saved['roster'])
        new_names = copy.deepcopy(old_names)
        evidence = legacy.capture_evidence(games)
        self.assertEqual(names_v7.capture_evidence(games), evidence)
        checked = datetime.fromisoformat('2026-09-20T16:40:00+00:00')
        old = legacy.apply_context_names(games, indexed, old_names, evidence, checked)
        new = names_v7.apply_context_names(games, indexed, new_names, evidence, checked)
        self.assertEqual(new, old)
        self.assertEqual(new_names, old_names)
        self.assertEqual(legacy.capture_evidence(self.games), {})
        self.assertEqual(legacy.apply_context_names(
            self.games, self.indexed, copy.deepcopy(self.names), {}, self.now), {})


if __name__ == '__main__':
    unittest.main()
