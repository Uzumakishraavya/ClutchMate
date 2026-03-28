# ClutchMate Architecture

This file explains how ClutchMate is built, how each component interacts, and the key design choices.

## System Overview

ClutchMate is a single-page study assistant experience served by a Flask backend and static frontend assets.

### Core components

- **Frontend**: Static HTML/CSS/JS in `frontend`
- **Backend**: Flask app in `backend/app.py`
- **Database**: SQLite database stored at `backend/instance/clutchmate.db`

## Backend

### Flask app

- `backend/app.py` is the main server.
- `app` serves frontend files from `frontend` using `static_folder='../frontend'`.
- `Flask-CORS` is enabled to support cross-origin access.
- `Flask-JWT-Extended` manages authentication tokens.
- `SQLAlchemy` handles database models and queries.

### Main backend responsibilities

- User authentication and session management
- Signup and login endpoints
- User personalization storage
- Dashboard and assignment APIs
- Wellness and study session tracking
- Optional integrations:
  - Google OAuth
  - Google Vision / OCR
  - n8n automation webhooks

### Database models

Important models include:

- `User`
  - `id`, `name`, `email`, `password`, `username`, `grade_class`, `subjects`, `current_grades`, `goals`
- `Assignment`
  - `id`, `user_id`, `title`, `deadline`, `completed`, `subject`
- `StudySession`
  - `user_id`, `subject`, `topic`, `duration`, `start_time`, `end_time`, `date`
- `BehaviorTracking`
  - `user_id`, `date`, `study_time`, `completed_tasks`, `skipped_tasks`

## Frontend

The UI is built using static markup and vanilla JS. Key pages are:

- `landingpage.html` — marketing + login/signup entry
- `signup2.html` — signup form with mascot animation
- `login2.html` — login form page
- `personalizationform.html` — user onboarding data collection
- `dashboard2.html` — main study dashboard and todo management

### Dashboard features

- Study tasks / todo list
- Assignment display and completion toggles
- Mental health / wellness metrics
- Performance summary cards
- Personalized hero content

## Integration flow

1. User signs up using `/auth/signup`.
2. Backend stores the user and returns a JWT.
3. Frontend saves the token and navigates to personalization.
4. User completes personalization and dashboard data is built.
5. Dashboard calls protected APIs using the JWT.
6. Assignment creation, completion, and study tracking are persisted in SQLite.

## Deployment notes

- The app is ready to run locally as a Flask server.
- For production, use a WSGI server such as Gunicorn or Waitress.
- If deployed externally, set secure environment values for `SECRET_KEY`, `JWT_SECRET_KEY`, and any third-party keys.

## Key strengths for the hackathon

- Focused student workflow from signup to study dashboard
- Assignment and task management combined with wellness and productivity analytics
- Ready to add AI tutor capabilities and automated reminders
- Simple setup for rapid demo delivery
