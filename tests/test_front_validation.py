import unittest
import json
import os
from Grinder import validate_front_config

class TestFrontValidation(unittest.TestCase):
    def setUp(self):
        with open(os.path.join('ToolLib', 'template1.json'), 'r', encoding='utf-8') as fh:
            self.template = json.load(fh)

    def test_template_valid(self):
        ok, errors = validate_front_config(self.template)
        self.assertTrue(ok, msg=f'Expected template to be valid, got errors: {errors}')

    def test_missing_front(self):
        cfg = {}
        ok, errors = validate_front_config(cfg)
        self.assertFalse(ok)
        self.assertIn('Missing section "aktionen.front" or "front"', errors)

    def test_invalid_x(self):
        cfg = json.loads(json.dumps(self.template))
        cfg['aktionen']['front']['x_start'] = 10
        cfg['aktionen']['front']['x_end'] = 5
        ok, errors = validate_front_config(cfg)
        self.assertFalse(ok)
        self.assertTrue(any('x_end must be greater' in e for e in errors))

    def test_old_front_structure_still_validates(self):
        cfg = {
            'front': {
                'x_start': 0.0,
                'x_end': 1.0,
                'zustellung_pro_pass': 0.1,
                'feed': 200.0,
                'spindle': 3000,
            },
            'werkzeug': {
                'durchmesser': 12.0,
            },
        }

        ok, errors = validate_front_config(cfg)

        self.assertTrue(ok, msg=f'Expected old front structure to be valid, got errors: {errors}')

if __name__ == '__main__':
    unittest.main()
