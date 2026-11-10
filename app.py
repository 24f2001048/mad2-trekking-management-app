from datetime import timedelta
from flask import Flask, render_template, request
from flask_jwt_extended import JWTManager
from models import db, User
from extensions import cache
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
    app.config["JWT_SECRET_KEY"] = "trek-app-super-secret-key-for-jwt-signing-2026"
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=12)
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    # Redis cache settings
    app.config["CACHE_TYPE"] = "RedisCache"
    app.config["CACHE_REDIS_URL"] = "redis://localhost:6379/0"
    app.config["CACHE_DEFAULT_TIMEOUT"] = 60       # cache expiry: 60 seconds

    db.init_app(app)
    cache.init_app(app)
    JWTManager(app)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(staff_bp)
    app.register_blueprint(user_bp)

    with app.app_context():
        db.create_all()
        create_admin()

    @app.after_request
    def clear_cache_on_write(response):
        # any successful create/update/delete may change a trek, so drop the cached list
        if request.method in ("POST", "PUT", "DELETE") and response.status_code < 400:
            cache.delete("open_treks")
        return response

    @app.route("/")
    def index():
        return render_template("index.html")

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)