from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity
from models import db, Trek, Booking
from utils import role_required, trek_to_dict

staff_bp = Blueprint("staff", __name__, url_prefix="/api/staff")


def get_my_trek(trek_id):
    """Returns the trek only if it is assigned to the logged-in staff, else None."""
    trek = Trek.query.get_or_404(trek_id)
    if trek.staff_id != int(get_jwt_identity()):
        return None
    return trek


@staff_bp.route("/treks")
@role_required("staff")
def my_treks():
    treks = Trek.query.filter_by(staff_id=int(get_jwt_identity())).order_by(Trek.id.desc()).all()
    return jsonify([trek_to_dict(t) for t in treks])


@staff_bp.route("/treks/<int:trek_id>", methods=["PUT"])
@role_required("staff")
def update_trek(trek_id):
    trek = get_my_trek(trek_id)
    if not trek:
        return jsonify({"error": "This trek is not assigned to you"}), 403
    if trek.status == "Pending":
        return jsonify({"error": "Admin must approve this trek first"}), 400
    if trek.is_started or trek.status == "Completed":
        return jsonify({"error": "Trek already started or completed"}), 400

    data = request.get_json() or {}
    try:
        total = int(data.get("total_slots"))
    except (TypeError, ValueError):
        return jsonify({"error": "Slots must be a number"}), 400
    if data.get("status") not in ("Open", "Closed"):
        return jsonify({"error": "Status must be Open or Closed"}), 400

    booked = Booking.query.filter_by(trek_id=trek.id, status="Booked").count()
    if total < 1 or total < booked:
        return jsonify({"error": f"Slots cannot be below {max(booked, 1)}"}), 400

    trek.total_slots = total
    trek.available_slots = total - booked
    trek.status = data["status"]
    db.session.commit()
    return jsonify(trek_to_dict(trek))


@staff_bp.route("/treks/<int:trek_id>/participants")
@role_required("staff")
def participants(trek_id):
    trek = get_my_trek(trek_id)
    if not trek:
        return jsonify({"error": "This trek is not assigned to you"}), 403
    rows = [b for b in trek.bookings if b.status in ("Booked", "Completed")]
    return jsonify([{
        "booking_id": b.id, "name": b.user.name, "email": b.user.email,
        "phone": b.user.phone, "status": b.status,
    } for b in rows])


@staff_bp.route("/treks/<int:trek_id>/start", methods=["PUT"])
@role_required("staff")
def start_trek(trek_id):
    trek = get_my_trek(trek_id)
    if not trek:
        return jsonify({"error": "This trek is not assigned to you"}), 403
    if trek.is_started:
        return jsonify({"error": "Trek already started"}), 400
    if trek.status not in ("Approved", "Open", "Closed"):
        return jsonify({"error": "Trek must be approved before it can start"}), 400
    trek.is_started = True
    trek.status = "Closed"          # no new bookings once the trek has started
    db.session.commit()
    return jsonify(trek_to_dict(trek))


@staff_bp.route("/treks/<int:trek_id>/complete", methods=["PUT"])
@role_required("staff")
def complete_trek(trek_id):
    trek = get_my_trek(trek_id)
    if not trek:
        return jsonify({"error": "This trek is not assigned to you"}), 403
    if not trek.is_started:
        return jsonify({"error": "Start the trek first"}), 400
    if trek.status == "Completed":
        return jsonify({"error": "Trek already completed"}), 400
    trek.status = "Completed"
    for b in trek.bookings:                 # every active booking becomes history
        if b.status == "Booked":
            b.status = "Completed"
    db.session.commit()
    return jsonify(trek_to_dict(trek))