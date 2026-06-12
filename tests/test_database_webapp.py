import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from webapp import create_app
from toolgrinder_db import initialize_database


class TestDatabaseWebapp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.app = create_app(
            {
                'TESTING': True,
                'DATABASE': str(root / 'toolgrinder.sqlite3'),
                'GENERATED_DIR': str(root / 'generated'),
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def test_bootstrap_imports_existing_templates_once(self):
        first = self.client.get('/api/bootstrap').get_json()
        second = self.client.get('/api/bootstrap').get_json()

        self.assertGreaterEqual(len(first['templates']), 5)
        self.assertEqual(len(first['templates']), len(second['templates']))
        self.assertGreaterEqual(len(first['cutters']), 1)
        self.assertGreaterEqual(len(first['strategies']), 1)
        self.assertGreaterEqual(len(first['grinding_tools']), 1)

    def test_version_one_database_migrates_template_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp) / 'legacy.sqlite3'
            db = sqlite3.connect(database)
            try:
                db.executescript(
                    """
                    CREATE TABLE schema_info (version INTEGER NOT NULL);
                    INSERT INTO schema_info(version) VALUES (1);
                    CREATE TABLE cutter_templates (
                        id INTEGER PRIMARY KEY,
                        source_name TEXT UNIQUE,
                        name TEXT NOT NULL,
                        cutter_type TEXT NOT NULL DEFAULT 'Schaftfraeser',
                        material TEXT NOT NULL DEFAULT 'VHM',
                        version INTEGER NOT NULL DEFAULT 1,
                        active INTEGER NOT NULL DEFAULT 1,
                        config_json TEXT NOT NULL,
                        source_sha256 TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    """
                )
                db.commit()
            finally:
                db.close()

            initialize_database(database, Path('ToolLib'))

            db = sqlite3.connect(database)
            try:
                version = db.execute('SELECT version FROM schema_info').fetchone()[0]
                columns = {
                    row[1] for row in db.execute('PRAGMA table_info(cutter_templates)')
                }
            finally:
                db.close()
            self.assertEqual(version, 2)
            self.assertIn('metadata_json', columns)

    def test_template_update_preserves_generator_config(self):
        bootstrap = self.client.get('/api/bootstrap').get_json()
        template_id = bootstrap['templates'][0]['id']

        response = self.client.patch(
            f'/api/cutter-templates/{template_id}',
            json={
                'name': 'Database Test',
                'type': 'Schaftfraeser',
                'material': 'VHM',
                'diameter': 9.5,
                'cutting_length': 18.0,
                'flutes': 3,
                'helix': 1.8,
                'target_diameter': 9.3,
                'front_x_end': 2.5,
                'tool_family': 'radius_mill',
                'cutting_direction': 'right',
                'helix_direction': 'right',
                'helix_angle_deg': 35.0,
                'corner_style': 'radius',
                'corner_radius': 0.5,
                'coating': 'AlCrN',
                'center_cutting': True,
                'variable_pitch': True,
            },
        )

        self.assertEqual(response.status_code, 200)
        template = response.get_json()['template']
        self.assertEqual(template['version'], 2)
        self.assertEqual(template['config']['fraeser']['durchmesser'], 9.5)
        self.assertEqual(template['config']['fraeser']['schneidenanzahl'], 3)
        self.assertEqual(template['config']['aktionen']['schneiden']['durchmesser_geschaerft'], 9.3)
        self.assertEqual(template['metadata']['helix_angle_deg'], 35.0)
        self.assertEqual(template['metadata']['corner_radius'], 0.5)
        self.assertTrue(template['metadata']['variable_pitch'])

    def test_generate_from_database_records_snapshot(self):
        bootstrap = self.client.get('/api/bootstrap').get_json()
        cutter = bootstrap['cutters'][0]
        strategy = next(
            item for item in bootstrap['strategies']
            if item['status'] == 'released' and 'edge' in item['parameters']['modes']
        )

        response = self.client.post(
            '/api/generate',
            json={
                'template_id': cutter['template_id'],
                'cutter_id': cutter['id'],
                'strategy_id': strategy['id'],
                'mode': 'edge',
            },
        )

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        payload = response.get_json()
        self.assertTrue(payload['ok'])
        self.assertTrue(payload['files'])
        after = self.client.get('/api/bootstrap').get_json()
        self.assertEqual(len(after['recent_jobs']), 1)
        self.assertEqual(after['recent_jobs'][0]['status'], 'generated')

    def test_new_template_is_independent_copy(self):
        bootstrap = self.client.get('/api/bootstrap').get_json()
        source = bootstrap['templates'][0]

        response = self.client.post(
            '/api/cutter-templates',
            json={'source_template_id': source['id'], 'name': 'Copy Test'},
        )

        self.assertEqual(response.status_code, 201)
        created = response.get_json()['template']
        self.assertNotEqual(created['id'], source['id'])
        source_detail = self.client.get(f"/api/cutter-templates/{source['id']}").get_json()
        self.assertEqual(
            json.dumps(created['config'], sort_keys=True),
            json.dumps(source_detail['config'], sort_keys=True),
        )

    def test_cutter_and_grinding_tool_crud(self):
        bootstrap = self.client.get('/api/bootstrap').get_json()
        template_id = bootstrap['templates'][0]['id']

        cutter_response = self.client.post(
            '/api/cutters',
            json={
                'tool_uid': 'TG-TEST-001',
                'template_id': template_id,
                'current_diameter': 10.0,
                'current_length': 24.0,
                'status': 'ready',
                'location': 'Test rack',
            },
        )
        self.assertEqual(cutter_response.status_code, 201)
        cutter = cutter_response.get_json()['cutter']
        update = self.client.patch(
            f"/api/cutters/{cutter['id']}",
            json={**cutter, 'current_diameter': 9.8, 'status': 'maintenance'},
        )
        self.assertEqual(update.status_code, 200)
        self.assertEqual(update.get_json()['cutter']['current_diameter'], 9.8)

        tool_response = self.client.post(
            '/api/grinding-tools',
            json={
                'tool_uid': 'GW-TEST-01',
                'name': 'Test wheel',
                'tool_type': 'edge',
                'specification': '1A1 CBN',
                'diameter': 100.0,
                'max_rpm': 5000,
                'status': 'ready',
            },
        )
        self.assertEqual(tool_response.status_code, 201)
        tool = tool_response.get_json()['grinding_tool']
        update = self.client.patch(
            f"/api/grinding-tools/{tool['id']}",
            json={**tool, 'diameter': 99.5, 'status': 'maintenance'},
        )
        self.assertEqual(update.status_code, 200)
        self.assertEqual(update.get_json()['grinding_tool']['diameter'], 99.5)

    def test_strategy_changes_create_new_version_and_draft_cannot_generate(self):
        first = self.client.post(
            '/api/strategies',
            json={
                'name': 'Test strategy',
                'status': 'draft',
                'description_de': 'Test',
                'description_en': 'Test',
                'modes': ['edge'],
                'requires_measurement': False,
            },
        )
        second = self.client.post(
            '/api/strategies',
            json={
                'name': 'Test strategy',
                'status': 'released',
                'description_de': 'Freigegeben',
                'description_en': 'Released',
                'modes': ['edge'],
                'requires_measurement': False,
            },
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(first.get_json()['strategy']['version'], 1)
        self.assertEqual(second.get_json()['strategy']['version'], 2)

        bootstrap = self.client.get('/api/bootstrap').get_json()
        cutter = bootstrap['cutters'][0]
        response = self.client.post(
            '/api/generate',
            json={
                'template_id': cutter['template_id'],
                'cutter_id': cutter['id'],
                'strategy_id': first.get_json()['strategy']['id'],
                'mode': 'edge',
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('freigegebene', response.get_data(as_text=True))


if __name__ == '__main__':
    unittest.main()
