from pathlib import Path
import tempfile
import unittest

from research.pgo_defensive_depth_candidate.validation import load_verified


class DefensiveEditionPinTests(unittest.TestCase):
    def test_missing_optional_edition_is_absent(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertIsNone(load_verified(Path(directory)/'absent',optional=True))

    def test_existing_invalid_edition_is_never_treated_as_absent(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError,'manifest is unavailable'):
                load_verified(directory,optional=True)

    def test_remanifested_package_requires_independent_review(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory)/'manifest.json').write_text('{"files": {}}',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'reviewed manifest'):
                load_verified(directory)


if __name__=='__main__':unittest.main()
