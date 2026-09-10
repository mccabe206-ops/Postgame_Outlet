"""Load only the independently reviewed descriptive edition, with an external pin."""
from pathlib import Path

from research.pgo_defensive_depth_candidate import evidence

EXPECTED_MANIFEST_SHA256 = 'f2859781dd2aaebe542c754ced1c89b518115087f9f4d7e3ce45db27d1b09aed'


def load_verified(directory=evidence.DEFAULT, optional=False):
    directory = Path(directory)
    if not directory.exists() and optional:
        return None
    try:
        if evidence.digest(directory/'manifest.json') != EXPECTED_MANIFEST_SHA256:
            raise ValueError('Defensive depth edition differs from the reviewed manifest')
    except OSError as error:
        raise ValueError('Defensive depth manifest is unavailable') from error
    return evidence.load_verified(directory)
