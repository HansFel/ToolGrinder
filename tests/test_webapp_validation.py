import json
import os
import unittest

from webapp import create_app, validate_config


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

    def test_edge_mode_ignores_unused_invalid_probe_config(self):
        cfg = json.loads(json.dumps(self.template))
        cfg['aktionen']['vermessen']['probe_feed'] = 0

        self.assertEqual(validate_config(cfg, 'edge'), [])

    def test_measure_mode_validates_probe_config(self):
        cfg = json.loads(json.dumps(self.template))
        cfg['aktionen']['vermessen']['probe_feed'] = 0

        errors = validate_config(cfg, 'measure')

        self.assertTrue(any('probe_feed' in error for error in errors))

    def test_index_exposes_german_english_language_switch(self):
        app = create_app()
        app.config['TESTING'] = True

        response = app.test_client().get('/')
        text = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('id="languageSelect"', text)
        self.assertIn('<option value="de">Deutsch</option>', text)
        self.assertIn('<option value="en">English</option>', text)
        self.assertIn('data-i18n="generate"', text)


if __name__ == '__main__':
    unittest.main()
