from functools import wraps
from flask import jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt, get_jwt_identity
from models import User


def role_required(*roles):
    """Use on a route: @role_required('admin') or @role_required('admin', 'staff')"""

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            if claims.get("role") not in roles:
                return jsonify({"error": "Access denied"}), 403
            user = User.query.get(int(get_jwt_identity()))
            if not user or user.is_blacklisted or not user.is_active_user:
                return jsonify({"error": "Account is disabled"}), 403
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def trek_to_dict(t):
    booked = len([b for b in t.bookings if b.status == "Booked"])
    return {
        "id": t.id, "name": t.name, "location": t.location,
        "difficulty": t.difficulty, "duration": t.duration,
        "total_slots": t.total_slots, "available_slots": t.available_slots,
        "booked_count": booked, "status": t.status,
        "start_date": t.start_date.isoformat() if t.start_date else None,
        "end_date": t.end_date.isoformat() if t.end_date else None,
        "instructions": t.instructions,
        "is_started": t.is_started,
        "staff_id": t.staff_id,
        "staff_name": t.staff.name if t.staff else None,
    }