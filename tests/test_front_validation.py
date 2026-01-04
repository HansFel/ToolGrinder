import unittest
import json
import os
from Grinder import validate_front_config

class TestFrontValidation(unittest.TestCase):
    def setUp(self):
        self.template = json.load(open(os.path.join('ToolLib','template1.json'),'r',encoding='utf-8'))

    def test_template_valid(self):
        ok, errors = validate_front_config(self.template)
        self.assertTrue(ok, msg=f'Expected template to be valid, got errors: {errors}')

    def test_missing_front(self):
        cfg = {}
        ok, errors = validate_front_config(cfg)
        self.assertFalse(ok)
        self.assertIn('Missing section "front"', errors)

    def test_invalid_x(self):
        cfg = json.loads(json.dumps(self.template))
        cfg['front']['x_start'] = 10
        cfg['front']['x_end'] = 5
        ok, errors = validate_front_config(cfg)
        self.assertFalse(ok)
        self.assertTrue(any('x_end must be greater' in e for e in errors))

if __name__ == '__main__':
    unittest.main()
