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
    probe_ball_radius,
    validate_probe_config,
)


class TestProbeMeasurement(unittest.TestCase):
    def setUp(self):
        with open(os.path.join('ToolLib', 'template1.json'), 'r', encoding='utf-8') as fh:
            self.template = json.load(fh)

    def test_probe_ball_radius_from_measure_config(self):
        self.assertEqual(probe_ball_radius(self.template), 1.5)

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

    def test_linuxcnc_measure_gcode_contains_probe_moves(self):
        cfg = json.loads(json.dumps(self.template))
        with tempfile.TemporaryDirectory() as tmp:
            cfg['aktionen']['vermessen']['ausgabe_datei'] = str(Path(tmp) / 'measure.ngc')
            generiere_linuxcnc_vermess_gcode(cfg, 'test.json')
            text = Path(cfg['aktionen']['vermessen']['ausgabe_datei']).read_text(encoding='utf-8')

        self.assertIn('G38.2 X-5.000 F50.000', text)
        self.assertIn('G38.2 Z-2.000 F50.000', text)
        self.assertIn('#5061', text)
        self.assertIn('#5070', text)


if __name__ == '__main__':
    unittest.main()
