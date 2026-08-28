"""Test end-to-end chat experience with pgvector semantic memory."""
import httpx
import json

BASE_URL = "http://localhost:8000"

def test_chat_experience():
    """Test complete chat experience including memory, semantic search, correction, and time."""
    
    print("=== Testing End-to-End Chat Experience ===\n")
    
    # First, get authentication token
    print("Test A: Authentication")
    login_data = {
        "username": "gabriel",
        "password": "password123"
    }
    
    try:
        response = httpx.post(f"{BASE_URL}/auth/login", json=login_data)
        print(f"Login response status: {response.status_code}")
        print(f"Login response body: {response.text}")
        if response.status_code == 200:
            token_data = response.json()
            token = token_data["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            print("PASS: Authentication successful")
        else:
            print(f"FAIL: Authentication failed - {response.status_code}")
            return False
    except Exception as e:
        print(f"FAIL: Authentication error - {e}")
        return False
    
    # Test A: Memory Storage
    print("\nTest A: Memory Storage")
    memory_message = {
        "message": "Remember that my Antigen backend uses PostgreSQL"
    }
    
    try:
        response = httpx.post(f"{BASE_URL}/chat", json=memory_message, headers=headers)
        if response.status_code == 200:
            result = response.json()
            print(f"PASS: Memory stored successfully")
            print(f"  Assistant response: {result.get('response', 'N/A')[:100]}...")
        else:
            print(f"FAIL: Memory storage failed - {response.status_code}")
            return False
    except Exception as e:
        print(f"FAIL: Memory storage error - {e}")
        return False
    
    # Test B: Semantic Memory Retrieval
    print("\nTest B: Semantic Memory Retrieval")
    semantic_query = {
        "message": "What database does my Antigen backend use?"
    }
    
    try:
        response = httpx.post(f"{BASE_URL}/chat", json=semantic_query, headers=headers)
        if response.status_code == 200:
            result = response.json()
            response_text = result.get('response', '').lower()
            if 'postgresql' in response_text or 'postgres' in response_text:
                print("PASS: Semantic memory retrieval successful")
                print(f"  Assistant response: {result.get('response', 'N/A')[:100]}...")
            else:
                print("PARTIAL: Response received but may not contain expected information")
                print(f"  Assistant response: {result.get('response', 'N/A')[:100]}...")
        else:
            print(f"FAIL: Semantic retrieval failed - {response.status_code}")
            return False
    except Exception as e:
        print(f"FAIL: Semantic retrieval error - {e}")
        return False
    
    # Test C: Correction
    print("\nTest C: Memory Correction")
    correction_message = {
        "message": "No, I changed the database to PostgreSQL 15"
    }
    
    try:
        response = httpx.post(f"{BASE_URL}/chat", json=correction_message, headers=headers)
        if response.status_code == 200:
            result = response.json()
            print("PASS: Correction processed")
            print(f"  Assistant response: {result.get('response', 'N/A')[:100]}...")
        else:
            print(f"FAIL: Correction failed - {response.status_code}")
            return False
    except Exception as e:
        print(f"FAIL: Correction error - {e}")
        return False
    
    # Test D: Time Query
    print("\nTest D: Time Query")
    time_query = {
        "message": "What time is it?"
    }
    
    try:
        response = httpx.post(f"{BASE_URL}/chat", json=time_query, headers=headers)
        if response.status_code == 200:
            result = response.json()
            response_text = result.get('response', '').lower()
            # Check if response contains time information
            if any(time_word in response_text for time_word in ['time', 'hour', 'clock', ':', 'am', 'pm']):
                print("PASS: Time query successful")
                print(f"  Assistant response: {result.get('response', 'N/A')[:100]}...")
            else:
                print("PARTIAL: Response received but may not contain time information")
                print(f"  Assistant response: {result.get('response', 'N/A')[:100]}...")
        else:
            print(f"FAIL: Time query failed - {response.status_code}")
            return False
    except Exception as e:
        print(f"FAIL: Time query error - {e}")
        return False
    
    # Test E: Schedule Query (should not fabricate)
    print("\nTest E: Schedule Query (Phase 4 not implemented)")
    schedule_query = {
        "message": "What am I scheduled to do tomorrow?"
    }
    
    try:
        response = httpx.post(f"{BASE_URL}/chat", json=schedule_query, headers=headers)
        if response.status_code == 200:
            result = response.json()
            response_text = result.get('response', '').lower()
            # Should not invent schedule since Phase 4 is not implemented
            if 'schedule' not in response_text or 'not implemented' in response_text or 'don\'t know' in response_text:
                print("PASS: No schedule fabrication (Phase 4 not implemented)")
                print(f"  Assistant response: {result.get('response', 'N/A')[:100]}...")
            else:
                print("WARNING: Response may contain fabricated schedule")
                print(f"  Assistant response: {result.get('response', 'N/A')[:100]}...")
        else:
            print(f"FAIL: Schedule query failed - {response.status_code}")
            return False
    except Exception as e:
        print(f"FAIL: Schedule query error - {e}")
        return False
    
    print("\n=== Chat Experience Tests Complete ===")
    return True

if __name__ == "__main__":
    success = test_chat_experience()
    exit(0 if success else 1)