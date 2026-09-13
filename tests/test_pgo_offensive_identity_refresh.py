import copy
import csv
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import pgo_season as season
from pgo_season_rollover import source_bytes

URL = 'https://github.com/nflverse/nflverse-data/releases/download/players/players.csv'
NOW = '2026-09-13T03:00:00Z'


class OffensiveIdentityRefreshTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.state = dict(status='READY', results=[], sources=[],
            weeks=[dict(games=[dict(game_id='future', lock_at='2026-09-13T16:00:00Z',
                                   margin=4.5, confidence={'points':4})])],
            replacement_source_check={'status':'READY'}, replacement_depth={'original':'defender evidence'})

    def raw(self):
        row = dict(gsis_id='00-0000001', pfr_id='TestPl00', display_name='Test Player',
            first_name='Test', common_first_name='Test', football_name='Test', last_name='Player',
            birth_date='2000-01-01', esb_id='', nfl_id='', smart_id='', espn_id='')
        stream = io.StringIO(); writer = csv.DictWriter(stream, fieldnames=list(row))
        writer.writeheader(); writer.writerow(row)
        return stream.getvalue().encode()

    def archive(self, captured=NOW):
        raw=self.raw(); path='source-archive/'+season.sha(raw)+'.csv'
        target=self.root/path; target.parent.mkdir(exist_ok=True); target.write_bytes(raw)
        return raw, dict(url=URL, path=path, sha256=season.sha(raw), bytes=len(raw), captured_at=captured)

    def refresh(self, state=None, checked=NOW, failure=None):
        self.assertTrue(hasattr(season, 'refresh_offensive_identity_source'), 'Player-ID source maintenance is missing')
        with patch.object(season, 'now', return_value=checked), \
             patch.object(season, 'fetch_source', side_effect=failure or (lambda url, root:self.archive(checked))) as fetch:
            season.refresh_offensive_identity_source(self.state if state is None else state, self.root)
        return fetch

    def test_archive_plain_csv_and_replay_exact_bytes(self):
        response=MagicMock(); response.__enter__.return_value=response
        response.status=200; response.read.return_value=self.raw()
        with patch.object(season.urllib.request, 'urlopen', return_value=response), patch.object(season, 'now', return_value=NOW):
            raw,ref=season.fetch_source(URL,self.root)
        self.assertTrue(ref['path'].endswith('.csv'), 'A player CSV must retain its actual format')
        self.assertEqual(source_bytes(self.root,ref,NOW),raw)
        state=dict(schema_version=1,season=2026,checked_at=NOW,status='READY',weeks=[],results=[],sources=[],rankings={},source_captures=[ref])
        with patch.object(season,'now',return_value=NOW): season.save_state(state,self.root)
        self.assertEqual(season.load_current(self.root)['source_captures'],[ref])

    def test_refresh_and_reuse_without_changing_roster_forecasts_or_defenders(self):
        before=copy.deepcopy(self.state)
        fetch=self.refresh()
        self.assertEqual(fetch.call_count,1)
        self.assertEqual(self.state['offensive_identity_source_check']['status'],'READY')
        self.assertEqual(self.state['sources'][0]['url'],URL)
        self.state['source_captures']=copy.deepcopy(self.state['sources']); self.state['sources']=[]
        fetch=self.refresh(checked='2026-09-13T03:15:00Z')
        self.assertEqual(fetch.call_count,0)
        self.assertEqual(self.state['sources'],self.state['source_captures'])
        for key in ('weeks','results','replacement_depth','replacement_source_check','status'):
            self.assertEqual(self.state[key],before[key])

    def test_failed_identity_source_is_independent_of_defenders_and_main(self):
        before=copy.deepcopy(self.state)
        fetch=self.refresh(failure=OSError('provider down'))
        self.assertEqual(fetch.call_count,1)
        self.assertEqual(self.state['offensive_identity_source_check']['status'],'BLOCKED')
        for key,value in before.items(): self.assertEqual(self.state[key],value)

    def test_latest_corrupt_or_conflicting_receipt_cannot_fall_back(self):
        _,ref=self.archive(); self.state['source_captures']=[ref]
        (self.root/ref['path']).write_bytes(b'corrupt')
        self.assertEqual(self.refresh().call_count,0)
        self.assertEqual(self.state['offensive_identity_source_check']['status'],'BLOCKED')
        self.archive()
        self.state['source_captures'].append(dict(ref,sha256='0'*64))
        self.assertEqual(self.refresh().call_count,0)
        self.assertEqual(self.state['offensive_identity_source_check']['status'],'BLOCKED')

    def test_stale_source_is_refreshed_but_future_source_is_not_admitted(self):
        _,ref=self.archive('2026-09-12T02:59:59Z'); self.state['source_captures']=[ref]
        self.assertEqual(self.refresh().call_count,1)
        self.assertEqual(self.state['offensive_identity_source_check']['status'],'READY')
        self.state['source_captures']=[dict(ref,captured_at='2026-09-13T03:00:01Z')]
        self.assertEqual(self.refresh().call_count,0)
        self.assertEqual(self.state['offensive_identity_source_check']['status'],'BLOCKED')

    def test_no_future_game_skips_identity_request(self):
        self.state['weeks']=[]
        self.assertEqual(self.refresh().call_count,0)
        self.assertEqual(self.state['offensive_identity_source_check']['status'],'IDLE')

    def test_source_failure_blocks_only_new_offensive_inventory(self):
        previous=dict(offensive_inventory=dict(inventory_version=1,status='DESCRIPTIVE / NOT IN MODEL',teams=[{'saved':1}],games=[]))
        self.state['checked_at']=NOW
        self.state['offensive_identity_source_check']=dict(status='BLOCKED',blocked_reason='Identity source unavailable')
        before=copy.deepcopy(self.state['weeks'])
        season.refresh_experiments(self.state,previous,self.root)
        self.assertEqual(self.state['offensive_inventory']['status'],'BLOCKED')
        self.assertEqual(self.state['offensive_inventory'].get('teams'),previous['offensive_inventory']['teams'])
        self.assertEqual(self.state['offensive_inventory'].get('blocked_reason'),'Identity source unavailable')
        self.assertEqual(self.state['weeks'],before)


if __name__ == '__main__': unittest.main()
