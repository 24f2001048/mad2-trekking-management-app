from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(db.Model):
    # One table for admin, staff and trekkers. The 'role' column tells them apart.
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'admin' / 'staff' / 'user'
    phone = db.Column(db.String(20))
    is_active_user = db.Column(db.Boolean, default=True)
    is_blacklisted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "role": self.role,
            "phone": self.phone,
            "is_active": self.is_active_user,
            "is_blacklisted": self.is_blacklisted,
        }


class Trek(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    location = db.Column(db.String(150), nullable=False)
    difficulty = db.Column(db.String(20), nullable=False)  # Easy / Moderate / Hard
    duration = db.Column(db.Integer, nullable=False)  # in days
    total_slots = db.Column(db.Integer, nullable=False)
    available_slots = db.Column(db.Integer, nullable=False)
    status = db.Column(
        db.String(20), default="Pending"
    )  # Pending/Approved/Open/Closed/Completed
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    instructions = db.Column(db.Text)
    is_started = db.Column(db.Boolean, default=False)
    staff_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    staff = db.relationship("User", backref="assigned_treks")


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    trek_id = db.Column(db.Integer, db.ForeignKey("trek.id"), nullable=False)
    booking_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(
        db.String(20), default="Booked"
    )  # Booked / Cancelled / Completed
    payment_status = db.Column(db.String(20), default="Pending")

    user = db.relationship("User", backref="bookings")
    trek = db.relationship("Trek", backref="bookings")

    # Database-level guard against duplicate bookings
    __table_args__ = (db.UniqueConstraint("user_id", "trek_id", name="uq_user_trek"),)
