import sqlite3


db = sqlite3.connect("database/convention_hall.db")
cursor = db.cursor()

print("Tables:")
for row in cursor.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
):
    print("-", row[0])

print("\nUsers:")
for row in cursor.execute("SELECT id, name, email, created_at FROM users"):
    print(row)

print("\nAdmins:")
for row in cursor.execute("SELECT id, username FROM admins"):
    print(row)

print("\nBookings:")
for row in cursor.execute(
    """
    SELECT id, user_name, hall_name, event_type, guests, booking_date, advance_payment, status, created_at
    FROM bookings
    """
):
    print(row)

db.close()
