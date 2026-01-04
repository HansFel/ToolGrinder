import unittest
import json
import os
from Grinder import compute_front_start_positions

class TestFrontPositions(unittest.TestCase):
    def setUp(self):
        self.template = json.load(open(os.path.join('ToolLib','template1.json'),'r',encoding='utf-8'))

    def test_positions_count_and_values(self):
        starts = compute_front_start_positions(self.template)
        # default template: x_start=0.0, x_step=0.5, anzahl_passe=5 -> starts at 0.0,0.5,1.0,1.5,2.0
        expected_x = [0.0, 0.5, 1.0, 1.5, 2.0]
        self.assertEqual(len(starts), 5)
        for i, (p, sx, d) in enumerate(starts):
            self.assertEqual(sx, expected_x[i])
            # depth should be negative and decreasing
            self.assertLess(d, 0)

if __name__ == '__main__':
    unittest.main()
