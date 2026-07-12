import os
import tempfile
import unittest

import app as app_module


class UserDashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test.db")
        app_module.DATABASE = self.db_path
        with app_module.app.app_context():
            app_module.init_db()
            db = app_module.get_db()
            db.execute(
                "INSERT INTO users (name, email, password, created_at) VALUES (?, ?, ?, ?)",
                ("Test User", "user@example.com", "hashed", "2024-01-01T00:00:00"),
            )
            db.commit()
        self.client = app_module.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_booking_redirects_to_dashboard_and_updates_dashboard(self):
        with self.client.session_transaction() as session:
            session["user_id"] = 1
            session["user_name"] = "Test User"

        response = self.client.post(
            "/booking",
            data={
                "hall_name": "Grand Palace Hall",
                "event_type": "Wedding",
                "guests": "200",
                "booking_date": "2024-08-01",
                "advance_payment": "20000",
            },
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/booking/1/payment", response.headers["Location"])

        dashboard_response = self.client.get("/dashboard")
        html = dashboard_response.get_data(as_text=True)
        self.assertIn("Grand Palace Hall", html)
        self.assertIn("Wedding", html)


if __name__ == "__main__":
    unittest.main()
