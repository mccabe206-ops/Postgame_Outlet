import copy
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import pgo_forecast_weekly as weekly


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


class ForecastWeeklyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.evidence = Path(self.temporary.name) / "evidence"
        self.source = self.evidence / "september-07"
        self.weekly_root = self.evidence / "weekly"
        self.source.mkdir(parents=True)
        (self.source / "manifest.json").write_bytes(b'{"fixture":1}\n')
        self.snapshot = {
            "schema_version": 1,
            "edition": "pgo-active-roster-2026-09-07",
            "generated_at": "2026-09-07T22:01:01.941144+00:00",
            "games": [
                self.game("2026_01_DAL_PHI", "2026-09-10T00:20:00+00:00", "DAL", "PHI", 1.5),
                self.game("2026_01_BUF_NYJ", "2026-09-13T17:00:00+00:00", "BUF", "NYJ", -2.25),
            ],
        }

    @staticmethod
    def game(game_id, kickoff, away, home, margin):
        return {
            "game_id": game_id,
            "season": 2026,
            "week": 1,
            "kickoff": kickoff,
            "game_type": "REG",
            "location": "Home",
            "home_rest": 7.0,
            "away_rest": 7.0,
            "home": home,
            "away": away,
            "margin": margin,
            "total": 45.5,
            "home_points": (45.5 + margin) / 2,
            "away_points": (45.5 - margin) / 2,
            "pgo_v0_margin": 0.5,
            "legacy_margin": 1.0,
            "old_selector_margin": margin,
        }

    def loader(self, snapshots=None):
        snapshots = snapshots or {self.source.resolve(): self.snapshot}

        def load(path):
            return copy.deepcopy(snapshots[Path(path).resolve()])

        return mock.patch.object(weekly.pgo_forecast_snapshot, "load_snapshot", side_effect=load)

    def record_at(self, when, *, game_ids=None, source=None, snapshots=None):
        with self.loader(snapshots), mock.patch.object(weekly, "_current_utc", return_value=when):
            return weekly.record_week(source or self.source, self.weekly_root, 1, game_ids)

    def load(self, snapshots=None):
        with self.loader(snapshots):
            return weekly.load_weekly(self.weekly_root)

    def test_records_one_second_before_cutoff(self):
        revision = self.record_at(
            datetime(2026, 9, 9, 23, 19, 59, tzinfo=UTC),
            game_ids=["2026_01_DAL_PHI"],
        )
        self.assertEqual(revision["registered_at"], "2026-09-09T23:19:59.000000Z")
        self.assertEqual(revision["games"][0]["lock_at"], "2026-09-09T23:20:00.000000Z")

    def test_corrected_source_dispatch_preserves_revision_and_derives_edition(self):
        self.snapshot['edition'] = weekly.pgo_forecast_corrected.EDITION
        self.snapshot['league_mean_total'] = 44.5
        (self.source / 'manifest.json').write_text(json.dumps({'edition': self.snapshot['edition']}))
        with mock.patch.object(weekly.pgo_forecast_corrected, 'load_snapshot', return_value=self.snapshot) as loader:
            revision = self.record_at(datetime(2026, 9, 8, 12, tzinfo=UTC))
            path = self.weekly_root / revision['revision']
            before = path.read_bytes()
            series = weekly.load_weekly(self.weekly_root)
            self.assertTrue(loader.called)
            self.assertEqual(series['games'][0]['source_edition'], self.snapshot['edition'])
            self.assertEqual(series['games'][0]['league_mean_total'], 44.5)
            self.assertNotIn('source_edition', revision['games'][0])
            self.assertEqual(path.read_bytes(), before)

    def test_unknown_source_edition_is_rejected(self):
        (self.source / 'manifest.json').write_text('{"edition":"unreviewed"}')
        with self.assertRaisesRegex(ValueError, 'Unknown weekly source edition'):
            self.record_at(datetime(2026, 9, 8, 12, tzinfo=UTC))

    def test_refuses_exactly_at_and_after_cutoff(self):
        for when in (
            datetime(2026, 9, 9, 23, 20, tzinfo=UTC),
            datetime(2026, 9, 9, 23, 20, 1, tzinfo=UTC),
        ):
            with self.subTest(when=when), self.assertRaisesRegex(ValueError, "cutoff"):
                self.record_at(when, game_ids=["2026_01_DAL_PHI"])
        self.assertFalse(self.weekly_root.exists())

    def test_refuses_when_clock_crosses_cutoff_before_exclusive_write(self):
        with self.loader(), mock.patch.object(weekly, "_current_utc", side_effect=[
            datetime(2026, 9, 9, 23, 19, 59, 999999, tzinfo=UTC),
            datetime(2026, 9, 9, 23, 20, tzinfo=UTC),
        ]), self.assertRaisesRegex(ValueError, "cutoff"):
            weekly.record_week(
                self.source, self.weekly_root, 1, ["2026_01_DAL_PHI"]
            )
        self.assertFalse(self.weekly_root.exists())

    def test_removes_new_revision_when_durable_write_crosses_cutoff(self):
        with self.loader(), mock.patch.object(weekly, "_current_utc", side_effect=[
            datetime(2026, 9, 9, 23, 19, 59, 999998, tzinfo=UTC),
            datetime(2026, 9, 9, 23, 19, 59, 999999, tzinfo=UTC),
            datetime(2026, 9, 9, 23, 20, tzinfo=UTC),
        ]), self.assertRaisesRegex(ValueError, "cutoff"):
            weekly.record_week(
                self.source, self.weekly_root, 1, ["2026_01_DAL_PHI"]
            )
        self.assertTrue(self.weekly_root.is_dir())
        self.assertEqual(list(self.weekly_root.iterdir()), [])

    def test_locked_thursday_does_not_block_selected_sunday_update(self):
        self.record_at(
            datetime(2026, 9, 9, 23, 19, tzinfo=UTC),
            game_ids=["2026_01_DAL_PHI"],
        )
        self.record_at(
            datetime(2026, 9, 11, 12, 0, tzinfo=UTC),
            game_ids=["2026_01_BUF_NYJ"],
        )
        series = self.load()
        self.assertEqual(series["count"], 2)
        self.assertEqual(len(series["revisions"]), 2)

    def test_appends_revision_and_returns_latest_game_with_history(self):
        first = self.record_at(
            datetime(2026, 9, 8, 12, 0, tzinfo=UTC),
            game_ids=["2026_01_BUF_NYJ"],
        )
        source_two = self.evidence / "september-10"
        source_two.mkdir()
        (source_two / "manifest.json").write_bytes(b'{"fixture":2}\n')
        changed = copy.deepcopy(self.snapshot)
        changed["generated_at"] = "2026-09-10T12:00:00+00:00"
        changed["games"][1]["margin"] = -3.5
        snapshots = {self.source.resolve(): self.snapshot, source_two.resolve(): changed}
        second = self.record_at(
            datetime(2026, 9, 10, 12, 1, tzinfo=UTC),
            game_ids=["2026_01_BUF_NYJ"], source=source_two, snapshots=snapshots,
        )
        series = self.load(snapshots)
        self.assertNotEqual(first["revision"], second["revision"])
        self.assertEqual(len(series["revisions"]), 2)
        self.assertEqual(series["games"][0]["margin"], -3.5)
        self.assertEqual(series["games"][0]["revision"], second["revision"])
        self.assertEqual(series["games"][0]["source_generated_at"], changed["generated_at"])

    def test_rejects_same_source_same_game_noop_and_older_registration(self):
        self.record_at(
            datetime(2026, 9, 8, 12, 0, 0, 1, tzinfo=UTC),
            game_ids=["2026_01_BUF_NYJ"],
        )
        with self.assertRaisesRegex(ValueError, "already records"):
            self.record_at(
                datetime(2026, 9, 8, 12, 0, 1, tzinfo=UTC),
                game_ids=["2026_01_BUF_NYJ"],
            )
        with self.assertRaisesRegex(ValueError, "later than"):
            self.record_at(
                datetime(2026, 9, 8, 12, 0, tzinfo=UTC),
                game_ids=["2026_01_DAL_PHI"],
            )

    def test_rejects_source_issued_after_registration(self):
        with self.assertRaisesRegex(ValueError, "issued after registration"):
            self.record_at(
                datetime(2026, 9, 7, 22, 1, tzinfo=UTC),
                game_ids=["2026_01_BUF_NYJ"],
            )

    def test_rejects_prior_schedule_identity_change(self):
        self.record_at(
            datetime(2026, 9, 8, 12, 0, tzinfo=UTC),
            game_ids=["2026_01_BUF_NYJ"],
        )
        source_two = self.evidence / "changed"
        source_two.mkdir()
        (source_two / "manifest.json").write_bytes(b'{"fixture":2}\n')
        changed = copy.deepcopy(self.snapshot)
        changed["generated_at"] = "2026-09-09T12:00:00+00:00"
        changed["games"][1]["kickoff"] = "2026-09-13T17:30:00+00:00"
        snapshots = {self.source.resolve(): self.snapshot, source_two.resolve(): changed}
        with self.assertRaisesRegex(ValueError, "identity changed"):
            self.record_at(
                datetime(2026, 9, 9, 12, 1, tzinfo=UTC),
                game_ids=["2026_01_BUF_NYJ"], source=source_two, snapshots=snapshots,
            )

    def test_load_rejects_noncanonical_bytes_and_rehashed_game_tamper(self):
        revision = self.record_at(
            datetime(2026, 9, 8, 12, 0, tzinfo=UTC),
            game_ids=["2026_01_BUF_NYJ"],
        )
        path = self.weekly_root / revision["revision"]
        original = path.read_bytes()
        path.write_bytes(original + b" ")
        with self.assertRaisesRegex(ValueError, "canonical"):
            self.load()
        path.write_bytes(original)
        changed = json.loads(original)
        changed["games"][0]["margin"] = 999
        payload = dict(changed)
        payload.pop("artifact_sha256")
        changed["artifact_sha256"] = hashlib.sha256(canonical(payload).encode()).hexdigest()
        path.write_text(canonical(changed) + "\n", encoding="utf-8", newline="")
        with self.assertRaisesRegex(ValueError, "source snapshot"):
            self.load()

    def test_load_rejects_self_rehashed_revision_registered_at_cutoff(self):
        revision = self.record_at(
            datetime(2026, 9, 8, 12, 0, tzinfo=UTC),
            game_ids=["2026_01_BUF_NYJ"],
        )
        old_path = self.weekly_root / revision["revision"]
        changed = json.loads(old_path.read_bytes())
        changed["registered_at"] = "2026-09-13T16:00:00.000000Z"
        changed["revision"] = "20260913T160000000000Z.json"
        payload = dict(changed)
        payload.pop("artifact_sha256")
        changed["artifact_sha256"] = hashlib.sha256(canonical(payload).encode()).hexdigest()
        old_path.unlink()
        (self.weekly_root / changed["revision"]).write_text(
            canonical(changed) + "\n", encoding="utf-8", newline=""
        )
        with self.assertRaisesRegex(ValueError, "cutoff"):
            self.load()

    def test_load_rejects_boolean_schema_version_even_when_rehashed(self):
        revision = self.record_at(
            datetime(2026, 9, 8, 12, 0, tzinfo=UTC),
            game_ids=["2026_01_BUF_NYJ"],
        )
        path = self.weekly_root / revision["revision"]
        changed = json.loads(path.read_bytes())
        changed["schema_version"] = True
        payload = dict(changed)
        payload.pop("artifact_sha256")
        changed["artifact_sha256"] = hashlib.sha256(canonical(payload).encode()).hexdigest()
        path.write_text(canonical(changed) + "\n", encoding="utf-8", newline="")
        with self.assertRaisesRegex(ValueError, "schema"):
            self.load()

    def test_load_rejects_manifest_tamper_and_source_escape(self):
        revision = self.record_at(
            datetime(2026, 9, 8, 12, 0, tzinfo=UTC),
            game_ids=["2026_01_BUF_NYJ"],
        )
        (self.source / "manifest.json").write_bytes(b'{"fixture":99}\n')
        with self.assertRaisesRegex(ValueError, "manifest"):
            self.load()
        (self.source / "manifest.json").write_bytes(b'{"fixture":1}\n')
        path = self.weekly_root / revision["revision"]
        changed = json.loads(path.read_bytes())
        changed["source_directory"] = "../../outside"
        payload = dict(changed)
        payload.pop("artifact_sha256")
        changed["artifact_sha256"] = hashlib.sha256(canonical(payload).encode()).hexdigest()
        path.write_text(canonical(changed) + "\n", encoding="utf-8", newline="")
        with self.assertRaisesRegex(ValueError, "outside"):
            self.load()

    def test_ignores_real_results_directory_and_caches_source_loads(self):
        self.record_at(
            datetime(2026, 9, 8, 12, 0, tzinfo=UTC),
            game_ids=["2026_01_DAL_PHI"],
        )
        self.record_at(
            datetime(2026, 9, 8, 12, 1, tzinfo=UTC),
            game_ids=["2026_01_BUF_NYJ"],
        )
        (self.weekly_root / "results").mkdir()
        load = mock.Mock(return_value=copy.deepcopy(self.snapshot))
        with mock.patch.object(weekly.pgo_forecast_snapshot, "load_snapshot", load):
            series = weekly.load_weekly(self.weekly_root)
        self.assertEqual(series["count"], 2)
        self.assertEqual(load.call_count, 1)

    def test_rejects_invalid_selection_and_duplicate_games_in_revision(self):
        with self.assertRaisesRegex(ValueError, "game id"):
            self.record_at(datetime(2026, 9, 8, 12, 0, tzinfo=UTC), game_ids=["missing"])
        revision = self.record_at(
            datetime(2026, 9, 8, 12, 1, tzinfo=UTC),
            game_ids=["2026_01_BUF_NYJ"],
        )
        path = self.weekly_root / revision["revision"]
        changed = json.loads(path.read_bytes())
        changed["games"].append(copy.deepcopy(changed["games"][0]))
        payload = dict(changed)
        payload.pop("artifact_sha256")
        changed["artifact_sha256"] = hashlib.sha256(canonical(payload).encode()).hexdigest()
        path.write_text(canonical(changed) + "\n", encoding="utf-8", newline="")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.load()

    def test_cli_records_and_verifies(self):
        with self.loader(), mock.patch.object(
            weekly, "_current_utc", return_value=datetime(2026, 9, 8, 12, tzinfo=UTC)
        ):
            self.assertEqual(weekly.main([
                "--snapshot", str(self.source), "--output", str(self.weekly_root),
                "--week", "1", "--game-id", "2026_01_BUF_NYJ",
            ]), 0)
        with self.loader():
            self.assertEqual(weekly.main(["--output", str(self.weekly_root), "--verify"]), 0)


if __name__ == "__main__":
    unittest.main()
