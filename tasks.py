import csv
import os
from datetime import datetime
from celery_app import celery

EXPORT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exports")


@celery.task
def export_booking_history(user_id):
    # imported here, not at the top, to avoid a circular import with app.py
    from app import app
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