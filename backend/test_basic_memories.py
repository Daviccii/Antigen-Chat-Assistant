"""Test basic memories endpoint to debug the 500 error."""
import requests

BASE_URL = "http://localhost:8000"

# Login
login_data = {
    "username": "testuser",
    "password": "testpass123"
}
response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
print(f"Login: {response.status_code}")

if response.status_code == 200:
    token_data = response.json()
    access_token = token_data.get("access_token")
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Test basic memories endpoint
    try:
        response = requests.get(f"{BASE_URL}/memories", headers=headers)
        print(f"Memories endpoint status: {response.status_code}")
        print(f"Memories endpoint response: {response.text}")
    except Exception as e:
        print(f"Memories endpoint failed: {e}")
