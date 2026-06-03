import json
import os
import unittest

from webapp import validate_config


class TestWebappValidation(unittest.TestCase):
    def setUp(self):
        with open(os.path.join('ToolLib', 'template1.json'), 'r', encoding='utf-8') as fh:
            self.template = json.load(fh)

    def test_template_with_limits_is_valid(self):
        self.assertEqual(validate_config(self.template, 'both'), [])

    def test_invalid_machine_limits_are_reported(self):
        cfg = json.loads(json.dumps(self.template))
        cfg['maschine']['limits']['x_min'] = 10.0
        cfg['maschine']['limits']['x_max'] = 5.0

        errors = validate_config(cfg, 'both')

        self.assertTrue(any('maschine.limits.x_min' in error for error in errors))


if __name__ == '__main__':
    unittest.main()
