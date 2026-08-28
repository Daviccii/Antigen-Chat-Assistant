"""Test API endpoints."""
import requests
import json

BASE_URL = "http://localhost:8000"

print("Testing API endpoints...")

# Test health endpoint
try:
    response = requests.get(f"{BASE_URL}/health")
    print(f"Health endpoint: {response.status_code} - {response.json()}")
except Exception as e:
    print(f"Health endpoint failed: {e}")

# Test AI status endpoint
try:
    response = requests.get(f"{BASE_URL}/ai/status")
    print(f"AI status endpoint: {response.status_code} - {response.json()}")
except Exception as e:
    print(f"AI status endpoint failed: {e}")

# Test login with known credentials
try:
    login_data = {
        "username": "testuser",
        "password": "testpass123"
    }
    response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    print(f"Login endpoint: {response.status_code} - {response.json()}")
    
    if response.status_code == 200:
        token_data = response.json()
        access_token = token_data.get("access_token")
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # Test /time endpoint
        try:
            response = requests.get(f"{BASE_URL}/time", headers=headers)
            print(f"Time endpoint: {response.status_code} - {response.json()}")
        except Exception as e:
            print(f"Time endpoint failed: {e}")
        
        # Test memories endpoint
        try:
            response = requests.get(f"{BASE_URL}/memories", headers=headers)
            print(f"Memories endpoint: {response.status_code} - {response.json()}")
        except Exception as e:
            print(f"Memories endpoint failed: {e}")
        
        # Test enhanced memories endpoint
        try:
            response = requests.get(f"{BASE_URL}/memories/enhanced", headers=headers)
            print(f"Enhanced memories endpoint: {response.status_code} - {response.json()}")
        except Exception as e:
            print(f"Enhanced memories endpoint failed: {e}")
        
        # Test projects endpoint
        try:
            response = requests.get(f"{BASE_URL}/projects", headers=headers)
            print(f"Projects endpoint: {response.status_code} - {response.json()}")
        except Exception as e:
            print(f"Projects endpoint failed: {e}")
        
        # Test create project
        try:
            project_data = {
                "name": "Test Project",
                "description": "A test project for Phase 3"
            }
            response = requests.post(f"{BASE_URL}/projects", json=project_data, headers=headers)
            print(f"Create project endpoint: {response.status_code} - {response.json()}")
        except Exception as e:
            print(f"Create project endpoint failed: {e}")
        
        # Test create enhanced memory
        try:
            memory_data = {
                "content": "Test enhanced memory for Phase 3",
                "category": "explicit",
                "importance": "HIGH",
                "confidence": 0.9
            }
            response = requests.post(f"{BASE_URL}/memories/enhanced", json=memory_data, headers=headers)
            print(f"Create enhanced memory endpoint: {response.status_code} - {response.json()}")
        except Exception as e:
            print(f"Create enhanced memory endpoint failed: {e}")
        
        # Test memory command detection
        try:
            command_data = {
                "message": "Remember that my backend uses PostgreSQL"
            }
            response = requests.post(f"{BASE_URL}/memories/detect-command", json=command_data, headers=headers)
            print(f"Memory command detection endpoint: {response.status_code} - {response.json()}")
        except Exception as e:
            print(f"Memory command detection endpoint failed: {e}")
        
        # Test relevant memories
        try:
            response = requests.get(f"{BASE_URL}/memories/relevant?query=PostgreSQL&limit=5", headers=headers)
            print(f"Relevant memories endpoint: {response.status_code} - {response.json()}")
        except Exception as e:
            print(f"Relevant memories endpoint failed: {e}")

except Exception as e:
    print(f"Login failed: {e}")

print("API endpoint testing completed!")
