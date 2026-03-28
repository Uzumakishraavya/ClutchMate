from app import app, db, User
from werkzeug.security import generate_password_hash
import json

with app.app_context():
    users = User.query.all()
    print(f"Found {len(users)} users:")
    for user in users:
        print(f"ID: {user.id}, Email: {user.email}, Name: {user.name}, Subjects: {user.subjects_list}")

        # Reset test user password
        if user.email == 'test@example.com':
            user.password = generate_password_hash('password123')
            db.session.commit()
            print("Reset test user password to 'password123'")