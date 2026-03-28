# ClutchMate Backend

A Flask-based REST API backend for the ClutchMate application with JWT authentication and user personalization.

## Features

- User authentication (signup/login) with JWT tokens
- User personalization data storage
- Dashboard API with study plan generation
- SQLite database for data persistence
- CORS enabled for frontend integration

## Tech Stack

- **Flask** - Web framework
- **Flask-JWT-Extended** - JWT authentication
- **Flask-SQLAlchemy** - Database ORM
- **Flask-CORS** - Cross-origin support
- **SQLite** - Database

## Installation

1. Navigate to the backend directory:
```bash
cd backend
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/Scripts/activate  # On Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run the application:
```bash
python app.py
```

The API will be available at `http://localhost:5000`

## Optional Google Vision Integration

- Set `GOOGLE_VISION_API_KEY` in your `.env` file to enable test-paper OCR and mistake analysis via the Google Vision API.
- Ensure the Google Cloud project has the Vision API enabled and billing turned on for the key to work.
- The new paper analyzer endpoint is `POST /api/paper-analyzer/analyze`, and it accepts `multipart/form-data` image uploads.

## Optional n8n Integration

ClutchMate can send server-side webhook events to n8n for automation flows such as onboarding, assignment reminders, email digests, or escalation workflows.

Add these variables to `backend/.env`:

```env
N8N_WEBHOOK_URL=https://your-n8n-instance/webhook/clutchmate-events
N8N_WEBHOOK_SECRET=replace-with-a-shared-secret
N8N_TIMEOUT_SECONDS=8
AUTOMATION_API_SECRET=replace-with-a-second-shared-secret
```

Current events sent by the backend:

- `user.signup`
- `assignment.created`
- `assignment.updated`
- `assignment.deleted`

Each webhook request includes:

- `source`
- `event_type`
- `sent_at`
- `payload`

Suggested n8n workflow:

1. Add a `Webhook` trigger node.
2. Check `X-ClutchMate-Secret` against your expected secret.
3. Branch on `event_type`.
4. For `assignment.created` or `assignment.updated`, schedule reminders or send notifications.
5. For `user.signup`, start onboarding messages or CRM/logging flows.

### Assignment Reminder Emails

The assignment webhook payload now includes both:

- `user` with `name`, `email`, `subjects`, and goals
- `assignment` with `title`, `subject`, `deadline`, and `completed`

This makes it easy for n8n to:

1. Trigger on `assignment.created` or `assignment.updated`
2. Filter out completed assignments
3. Wait until a chosen offset before the deadline
4. Send an email reminder to `payload.user.email`

### Daily Summary Emails

ClutchMate also exposes a secure automation endpoint for n8n cron jobs:

- `GET /api/automation/daily-summaries`

Pass this header:

```http
X-Automation-Secret: your AUTOMATION_API_SECRET value
```

Optional query parameter:

- `user_id`

The response includes, for each user:

- `today_study_minutes`
- `pending_assignment_count`
- `overdue_count`
- `due_today_count`
- `due_tomorrow_count`
- `overdue_assignments`
- `due_today_assignments`
- `due_tomorrow_assignments`
- `upcoming_assignments`

Suggested n8n daily-summary workflow:

1. Trigger with `Schedule`.
2. Call `GET /api/automation/daily-summaries` with `X-Automation-Secret`.
3. Loop through `summaries`.
4. Skip users without email.
5. Build a friendly daily digest email from the assignment counts and study minutes.
6. Send through Gmail, SMTP, Resend, or another email node.

## API Endpoints

### Authentication

- **POST** `/auth/signup` - Register a new user
- **POST** `/auth/login` - Login user and get JWT token

### Protected Routes (require JWT token in Authorization header)

- **POST** `/user/personalize` - Save user personalization data
- **GET** `/dashboard` - Get user dashboard with study plan

## Database Schema

### User Table
- `id` (Integer, Primary Key)
- `name` (String)
- `email` (String, Unique)
- `password` (String, Hashed)
- `subjects` (Text, JSON list)
- `current_grades` (Text, JSON object)
- `goals` (Text, JSON object)

## Usage

1. **Signup**: Send POST request to `/auth/signup` with name, email, password
2. **Login**: Send POST request to `/auth/login` with email, password (returns JWT token)
3. **Personalize**: Send POST request to `/user/personalize` with JWT token in header and personalization data
4. **Dashboard**: Send GET request to `/dashboard` with JWT token in header
