import os
import tempfile
import unittest

import app as app_module


class ReportsAdminTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test.db")
        app_module.DATABASE = self.db_path
        with app_module.app.app_context():
            app_module.init_db()
        self.client = app_module.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_reports_page_requires_admin_login(self):
        response = self.client.get("/admin/reports")
        self.assertEqual(response.status_code, 302)

    def test_reports_page_renders_for_admin(self):
        with self.client.session_transaction() as session:
            session["admin_id"] = 1
            session["admin_name"] = "admin"

        response = self.client.get("/admin/reports")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Reports & Analytics", html)


if __name__ == "__main__":
    unittest.main()
