import copy
from contextlib import redirect_stderr
import csv
from datetime import UTC, datetime
import hashlib
import io
import json
import math
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import generate_site
import pgo_forecast_lab


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "docs/evidence/forecast-lab-2026"
LOCK = ARCHIVE / "prospective_lock.json"
PREDICTIONS = ARCHIVE / "prospective_predictions.csv"
ATTESTATION = ROOT / "research/pgo_stability_blend/prospective_attestation.json"


class ForecastLabTests(unittest.TestCase):
    def synthetic_lock(self):
        return {
            "as_of": "2026-07-21T12:00:00-04:00",
            "candidate": {
                "as_of": "2026-08-26T14:29:26-04:00",
                "formula": "0.75*pgo_v0_prediction+0.25*challenger_prediction",
            },
            "games": [
                {
                    "game_id": "g1", "season": 2026, "week": 1,
                    "kickoff": "2026-09-10T00:20:00+00:00",
                    "home": "SEA", "away": "NE", "game_type": "REG",
                    "location": "Home", "candidate_prediction": 1.0,
                    "pgo_v0_prediction": 2.0, "challenger_prediction": -2.0,
                    "challenger_full_strength_prediction": -1.0,
                },
                {
                    "game_id": "g2", "season": 2026, "week": 1,
                    "kickoff": "2026-09-11T00:35:00+00:00",
                    "home": "LAR", "away": "SF", "game_type": "REG",
                    "location": "Neutral", "candidate_prediction": -4.0,
                    "pgo_v0_prediction": -1.0, "challenger_prediction": -13.0,
                    "challenger_full_strength_prediction": -12.0,
                },
            ],
        }

    def synthetic_snapshot(self):
        teams = []
        for rank, team in enumerate(
                sorted(pgo_forecast_lab.pgo_prospective.pgo_model.CURRENT_TEAMS), 1):
            teams.append({
                "rank": rank,
                "team": team,
                "rating": 10.0 - rank,
                "qb_name": f"{team} QB1",
                "qb_gsis_id": f"{team}-QB1",
                "old_selector_qb_name": f"{team} old QB",
                "old_selector_rating": 9.5 - rank,
                "features": {},
                "contributions": {},
            })
        return {
            "generated_at": "2026-09-07T22:00:00Z",
            "league_mean_total": 46.0,
            "teams": teams,
            "games": [
                {
                    "game_id": "s1", "season": 2026, "week": 1,
                    "kickoff": "2026-09-10T00:20:00+00:00",
                    "home": "SEA", "away": "NE", "game_type": "REG",
                    "location": "Home", "home_rest": 7.0, "away_rest": 7.0,
                    "margin": 2.5, "total": 45.0,
                    "home_points": 23.75, "away_points": 21.25,
                    "pgo_v0_margin": 1.0, "legacy_margin": 0.5,
                    "old_selector_margin": 2.0,
                },
                {
                    "game_id": "s2", "season": 2026, "week": 18,
                    "kickoff": "2027-01-04T01:20:00+00:00",
                    "home": "LAR", "away": "SF", "game_type": "REG",
                    "location": "Home", "home_rest": 7.0, "away_rest": 7.0,
                    "margin": -3.0, "total": 44.0,
                    "home_points": 20.5, "away_points": 23.5,
                    "pgo_v0_margin": -1.0, "legacy_margin": -2.0,
                    "old_selector_margin": -2.5,
                },
            ],
            "lock": {
                "as_of": "2026-09-07T22:00:00+00:00",
                "games": [
                    {
                        "game_id": "s1", "season": 2026, "week": 1,
                        "kickoff": "2026-09-10T00:20:00+00:00",
                        "home": "SEA", "away": "NE", "game_type": "REG",
                        "location": "Home", "candidate_prediction": 2.5,
                    },
                    {
                        "game_id": "s2", "season": 2026, "week": 18,
                        "kickoff": "2027-01-04T01:20:00+00:00",
                        "home": "LAR", "away": "SF", "game_type": "REG",
                        "location": "Home", "candidate_prediction": -3.0,
                    },
                ],
            },
            "method": {
                "name": "Active-roster preseason scenario",
                "status": "EXPERIMENTAL — HOLD",
                "roster_policy": "ACT-only roster captured September 7.",
                "injury_coverage": "No comprehensive injury or inactive adjustment.",
                "history": "Performance features use games through 2025.",
                "totals": "Prior-season PF/PA mean.",
                "fit_recovery": "Public fit reproduced exactly.",
                "evaluation": "New inference policy is not historically validated.",
                "schedule": "Week 18 times are provisional.",
            },
            "sources": [],
        }

    def result_rows(self):
        return [
            {
                "game_id": "g1", "season": "2026", "week": "1",
                "kickoff": "2026-09-10T00:20:00+00:00", "game_type": "REG",
                "home_team": "SEA", "away_team": "NE",
                "home_score": "24", "away_score": "21",
                "finalized_at": "2026-09-10T03:30:00+00:00",
            },
            {
                "game_id": "g2", "season": "2026", "week": "1",
                "kickoff": "2026-09-11T00:35:00+00:00", "game_type": "REG",
                "home_team": "LAR", "away_team": "SF",
                "home_score": "17", "away_score": "19",
                "finalized_at": "2026-09-11T04:00:00+00:00",
            },
        ]

    def csv_bytes(self, rows):
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=pgo_forecast_lab.RESULT_COLUMNS,
                                lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        return output.getvalue().encode("utf-8")

    def write_capture(self, root, name, rows, *, captured_at=None,
                      source_url="https://example.com/results.csv"):
        directory = root / name
        directory.mkdir(parents=True)
        payload = self.csv_bytes(rows)
        (directory / "results.csv").write_bytes(payload)
        metadata = {
            "schema_version": 1,
            "kind": "pgo_forecast_lab_result_transcription",
            "captured_at": captured_at or name.replace(
                name, f"{name[:4]}-{name[4:6]}-{name[6:8]}T{name[9:11]}:{name[11:13]}:{name[13:15]}Z"
            ),
            "source_url": source_url,
            "results_file": "results.csv",
            "results_file_sha256": hashlib.sha256(payload).hexdigest(),
            "rows": len(rows),
        }
        (directory / "capture.json").write_text(
            json.dumps(metadata, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8", newline="",
        )

    def test_load_archive_verifies_real_272_game_artifacts(self):
        lock = pgo_forecast_lab.load_archive(LOCK, PREDICTIONS, ATTESTATION)

        self.assertEqual(len(lock["games"]), 272)
        self.assertEqual(lock["candidate"]["pgo_v1_weight"], 0.25)
        self.assertEqual(
            hashlib.sha256(LOCK.read_bytes()).hexdigest(),
            "d6ebf73188c41046f945a54653bdb89eadc2dc18d917276a47c0166b9ada98e9",
        )
        self.assertEqual(
            hashlib.sha256(PREDICTIONS.read_bytes()).hexdigest(),
            "8b17ab8c4744586e5386a7755ceaf63ccf8a8438533e8c904de68b5bc25dca6f",
        )

    def test_load_archive_rejects_tampered_csv(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            lock_path = root / "lock.json"
            csv_path = root / "predictions.csv"
            attestation_path = root / "attestation.json"
            lock_path.write_bytes(LOCK.read_bytes())
            csv_path.write_bytes(PREDICTIONS.read_bytes() + b"tampered")
            attestation_path.write_bytes(ATTESTATION.read_bytes())

            with self.assertRaisesRegex(ValueError, "prediction CSV"):
                pgo_forecast_lab.load_archive(lock_path, csv_path, attestation_path)

    def test_load_archive_requires_exact_published_attestation_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            changed = Path(temp) / "attestation.json"
            changed.write_bytes(ATTESTATION.read_bytes() + b"\n")
            with self.assertRaisesRegex(ValueError, "published attestation"):
                pgo_forecast_lab.load_archive(LOCK, PREDICTIONS, changed)

    def test_load_archive_runs_internal_lock_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            lock = json.loads(LOCK.read_bytes())
            lock["games"][0]["candidate_prediction"] += 100
            lock["prediction_integrity_sha256"] = (
                pgo_forecast_lab.pgo_prospective._prediction_integrity_hash(
                    lock["games"], include_candidate=True
                )
            )
            lock["artifact_sha256"] = (
                pgo_forecast_lab.pgo_prospective._artifact_hash(lock)
            )
            lock_bytes = (
                pgo_forecast_lab.pgo_prospective._canonical(lock) + "\n"
            ).encode("utf-8")
            predictions = pgo_forecast_lab.pgo_prospective._prediction_csv(
                lock
            ).encode("utf-8")
            attestation = copy.deepcopy(json.loads(ATTESTATION.read_bytes()))
            attestation["derived"].update({
                "lock_artifact_sha256": lock["artifact_sha256"],
                "lock_file_sha256": hashlib.sha256(lock_bytes).hexdigest(),
                "prediction_integrity_sha256": lock["prediction_integrity_sha256"],
                "predictions_file_sha256": hashlib.sha256(predictions).hexdigest(),
            })
            attestation["artifact_sha256"] = (
                pgo_forecast_lab.pgo_prospective._artifact_hash(attestation)
            )
            attestation_bytes = (
                pgo_forecast_lab.pgo_prospective._canonical(attestation) + "\n"
            ).encode("utf-8")
            paths = root / "lock.json", root / "predictions.csv", root / "attestation.json"
            paths[0].write_bytes(lock_bytes)
            paths[1].write_bytes(predictions)
            paths[2].write_bytes(attestation_bytes)

            with patch.object(
                    pgo_forecast_lab, "EXPECTED_ATTESTATION_SHA256",
                    hashlib.sha256(attestation_bytes).hexdigest()), \
                    self.assertRaisesRegex(ValueError, "candidate prediction"):
                pgo_forecast_lab.load_archive(*paths)

    def test_load_results_merges_incremental_captures_and_metrics(self):
        rows = self.result_rows()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write_capture(root, "20260910T040000Z", rows[:1])
            self.write_capture(root, "20260911T050000Z", rows[1:])

            loaded, provenance = pgo_forecast_lab.load_results(
                root, self.synthetic_lock()
            )
            metrics = pgo_forecast_lab.interim_metrics(
                self.synthetic_lock(), loaded
            )

        self.assertEqual([row["game_id"] for row in loaded], ["g1", "g2"])
        self.assertEqual(len(provenance), 2)
        self.assertEqual(metrics["blend"]["mae"], 2.0)
        self.assertEqual(metrics["blend"]["rmse"], 2.0)
        self.assertEqual(metrics["pgo_v0"]["mae"], 1.0)
        self.assertEqual(metrics["zero"]["mae"], 2.5)
        self.assertAlmostEqual(metrics["zero"]["rmse"], math.sqrt(6.5))
        self.assertEqual(metrics["venue"]["mae"], 1.25)
        self.assertEqual(metrics["blend"]["winner"], {
            "correct": 2, "denominator": 2, "accuracy": 1.0,
        })

    def test_load_results_rejects_duplicate_or_invalid_rows(self):
        rows = self.result_rows()
        cases = {
            "duplicate": (rows[:1], rows[:1], "duplicate result"),
            "identity": ([{**rows[0], "home_team": "SF"}], None, "locked home team"),
            "fractional": ([{**rows[0], "home_score": "24.5"}], None, "integer scores"),
            "late-capture": (rows[:1], None, "after capture"),
        }
        for name, (first, second, error) in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                captured = (
                    "2026-09-10T02:00:00Z" if name == "late-capture"
                    else "2026-09-10T04:00:00Z"
                )
                directory_name = (
                    "20260910T020000Z" if name == "late-capture"
                    else "20260910T040000Z"
                )
                self.write_capture(root, directory_name, first,
                                   captured_at=captured)
                if second:
                    self.write_capture(root, "20260911T050000Z", second,
                                       captured_at="2026-09-11T05:00:00Z")
                with self.assertRaisesRegex(ValueError, error):
                    pgo_forecast_lab.load_results(root, self.synthetic_lock())

    def test_load_results_rejects_tampered_hash_and_non_https_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write_capture(root, "20260910T040000Z", self.result_rows()[:1])
            metadata_path = root / "20260910T040000Z/capture.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["source_url"] = "http://example.com/results.csv"
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "HTTPS"):
                pgo_forecast_lab.load_results(root, self.synthetic_lock())

            metadata["source_url"] = "https://example.com/results.csv"
            metadata["results_file_sha256"] = "0" * 64
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "hash"):
                pgo_forecast_lab.load_results(root, self.synthetic_lock())

    def test_result_parser_rejects_duplicate_or_wrong_field_counts(self):
        rows = self.result_rows()[:1]
        valid = self.csv_bytes(rows).decode("utf-8").splitlines()
        cases = {
            "duplicate": (
                valid[0] + ",home_score\n" + valid[1] + ",999\n",
                "duplicate result CSV columns",
            ),
            "surplus": (valid[0] + "\n" + valid[1] + ",oops\n", "field count"),
            "incomplete": (valid[0] + "\n" + valid[1].rsplit(",", 1)[0] + "\n", "field count"),
        }
        for name, (payload, error) in cases.items():
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, error):
                pgo_forecast_lab._accepted_results(
                    payload.encode("utf-8"), self.synthetic_lock(),
                    "2026-09-10T04:00:00Z", name,
                )

    def test_record_results_is_utf8_exact_and_append_only(self):
        rows = self.result_rows()[:1]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "reviewed.csv"
            payload = self.csv_bytes(rows)
            source.write_bytes(payload)
            capture_root = root / "captures"

            frozen_now = datetime(2026, 9, 10, 4, tzinfo=UTC)
            with patch.object(pgo_forecast_lab, "_current_utc",
                              return_value=frozen_now):
                path = pgo_forecast_lab.record_results(
                    source, "https://example.com/results.csv", capture_root,
                    self.synthetic_lock(),
                )
            self.assertEqual((path / "results.csv").read_bytes(), payload)
            with patch.object(pgo_forecast_lab, "_current_utc",
                              return_value=frozen_now), \
                    self.assertRaisesRegex(ValueError, "already exists"):
                pgo_forecast_lab.record_results(
                    source, "https://example.com/results.csv", capture_root,
                    self.synthetic_lock(),
                )

            source.write_bytes(b"\xff")
            with patch.object(
                    pgo_forecast_lab, "_current_utc",
                    return_value=datetime(2026, 9, 11, 5, tzinfo=UTC)), \
                    self.assertRaisesRegex(ValueError, "UTF-8"):
                pgo_forecast_lab.record_results(
                    source, "https://example.com/results.csv", capture_root,
                    self.synthetic_lock(),
                )

    def test_cli_has_no_historical_capture_time_override(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            pgo_forecast_lab.main(["--captured-at", "2026-09-10T04:00:00Z"])

    def test_cli_refuses_output_that_can_overwrite_archive_inputs(self):
        outputs = [LOCK, ARCHIVE / "alternate.html", ARCHIVE / "results/page.html"]
        for output in outputs:
            with self.subTest(output=output), \
                    patch.object(pgo_forecast_lab, "load_archive") as load, \
                    patch.object(pgo_forecast_lab, "atomic_write_text") as write, \
                    redirect_stderr(io.StringIO()):
                self.assertEqual(
                    pgo_forecast_lab.main(["--output", str(output)]), 1
                )
                load.assert_not_called()
                write.assert_not_called()

    def test_result_capture_paths_preserve_exact_bytes_in_git(self):
        attributes = [
            "docs/evidence/forecast-lab-2026/results/20260910T040000Z/results.csv",
            "docs/evidence/forecast-lab-2026/results/20260910T040000Z/capture.json",
        ]
        payload = b"a,b\r\n1,2\r\n"
        raw = subprocess.check_output(
            ["git", "hash-object", "--no-filters", "--stdin"], input=payload,
        )
        for path in attributes:
            with self.subTest(path=path):
                attr = subprocess.check_output(
                    ["git", "check-attr", "text", "--", path], text=True,
                )
                filtered = subprocess.check_output(
                    ["git", "hash-object", f"--path={path}", "--stdin"],
                    input=payload,
                )
                self.assertIn("text: unset", attr)
                self.assertEqual(filtered, raw)

    def test_render_lab_is_standalone_honest_and_escaped(self):
        lock = pgo_forecast_lab.load_archive(LOCK, PREDICTIONS, ATTESTATION)
        html = pgo_forecast_lab.render_lab(lock, [], [])

        self.assertIn("PGO Forecast Lab", html)
        self.assertIn("Can PGO predict football?", html)
        self.assertIn("Experimental", html)
        self.assertIn("Interim tracking", html)
        self.assertIn("0 of 272", html)
        self.assertIn("positive favors the home team", html)
        self.assertIn("negative favors the away team", html)
        self.assertIn("theoretical 50%", html)
        self.assertIn("Staff Picks", html)
        self.assertIn("No editorial picks are published", html)
        self.assertIn("McCabe Ratings", html)
        self.assertNotIn("McCabe rating gap", html)
        self.assertNotIn("PGO-minus-McCabe", html)
        self.assertNotIn("win probability", html.lower())
        self.assertEqual(html.count('data-game-id="'), 272)
        self.assertIn('<details class="forecast-week" open>', html)
        self.assertLess(html.index("Blend home margin"),
                        html.index("Frozen kickoff"))
        self.assertIn("prospective_lock.json", html)
        self.assertIn("prospective_predictions.csv", html)
        self.assertIn("July 21, 2026 at 12:00 PM EDT", html)
        self.assertIn("August 26, 2026 at 4:07 PM EDT", html)
        self.assertIn(
            '<time datetime="2026-09-10T00:20:00+00:00">'
            "September 10, 2026 at 12:20 AM UTC</time>",
            html,
        )
        self.assertIn(
            '<link href="https://fonts.googleapis.com/css2?family=Oswald', html
        )

        escaped = pgo_forecast_lab.render_lab(
            self.synthetic_lock(), [], [{"source_url": "https://example.com/?x=<tag>"}]
        )
        self.assertNotIn("<tag>", escaped)
        self.assertIn("&lt;tag&gt;", escaped)
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            pgo_forecast_lab.render_lab(
                self.synthetic_lock(), [],
                [{"source_url": "javascript:alert(1)"}],
            )

    def test_render_lab_fails_when_shared_style_markers_change(self):
        with patch.object(generate_site, "TEMPLATE", "<html></html>"), \
                self.assertRaisesRegex(ValueError, "style"):
            pgo_forecast_lab.render_lab(self.synthetic_lock(), [], [])

    def test_snapshot_interim_metrics_use_separate_margin_total_and_score_targets(self):
        snapshot = self.synthetic_snapshot()
        results = [{
            "game_id": "s1", "home_score": 24, "away_score": 21,
            "actual_margin": 3,
        }]

        metrics = pgo_forecast_lab.snapshot_interim_metrics(snapshot, results)

        self.assertEqual(metrics["count"], 1)
        self.assertEqual(metrics["margin"]["mae"], 0.5)
        self.assertEqual(metrics["total"]["mae"], 0.0)
        self.assertEqual(metrics["score"]["count"], 2)
        self.assertEqual(metrics["score"]["mae"], 0.25)
        self.assertEqual(metrics["winner"], {
            "correct": 1, "denominator": 1, "accuracy": 1.0,
        })
        self.assertEqual(metrics["baselines"]["pgo_v0"]["margin"]["mae"], 2.0)
        self.assertEqual(metrics["baselines"]["legacy"]["margin"]["mae"], 2.5)
        self.assertEqual(metrics["baselines"]["zero"]["margin"]["mae"], 3.0)
        combined = metrics["baselines"]["league_mean_venue"]
        self.assertEqual(combined["margin"]["mae"], 0.5)
        self.assertEqual(combined["total"]["mae"], 1.0)
        self.assertEqual(combined["score"]["mae"], 0.5)
        cards = pgo_forecast_lab._snapshot_metric_cards(metrics)
        self.assertIn("Original archive margin", cards)
        self.assertIn("League mean + venue", cards)
        self.assertIn("Unavailable", cards)
        self.assertEqual(metrics["ties"], {"actual": 0, "forecast": 0})
        snapshot["games"][0]["margin"] = 0.0
        tied = pgo_forecast_lab.snapshot_interim_metrics(snapshot, results)
        self.assertEqual(tied["ties"], {"actual": 0, "forecast": 1})
        self.assertIsNone(tied["winner"]["accuracy"])

    def test_render_snapshot_is_primary_and_preserves_the_original_archive(self):
        archive = self.synthetic_lock()
        snapshot = self.synthetic_snapshot()

        page = pgo_forecast_lab.render_lab(
            archive, [], [], snapshot=snapshot,
            snapshot_results=[], snapshot_provenance=[{
                "captured_at": "2026-09-11T05:00:00Z",
                "source_url": "https://example.com/results.csv",
                "rows": 1,
                "results_file_sha256": "a" * 64,
            }],
        )

        self.assertLess(page.index("September 7 preseason snapshot"),
                        page.index("Original July/August archive"))
        self.assertIn("Active-roster preseason scenario", page)
        self.assertIn("ACT is an administrative roster status", page)
        self.assertIn("same September 7 state", page)
        self.assertIn("SEA -2.5", page)
        self.assertIn("SF -3.0", page)
        self.assertIn("NE 21, SEA 24", page)
        self.assertIn("SF 24, LAR 21", page)
        self.assertIn("45.0", page)
        self.assertIn("44.0", page)
        self.assertIn(
            '<time datetime="2026-09-10T00:20:00+00:00">'
            "September 9, 2026 at 8:20 PM EDT</time>", page,
        )
        self.assertIn(
            "Scores are rounded to whole points; spreads and totals to one decimal. "
            "Evaluation uses the original unrounded projections.", page,
        )
        self.assertIn(
            "<th>Projected total</th><th>Frozen kickoff</th><th>Actual</th>", page,
        )
        self.assertIn("Week 18", page)
        self.assertIn("Week 18 times are provisional", page)
        self.assertIn("September results provenance", page)
        self.assertIn("https://example.com/results.csv", page)
        self.assertEqual(page.count('class="snapshot-team"'), 32)
        self.assertIn("prospective_lock.json", page)
        self.assertIn("Frozen 25% stability blend", page)
        self.assertNotIn("win probability", page.lower())
        self.assertNotIn("League mean + venue", page)
        for margin in (0.0, 0.0009, -0.0179):
            self.assertEqual(
                pgo_forecast_lab._spread({**snapshot["games"][0], "margin": margin}),
                "Pick'em",
            )

    def test_render_snapshot_rejects_a_post_kickoff_generation_time(self):
        snapshot = self.synthetic_snapshot()
        snapshot["generated_at"] = snapshot["games"][0]["kickoff"]

        with self.assertRaisesRegex(ValueError, "before every kickoff"):
            pgo_forecast_lab.render_lab(
                self.synthetic_lock(), [], [], snapshot=snapshot,
                snapshot_results=[], snapshot_provenance=[],
            )

    def test_cli_loads_a_present_snapshot_and_renders_it_as_primary(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            snapshot_dir = root / "snapshot"
            snapshot_dir.mkdir()
            output = root / "lab.html"
            with patch.object(pgo_forecast_lab, "load_archive",
                              return_value=self.synthetic_lock()), \
                    patch.object(pgo_forecast_lab.pgo_forecast_snapshot,
                                 "load_snapshot",
                                 return_value=self.synthetic_snapshot()) as load, \
                    patch.object(pgo_forecast_lab, "load_results",
                                 side_effect=[([], []), ([], []), ([], [])]), \
                    patch.object(pgo_forecast_lab, "atomic_write_text") as write:
                status = pgo_forecast_lab.main([
                    "--snapshot", str(snapshot_dir),
                    "--weekly", str(root / "weekly"),
                    "--output", str(output),
                ])

            self.assertEqual(status, 0)
            load.assert_called_once_with(snapshot_dir)
            self.assertIn("September 7 preseason snapshot", write.call_args.args[1])

    def test_cli_fails_closed_when_a_present_snapshot_is_damaged(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            snapshot_dir = root / "snapshot"
            snapshot_dir.mkdir()
            output = root / "lab.html"
            with patch.object(pgo_forecast_lab, "load_archive",
                              return_value=self.synthetic_lock()), \
                    patch.object(pgo_forecast_lab.pgo_forecast_snapshot,
                                 "load_snapshot", side_effect=ValueError("damaged")), \
                    patch.object(pgo_forecast_lab, "atomic_write_text") as write, \
                    redirect_stderr(io.StringIO()):
                status = pgo_forecast_lab.main([
                    "--snapshot", str(snapshot_dir),
                    "--output", str(output),
                ])

            self.assertEqual(status, 1)
            write.assert_not_called()

    def test_default_snapshot_requires_the_pinned_manifest_and_presence(self):
        with tempfile.TemporaryDirectory() as temp:
            default = Path(temp) / "missing"
            with patch.object(pgo_forecast_lab, "SNAPSHOT_DIR", default), \
                    patch.object(pgo_forecast_lab,
                                 "EXPECTED_SNAPSHOT_MANIFEST_SHA256", "a" * 64):
                with self.assertRaisesRegex(ValueError, "default snapshot is missing"):
                    pgo_forecast_lab._load_snapshot(default)

            default.mkdir()
            (default / "manifest.json").write_bytes(b"changed\n")
            with patch.object(pgo_forecast_lab, "SNAPSHOT_DIR", default), \
                    patch.object(pgo_forecast_lab,
                                 "EXPECTED_SNAPSHOT_MANIFEST_SHA256", "a" * 64), \
                    patch.object(pgo_forecast_lab.pgo_forecast_snapshot,
                                 "load_snapshot") as load:
                with self.assertRaisesRegex(ValueError, "manifest hash"):
                    pgo_forecast_lab._load_snapshot(default)
                load.assert_not_called()

    def test_cli_records_results_against_the_verified_snapshot_series(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            snapshot_dir = root / "snapshot"
            snapshot_dir.mkdir()
            reviewed = root / "reviewed.csv"
            reviewed.write_bytes(self.csv_bytes([{
                "game_id": "s1", "season": "2026", "week": "1",
                "kickoff": "2026-09-10T00:20:00+00:00", "game_type": "REG",
                "home_team": "SEA", "away_team": "NE",
                "home_score": "24", "away_score": "21",
                "finalized_at": "2026-09-10T03:30:00+00:00",
            }]))
            output = root / "lab.html"
            captured = datetime(2026, 9, 10, 4, tzinfo=UTC)
            with patch.object(pgo_forecast_lab, "load_archive",
                              return_value=self.synthetic_lock()), \
                    patch.object(pgo_forecast_lab.pgo_forecast_snapshot,
                                 "load_snapshot",
                                 return_value=self.synthetic_snapshot()), \
                    patch.object(pgo_forecast_lab, "_current_utc",
                                 return_value=captured):
                status = pgo_forecast_lab.main([
                    "--snapshot", str(snapshot_dir),
                    "--weekly", str(root / "weekly"),
                    "--captures", str(root / "old-results"),
                    "--record-snapshot-results", str(reviewed),
                    "--source-url", "https://example.com/results.csv",
                    "--output", str(output),
                ])

            self.assertEqual(status, 0)
            capture = snapshot_dir / "results/20260910T040000Z"
            self.assertTrue((capture / "results.csv").is_file())
            self.assertIn("1 of 2 finalized results recorded", output.read_text(encoding="utf-8"))

    def test_cli_result_recording_targets_are_mutually_exclusive(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr), self.assertRaises(SystemExit):
            pgo_forecast_lab.main([
                "--record-results", "old.csv",
                "--record-snapshot-results", "new.csv",
            ])
        self.assertIn("not allowed with argument", stderr.getvalue())

    def test_weekly_cutoff_is_per_matchup_and_preseason_stays_separate(self):
        snapshot = self.synthetic_snapshot()
        weekly = {"games": [
            {**snapshot["games"][0], "lock_at": "2026-09-09T23:20:00Z",
             "registered_at": "2026-09-07T22:10:00Z",
             "source_generated_at": snapshot["generated_at"]},
            {**snapshot["games"][1], "lock_at": "2027-01-04T00:20:00Z",
             "registered_at": "2026-09-07T22:10:00Z",
             "source_generated_at": snapshot["generated_at"]},
        ], "revisions": []}
        with patch.object(pgo_forecast_lab, "_current_utc",
                          return_value=datetime(2026, 9, 9, 23, 20, tzinfo=UTC)):
            page = pgo_forecast_lab.render_lab(
                self.synthetic_lock(), [], [], snapshot=snapshot, weekly=weekly,
            )
        self.assertEqual(page.count('data-weekly-game-id="'), 2)
        self.assertIn('data-weekly-cutoff="2026-09-09T23:20:00Z">Locked</span>', page)
        self.assertIn('data-weekly-cutoff="2027-01-04T00:20:00Z">Draft</span>', page)
        self.assertIn("September 9, 2026 at 7:20 PM EDT", page)
        self.assertIn("60 minutes before kickoff", page)
        self.assertIn("SEA -2.5", page)
        self.assertLess(page.index("Weekly game forecasts"),
                        page.index("September 7 preseason baseline"))
        self.assertIn('<details class="preseason-archive" id="preseason-baseline">', page)
        self.assertIn('data-snapshot-game-id="s1"', page)
        self.assertIn("Original July/August archive", page)

    def test_weekly_results_use_their_own_verified_forecast_series(self):
        snapshot = self.synthetic_snapshot()
        weekly = {"games": [{**snapshot["games"][0],
            "lock_at": "2026-09-09T23:20:00Z",
            "registered_at": "2026-09-07T22:10:00Z",
            "source_generated_at": snapshot["generated_at"],
        }], "revisions": []}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            reviewed = root / "reviewed.csv"
            reviewed.write_bytes(self.csv_bytes([{
                "game_id": "s1", "season": "2026", "week": "1",
                "kickoff": "2026-09-10T00:20:00+00:00", "game_type": "REG",
                "home_team": "SEA", "away_team": "NE",
                "home_score": "24", "away_score": "21",
                "finalized_at": "2026-09-10T03:30:00+00:00",
            }]))
            weekly_root = root / "weekly"
            with patch.object(pgo_forecast_lab, "load_archive",
                              return_value=self.synthetic_lock()), \
                    patch.object(pgo_forecast_lab, "_load_snapshot",
                                 return_value=snapshot), \
                    patch.object(pgo_forecast_lab.pgo_forecast_weekly, "load_weekly",
                                 return_value=weekly), \
                    patch.object(pgo_forecast_lab, "_current_utc",
                                 return_value=datetime(2026, 9, 10, 4, tzinfo=UTC)):
                self.assertEqual(pgo_forecast_lab.main([
                    "--snapshot", str(root / "preseason"),
                    "--weekly", str(weekly_root),
                    "--captures", str(root / "legacy"),
                    "--record-weekly-results", str(reviewed),
                    "--source-url", "https://example.com/results.csv",
                    "--output", str(root / "lab.html"),
                ]), 0)
            self.assertTrue((weekly_root / "results/20260910T040000Z/results.csv").is_file())
            self.assertFalse((root / "preseason/results").exists())
            self.assertFalse((root / "legacy").exists())
            page = (root / "lab.html").read_text(encoding="utf-8")
            self.assertIn("1 of 1 recorded weekly forecasts have finalized results", page)
            self.assertIn("0 of 2 finalized results recorded", page)


if __name__ == "__main__":
    unittest.main()
