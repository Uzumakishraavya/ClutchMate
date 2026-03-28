import requests
base = "http://localhost:5000"
print("ping", requests.get(base + "/").status_code)
creds = {'name':'test','email':'test@example.com','password':'password123'}
r = requests.post(base + '/auth/signup', json=creds)
print('signup', r.status_code, r.text)
if r.status_code not in (200, 201):
    r2 = requests.post(base + '/auth/login', json={'email': creds['email'], 'password': creds['password']})
    print('login', r2.status_code, r2.text)
else:
    r2 = requests.post(base + '/auth/login', json={'email': creds['email'], 'password': creds['password']})
    print('login', r2.status_code, r2.text)
if r2 is not None and r2.status_code == 200:
    token = r2.json().get('token')
    resp = requests.get(base + '/api/dashboard', headers={'Authorization': f'Bearer {token}'})
    print('dashboard', resp.status_code, resp.text)
