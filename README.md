# Trekking Management Application (MAD-2)

A web app for managing treks with three roles: Admin, Trek Staff and Trekker.

## Tech stack
Flask (API), Vue 3 via CDN (UI), Bootstrap, SQLite, Redis (cache), Celery + Redis (background jobs).

## Setup
Requires Python 3 and Redis.

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
brew install redis && brew services start redis    # macOS
```

## Run (three terminals, venv active in each)
```bash
python app.py                                      # 1. Flask app
celery -A celery_app worker --loglevel=info --pool=solo   # 2. background worker
celery -A celery_app beat --loglevel=info          # 3. scheduler
```
Open http://127.0.0.1:5000

The database and the admin account are created automatically on first run.

**Admin login:** admin@trek.com / admin123

## Optional email settings
Set `MAIL_USER`, `MAIL_PASSWORD` and `ADMIN_EMAIL` as environment variables to send real
emails. Without them, emails are saved as HTML files in the `exports/` folder.

## Features
- Admin: manage treks, add staff, assign staff, search, blacklist or deactivate users, view bookings and stats
- Staff: view assigned treks, update slots and status, view participants, mark started or completed
- Trekker: register, search and filter treks, book and cancel, booking history, edit profile, export CSV
- Redis caching of the trek list (60 second expiry)
- Celery jobs: daily reminder (8:00 AM), monthly report (1st of the month), CSV export (on demand)

## Structure
- `app.py`: app setup, admin seeding, cache clearing
- `models.py`: User, Trek, Booking
- `auth.py`, `admin.py`, `staff.py`, `user.py`: API routes
- `utils.py`: role-based access decorator
- `celery_app.py`, `tasks.py`, `mailer.py`: background jobs
- `templates/index.html`, `static/app.js`: Vue front end