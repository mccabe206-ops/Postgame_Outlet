import copy
import csv
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import pgo_offensive_inventory as inventory
import pgo_injury_usage_monitor as shared
from pgo_season import canonical, sha
from tests.test_pgo_offensive_inventory import GAME, NOW, archive, fixture_rows, sources, identity_rows, identity_source

CHECK = '2026-09-11T12:00:00+00:00'


class OffensiveUsageTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('pgo_offensive_usage_monitor'), 'Offensive usage API is missing')
        import pgo_offensive_usage_monitor as api
        self.api = api
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.root = Path(self.tmp.name)
        self.roster, self.depth = fixture_rows()
        self.first = self.save(NOW, '2026-09-10T20:00:01Z')
        self.final = dict(GAME, home_team='LAR', away_team='SF', home_score=20, away_score=21,
                          actual_margin=-1, finalized_at='2026-09-11T03:30:00Z')
        self.state = dict(schema_version=1, season=2026, checked_at=CHECK, results=[self.final],
                          schedule=[GAME], weeks=[dict(games=[GAME])], replacement_depth={'preserve': 'defense'},
                          injury_usage={'preserve': 'defensive study'})
        player = next(row for row in self.roster if row['team'] == 'SF')
        self.row = dict(game_id=GAME['game_id'], season='2026', week='1', game_type='REG', team='SF', opponent='LA',
                        pfr_player_id=player['pfr_id'], offense_snaps='0')
        verification = patch.object(api, 'verify_finals'); verification.start(); self.addCleanup(verification.stop)

    def save(self, generated, durable, malformed=False, inventory_present=True):
        state = dict(schema_version=1, season=2026, checked_at=generated,
                      source_captures=sources(self.root, self.roster, self.depth), weeks=[dict(games=[GAME])])
        if inventory_present:
            state['offensive_inventory'] = inventory.capture(state, self.root, generated)
            if malformed == 'missing_version': state['offensive_inventory'].pop('inventory_version')
            elif malformed == 'missing_games': state['offensive_inventory'].pop('games')
            elif malformed == 'top_level': state['offensive_inventory'] = None
            elif malformed: state['offensive_inventory']['teams'][0]['players'] = [dict(gsis_id='bad')]
        return archive(self.root, state, durable)

    def response(self, rows=None):
        stream = io.StringIO(); writer = csv.DictWriter(stream, fieldnames=list(self.row))
        writer.writeheader(); writer.writerows([self.row] if rows is None else rows)
        response = MagicMock(); response.__enter__.return_value = response
        response.status = 200; response.headers = {}; response.read.return_value = stream.getvalue().encode()
        return response

    def refresh(self, old=None, checked=CHECK, rows=None):
        before = copy.deepcopy(self.state)
        with patch.object(shared, 'urlopen', return_value=self.response(rows)) as fetch, patch.object(shared, 'now', return_value=checked):
            result = self.api.refresh_shadow(self.state, {'offensive_usage': old} if old else {}, self.root, checked)
        self.assertEqual(self.state, before)
        return result, fetch

    def test_latest_durable_pre_t60_offensive_cohort_and_zero_vs_missing(self):
        selected = self.save('2026-09-10T21:00:00Z', '2026-09-10T21:00:01Z')
        self.save('2026-09-10T23:34:59Z', GAME['lock_at'])
        result, fetch = self.refresh()
        self.assertEqual(result['status'], 'READY'); fetch.assert_called_once()
        self.assertEqual(result['selected_games'], {GAME['game_id']: selected})
        self.assertEqual(result['metrics']['cohort_rows'], 2); self.assertEqual(result['metrics']['observed_zero'], 1)
        self.assertEqual(result['metrics']['missing_target'], 1); self.assertEqual(result['predictive_status'], 'UNAVAILABLE')
        report = json.loads((self.root/result['report']['path']).read_bytes())
        self.assertTrue(all('offensive_snaps' in row and 'defensive_snaps' not in row for row in report['rows']))

    def test_invalid_latest_freezes_and_blocks_without_fallback(self):
        selected = self.save('2026-09-10T22:00:00Z', '2026-09-10T22:00:01Z', malformed=True)
        result, fetch = self.refresh(); self.assertEqual(result['status'], 'BLOCKED'); fetch.assert_not_called()
        self.assertEqual(result['selected_games'], {GAME['game_id']: selected})
        again, _ = self.refresh(result); self.assertEqual(again['selected_games'], result['selected_games'])

    def test_missing_version_games_or_top_level_cannot_fallback_to_older_inventory(self):
        for minute, malformed in enumerate(('missing_version', 'missing_games', 'top_level')):
            selected = self.save(f'2026-09-10T22:0{minute}:00Z', f'2026-09-10T22:0{minute}:01Z', malformed=malformed)
            with self.subTest(malformed=malformed):
                result, fetch = self.refresh()
                self.assertEqual(result['selected_games'], {GAME['game_id']: selected})
                self.assertEqual(result['status'], 'BLOCKED'); fetch.assert_not_called()

    def test_selected_cohort_and_report_stay_fixed_and_share_target_receipt(self):
        first, _ = self.refresh()
        self.save('2026-09-10T22:00:00Z', '2026-09-10T22:00:01Z')
        self.state['injury_usage'] = dict(source=first['source'], last_attempt=first['last_attempt'])
        again, fetch = self.refresh(first, '2026-09-11T13:00:00Z')
        fetch.assert_not_called(); self.assertEqual(first['selected_games'], again['selected_games'])
        self.assertEqual(first['report'], again['report'])
        fresh, fetch = self.refresh(None, '2026-09-11T13:00:00Z')
        fetch.assert_not_called(); self.assertEqual(fresh['source'], first['source'])

    def test_missing_inventory_is_permanent_exclusion_and_pending_does_not_fetch(self):
        self.state['results'] = []
        result, fetch = self.refresh(); fetch.assert_not_called(); self.assertEqual(result['pending_games'], 1)
        self.state['results'] = [dict(self.final, game_id='2026_01_NE_SEA')]
        first, fetch = self.refresh(); fetch.assert_not_called()
        self.assertEqual(first['excluded_games'], [dict(game_id='2026_01_NE_SEA', reason='MISSING_PREGAME_INVENTORY')])
        again, fetch = self.refresh(first); fetch.assert_not_called(); self.assertEqual(again['excluded_games'], first['excluded_games'])

    def test_duplicate_malformed_missing_and_wrong_team_targets_are_unknown(self):
        for changed in (dict(offense_snaps='NaN'), dict(offense_snaps=''), dict(offense_snaps='-1')):
            result, _ = self.refresh(rows=[self.row, dict(self.row, **changed)])
            self.assertEqual(result['metrics']['joined'], 0); self.assertEqual(result['metrics']['observed_zero'], 0)
            self.assertEqual(result['metrics']['exclusions']['DUPLICATE_TARGET_IDENTITY'], 1)
        for changed in (dict(opponent='SEA'), dict(team='LAR'), dict(pfr_player_id='unknown'), dict(week='2')):
            result, _ = self.refresh(rows=[dict(self.row, **changed)])
            self.assertEqual(result['metrics']['joined'], 0)

    def test_target_at_final_is_pending_until_actual_later_capture(self):
        result, _ = self.refresh(checked=self.final['finalized_at'])
        self.assertEqual(result['metrics']['joined'], 0)
        self.assertEqual(result['metrics']['exclusions']['TARGET_BEFORE_FINAL_OBSERVATION'], 2)
        again, fetch = self.refresh(result)
        fetch.assert_called_once(); self.assertEqual(again['metrics']['joined'], 1)

    def test_preserved_report_source_and_archive_tampering_block(self):
        first, _ = self.refresh()
        for path in (self.root/first['source']['path'], self.root/first['report']['path'], self.root/self.first['path']/'state.json'):
            raw = path.read_bytes(); path.write_bytes(raw+b' ')
            try:
                result, fetch = self.refresh(first); self.assertEqual(result['status'], 'BLOCKED'); fetch.assert_not_called()
            finally: path.write_bytes(raw)

    def test_source_failure_is_retained_throttled_and_optional(self):
        from urllib.error import URLError
        with patch.object(shared, 'urlopen', side_effect=URLError('private')), patch.object(shared, 'now', return_value=CHECK):
            result = self.api.refresh_shadow(self.state, {}, self.root, CHECK)
        self.assertEqual(result['status'], 'BLOCKED'); self.assertNotIn('private', json.dumps(result))
        self.assertTrue((self.root/result['last_attempt']['path']).is_file())
        again, fetch = self.refresh(result, '2026-09-11T13:00:00Z')
        fetch.assert_not_called(); self.assertEqual(again['status'], 'BLOCKED')

    def test_pfr_name_conflict_and_extra_csv_fields_do_not_admit(self):
        self.row['player'] = 'A Different Person'
        result, _ = self.refresh()
        self.assertEqual(result['metrics']['joined'], 0)
        self.assertEqual(result['metrics']['invalid_target_rows'], 1)
        self.row.pop('player')
        response = self.response(); response.read.return_value += b'2026_01_SF_LA,2026,1,REG,SF,LA,Test0028,0,extra\n'
        with patch.object(shared, 'urlopen', return_value=response), patch.object(shared, 'now', return_value=CHECK):
            result = self.api.refresh_shadow(self.state, {}, self.root, CHECK)
        self.assertEqual(result['status'], 'BLOCKED')

    def test_delayed_final_requires_new_target_capture(self):
        first, _ = self.refresh()
        self.final['finalized_at'] = '2026-09-11T12:30:00Z'
        result, fetch = self.refresh(first, '2026-09-11T13:00:00Z')
        fetch.assert_called_once(); self.assertEqual(result['metrics']['joined'], 1)

    def test_selected_reader_tamper_never_uses_later_roster(self):
        first, _ = self.refresh()
        self.roster[0]['full_name'] = 'Later Roster'
        self.save('2026-09-10T22:00:00Z', '2026-09-10T22:00:01Z')
        first_state = json.loads((self.root/self.first['path']/'state.json').read_bytes())
        path = self.root/first_state['source_captures'][0]['path']
        path.write_bytes(path.read_bytes()+b' ')
        result, fetch = self.refresh(first)
        fetch.assert_not_called(); self.assertEqual(result['status'], 'BLOCKED')
        self.assertEqual(result['selected_games'], first['selected_games'])

    def save_v2(self, mutate=None, durable='2026-09-10T22:00:01Z'):
        for row in self.roster: row.update(pfr_id='', birth_date='1995-01-02')
        players = identity_rows(self.roster)
        if mutate: mutate(players)
        state = dict(schema_version=1, season=2026, checked_at='2026-09-10T22:00:00Z',
                     source_captures=sources(self.root, self.roster, self.depth), weeks=[dict(games=[GAME])])
        state['source_captures'].append(identity_source(self.root, players))
        state['offensive_inventory'] = inventory.capture(state, self.root, state['checked_at'], inventory_version=2)
        return archive(self.root, state, durable), players

    def test_v2_missing_roster_pfr_links_zero_positive_and_pins_new_protocol(self):
        selected, players = self.save_v2()
        rows = [dict(self.row, team=row['team'], opponent='SF' if row['team'] == 'LAR' else 'LA',
                     pfr_player_id=next(p['pfr_id'] for p in players if p['gsis_id'] == row['gsis_id']),
                     offense_snaps='0' if row['team'] == 'SF' else '17')
                for row in self.roster if row['team'] in ('SF', 'LAR')]
        result, _ = self.refresh(rows=rows)
        self.assertEqual(result['selected_games'], {GAME['game_id']: selected})
        self.assertEqual(result['status'], 'READY'); self.assertEqual(result['metrics']['joined'], 2)
        self.assertEqual(result['metrics']['observed_zero'], 1); self.assertEqual(result['metrics']['observed_positive'], 1)
        report = json.loads((self.root/result['report']['path']).read_bytes())
        self.assertIn('pgo_player_identity.py', report['inputs'])
        self.assertIn('research/pgo_offensive_usage_20260912/inventory-v2-addendum.md', report['inputs'])
        self.assertTrue(all(not row['pfr_id'] for row in self.roster))

    def test_v2_conflicting_identity_never_becomes_target_zero(self):
        def conflict(players):
            sf = next(p for p in players if p['last_name'] == 'SF'); sf['birth_date'] = '1996-01-02'
        selected, players = self.save_v2(conflict)
        self.row['pfr_player_id'] = next(p['pfr_id'] for p in players if p['last_name'] == 'SF')
        result, _ = self.refresh()
        self.assertEqual(result['status'], 'READY'); self.assertEqual(result['metrics']['joined'], 0)
        self.assertEqual(result['metrics']['observed_zero'], 0)
        snapshot, roster = inventory.load_inventory(self.root, selected)
        self.assertEqual(next(r for r in roster if r['team'] == 'SF')['pfr_id'], '')
        self.assertEqual(next(t for t in snapshot['teams'] if t['team'] == 'SF')['players'][0]['usage_identity']['status'], 'CONFLICT')

    def test_v2_archive_completed_at_t60_cannot_replace_v1_cohort(self):
        self.save_v2(durable=GAME['lock_at'])
        result, _ = self.refresh()
        self.assertEqual(result['selected_games'], {GAME['game_id']: self.first})

    def test_v2_team_version_mismatch_rejected(self):
        selected, _ = self.save_v2(); snapshot, roster = inventory.load_inventory(self.root, selected)
        next(t for t in snapshot['teams'] if t['team'] == 'SF')['inventory_version'] = 1
        with self.assertRaises(ValueError): self.api.link(snapshot, roster, [], self.final, CHECK)

    def test_v2_qualified_provider_alias_is_used_only_by_v2(self):
        def alias(players):
            next(p for p in players if p['last_name'] == 'SF')['common_first_name'] = 'Athlete'
        selected, players = self.save_v2(alias)
        self.row.update(player='Athlete SF', pfr_player_id=next(p['pfr_id'] for p in players if p['last_name'] == 'SF'))
        result, _ = self.refresh(); self.assertEqual(result['metrics']['joined'], 1)
        v1, original = inventory.load_inventory(self.root, self.first)
        sf = next(row for row in original if row['team'] == 'SF'); sf['_usage_identity_aliases'] = ['athlete sf']
        result = self.api.link(v1, original, [dict(self.row, pfr_player_id=sf['pfr_id'])], self.final, CHECK)
        self.assertEqual(result['joined'], 0)
        v2, derived = inventory.load_inventory(self.root, selected)
        self.assertEqual(self.api.link(v2, derived, [dict(self.row, player='Other Person')], self.final, CHECK)['joined'], 0)

    def test_v2_duplicate_provider_pfr_and_auxiliary_conflict_do_not_admit(self):
        for row in self.roster: row['esb_id'] = 'roster-esb'
        def conflicts(players):
            sf = next(p for p in players if p['last_name'] == 'SF')
            lar = next(p for p in players if p['last_name'] == 'LAR')
            sf['pfr_id'] = lar['pfr_id']; sf['esb_id'] = 'other-esb'
        selected, players = self.save_v2(conflicts)
        self.row['pfr_player_id'] = next(p['pfr_id'] for p in players if p['last_name'] == 'SF')
        result, _ = self.refresh(); self.assertEqual(result['metrics']['joined'], 0)
        snapshot, roster = inventory.load_inventory(self.root, selected)
        for team in snapshot['teams']:
            if team['team'] in ('SF', 'LAR'):
                self.assertEqual(team['players'][0]['usage_identity']['status'], 'CONFLICT')
        self.assertTrue(all(not r['pfr_id'] for r in roster if r['team'] in ('SF', 'LAR')))

    def test_v2_actual_pinned_offensive_linemen_missing_ids_link_zero_and_positive(self):
        from research.pgo_replacement_depth_20260910 import capture as source
        repo = Path(__file__).resolve().parents[1]
        ref = dict(path='source-archive/49de6434fb4ec3d13abb7de9906bf931fb35ea4fcb2e7ac357ca8e1d3e3d6e92.csv.gz',
                   sha256='49de6434fb4ec3d13abb7de9906bf931fb35ea4fcb2e7ac357ca8e1d3e3d6e92', bytes=362154,
                   url=source.ROSTER_URL, captured_at='2026-09-12T23:54:42.450271+00:00')
        real = list(source._csv(source.read_source(repo/'docs/evidence/season-2026', ref, '2026-09-13T02:17:58Z')))
        # Exact excerpts of full provider SHA b2fd8b7a...; observations are used in a disposable synthetic game only.
        pairs = [('SF', '00-0027857', 'WillTr21', 'Trent Williams', 'Trenton', 'Trent', 'Williams', '1988-07-19'),
                 ('LAR', '00-0030097', 'QuesDa00', 'David Quessenberry', 'David', 'David', 'Quessenberry', '1990-08-24')]
        for row in self.roster: row.update(birth_date='1995-01-02', pfr_id='')
        providers = identity_rows(self.roster)
        for team, gsis, pfr, name, first, common, last, dob in pairs:
            row = next(r for r in real if inventory.normalize_team(r['team']) == team and r['gsis_id'] == gsis)
            self.assertEqual(row['pfr_id'], ''); self.assertEqual(row['position'], 'OL')
            index = next(i for i,r in enumerate(self.roster) if r['team'] == team)
            self.roster[index] = {key:row.get(key, '') for key in self.roster[index]}
            self.depth[index].update(gsis_id=gsis, player_name=row['full_name'], pos_abb='LT')
            providers[index].update(gsis_id=gsis, pfr_id=pfr, display_name=name, first_name=first,
                                    common_first_name=common, last_name=last, birth_date=dob)
        checked = '2026-09-13T02:17:58Z'
        game = dict(GAME, kickoff='2026-09-14T00:35:00Z', lock_at='2026-09-13T23:35:00Z')
        for row in self.depth: row['dt'] = checked
        state = dict(schema_version=1, season=2026, checked_at=checked,
                     source_captures=sources(self.root, self.roster, self.depth, checked), weeks=[dict(games=[game])])
        state['source_captures'].append(identity_source(self.root, providers, checked))
        state['offensive_inventory'] = inventory.capture(state, self.root, checked, inventory_version=2)
        pointer = archive(self.root, state, '2026-09-13T02:17:59Z'); snapshot, roster = inventory.load_inventory(self.root, pointer)
        final = dict(self.final, kickoff=game['kickoff'], finalized_at='2026-09-14T04:00:00Z')
        snaps = [dict(self.row, team=t, opponent='SF' if t == 'LAR' else 'LA', pfr_player_id=pfr,
                      player=name, offense_snaps='0' if t == 'SF' else '25') for t,_,pfr,name,*_ in pairs]
        linked = self.api.link(snapshot, roster, snaps, final, '2026-09-14T05:00:00Z')
        self.assertEqual((linked['joined'], linked['observed_zero'], linked['observed_positive']), (2,1,1))


if __name__ == '__main__':
    unittest.main()
