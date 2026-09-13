import copy
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pgo_player_identity as identity


NOW = '2026-09-13T02:17:57.832011+00:00'
PUBLISHED = '2026-09-12T11:52:49+00:00'


def roster(gsis='00-0000001', pfr='', name='Jane Doe', dob='1995-01-02', **values):
    row = {
        'gsis_id': gsis, 'pfr_id': pfr, 'full_name': name,
        'first_name': name.split()[0], 'football_name': name.split()[0],
        'last_name': name.split()[-1], 'birth_date': dob,
        'esb_id': 'ESB1', 'gsis_it_id': 'NFL1', 'smart_id': 'SMART1',
        'espn_id': '101', 'team': 'PIT',
    }
    row.update(values)
    return row


def player(gsis='00-0000001', pfr='DoeJa00', name='Jane Doe', dob='1995-01-02', **values):
    row = {
        'gsis_id': gsis, 'pfr_id': pfr, 'display_name': name,
        'first_name': name.split()[0], 'common_first_name': name.split()[0],
        'football_name': name.split()[0], 'last_name': name.split()[-1],
        'birth_date': dob, 'esb_id': 'ESB1', 'nfl_id': 'NFL1',
        'smart_id': 'SMART1', 'espn_id': '101',
    }
    row.update(values)
    return row


class ResolveTests(unittest.TestCase):
    def test_provider_fills_missing_pfr_without_mutating_inputs(self):
        source_roster, players = [roster()], [player()]
        before_roster, before_players = copy.deepcopy(source_roster), copy.deepcopy(players)

        enriched, records = identity.resolve(source_roster, players)

        self.assertEqual(enriched[0]['pfr_id'], 'DoeJa00')
        self.assertEqual(enriched[0]['_usage_identity_aliases'], ['jane doe'])
        self.assertEqual(records, {'00-0000001': {
            'pfr_id': 'DoeJa00', 'status': 'PROVIDER', 'reasons': [],
            'aliases': ['jane doe']}})
        self.assertEqual(source_roster, before_roster)
        self.assertEqual(players, before_players)
        self.assertIsNot(enriched, source_roster)
        self.assertIsNot(enriched[0], source_roster[0])

    def test_unique_roster_pfr_survives_absent_provider(self):
        enriched, records = identity.resolve([roster(pfr='DoeJa00')], [])
        self.assertEqual(enriched[0]['pfr_id'], 'DoeJa00')
        self.assertEqual(records['00-0000001'], {
            'pfr_id': 'DoeJa00', 'status': 'ROSTER', 'reasons': [],
            'aliases': []})
        self.assertEqual(enriched[0]['_usage_identity_aliases'], [])

    def test_auxiliary_conflict_withholds_existing_pfr(self):
        current = roster(gsis='00-0031484', pfr='ManhCh00', name='Chris Manhertz',
                         dob='1992-04-10', espn_id='2531358')
        provider = player(gsis='00-0031484', pfr='ManhCh00', name='Chris Manhertz',
                          dob='1992-04-10', espn_id='4071345')

        enriched, records = identity.resolve([current], [provider])

        self.assertEqual(enriched[0]['pfr_id'], '')
        self.assertEqual(records['00-0031484'], {
            'pfr_id': None, 'status': 'CONFLICT',
            'reasons': ['ESPN_ID_MISMATCH'], 'aliases': []})

    def test_missing_link_requires_name_dob_and_consistent_available_aux_ids(self):
        cases = (
            (player(name='Other Person'), 'NAME_MISMATCH', 'CONFLICT'),
            (player(display_name='', first_name='', common_first_name='',
                    football_name='', last_name=''), 'NAME_MISSING', 'MISSING'),
            (player(dob=''), 'DOB_MISSING', 'MISSING'),
            (player(dob='1996-01-02'), 'DOB_MISMATCH', 'CONFLICT'),
            (player(espn_id='999'), 'ESPN_ID_MISMATCH', 'CONFLICT'),
        )
        for provider, reason, status in cases:
            with self.subTest(reason=reason):
                enriched, records = identity.resolve([roster()], [provider])
                self.assertEqual(enriched[0]['pfr_id'], '')
                self.assertEqual(records['00-0000001']['status'], status)
                self.assertIn(reason, records['00-0000001']['reasons'])

    def test_matching_malformed_birth_dates_cannot_corroborate_a_new_link(self):
        enriched, records = identity.resolve(
            [roster(dob='invalid-date')], [player(dob='invalid-date')])
        self.assertEqual(enriched[0]['pfr_id'], '')
        self.assertEqual(records['00-0000001']['status'], 'CONFLICT')
        self.assertIn('DOB_INVALID', records['00-0000001']['reasons'])

        for invalid in ('2026-02-30', '2026-W01-1'):
            with self.subTest(invalid=invalid):
                _, records = identity.resolve([roster(dob=invalid)], [player(dob=invalid)])
                self.assertNotEqual(records['00-0000001']['status'], 'PROVIDER')

    def test_none_alias_components_do_not_invent_a_matching_name(self):
        current = roster(name='None Player', first_name=None, football_name=None)
        provider = player(display_name=None, first_name=None, common_first_name=None,
                          football_name=None, last_name='Player')
        enriched, records = identity.resolve([current], [provider])
        self.assertEqual(enriched[0]['pfr_id'], '')
        self.assertEqual(records['00-0000001']['status'], 'MISSING')
        self.assertIn('NAME_MISSING', records['00-0000001']['reasons'])

    def test_malformed_nonempty_pfr_is_never_retained_or_filled(self):
        for current, provider in (
                (roster(pfr='bad id!'), None),
                (roster(), player(pfr='bad/id'))):
            with self.subTest(current=current['pfr_id']):
                enriched, records = identity.resolve([current], [] if provider is None else [provider])
                self.assertEqual(enriched[0]['pfr_id'], '')
                self.assertEqual(records['00-0000001']['status'], 'CONFLICT')
                self.assertIn('PFR_INVALID', records['00-0000001']['reasons'])
        for observed_legacy_shape in ("O'ShJa00", 'El-MHi20', 'Cox_Mi20', 'AdamD.00'):
            with self.subTest(observed_legacy_shape=observed_legacy_shape):
                _, records = identity.resolve([roster()], [player(pfr=observed_legacy_shape)])
                self.assertEqual(records['00-0000001']['status'], 'PROVIDER')

    def test_duplicate_provider_gsis_or_pfr_rejects_affected_rows(self):
        current = [roster(), roster(gsis='00-0000002', name='John Roe', dob='1994-01-01',
                                   esb_id='ESB2', gsis_it_id='NFL2', smart_id='SMART2', espn_id='102')]
        duplicate_gsis = [player(), player(pfr='DoeJa01')]
        enriched, records = identity.resolve(current[:1], duplicate_gsis)
        self.assertEqual(enriched[0]['pfr_id'], '')
        self.assertEqual(records['00-0000001']['status'], 'CONFLICT')
        self.assertIn('DUPLICATE_PROVIDER_GSIS', records['00-0000001']['reasons'])

        providers = [player(), player(gsis='00-0000002', pfr='DoeJa00', name='John Roe',
                                      dob='1994-01-01', esb_id='ESB2', nfl_id='NFL2',
                                      smart_id='SMART2', espn_id='102')]
        enriched, records = identity.resolve(current, providers)
        self.assertEqual([r['pfr_id'] for r in enriched], ['', ''])
        self.assertTrue(all(r['status'] == 'CONFLICT' for r in records.values()))
        self.assertTrue(all('DUPLICATE_PROVIDER_PFR' in r['reasons'] for r in records.values()))

    def test_current_identity_duplicates_fail_closed(self):
        with self.assertRaisesRegex(ValueError, 'Duplicate roster GSIS'):
            identity.resolve([roster(), roster()], [])

        current = [roster(pfr='DoeJa00'),
                   roster(gsis='00-0000002', pfr='DoeJa00', name='John Roe')]
        enriched, records = identity.resolve(current, [])
        self.assertEqual([r['pfr_id'] for r in enriched], ['', ''])
        self.assertTrue(all(r['status'] == 'CONFLICT' for r in records.values()))
        self.assertTrue(all(r['reasons'] == ['DUPLICATE_ROSTER_PFR'] for r in records.values()))

    def test_provider_candidate_cannot_take_another_roster_players_pfr(self):
        current = [roster(), roster(gsis='00-0000002', pfr='DoeJa00', name='John Roe')]
        enriched, records = identity.resolve(current, [player()])
        self.assertEqual(enriched[0]['pfr_id'], '')
        self.assertEqual(records['00-0000001']['status'], 'CONFLICT')
        self.assertIn('ROSTER_PFR_OWNER_MISMATCH', records['00-0000001']['reasons'])

    def test_noncanonical_gsis_stays_unresolved(self):
        current = [roster(gsis='HEN032810', pfr='HendCh00')]
        enriched, records = identity.resolve(current, [player(gsis='HEN032810', pfr='HendCh00')])
        self.assertEqual(enriched[0]['pfr_id'], '')
        self.assertEqual(records, {})


class SourceTests(unittest.TestCase):
    def csv(self, *, header=None, row=None):
        header = list(header or identity.REQUIRED_COLUMNS)
        values = player()
        row = list(row or (values[name] for name in header))
        return (','.join(header) + '\n' + ','.join(row) + '\n').encode()

    def test_parse_requires_strict_schema_and_row_width(self):
        raw = self.csv()
        self.assertEqual(identity.parse(raw), [player()])
        with self.assertRaisesRegex(ValueError, 'Missing player columns'):
            identity.parse(self.csv(header=identity.REQUIRED_COLUMNS[:-1]))
        with self.assertRaisesRegex(ValueError, 'Duplicate player column'):
            identity.parse(self.csv(header=[*identity.REQUIRED_COLUMNS, 'gsis_id']))
        with self.assertRaisesRegex(ValueError, 'player row width'):
            identity.parse(self.csv(row=[*player().values(), 'extra']))
        with self.assertRaisesRegex(ValueError, 'UTF-8'):
            identity.parse(b'\xff')

    def test_read_source_checks_custody_and_clocks(self):
        raw = self.csv()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'sources').mkdir()
            name = hashlib.sha256(raw).hexdigest() + '.csv'
            path = root / 'sources' / name
            path.write_bytes(raw)
            ref = {
                'url': identity.URL, 'path': 'sources/' + name,
                'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw),
                'captured_at': NOW, 'published_at': PUBLISHED,
            }
            self.assertEqual(identity.read_source(root, ref, NOW), raw)

            for field in ('url', 'sha256', 'captured_at'):
                bad = dict(ref); bad.pop(field)
                with self.subTest(missing=field), self.assertRaises(ValueError):
                    identity.read_source(root, bad, NOW)
            for field in ('captured_at', 'published_at'):
                bad = dict(ref); bad[field] = '2026-09-13T02:17:58+00:00'
                with self.subTest(future=field), self.assertRaises(ValueError):
                    identity.read_source(root, bad, NOW)
            bad = dict(ref); bad['published_at'] = '2026-09-13T02:17:58+00:00'
            with self.assertRaises(ValueError):
                identity.read_source(root, bad, '2026-09-14T00:00:00+00:00')
            no_publication = dict(ref); no_publication['published_at'] = None
            self.assertEqual(identity.read_source(root, no_publication, NOW), raw)
            bad_hash = dict(ref); bad_hash['sha256'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'hash differs'):
                identity.read_source(root, bad_hash, NOW)
            with self.assertRaisesRegex(ValueError, 'older than 24 hours'):
                identity.read_source(root, ref, '2026-09-14T02:17:58+00:00')
            self.assertEqual(identity.read_source(
                root, ref, '2026-09-14T02:17:58+00:00', allow_stale=True), raw)
            with self.assertRaisesRegex(ValueError, 'hash differs'):
                identity.read_source(root, bad_hash, '2026-09-14T02:17:58+00:00',
                                     allow_stale=True)

            original = Path.is_symlink
            with mock.patch.object(Path, 'is_symlink', lambda self: self == root or original(self)):
                with self.assertRaisesRegex(ValueError, 'symlink'):
                    identity.read_source(root, ref, NOW)
            with mock.patch.object(Path, 'is_symlink',
                                   lambda self: self == path.parent or original(self)):
                with self.assertRaisesRegex(ValueError, 'parent symlink'):
                    identity.read_source(root, ref, NOW)


if __name__ == '__main__':
    unittest.main()
