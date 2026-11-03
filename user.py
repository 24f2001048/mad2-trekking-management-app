from datetime import date, datetime
from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity
from models import db, User, Trek, Booking
from utils import role_required, trek_to_dict

user_bp = Blueprint("user", __name__, url_prefix="/api/user")


def current_user_id():
    return int(get_jwt_identity())


# ---------- Browse and filter ----------
@user_bp.route("/treks")
@role_required("user")
def browse_treks():
    q = request.args.get("q", "").strip()
    location = request.args.get("location", "").strip()
    difficulty = request.args.get("difficulty", "").strip()
    max_days = request.args.get("max_days", "").strip()

    # users only see approved or open treks
    query = Trek.query.filter(Trek.status.in_(["Approved", "Open"]))
    if q:
        query = query.filter(Trek.name.ilike(f"%{q}%"))
    if location:
        query = query.filter(Trek.location.ilike(f"%{location}%"))
    if difficulty:
        query = query.filter(Trek.difficulty == difficulty)
    if max_days.isdigit():
        query = query.filter(Trek.duration <= int(max_days))

    my_active = {b.trek_id for b in
                 Booking.query.filter_by(user_id=current_user_id(), status="Booked")}
    result = []
    for t in query.order_by(Trek.id.desc()).all():
        data = trek_to_dict(t)
        data["already_booked"] = t.id in my_active
        result.append(data)
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