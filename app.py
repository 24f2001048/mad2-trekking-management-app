from flask import Flask, render_template
from flask_jwt_extended import JWTManager
from models import db, User
from auth import auth_bp
from admin import admin_bp
from staff import staff_bp
from user import user_bp


def create_admin():
    """Runs on startup; creates the one admin only if none exists."""
    if not User.query.filter_by(role="admin").first():
        admin = User(name="Admin", email="admin@trek.com", role="admin")
        admin.set_password("admin123")
        db.session.add(admin)
        db.session.commit()


def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///trek.db"
    app.config["JWT_SECRET_KEY"] = "change-this-secret-key"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    JWTManager(app)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(staff_bp)
    app.register_blueprint(user_bp)

    with app.app_context():
        db.create_all()  # creates tables from the models
        create_admin()

    @app.route("/")
    def index():
        return render_template("index.html")  # only the entry point; Vue does the UI

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
