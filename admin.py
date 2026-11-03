from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from sqlalchemy import or_
from models import db, User, Trek, Booking
from utils import role_required, trek_to_dict
from auth import EMAIL_PATTERN


admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


DIFFICULTIES = ["Easy", "Moderate", "Hard"]
STATUSES = ["Pending", "Approved", "Open", "Closed", "Completed"]


def parse_date(value):
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def validate_trek(data):
    """Returns (error_message, None) or (None, cleaned_data)."""
    name = (data.get("name") or "").strip()
    location = (data.get("location") or "").strip()
    if not name or not location:
        return "Name and location are required", None
    if data.get("difficulty") not in DIFFICULTIES:
        return "Difficulty must be Easy, Moderate or Hard", None
    try:
        duration = int(data.get("duration"))
        total_slots = int(data.get("total_slots"))
    except (TypeError, ValueError):
        return "Duration and slots must be numbers", None
    if duration < 1 or total_slots < 1:
        return "Duration and slots must be at least 1", None
    status = data.get("status") or "Pending"
    if status not in STATUSES:
        return "Invalid status", None
    try:
        start = parse_date(data.get("start_date"))
    except ValueError:
        return "Start date must be in YYYY-MM-DD format", None
    # end date is calculated, not typed: a 5-day trek starting on the 2nd ends on the 6th
    end = start + timedelta(days=duration - 1) if start else None
    if start and end and end < start:
        return "End date cannot be before start date", None

    return None, {
        "name": name, "location": location, "difficulty": data["difficulty"],
        "duration": duration, "total_slots": total_slots, "status": status,
        "start_date": start, "end_date": end,
        "instructions": data.get("instructions"),
    }


# ---------- Dashboard ----------
@admin_bp.route("/stats")
@role_required("admin")
def stats():
    return jsonify({
        "treks": Trek.query.count(),
        "users": User.query.filter_by(role="user").count(),
        "staff": User.query.filter_by(role="staff").count(),
        "bookings": Booking.query.count(),
    })


# ---------- Trek CRUD ----------
@admin_bp.route("/treks")
@role_required("admin")
def list_treks():
    q = request.args.get("q", "").strip()
    query = Trek.query
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Trek.name.ilike(like), Trek.location.ilike(like)))
    return jsonify([trek_to_dict(t) for t in query.order_by(Trek.id.desc()).all()])


@admin_bp.route("/treks", methods=["POST"])
@role_required("admin")
def create_trek():
    error, clean = validate_trek(request.get_json() or {})
    if error:
        return jsonify({"error": error}), 400
    trek = Trek(**clean, available_slots=clean["total_slots"])
    db.session.add(trek)
    db.session.commit()
    return jsonify(trek_to_dict(trek)), 201


@admin_bp.route("/treks/<int:trek_id>", methods=["PUT"])
@role_required("admin")
def update_trek(trek_id):
    trek = Trek.query.get_or_404(trek_id)
    error, clean = validate_trek(request.get_json() or {})
    if error:
        return jsonify({"error": error}), 400

    # keep available_slots consistent with people who already booked
    booked = Booking.query.filter_by(trek_id=trek.id, status="Booked").count()
    if clean["total_slots"] < booked:
        return jsonify({"error": f"{booked} users already booked; slots cannot be below that"}), 400

    for key, value in clean.items():
        setattr(trek, key, value)
    trek.available_slots = trek.total_slots - booked
    db.session.commit()
    return jsonify(trek_to_dict(trek))


@admin_bp.route("/treks/<int:trek_id>", methods=["DELETE"])
@role_required("admin")
def delete_trek(trek_id):
    trek = Trek.query.get_or_404(trek_id)
    if trek.bookings:
        return jsonify({"error": "Trek has bookings. Set its status to Closed instead."}), 400
    db.session.delete(trek)
    db.session.commit()
    return jsonify({"message": "Trek deleted"})


@admin_bp.route("/treks/<int:trek_id>/assign", methods=["PUT"])
@role_required("admin")
def assign_staff(trek_id):
    trek = Trek.query.get_or_404(trek_id)
    staff_id = (request.get_json() or {}).get("staff_id")
    if not staff_id:                       # empty value = unassign
        trek.staff_id = None
    else:
        staff = User.query.filter_by(id=staff_id, role="staff").first()
        if not staff or staff.is_blacklisted:
            return jsonify({"error": "Invalid staff member"}), 400
        trek.staff_id = staff.id
    db.session.commit()
    return jsonify(trek_to_dict(trek))


# ---------- Staff and users ----------
@admin_bp.route("/staff", methods=["POST"])
@role_required("admin")
def create_staff():
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if not name or not email or len(password) < 6:
        return jsonify({"error": "Name, email and a password of 6+ characters are required"}), 400
    if not EMAIL_PATTERN.match(email):
        return jsonify({"error": "Invalid email"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 409
    staff = User(name=name, email=email, role="staff", phone=data.get("phone"))
    staff.set_password(password)
    db.session.add(staff)
    db.session.commit()
    return jsonify(staff.to_dict()), 201


@admin_bp.route("/users")
@role_required("admin")
def list_users():
    role = request.args.get("role", "user")          # 'user' or 'staff'
    q = request.args.get("q", "").strip()
    query = User.query.filter_by(role=role)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(User.name.ilike(like), User.email.ilike(like)))
    return jsonify([u.to_dict() for u in query.order_by(User.id.desc()).all()])


@admin_bp.route("/users/<int:user_id>/status", methods=["PUT"])
@role_required("admin")
def set_user_status(user_id):
    user = User.query.get_or_404(user_id)
    if user.role == "admin":
        return jsonify({"error": "Cannot change the admin"}), 400
    data = request.get_json() or {}
    field = data.get("field")
    if field not in ("is_blacklisted", "is_active_user"):
        return jsonify({"error": "Invalid field"}), 400
    setattr(user, field, bool(data.get("value")))
    db.session.commit()
    return jsonify(user.to_dict())


# ---------- Bookings ----------
@admin_bp.route("/bookings")
@role_required("admin")
def all_bookings():
    q = request.args.get("q", "").strip()
    query = Booking.query.join(User).join(Trek)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(User.name.ilike(like), Trek.name.ilike(like)))
    rows = query.order_by(Booking.id.desc()).all()
    return jsonify([{
        "id": b.id, "user_name": b.user.name, "trek_name": b.trek.name,
        "booking_date": b.booking_date.strftime("%Y-%m-%d %H:%M"),
        "status": b.status,
    } for b in rows])