import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pgo_publication_guard import check_publication


class PublicationGuardTests(unittest.TestCase):
    def setUp(self):
        self.guard = check_publication
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.git('init', '-q')
        self.git('config', 'user.name', 'Publication test')
        self.git('config', 'user.email', 'publication@example.invalid')
        self.git('config', 'commit.gpgsign', 'false')
        self.git('config', 'core.autocrlf', 'false')
        self.write('docs/evidence/frozen.json', 'frozen\n')
        self.write('docs/evidence/season-2026/runs-v2/old/state.json.gz', 'frozen archive\n')
        self.tested = self.commit()

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.root,
                                       stderr=subprocess.PIPE).decode().strip()

    def write(self, name, content='changed\n'):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')

    def commit(self):
        self.git('add', '.')
        self.git('commit', '-qm', 'fixture')
        return self.git('rev-parse', 'HEAD')

    def test_unchanged_tested_commit_is_accepted(self):
        result = self.guard(self.tested, self.root)
        self.assertEqual(result['publication_sha'], self.tested)
        self.assertEqual(result['mutable_files'], [])

    def test_latest_mutable_state_and_pages_are_accepted(self):
        paths = ['docs/index.html', 'docs/forecast-lab.html',
                 'docs/evidence/season-2026/current.json',
                 'docs/evidence/season-2026/runs-v2/new/state.json.gz',
                 'docs/evidence/season-2026/offensive-usage/reports/new.json',
                 'docs/evidence/season-2026/injury-usage/targets/new/receipt.json']
        for path in paths:
            self.write(path)
        latest = self.commit()
        result = self.guard(self.tested, self.root)
        self.assertEqual(result['publication_sha'], latest)
        self.assertEqual(set(result['mutable_files']), set(paths))

    def test_source_config_and_frozen_evidence_drift_are_rejected(self):
        for path in ['pgo_season.py', 'pgo_publication_guard.py', 'requirements-pgo.txt',
                     '.github/workflows/update-board.yml', 'docs/pgo-theme.css',
                     'docs/evidence/season-2026/model-seed.json',
                     'docs/evidence/penalty-model-2026/final-fit.json',
                     'docs/evidence/season-2026-other/current.json']:
            with self.subTest(path=path):
                self.write(path)
                self.commit()
                with self.assertRaisesRegex(ValueError, 'Untested changes'):
                    self.guard(self.tested, self.root)
                self.git('checkout', '--detach', self.tested)

    def test_existing_archives_cannot_be_rewritten_or_deleted(self):
        name = 'docs/evidence/season-2026/runs-v2/old/state.json.gz'
        for operation in ('rewrite', 'delete'):
            with self.subTest(operation=operation):
                if operation == 'rewrite':
                    self.write(name, 'different archived forecast\n')
                else:
                    self.git('rm', name)
                self.commit()
                with self.assertRaisesRegex(ValueError, 'Untested changes'):
                    self.guard(self.tested, self.root)
                self.git('checkout', '--detach', self.tested)

    def test_renaming_frozen_evidence_into_mutable_folder_is_rejected(self):
        self.git('mv', 'docs/evidence/frozen.json', 'docs/evidence/season-2026/frozen.json')
        self.commit()
        with self.assertRaisesRegex(ValueError, 'Untested changes'):
            self.guard(self.tested, self.root)

    def test_identical_tree_without_tested_ancestry_is_rejected(self):
        tree = self.git('rev-parse', self.tested + '^{tree}')
        unrelated = self.git('commit-tree', tree, '-m', 'Unrelated history')
        self.git('checkout', '--detach', unrelated)
        with self.assertRaisesRegex(ValueError, 'ancestor'):
            self.guard(self.tested, self.root)

    def test_only_a_full_commit_sha_is_accepted(self):
        for value in ['HEAD', self.tested[:7], '--all', '0' * 40]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.guard(value, self.root)

    def test_only_exactly_replayed_added_weekly_report_pairs_are_admitted(self):
        import pgo_weekly_review as reviews
        from tests.test_pgo_weekly_review import WeeklyReviewTests
        fixture = WeeklyReviewTests()
        fixture.archive(self.root, fixture.fixture())
        with patch.object(reviews, 'verify_sources'):
            paths = reviews.publish(self.root)
            latest = self.commit()
            self.assertEqual(self.guard(self.tested, self.root)['publication_sha'], latest)
            # A locally rebuilt pair can replay yet still disagree with the
            # archive bytes committed at publication HEAD.
            import pgo_season as season
            receipt_name = next(p for p in paths if p.endswith('.json'))
            receipt = season.read_json(self.root/receipt_name)
            archive = self.root/'docs/evidence/season-2026'/receipt['source_pointer']['path']
            payload = (archive/'state.json').read_bytes() + b' '
            (archive/'state.json').write_bytes(payload)
            manifest = season.canonical(dict(files={'state.json':dict(sha256=season.sha(payload),bytes=len(payload))}))
            (archive/'manifest.json').write_bytes(manifest)
            pointer = dict(receipt['source_pointer'], manifest_sha256=season.sha(manifest))
            raw, receipt_raw = reviews.build(self.root,pointer,1)
            (self.root/receipt_name).write_bytes(receipt_raw)
            (self.root/receipt_name.replace('.json','.html')).write_bytes(raw)
            with self.assertRaisesRegex(ValueError, 'committed bytes'):
                self.guard(self.tested, self.root)
            self.git('restore','--worktree','.')
            # A new report is not a free-form HTML publishing path.
            self.git('checkout', '--detach', self.tested)
            for path in paths: self.write(path, 'arbitrary HTML or receipt')
            self.commit()
            with self.assertRaises((ValueError, KeyError)):
                self.guard(self.tested, self.root)

    def test_existing_weekly_report_cannot_be_modified_or_deleted(self):
        name = 'docs/analysis/weekly/2026-week1-final.html'
        self.write(name, 'previous report')
        tested = self.commit()
        self.write(name, 'replacement report')
        self.commit()
        with self.assertRaisesRegex(ValueError, 'Untested changes'):
            self.guard(tested, self.root)


if __name__ == '__main__':
    unittest.main()
