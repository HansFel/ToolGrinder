import json
import os
import unittest

from Grinder import (
    ensure_gcode_within_machine_limits,
    parse_gcode_axes,
    validate_gcode_against_machine_limits,
    validate_machine_limits_config,
)


class TestMachineLimits(unittest.TestCase):
    def setUp(self):
        with open(os.path.join('ToolLib', 'template1.json'), 'r', encoding='utf-8') as fh:
            self.template = json.load(fh)

    def test_parse_gcode_axes_ignores_comments(self):
        axes = parse_gcode_axes('G1 X12.5 Z-0.2 A90.0 F200 (Y999)')

        self.assertEqual(axes, {'X': 12.5, 'Z': -0.2, 'A': 90.0})

    def test_parse_gcode_axes_keeps_words_after_parenthesis_comment(self):
        axes = parse_gcode_axes('G0 (Zwischenkommentar) X5.0 Z10.0')

        self.assertEqual(axes, {'X': 5.0, 'Z': 10.0})

    def test_missing_limits_are_allowed(self):
        cfg = json.loads(json.dumps(self.template))
        del cfg['maschine']['limits']

        self.assertEqual(validate_machine_limits_config(cfg), [])
        self.assertEqual(validate_gcode_against_machine_limits(['G0 X999 Z999'], cfg), [])

    def test_invalid_limit_config_is_reported(self):
        cfg = json.loads(json.dumps(self.template))
        cfg['maschine']['limits'] = {'x_min': 10, 'x_max': 5, 'z_min': 'unten'}

        errors = validate_machine_limits_config(cfg)

        self.assertTrue(any('x_min' in error and 'x_max' in error for error in errors))
        self.assertTrue(any('z_min' in error for error in errors))

    def test_gcode_limit_violation_is_reported(self):
        cfg = json.loads(json.dumps(self.template))
        cfg['maschine']['limits'] = {'x_min': -1.0, 'x_max': 5.0, 'z_min': 0.0, 'z_max': 20.0}

        errors = validate_gcode_against_machine_limits(['G0 X0 Z10', 'G1 X6.2 Z-0.1 F200'], cfg)

        self.assertEqual(len(errors), 2)
        self.assertTrue(any('X=6.200' in error for error in errors))
        self.assertTrue(any('Z=-0.100' in error for error in errors))

    def test_ensure_gcode_raises_on_violation(self):
        cfg = json.loads(json.dumps(self.template))
        cfg['maschine']['limits'] = {'a_min': 0.0, 'a_max': 180.0}

        with self.assertRaises(ValueError):
            ensure_gcode_within_machine_limits(['G0 A270'], cfg)


if __name__ == '__main__':
    unittest.main()
