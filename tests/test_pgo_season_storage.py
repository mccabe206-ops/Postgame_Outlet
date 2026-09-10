import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest

import pgo_season as season
import pgo_season_availability as availability
from tests import test_pgo_season_availability as availability_tests


class SeasonStorageTests(unittest.TestCase):
    def test_compact_capture_preserves_name_aliases_and_offline_replay(self):
        fixture=availability_tests.SeasonAvailabilityTests(); fixture.setUp()
        roster=copy.deepcopy(fixture.roster)
        roster[0].update(first_name="Drake",football_name="Drake",last_name="Maye",unused_payload="x"*100000)
        roster.append(dict(team="BUF",gsis_id="00-9999999",full_name="Unused Player",position="WR",status="ACT"))
        before=copy.deepcopy(roster)
        def fetch(url):
            raw=fixture.report().encode() if url==availability.REPORT_URL else b"<html></html>"
            return dict(body=raw,status=200,final_url=url)
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)/"capture"
            result=availability.capture_availability([fixture.game],roster,fixture.qbs,directory,now=fixture.now,fetch=fetch)
            self.assertEqual(result,availability.load_availability(directory))
            packed=(directory/"inputs.json.gz").read_bytes()
            saved=json.loads(gzip.decompress(packed))
            self.assertLess(len(packed),2000)
            self.assertNotIn("unused_payload",saved["roster"][0])
            self.assertEqual(saved["roster"][0]["football_name"],"Drake")
            self.assertNotIn("BUF",{r["team"] for r in saved["roster"]})
            self.assertTrue(all(p.name.endswith(".gz") for p in (directory/"raw").iterdir()))
        self.assertEqual(roster,before)

    def test_legacy_state_still_loads_and_new_states_are_compressed(self):
        state=dict(schema_version=1,season=2026,current_week=1,status="READY",checked_at="2026-09-09T18:00:00Z",weeks=[],rankings={},results=[],sources=[],repeated="same "*10000)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); old=root/"runs/20260909T180000000000Z";old.mkdir(parents=True)
            raw=season.canonical(state); (old/"state.json").write_bytes(raw)
            manifest=season.canonical(dict(files={"state.json":dict(sha256=season.sha(raw),bytes=len(raw))}))
            (old/"manifest.json").write_bytes(manifest)
            (root/"current.json").write_bytes(season.canonical(dict(path=old.relative_to(root).as_posix(),manifest_sha256=season.sha(manifest))))
            self.assertEqual(season.load_current(root),state)
            newer=dict(state,checked_at="2026-09-09T18:15:00Z")
            directory=season.save_state(newer,root)
            self.assertLess((directory/"state.json.gz").stat().st_size,len(raw)/10)
            self.assertEqual(season.load_current(root),newer)
            self.assertEqual((old/"state.json").read_bytes(),raw)
            self.assertTrue(season.archive_href(directory.relative_to(root).as_posix()+"/state.json.gz").startswith("https://raw.githubusercontent.com/"))
            self.assertEqual(season.archive_href("runs/old/state.json"),"evidence/season-2026/runs/old/state.json")

    def test_future_archives_are_excluded_from_pages_while_originals_remain(self):
        root=Path(__file__).resolve().parents[1]
        config=(root/"docs/_config.yml").read_text(encoding="utf-8")
        self.assertFalse((root/"docs/.nojekyll").exists())
        for folder in ("runs-v2","availability-v2","source-archive"):
            self.assertIn("evidence/season-2026/"+folder,config)
        self.assertNotIn("- evidence/season-2026/runs\n",config)
        self.assertNotIn("- evidence/season-2026/availability\n",config)
        self.assertNotIn("current.json",config)


if __name__=="__main__":unittest.main()
