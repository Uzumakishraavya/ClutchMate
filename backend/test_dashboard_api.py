import requests

base = "http://localhost:5000"

# Test login
creds = {'email': 'test@example.com', 'password': 'password123'}
r = requests.post(base + '/auth/login', json=creds)
print('login status:', r.status_code)

if r.status_code == 200:
    token = r.json().get('token')
    print('Login successful, token length:', len(token))

    headers = {'Authorization': f'Bearer {token}'}

    # Test dashboard API
    r2 = requests.get(base + '/api/dashboard', headers=headers)
    print('dashboard API status:', r2.status_code)

    if r2.status_code == 200:
        data = r2.json()
        print('Dashboard API working! Data keys:', list(data.keys())[:5])
    else:
        print('Dashboard API error:', r2.text)

else:
    print('Login failed:', r.text)