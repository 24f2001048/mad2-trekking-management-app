from datetime import date, datetime
from flask import Blueprint, request, jsonify, send_from_directory
from flask_jwt_extended import get_jwt_identity
from celery.result import AsyncResult
from models import db, User, Trek, Booking
from utils import role_required, trek_to_dict
from extensions import cache
from celery_app import celery
from tasks import export_booking_history, EXPORT_DIR

user_bp = Blueprint("user", __name__, url_prefix="/api/user")


def current_user_id():
    return int(get_jwt_identity())


def get_open_treks():
    """The unfiltered list of Approved/Open treks, kept in Redis for 60 seconds."""
    data = cache.get("open_treks")
    if data is None:                                   # cache miss: read from the database
        treks = Trek.query.filter(Trek.status.in_(["Approved", "Open"])) \
                          .order_by(Trek.id.desc()).all()
        data = [trek_to_dict(t) for t in treks]
        cache.set("open_treks", data, timeout=60)
    return data


@user_bp.route("/treks")
@role_required("user")
def browse_treks():
    q = request.args.get("q", "").strip().lower()
    location = request.args.get("location", "").strip().lower()
    difficulty = request.args.get("difficulty", "").strip()
    max_days = request.args.get("max_days", "").strip()

    my_active = {b.trek_id for b in
                 Booking.query.filter_by(user_id=current_user_id(), status="Booked")}
    result = []
    for t in get_open_treks():
        if q and q not in t["name"].lower():
            continue
        if location and location not in t["location"].lower():
            continue
        if difficulty and t["difficulty"] != difficulty:
            continue
        if max_days.isdigit() and t["duration"] > int(max_days):
            continue
        item = dict(t)                                  # copy, then add the per-user flag
        item["already_booked"] = t["id"] in my_active
        result.append(item)
    return jsonify(result)

# ---------- Book ----------
@user_bp.route("/treks/<int:trek_id>/book", methods=["POST"])
@role_required("user")
def book_trek(trek_id):
    trek = Trek.query.get_or_404(trek_id)
    uid = current_user_id()

    # Rule 1: booking only when the trek is Open
    if trek.status != "Open":
        return jsonify({"error": "This trek is not open for booking"}), 400
    # Rule 2: no overbooking
    if trek.available_slots < 1:
        return jsonify({"error": "No slots available"}), 400

    # Rule 3: no duplicate bookings
    existing = Booking.query.filter_by(user_id=uid, trek_id=trek.id).first()
    if existing and existing.status != "Cancelled":
        return jsonify({"error": "You have already booked this trek"}), 409

    if existing:                          # re-booking after a cancellation
        existing.status = "Booked"        # reuse the row (the unique constraint allows only one)
        existing.booking_date = datetime.utcnow()
    else:
        db.session.add(Booking(user_id=uid, trek_id=trek.id))
    trek.available_slots -= 1
    db.session.commit()
    return jsonify({"message": "Trek booked successfully"}), 201


# ---------- Cancel ----------
@user_bp.route("/bookings/<int:booking_id>/cancel", methods=["PUT"])
@role_required("user")
def cancel_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.user_id != current_user_id():
        return jsonify({"error": "Not your booking"}), 403
    if booking.status != "Booked":
        return jsonify({"error": "Only active bookings can be cancelled"}), 400

    trek = booking.trek
    if trek.is_started or trek.status == "Completed":
        return jsonify({"error": "Trek has already started"}), 400
    if trek.start_date and date.today() >= trek.start_date:
        return jsonify({"error": "Cannot cancel on or after the start date"}), 400

    booking.status = "Cancelled"
    trek.available_slots += 1             # give the slot back
    db.session.commit()
    return jsonify({"message": "Booking cancelled"})


# ---------- History ----------
@user_bp.route("/bookings")
@role_required("user")
def my_bookings():
    rows = Booking.query.filter_by(user_id=current_user_id()).order_by(Booking.id.desc()).all()
    return jsonify([{
        "id": b.id, "trek_id": b.trek_id, "trek_name": b.trek.name,
        "location": b.trek.location,
        "start_date": b.trek.start_date.isoformat() if b.trek.start_date else None,
        "end_date": b.trek.end_date.isoformat() if b.trek.end_date else None,
        "booking_date": b.booking_date.strftime("%Y-%m-%d %H:%M"),
        "booking_status": b.status, "trek_status": b.trek.status,
        "trek_started": b.trek.is_started,
    } for b in rows])


# ---------- Profile ----------
@user_bp.route("/profile")
@role_required("user")
def get_profile():
    return jsonify(User.query.get(current_user_id()).to_dict())


@user_bp.route("/profile", methods=["PUT"])
@role_required("user")
def update_profile():
    user = User.query.get(current_user_id())
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Name is required"}), 400
    user.name = name
    user.phone = (data.get("phone") or "").strip()
    db.session.commit()
    return jsonify(user.to_dict())

# ---------- CSV export (runs in the background with Celery) ----------
@user_bp.route("/export", methods=["POST"])
@role_required("user")
def start_export():
    task = export_booking_history.delay(current_user_id())     # returns immediately
    return jsonify({"task_id": task.id}), 202


@user_bp.route("/export/<task_id>")
@role_required("user")
def export_status(task_id):
    result = AsyncResult(task_id, app=celery)
    if result.state == "SUCCESS":
        return jsonify({"state": "done", "file": result.result})
    if result.state == "FAILURE":
        return jsonify({"state": "failed"})
    return jsonify({"state": "pending"})


@user_bp.route("/export/download/<filename>")
@role_required("user")
def download_export(filename):
    if not filename.startswith(f"bookings_{current_user_id()}_"):
        return jsonify({"error": "Not your file"}), 403
    return send_from_directory(EXPORT_DIR, filename, as_attachment=True)