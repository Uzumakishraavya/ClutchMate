# ClutchMate API Reference

This document covers the main backend API endpoints used by the app.

## Authentication

### `POST /auth/signup`

Register a new user.

Request body:

```json
{
  "name": "Jane Doe",
  "email": "jane@example.com",
  "username": "jane",
  "password": "secret123"
}
```

Response:

- `201 Created` on success
- `409 Conflict` if email or username already exists

### `POST /auth/login`

Login with existing credentials.

Request body:

```json
{
  "email": "jane@example.com",
  "password": "secret123"
}
```

Response:

- `200 OK` with token and user_id
- `401 Unauthorized` on invalid credentials

## Assignments / Todo

### `GET /api/assignments`

Returns the current user's assignments.

Headers:

- `Authorization: Bearer <token>`

Response:

- `200 OK` with an array of assignments

### `POST /api/assignments`

Create a new assignment/todo.

Request body:

```json
{
  "title": "Finish biology notes",
  "subject": "Biology"
}
```

Response:

- `201 Created`
- `400 Bad Request` if title is missing

### `PUT /api/assignments/<assignment_id>`

Update assignment fields such as completion.

Request body example:

```json
{
  "completed": true
}
```

### `DELETE /api/assignments/<assignment_id>`

Delete an assignment.

Headers:

- `Authorization: Bearer <token>`

## Study sessions

### `POST /api/study/start`

Start a study session.

### `POST /api/study/stop`

Stop a study session and record duration.

### `GET /api/study/today`

Get today's study time summary.

## Wellness and mental health

### `GET /api/wellness`

Returns mental health metrics and study summary.

### `POST /api/wellness/mood`

Save mood data:

```json
{
  "mood": "good",
  "note": "Felt focused today",
  "sleep_hours": 7.5
}
```

## Automation / Webhooks

### `GET /api/automation/daily-summaries`

Secure endpoint for automation jobs.

Headers:

- `X-Automation-Secret: <AUTOMATION_API_SECRET>`

Response includes daily assignment summaries for users.
