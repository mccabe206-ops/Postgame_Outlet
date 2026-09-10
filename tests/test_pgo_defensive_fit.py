import unittest

from research.pgo_defensive_depth_candidate import train


class DefenseFitTests(unittest.TestCase):
    def test_extra_defense_block_cannot_change_base_features_or_targets(self):
        old = dict(game_id='g', season=2020, week=1, kickoff='2020-09-01T20:00:00+00:00', actual_margin=7., features={'base': 1.})
        row = train.audit.ch.FeatureRow(**{**old, 'features': {**old['features'], **{k: None for k in train.FEATURES}}, 'subgroup_flags': {}})
        train.validate_rows([row], [old])
        row.features['base'] = 2.
        with self.assertRaisesRegex(ValueError, 'baseline feature'):
            train.validate_rows([row], [old])
        row.features['base'] = 1.
        with self.assertRaisesRegex(ValueError, 'identity, order or target'):
            train.validate_rows([row], [{**old, 'actual_margin': 8.}])


if __name__ == '__main__':
    unittest.main()
