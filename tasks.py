import csv
import importlib.util
import os
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from html import escape
from celery_app import celery

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

EXPORT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exports")


def get_flask_app():
    if PROJECT_DIR not in sys.path:
        sys.path.insert(0, PROJECT_DIR)
    app_module = sys.modules.get("app")
    if app_module is None:
        spec = importlib.util.spec_from_file_location(
            "app", os.path.join(PROJECT_DIR, "app.py")
        )
        if spec is None or spec.loader is None:
            raise ImportError("Unable to load the Flask app module")
        app_module = importlib.util.module_from_spec(spec)
        sys.modules["app"] = app_module
        spec.loader.exec_module(app_module)
    return app_module.app


@celery.task
def export_booking_history(user_id):
    # imported here, not at the top, to avoid a circular import with app.py
    app = get_flask_app()
    from models import Booking

    os.makedirs(EXPORT_DIR, exist_ok=True)
    filename = f"bookings_{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"

    with app.app_context():            # the worker needs the Flask app to use the database
        bookings = Booking.query.filter_by(user_id=user_id).order_by(Booking.id).all()
        with open(os.path.join(EXPORT_DIR, filename), "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["User ID", "Trek Name", "Location", "Booking Status",
                             "Start Date", "End Date"])
            for b in bookings:
                writer.writerow([b.user_id, b.trek.name, b.trek.location, b.status,
                                 b.trek.start_date, b.trek.end_date])
    return filename

@celery.task
def send_daily_reminders():
    """Scheduled daily: remind every trekker whose booked trek starts within 3 days."""
    app = get_flask_app()
    from models import Booking, Trek
    from mailer import send_email

    today = date.today()
    limit = today + timedelta(days=3)
    sent = 0
    with app.app_context():
        bookings = Booking.query.join(Trek).filter(
            Booking.status == "Booked",
            Trek.start_date >= today,
            Trek.start_date <= limit,
        ).all()
        for b in bookings:
            user, trek = b.user, b.trek
            if user.is_blacklisted or not user.is_active_user:
                continue
            staff = trek.staff.name if trek.staff else "to be announced"
            html = f"""
            <h3>Trek reminder: {escape(trek.name)}</h3>
            <p>Hi {escape(user.name)}, your trek starts on <b>{trek.start_date}</b>.</p>
            <ul>
              <li>Location: {escape(trek.location)}</li>
              <li>Difficulty: {trek.difficulty}, {trek.duration} day(s)</li>
              <li>Trek leader: {escape(staff)}</li>
            </ul>
            <p><b>Instructions:</b> {escape(trek.instructions or 'None')}</p>
            """
            send_email(user.email, "Reminder: " + trek.name, html)
            sent += 1
    return f"{sent} reminder(s) sent"


@celery.task
def generate_monthly_report(start=None, end=None):
    """Scheduled on the 1st: report for the previous month, emailed to the admin.
    start / end ('YYYY-MM-DD') are only for testing a custom period by hand."""
    app = get_flask_app()
    from models import User, Trek, Booking
    from mailer import send_email

    if start and end:
        start_date, end_date = date.fromisoformat(start), date.fromisoformat(end)
    else:
        end_date = date.today().replace(day=1)                       # 1st of this month
        start_date = (end_date - timedelta(days=1)).replace(day=1)   # 1st of last month
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.min.time())

    with app.app_context():
        # treks that finished in the period, and the users who took part in them
        done = Trek.query.filter(Trek.status == "Completed",
                                 Trek.end_date >= start_date, Trek.end_date < end_date).all()
        done_ids = [t.id for t in done]
        participants = set()
        if done_ids:
            rows = Booking.query.filter(Booking.trek_id.in_(done_ids),
                                        Booking.status == "Completed").all()
            participants = {b.user_id for b in rows}

        # popular treks = most bookings made during the period (cancelled ones excluded)
        month_bookings = Booking.query.filter(Booking.booking_date >= start_dt,
                                              Booking.booking_date < end_dt,
                                              Booking.status != "Cancelled").all()
        popular = Counter(b.trek.name for b in month_bookings).most_common(3)

        popular_html = "".join(f"<li>{escape(name)} ({count} bookings)</li>"
                               for name, count in popular) or "<li>No bookings</li>"
        html = f"""
        <h2>Monthly Trekking Report</h2>
        <p>Period: {start_date} to {end_date - timedelta(days=1)}</p>
        <table border="1" cellpadding="6" style="border-collapse:collapse">
          <tr><td>Treks conducted</td><td>{len(done)}</td></tr>
          <tr><td>Users who participated</td><td>{len(participants)}</td></tr>
        </table>
        <h3>Popular treks</h3>
        <ol>{popular_html}</ol>
        """
        admin = User.query.filter_by(role="admin").first()
        to = os.environ.get("ADMIN_EMAIL") or admin.email
        send_email(to, f"Monthly Trekking Report ({start_date:%B %Y})", html)
    return f"Report sent for {start_date} to {end_date}"