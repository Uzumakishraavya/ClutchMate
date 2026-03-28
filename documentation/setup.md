# ClutchMate Setup Guide

This guide walks through how to set up and run the ClutchMate app locally.

## Prerequisites

- Python 3.11+ (or 3.10+)
- Git
- Optional: Visual Studio Code

## 1. Clone the repository

```bash
cd "c:/Users/profa/OneDrive/Documents/coding_projects"
git clone <your-repo-url> "ClutchMate lovhack"
cd "ClutchMate lovhack"
```

## 2. Create and activate a virtual environment

On Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If using Command Prompt:

```cmd
.venv\Scripts\activate.bat
```

## 3. Install backend dependencies

```powershell
cd backend
pip install -r requirements.txt
```

## 4. Configure environment variables

Create a `.env` file inside `backend/` with the following values:

```env
SECRET_KEY=replace-with-a-secure-secret
JWT_SECRET_KEY=replace-with-a-jwt-secret
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=
OPENAI_API_KEY=
N8N_WEBHOOK_URL=
N8N_WEBHOOK_SECRET=
AUTOMATION_API_SECRET=
```

Only the first two secrets are required to run the app locally.

## 5. Run the backend server

From the `backend` folder:

```powershell
python app.py
```

The backend will serve the frontend files from `frontend` via Flask.

## 6. Open the app

Open your browser to:

```text
http://localhost:5000
```

## 7. Common troubleshooting

- If the app cannot connect to the database, delete `backend/instance/clutchmate.db` and restart.
- If the signup/login page appears broken, ensure the server is running and the static folder points to `../frontend`.
- For Windows PowerShell execution policy issues, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

## 8. Frontend files

The frontend pages are in the root folder:

- `frontend/landingpage.html`
- `frontend/signup2.html`
- `frontend/login2.html`
- `frontend/personalizationform.html`
- `frontend/dashboard2.html`

These pages are served by Flask from the backend static folder configuration.
