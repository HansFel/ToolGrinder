import unittest
import json
import os
from Grinder import compute_front_start_positions

class TestFrontPositions(unittest.TestCase):
    def setUp(self):
        with open(os.path.join('ToolLib', 'template1.json'), 'r', encoding='utf-8') as fh:
            self.template = json.load(fh)

    def test_positions_count_and_values(self):
        starts = compute_front_start_positions(self.template)
        # template1: x_start=0.0, x_end=3.0, x_step=0.01 -> 301 starts incl. both ends
        self.assertEqual(len(starts), 301)
        self.assertEqual(starts[0], (1, 0.0, 0.0))
        self.assertEqual(starts[-1], (301, 3.0, 0.0))
        self.assertAlmostEqual(starts[50][1], 0.5)

    def test_positions_cap_at_x_end(self):
        cfg = json.loads(json.dumps(self.template))
        cfg['aktionen']['front']['x_end'] = 0.03
        cfg['aktionen']['front']['zustellung_pro_pass'] = 0.02

        starts = compute_front_start_positions(cfg)

        self.assertEqual(starts, [
            (1, 0.0, 0.0),
            (2, 0.02, 0.0),
            (3, 0.03, 0.0),
        ])

if __name__ == '__main__':
    unittest.main()
