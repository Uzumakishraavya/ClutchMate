import requests
import json

base = "http://localhost:5000"

# Test login
creds = {'email': 'test@example.com', 'password': 'password123'}
r = requests.post(base + '/auth/login', json=creds)
print('login status:', r.status_code)

if r.status_code == 200:
    token = r.json().get('token')
    print('Login successful, token:', token[:20] + '...')

    headers = {'Authorization': f'Bearer {token}'}

    # Update user subjects
    personalization_data = {
        'subjects': ['Mathematics', 'Physics', 'Chemistry'],
        'gradeClass': '12th Grade'
    }

    r2 = requests.post(base + '/user/personalize', json=personalization_data, headers=headers)
    print('personalization status:', r2.status_code, r2.text)

    # Test knowledge map API
    r3 = requests.get(base + '/api/knowledge-map', headers=headers)
    print('knowledge map status:', r3.status_code)

    if r3.status_code == 200:
        data = r3.json()
        print('Knowledge map subjects:', data.get('subjects', []))
        print('Node count:', data.get('node_count', 0))
        print('Edge count:', data.get('edge_count', 0))
        print('Image data length:', len(data.get('map_image', '')))
        print('SUCCESS: Knowledge map API working!')
    else:
        print('Knowledge map error:', r3.text)

else:
    print('Login failed:', r.text)