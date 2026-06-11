import json
import os
import tempfile
import unittest
from pathlib import Path

from Grinder import (
    berechne_durchmesser_aus_z_antastung,
    berechne_drall_grad_pro_mm,
    generiere_linuxcnc_vermess_gcode,
    korrigiere_tastpunkt_linear,
    probe_a_search_span,
    probe_ball_radius,
    probe_y_center_for_helix,
    validate_probe_config,
)


class TestProbeMeasurement(unittest.TestCase):
    def setUp(self):
        with open(os.path.join('ToolLib', 'template1.json'), 'r', encoding='utf-8') as fh:
            self.template = json.load(fh)

    def test_probe_ball_radius_from_measure_config(self):
        self.assertEqual(probe_ball_radius(self.template), 1.5)

    def test_right_hand_probe_y_center_uses_ball_radius(self):
        self.template['aktionen']['vermessen']['drallrichtung'] = 'rechts'

        self.assertEqual(probe_y_center_for_helix(self.template), 1.5)

    def test_a_search_span_uses_one_flute_pitch(self):
        cfg = json.loads(json.dumps(self.template))

        cfg['fraeser']['schneidenanzahl'] = 1
        self.assertEqual(probe_a_search_span(cfg), 360.0)
        cfg['fraeser']['schneidenanzahl'] = 2
        self.assertEqual(probe_a_search_span(cfg), 180.0)
        cfg['fraeser']['schneidenanzahl'] = 3
        self.assertEqual(probe_a_search_span(cfg), 120.0)

    def test_linear_probe_correction(self):
        self.assertEqual(korrigiere_tastpunkt_linear(10.0, '-X', 3.0), 8.5)
        self.assertEqual(korrigiere_tastpunkt_linear(10.0, '+X', 3.0), 11.5)

    def test_diameter_from_z_probe_hit(self):
        diameter = berechne_durchmesser_aus_z_antastung(7.5, 3.0, z_mitte=0.0, richtung='-Z')

        self.assertEqual(diameter, 12.0)

    def test_helix_slope_from_two_points(self):
        self.assertEqual(berechne_drall_grad_pro_mm(0.0, 12.0, 10.0, 32.0), 2.0)

    def test_probe_config_validates_template(self):
        self.assertEqual(validate_probe_config(self.template), [])

    def test_probe_config_rejects_duplicate_result_parameters(self):
        cfg = json.loads(json.dumps(self.template))
        cfg['aktionen']['vermessen']['ergebnis_parameter']['durchmesser'] = 4901

        errors = validate_probe_config(cfg)

        self.assertTrue(any('bereits' in error for error in errors))

    def test_probe_config_requires_two_distinct_helix_positions(self):
        cfg = json.loads(json.dumps(self.template))
        cfg['aktionen']['vermessen']['drall_messpunkte'][1]['x'] = 0.0

        errors = validate_probe_config(cfg)

        self.assertTrue(any('unterschiedliche X-Werte' in error for error in errors))

    def test_probe_config_checks_variable_targets_against_machine_limits(self):
        cfg = json.loads(json.dumps(self.template))
        cfg['aktionen']['vermessen']['diameter_z_probe_target'] = -6.0

        errors = validate_probe_config(cfg)

        self.assertTrue(any('diameter_z_probe_target' in error and 'z_min' in error for error in errors))

    def test_rapid_feed_is_optional(self):
        cfg = json.loads(json.dumps(self.template))
        del cfg['aktionen']['vermessen']['rapid_feed']

        self.assertEqual(validate_probe_config(cfg), [])

    def test_invalid_search_angle_returns_validation_error(self):
        cfg = json.loads(json.dumps(self.template))
        cfg['aktionen']['vermessen']['a_such_start'] = 'links'

        errors = validate_probe_config(cfg)

        self.assertTrue(any('a_such_start' in error for error in errors))

    def test_linuxcnc_measure_gcode_contains_probe_moves(self):
        cfg = json.loads(json.dumps(self.template))
        with tempfile.TemporaryDirectory() as tmp:
            cfg['aktionen']['vermessen']['ausgabe_datei'] = str(Path(tmp) / 'measure.ngc')
            generiere_linuxcnc_vermess_gcode(cfg, 'test.json')
            text = Path(cfg['aktionen']['vermessen']['ausgabe_datei']).read_text(encoding='utf-8')

        self.assertIn('G38.3 X-5.000 F50.000', text)
        self.assertIn('o100 if [#<_task> AND [#5070 EQ 0]]', text)
        self.assertIn('(abort,ToolGrinder: Kein Tastkontakt - Stirnkante in X antasten)', text)
        self.assertIn('G0 Y1.500', text)
        self.assertIn('o110 while [#<_tg_a> LE 90.000]', text)
        self.assertIn('G38.3 Z#<_tg_probe_target_z> F#<_tg_probe_feed>', text)
        self.assertIn('o111 if [#5063 GT #<_tg_best_z>]', text)
        self.assertIn('G0 A#<_tg_best_a>', text)
        self.assertIn('#<_tg_diameter>', text)
        self.assertIn('#<_tg_helix_slope>', text)
        self.assertIn('#<_tg_helix_delta_a>', text)
        self.assertIn('#4901 = #<_tg_front_x>', text)
        self.assertIn('#4902 = #<_tg_diameter>', text)
        self.assertIn('#4903 = #<_tg_helix_slope>', text)
        self.assertIn('#4904 = #<_tg_best_a>', text)
        self.assertIn('#5061', text)
        self.assertIn('#5070', text)


if __name__ == '__main__':
    unittest.main()
