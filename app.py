import csv
from datetime import datetime
from io import BytesIO, StringIO
import os
import sqlite3

from flask import (
    Flask,
    flash,
    g,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from reportlab.pdfgen import canvas
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "smart-convention-hall-secret")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "database", "convention_hall.db")
MIN_ADVANCE_PAYMENT = 10000

PAYMENT_DETAILS = {
    "account_name": "Smart Convention Hall",
    "account_number": "123456789012",
    "ifsc": "SBIN0001234",
    "bank": "State Bank of India",
    "upi_id": "smartconventionhall@upi",
}

HALLS = [
    {
        "name": "Grand Palace Hall",
        "capacity": 1000,
        "best_for": "Wedding",
        "base_price": 85000,
        "features": "Large stage, premium lighting, dining space",
        "photo": "https://images.unsplash.com/photo-1519167758481-83f550bb49b3?auto=format&fit=crop&w=900&q=80",
    },
    {
        "name": "Royal Convention Center",
        "capacity": 600,
        "best_for": "Conference",
        "base_price": 65000,
        "features": "Projector, sound system, business seating",
        "photo": "https://images.unsplash.com/photo-1511578314322-379afb476865?auto=format&fit=crop&w=900&q=80",
    },
    {
        "name": "Diamond Auditorium",
        "capacity": 350,
        "best_for": "Birthday Party",
        "base_price": 40000,
        "features": "Compact stage, decoration support, music system",
        "photo": "https://images.unsplash.com/photo-1492684223066-81342ee5ff30?auto=format&fit=crop&w=900&q=80",
    },
    {
        "name": "MAK Auditorium",
        "capacity": 1000,
        "best_for": "Wedding",
        "base_price": 45000,
        "features": "Modern seating, stage lighting, sound system, parking area",
        "photo": "/static/images/mak-auditorium.jpeg",
    },
    {
        "name": "Shadhi Lounge",
        "capacity": 800,
        "best_for": "Conference",
        "base_price": 70000,
        "features": "Elegant interiors, premium seating, AV support, catering space",
        "photo": "static/images/shadhi-lounge-malappuram-auditoriums-s2dz5gzoer.avif",
    },
    {
        "name": "VALENCIA GALLERIA ",
        "capacity": 2000,
        "best_for": "Wedding",
        "base_price": 100000,
        "features": "Grand foyer, luxury decor, large banquet area, parking",
        "photo": "static/images/velancia.jpg",
    },
]


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            user_name TEXT NOT NULL,
            hall_name TEXT NOT NULL,
            event_type TEXT NOT NULL,
            guests INTEGER NOT NULL,
            booking_date TEXT NOT NULL,
            advance_payment INTEGER NOT NULL DEFAULT 10000,
            status TEXT NOT NULL DEFAULT 'Confirmed',
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        """
    )

    columns = db.execute("PRAGMA table_info(bookings)").fetchall()
    column_names = [column["name"] for column in columns]
    if "advance_payment" not in column_names:
        db.execute("ALTER TABLE bookings ADD COLUMN advance_payment INTEGER NOT NULL DEFAULT 10000")
    db.execute(
        "UPDATE bookings SET advance_payment = ? WHERE advance_payment < ?",
        (MIN_ADVANCE_PAYMENT, MIN_ADVANCE_PAYMENT),
    )

    admin = db.execute("SELECT id FROM admins WHERE username = ?", ("admin",)).fetchone()
    if admin is None:
        db.execute(
            "INSERT INTO admins (username, password) VALUES (?, ?)",
            ("admin", generate_password_hash("admin123")),
        )
    db.commit()


@app.before_request
def prepare_database():
    init_db()


def login_required():
    if "user_id" not in session:
        flash("Please login to continue.", "warning")
        return False
    return True


def admin_required():
    if "admin_id" not in session:
        flash("Admin login required.", "warning")
        return False
    return True


def recommend_hall(event_type, guests):
    possible_halls = [hall for hall in HALLS if guests <= hall["capacity"]]
    if not possible_halls:
        return {
            "name": "Custom Outdoor Venue",
            "reason": "Your guest count is above our standard hall capacity. A custom arrangement is recommended.",
            "price": 125000,
        }

    exact = [hall for hall in possible_halls if hall["best_for"] == event_type]
    hall = exact[0] if exact else possible_halls[0]
    return {
        "name": hall["name"],
        "reason": f"Best match for {event_type} with capacity for up to {hall['capacity']} guests.",
        "price": hall["base_price"],
    }


def get_booked_halls(booking_date, exclude_booking_id=None):
    if not booking_date:
        return []

    sql = "SELECT hall_name FROM bookings WHERE booking_date = ?"
    values = [booking_date]
    if exclude_booking_id:
        sql += " AND id != ?"
        values.append(exclude_booking_id)

    rows = get_db().execute(sql, values).fetchall()
    return [row["hall_name"] for row in rows]


@app.route("/")
def index():
    return render_template("index.html", halls=HALLS)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        try:
            get_db().execute(
                "INSERT INTO users (name, email, password, created_at) VALUES (?, ?, ?, ?)",
                (name, email, generate_password_hash(password), datetime.now().isoformat(timespec="seconds")),
            )
            get_db().commit()
            flash("Registration successful. Please login.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Email already registered.", "danger")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

        if user and check_password_hash(user["password"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            flash("Welcome back.", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for("index"))


@app.route("/dashboard")
def dashboard():
    if not login_required():
        return redirect(url_for("login"))

    db = get_db()
    bookings = db.execute(
        "SELECT * FROM bookings WHERE user_id = ? ORDER BY booking_date DESC",
        (session["user_id"],),
    ).fetchall()
    hall_stats = db.execute(
        "SELECT hall_name, COUNT(*) AS total FROM bookings GROUP BY hall_name ORDER BY total DESC"
    ).fetchall()
    return render_template("dashboard.html", bookings=bookings, hall_stats=hall_stats)


@app.route("/booking", methods=["GET", "POST"])
def booking():
    if not login_required():
        return redirect(url_for("login"))

    recommendation = None
    unavailable_message = None
    selected_date = request.args.get("booking_date", "")
    booked_halls = get_booked_halls(selected_date)
    if request.method == "POST":
        event_type = request.form["event_type"]
        guests = int(request.form["guests"])
        hall_name = request.form["hall_name"]
        booking_date = request.form["booking_date"]
        advance_payment = int(request.form.get("advance_payment") or MIN_ADVANCE_PAYMENT)
        selected_date = booking_date
        booked_halls = get_booked_halls(selected_date)

        clash = get_db().execute(
            "SELECT id FROM bookings WHERE hall_name = ? AND booking_date = ?",
            (hall_name, booking_date),
        ).fetchone()
        if clash:
            unavailable_message = f"{hall_name} is not available on {booking_date}. Please choose another hall or date."
            flash(unavailable_message, "danger")
        elif advance_payment < MIN_ADVANCE_PAYMENT:
            flash(f"Advance payment must be at least Rs. {MIN_ADVANCE_PAYMENT:,}.", "danger")
        else:
            cursor = get_db().execute(
                """
                INSERT INTO bookings
                (user_id, user_name, hall_name, event_type, guests, booking_date, advance_payment, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session["user_id"],
                    session["user_name"],
                    hall_name,
                    event_type,
                    guests,
                    booking_date,
                    advance_payment,
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )
            get_db().commit()
            flash("Hall booked successfully.", "success")
            return redirect(url_for("dashboard"))

    event_type = request.args.get("event_type", "Wedding")
    guests = int(request.args.get("guests", 500))
    recommendation = recommend_hall(event_type, guests)
    return render_template(
        "booking.html",
        halls=HALLS,
        recommendation=recommendation,
        unavailable_message=unavailable_message,
        selected_date=selected_date,
        booked_halls=booked_halls,
        min_advance_payment=MIN_ADVANCE_PAYMENT,
    )


@app.route("/booking/<int:booking_id>/payment")
def booking_payment(booking_id):
    if not login_required():
        return redirect(url_for("login"))

    booking_data = get_db().execute(
        "SELECT * FROM bookings WHERE id = ? AND user_id = ?",
        (booking_id, session["user_id"]),
    ).fetchone()
    if booking_data is None:
        flash("Booking not found.", "danger")
        return redirect(url_for("view_bookings"))

    return render_template(
        "payment.html",
        booking=booking_data,
        payment_details=PAYMENT_DETAILS,
    )


@app.route("/bookings")
def view_bookings():
    if not login_required():
        return redirect(url_for("login"))

    search = request.args.get("search", "").strip()
    db = get_db()
    if search:
        bookings = db.execute(
            """
            SELECT * FROM bookings
            WHERE user_id = ? AND (hall_name LIKE ? OR event_type LIKE ? OR booking_date LIKE ?)
            ORDER BY booking_date DESC
            """,
            (session["user_id"], f"%{search}%", f"%{search}%", f"%{search}%"),
        ).fetchall()
    else:
        bookings = db.execute(
            "SELECT * FROM bookings WHERE user_id = ? ORDER BY booking_date DESC",
            (session["user_id"],),
        ).fetchall()

    return render_template("bookings.html", bookings=bookings, search=search)


@app.route("/booking/<int:booking_id>/edit", methods=["GET", "POST"])
def edit_booking(booking_id):
    if not admin_required():
        return redirect(url_for("admin_login"))

    return redirect(url_for("admin_edit_booking", booking_id=booking_id))


@app.route("/booking/<int:booking_id>/delete", methods=["POST"])
def delete_booking(booking_id):
    if not admin_required():
        return redirect(url_for("admin_login"))

    return redirect(url_for("admin_delete_booking", booking_id=booking_id))


@app.route("/recommend", methods=["GET", "POST"])
def recommend():
    result = None
    if request.method == "POST":
        result = recommend_hall(request.form["event_type"], int(request.form["guests"]))
    return render_template("recommend.html", result=result)


@app.route("/budget", methods=["GET", "POST"])
def budget():
    total = None
    details = None
    if request.method == "POST":
        guests = int(request.form["guests"])
        event_type = request.form["event_type"]
        food = request.form["food"]
        decoration = request.form["decoration"]
        hall = recommend_hall(event_type, guests)

        food_cost = guests * (350 if food == "Standard" else 650)
        decoration_cost = 20000 if decoration == "Standard" else 60000
        total = hall["price"] + food_cost + decoration_cost
        details = {"hall": hall, "food_cost": food_cost, "decoration_cost": decoration_cost}

    return render_template("budget.html", total=total, details=details)


@app.route("/chatbot", methods=["GET", "POST"])
def chatbot():
    response = None
    if request.method == "POST":
        message = request.form["message"].lower()
        if "price" in message or "cost" in message or "budget" in message:
            response = "Our hall packages start from ₹40,000. Use the budget estimator for a full estimate."
        elif "capacity" in message or "guest" in message:
            response = "Our halls support events from 100 to 1000 guests."
        elif "wedding" in message:
            response = "Grand Palace Hall is recommended for wedding events."
        elif "conference" in message or "meeting" in message:
            response = "Royal Convention Center is best for conferences and business events."
        elif "book" in message:
            response = "Login, open the booking page, choose a hall and date, then confirm your booking."
        else:
            response = "I can help with hall prices, capacity, booking, wedding, conference and budget questions."

    return render_template("chatbot.html", response=response)


@app.route("/report")
def download_report():
    if not login_required():
        return redirect(url_for("login"))

    bookings = get_db().execute(
        "SELECT * FROM bookings WHERE user_id = ? ORDER BY booking_date DESC",
        (session["user_id"],),
    ).fetchall()

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(170, 800, "Smart Convention Hall Booking Report")
    pdf.setFont("Helvetica", 11)
    y = 760
    for booking_data in bookings:
        pdf.drawString(
            40,
            y,
            f"#{booking_data['id']} | {booking_data['hall_name']} | {booking_data['event_type']} | "
            f"{booking_data['guests']} guests | {booking_data['booking_date']} | "
            f"Advance: Rs. {booking_data['advance_payment']}",
        )
        y -= 24
        if y < 60:
            pdf.showPage()
            y = 800
    pdf.save()
    buffer.seek(0)

    response = make_response(buffer.getvalue())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = "attachment; filename=booking_report.pdf"
    return response


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        admin = get_db().execute("SELECT * FROM admins WHERE username = ?", (username,)).fetchone()
        if admin and check_password_hash(admin["password"], password):
            session.clear()
            session["admin_id"] = admin["id"]
            session["admin_name"] = admin["username"]
            return redirect(url_for("admin"))
        flash("Invalid admin credentials.", "danger")

    return render_template("admin_login.html")


@app.route("/admin")
def admin():
    if not admin_required():
        return redirect(url_for("admin_login"))

    db = get_db()
    users = db.execute("SELECT COUNT(*) AS total FROM users").fetchone()["total"]
    bookings = db.execute("SELECT COUNT(*) AS total FROM bookings").fetchone()["total"]
    latest = db.execute("SELECT * FROM bookings ORDER BY created_at DESC LIMIT 8").fetchall()
    return render_template("admin.html", users=users, bookings=bookings, latest=latest)


@app.route("/admin/reports", methods=["GET"])
def admin_reports():
    if not admin_required():
        return redirect(url_for("admin_login"))

    db = get_db()
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()
    hall_filter = request.args.get("hall", "").strip()
    event_filter = request.args.get("event_type", "").strip()
    status_filter = request.args.get("status", "").strip()

    query = "SELECT * FROM bookings WHERE 1=1"
    params = []
    if start_date:
        query += " AND booking_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND booking_date <= ?"
        params.append(end_date)
    if hall_filter:
        query += " AND hall_name = ?"
        params.append(hall_filter)
    if event_filter:
        query += " AND event_type = ?"
        params.append(event_filter)
    if status_filter:
        query += " AND status = ?"
        params.append(status_filter)
    query += " ORDER BY booking_date DESC"

    bookings = db.execute(query, params).fetchall()

    summary = {
        "total_bookings": len(bookings),
        "confirmed_bookings": sum(1 for b in bookings if str(b["status"]).lower() == "confirmed"),
        "pending_bookings": sum(1 for b in bookings if str(b["status"]).lower() == "pending"),
        "cancelled_or_rejected_bookings": sum(
            1 for b in bookings if str(b["status"]).lower() in {"cancelled", "rejected"}
        ),
        "total_customers": len({b["user_id"] for b in bookings if b["user_id"] is not None}),
        "total_advance_amount": sum(int(b["advance_payment"] or 0) for b in bookings),
        "advance_payments_received": sum(1 for b in bookings if int(b["advance_payment"] or 0) >= MIN_ADVANCE_PAYMENT),
    }

    monthly_bookings = db.execute(
        "SELECT substr(booking_date, 1, 7) AS month, COUNT(*) AS total FROM bookings GROUP BY substr(booking_date, 1, 7) ORDER BY month"
    ).fetchall()
    monthly_advance = db.execute(
        "SELECT substr(booking_date, 1, 7) AS month, SUM(advance_payment) AS total FROM bookings GROUP BY substr(booking_date, 1, 7) ORDER BY month"
    ).fetchall()
    booking_statuses = db.execute(
        "SELECT status, COUNT(*) AS total FROM bookings GROUP BY status ORDER BY total DESC"
    ).fetchall()
    event_types = db.execute(
        "SELECT event_type, COUNT(*) AS total FROM bookings GROUP BY event_type ORDER BY total DESC"
    ).fetchall()
    hall_performance = db.execute(
        "SELECT hall_name, COUNT(*) AS total FROM bookings GROUP BY hall_name ORDER BY total DESC"
    ).fetchall()

    halls = [row["hall_name"] for row in db.execute("SELECT DISTINCT hall_name FROM bookings ORDER BY hall_name")]
    event_types_list = [row["event_type"] for row in db.execute("SELECT DISTINCT event_type FROM bookings ORDER BY event_type")]
    statuses = [row["status"] for row in db.execute("SELECT DISTINCT status FROM bookings ORDER BY status")]

    return render_template(
        "admin_reports.html",
        bookings=bookings,
        summary=summary,
        monthly_bookings=monthly_bookings,
        monthly_advance=monthly_advance,
        booking_statuses=booking_statuses,
        event_types=event_types,
        hall_performance=hall_performance,
        halls=halls,
        event_types_list=event_types_list,
        statuses=statuses,
        start_date=start_date,
        end_date=end_date,
        hall_filter=hall_filter,
        event_filter=event_filter,
        status_filter=status_filter,
    )


@app.route("/admin/reports/pdf")
def admin_reports_pdf():
    if not admin_required():
        return redirect(url_for("admin_login"))

    db = get_db()
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()
    hall_filter = request.args.get("hall", "").strip()
    event_filter = request.args.get("event_type", "").strip()
    status_filter = request.args.get("status", "").strip()

    query = "SELECT * FROM bookings WHERE 1=1"
    params = []
    if start_date:
        query += " AND booking_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND booking_date <= ?"
        params.append(end_date)
    if hall_filter:
        query += " AND hall_name = ?"
        params.append(hall_filter)
    if event_filter:
        query += " AND event_type = ?"
        params.append(event_filter)
    if status_filter:
        query += " AND status = ?"
        params.append(status_filter)
    query += " ORDER BY booking_date DESC"

    bookings = db.execute(query, params).fetchall()
    total_advance = sum(int(b["advance_payment"] or 0) for b in bookings)

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(120, 800, "Smart Convention Hall - Reports & Analytics")
    pdf.setFont("Helvetica", 11)
    pdf.drawString(40, 770, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    pdf.drawString(40, 750, f"Filters: {start_date or '-'} to {end_date or '-'} | Hall: {hall_filter or '-'} | Event: {event_filter or '-'} | Status: {status_filter or '-'}")
    pdf.drawString(40, 730, f"Total Bookings: {len(bookings)} | Advance Amount Collected: Rs. {total_advance:,}")
    y = 700
    for booking_data in bookings:
        pdf.drawString(
            40,
            y,
            f"#{booking_data['id']} | {booking_data['user_name']} | {booking_data['hall_name']} | {booking_data['event_type']} | {booking_data['booking_date']} | Status: {booking_data['status']} | Advance: Rs. {booking_data['advance_payment']}",
        )
        y -= 16
        if y < 60:
            pdf.showPage()
            y = 800
    pdf.save()
    buffer.seek(0)

    response = make_response(buffer.getvalue())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = "attachment; filename=reports_analytics.pdf"
    return response


@app.route("/admin/reports/csv")
def admin_reports_csv():
    if not admin_required():
        return redirect(url_for("admin_login"))

    db = get_db()
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()
    hall_filter = request.args.get("hall", "").strip()
    event_filter = request.args.get("event_type", "").strip()
    status_filter = request.args.get("status", "").strip()

    query = "SELECT id, user_name, hall_name, event_type, booking_date, guests, status, advance_payment FROM bookings WHERE 1=1"
    params = []
    if start_date:
        query += " AND booking_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND booking_date <= ?"
        params.append(end_date)
    if hall_filter:
        query += " AND hall_name = ?"
        params.append(hall_filter)
    if event_filter:
        query += " AND event_type = ?"
        params.append(event_filter)
    if status_filter:
        query += " AND status = ?"
        params.append(status_filter)
    query += " ORDER BY booking_date DESC"

    rows = db.execute(query, params).fetchall()

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Booking ID", "Customer Name", "Hall Name", "Event Type", "Event Date", "Guests", "Booking Status", "Advance Amount"])
    for row in rows:
        writer.writerow([row["id"], row["user_name"], row["hall_name"], row["event_type"], row["booking_date"], row["guests"], row["status"], row["advance_payment"]])

    response = make_response(output.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = "attachment; filename=reports_analytics.csv"
    return response


@app.route("/admin/users")
def admin_users():
    if not admin_required():
        return redirect(url_for("admin_login"))

    users = get_db().execute("SELECT id, name, email, created_at FROM users ORDER BY id DESC").fetchall()
    return render_template("users.html", users=users)


@app.route("/admin/users/<int:user_id>/edit", methods=["GET", "POST"])
def admin_edit_user(user_id):
    if not admin_required():
        return redirect(url_for("admin_login"))

    user = get_db().execute("SELECT id, name, email FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        flash("User not found.", "danger")
        return redirect(url_for("admin_users"))

    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        get_db().execute(
            "UPDATE users SET name = ?, email = ? WHERE id = ?",
            (name, email, user_id),
        )
        get_db().commit()
        flash("User updated successfully.", "success")
        return redirect(url_for("admin_users"))

    return render_template("admin_edit_user.html", user=user)


@app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
def admin_delete_user(user_id):
    if not admin_required():
        return redirect(url_for("admin_login"))

    get_db().execute("DELETE FROM bookings WHERE user_id = ?", (user_id,))
    get_db().execute("DELETE FROM users WHERE id = ?", (user_id,))
    get_db().commit()
    flash("User deleted successfully.", "success")
    return redirect(url_for("admin_users"))


@app.route("/admin/bookings/<int:booking_id>/edit", methods=["GET", "POST"])
def admin_edit_booking(booking_id):
    if not admin_required():
        return redirect(url_for("admin_login"))

    booking_data = get_db().execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()
    if booking_data is None:
        flash("Booking not found.", "danger")
        return redirect(url_for("admin"))

    if request.method == "POST":
        hall_name = request.form["hall_name"]
        event_type = request.form["event_type"]
        guests = int(request.form["guests"])
        booking_date = request.form["booking_date"]
        advance_payment = int(request.form.get("advance_payment") or MIN_ADVANCE_PAYMENT)
        status = request.form.get("status", booking_data["status"])

        get_db().execute(
            """
            UPDATE bookings
            SET hall_name = ?, event_type = ?, guests = ?, booking_date = ?, advance_payment = ?, status = ?
            WHERE id = ?
            """,
            (hall_name, event_type, guests, booking_date, advance_payment, status, booking_id),
        )
        get_db().commit()
        flash("Booking updated successfully.", "success")
        return redirect(url_for("admin"))

    return render_template("admin_edit_booking.html", booking=booking_data, halls=HALLS, min_advance_payment=MIN_ADVANCE_PAYMENT)


@app.route("/admin/bookings/<int:booking_id>/delete", methods=["POST"])
def admin_delete_booking(booking_id):
    if not admin_required():
        return redirect(url_for("admin_login"))

    get_db().execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
    get_db().commit()
    flash("Booking deleted successfully.", "success")
    return redirect(url_for("admin"))


if __name__ == "__main__":
    app.run(debug=True)
