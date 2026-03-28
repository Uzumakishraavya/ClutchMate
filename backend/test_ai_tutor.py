from app import app, db
from models import User
from flask_jwt_extended import create_access_token
import json

with app.app_context():
    db.create_all()
    user = User.query.filter_by(email='ai_tutor_test@example.com').first()
    if not user:
        user = User(name='AI Tutor Test', email='ai_tutor_test@example.com', password='test')
        db.session.add(user)
        db.session.commit()
    token = create_access_token(identity=str(user.id))
    client = app.test_client()
    response = client.post(
        '/api/ai-tutor',
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        },
        data=json.dumps({'prompt': 'Explain photosynthesis in simple terms.'})
    )
    print('status', response.status_code)
    print(response.get_data(as_text=True))
