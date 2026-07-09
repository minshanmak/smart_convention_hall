import os
import tempfile
import unittest

import app as app_module


class AdminEditTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test.db")
        app_module.DATABASE = self.db_path
        with app_module.app.app_context():
            app_module.init_db()
            db = app_module.get_db()
            db.execute(
                "INSERT INTO users (name, email, password, created_at) VALUES (?, ?, ?, ?)",
                ("Test User", "test@example.com", "hashed", "2024-01-01T00:00:00"),
            )
            db.execute(
                "INSERT INTO bookings (user_id, user_name, hall_name, event_type, guests, booking_date, advance_payment, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (1, "Test User", "Grand Palace Hall", "Wedding", 200, "2024-02-01", 20000, "Confirmed", "2024-01-01T00:00:00"),
            )
            db.commit()
        self.client = app_module.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_admin_edit_user_requires_login(self):
        response = self.client.get("/admin/users/1/edit")
        self.assertEqual(response.status_code, 302)

    def test_user_bookings_page_hides_edit_delete_controls(self):
        with self.client.session_transaction() as session:
            session["user_id"] = 1
            session["user_name"] = "Test User"

        response = self.client.get("/bookings")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertNotIn("/booking/1/edit", html)
        self.assertNotIn("/booking/1/delete", html)

    def test_user_booking_edit_route_is_restricted(self):
        with self.client.session_transaction() as session:
            session["user_id"] = 1
            session["user_name"] = "Test User"

        response = self.client.get("/booking/1/edit")
        self.assertEqual(response.status_code, 302)

    def test_admin_edit_booking_renders_for_admin(self):
        with self.client.session_transaction() as session:
            session["admin_id"] = 1
            session["admin_name"] = "admin"

        response = self.client.get("/admin/bookings/1/edit")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Edit Booking", html)


if __name__ == "__main__":
    unittest.main()
