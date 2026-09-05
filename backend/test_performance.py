"""Performance baseline test script to measure current latency."""

import asyncio
import httpx
import time
import json
from typing import Dict, Any

# Configuration
API_BASE = "http://localhost:8000"
TEST_MESSAGE = "Hello, how are you today?"
MODEL = "ollama:llama3.2"

async def test_chat_performance():
    """Test chat endpoint performance with timing measurements."""
    
    # First, we need to authenticate
    async with httpx.AsyncClient() as client:
        # Login (assuming user exists)
        login_response = await client.post(
            f"{API_BASE}/auth/login",
            json={"username": "gabriel", "password": "gabriel"}
        )
        
        if login_response.status_code != 200:
            print(f"Login failed: {login_response.status_code}")
            print(login_response.text)
            return
        
        token_data = login_response.json()
        token = token_data["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        print("Authentication successful")
        
        # Test chat performance
        timings = {}
        
        # Start timing
        request_start = time.time()
        
        # Send chat request
        chat_start = time.time()
        response = await client.post(
            f"{API_BASE}/chat",
            json={
                "message": TEST_MESSAGE,
                "conversation_id": None,
                "model": MODEL
            },
            headers=headers,
            timeout=120.0
        )
        chat_end = time.time()
        timings["chat_request"] = chat_end - chat_start
        
        if response.status_code != 200:
            print(f"Chat request failed: {response.status_code}")
            print(response.text)
            return
        
        # Process streaming response
        stream_start = time.time()
        first_token_time = None
        token_count = 0
        full_response = ""
        
        async for line in response.aiter_lines():
            if not line.strip():
                continue
            
            try:
                chunk = json.loads(line)
                
                if "delta" in chunk:
                    if first_token_time is None:
                        first_token_time = time.time()
                        timings["time_to_first_token"] = first_token_time - stream_start
                    
                    full_response += chunk["delta"]
                    token_count += 1
                
                if chunk.get("done"):
                    break
            except json.JSONDecodeError:
                continue
        
        stream_end = time.time()
        timings["total_stream_time"] = stream_end - stream_start
        timings["total_tokens"] = token_count
        timings["response_length"] = len(full_response)
        
        total_end = time.time()
        timings["total_latency"] = total_end - request_start
        
        # Print results
        print("\n" + "="*50)
        print("PERFORMANCE BASELINE RESULTS")
        print("="*50)
        print(f"Test message: '{TEST_MESSAGE}'")
        print(f"Model: {MODEL}")
        print(f"Response length: {timings['response_length']} characters")
        print(f"Tokens received: {timings['total_tokens']}")
        print(f"\nTimings:")
        print(f"  Total latency: {timings['total_latency']:.3f}s")
        print(f"  Chat request: {timings['chat_request']:.3f}s")
        print(f"  Time to first token: {timings.get('time_to_first_token', 'N/A')}")
        print(f"  Total stream time: {timings['total_stream_time']:.3f}s")
        print(f"\nResponse preview:")
        print(f"  {full_response[:200]}...")
        print("="*50)
        
        return timings

if __name__ == "__main__":
    print("Starting performance baseline test...")
    asyncio.run(test_chat_performance())