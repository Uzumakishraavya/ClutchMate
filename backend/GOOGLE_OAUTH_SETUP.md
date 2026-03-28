# Google OAuth Setup Guide for ClutchMate

## Overview
Google OAuth is now integrated into ClutchMate. Users can sign up and login using their Google account instead of creating a separate password.

## Setup Steps

### 1. Get Google OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Go to **APIs & Services** → **Credentials**
4. Click **Create Credentials** → **OAuth client ID**
5. Choose **Web application**
6. Add authorized redirect URIs:
   - `http://localhost:5000/auth/google/callback` (for local development)
   - `https://yourdomain.com/auth/google/callback` (for production)
7. Copy your **Client ID** and **Client Secret**

### 2. Configure Environment Variables

Create a `.env` file in the `backend/` directory:

```env
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:5000/auth/google/callback
SECRET_KEY=your-secret-key
JWT_SECRET_KEY=your-jwt-secret-key
```

Or set them as system environment variables:

**Windows (PowerShell):**
```powershell
$env:GOOGLE_CLIENT_ID = "your-client-id.apps.googleusercontent.com"
$env:GOOGLE_CLIENT_SECRET = "your-client-secret"
```

**Windows (Command Prompt):**
```cmd
set GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
set GOOGLE_CLIENT_SECRET=your-client-secret
```

**Mac/Linux (Bash):**
```bash
export GOOGLE_CLIENT_ID="your-client-id.apps.googleusercontent.com"
export GOOGLE_CLIENT_SECRET="your-client-secret"
```

### 3. Enable Flask Sessions

The `.env` file needs to be in the `backend/` directory. The app will automatically load it via `python-dotenv`.

### 4. Test the Flow

1. Start the Flask server: `python app.py`
2. Open `http://localhost:5000/`
3. Click "Continue with Google"
4. Sign in with your Google account
5. You'll be automatically logged in and redirected to the dashboard

## How It Works

1. **Login Click**: User clicks "Continue with Google" button
2. **OAuth Redirect**: User is redirected to Google's login page
3. **Authorization**: User grants permission for ClutchMate to access their profile
4. **Callback**: Google redirects back to `/auth/google/callback`
5. **User Creation**: If new, a user account is automatically created with:
   - Name from Google profile
   - Email from Google account
   - Random password (not used for Google auth)
6. **Token Generation**: JWT token is created and stored in localStorage
7. **Dashboard Access**: User is automatically logged into the dashboard

## Troubleshooting

### "Google OAuth not configured"
- Ensure `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` environment variables are set
- Restart the Flask server after setting environment variables
- Check `.env` file is in the `backend/` directory

### Redirect URI Mismatch
- Make sure the redirect URI in your code matches exactly what you registered in Google Cloud Console
- For local dev: `http://localhost:5000/auth/google/callback`
- No trailing slashes or different ports will cause errors

### Session Issues
- Clear your browser cookies if you encounter state validation errors
- Flask needs `SESSION_COOKIE_SECURE=False` for local development (already configured)

## Security Notes

1. **Never commit** `.env` file to version control - it contains secrets
2. **Different tokens per environment**: Use different Google OAuth apps for dev/production
3. **HTTPS required** in production: Set `SESSION_COOKIE_SECURE=True` and use HTTPS
4. **Token expiration**: JWT tokens don't expire in current setup - add expiration in production

## Features

✅ One-click Google sign-up  
✅ Automatic account creation  
✅ JWT token generation  
✅ Secure session management  
✅ Works with existing email/password auth  

## Files Modified

- `backend/app.py` - Added Google OAuth routes
- `backend/requirements.txt` - Added Google auth libraries
- `frontend/login2.html` - Enabled Google login button
- `frontend/dashboard2.html` - Added URL token handling
- `backend/.env.example` - Configuration template
