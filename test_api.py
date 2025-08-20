import requests
import json

def test_api():
    base_url = "http://localhost:8000"
    
    print("🧪 Testing GPT-API Backend")
    print("=" * 40)
    
    # Test 1: Debug routes endpoint (no auth required)
    try:
        print("\n1. Testing debug/routes endpoint...")
        response = requests.get(f"{base_url}/debug/routes")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            routes = response.json()
            print(f"   Found {len(routes)} routes:")
            for route in routes[:10]:  # Show first 10 routes
                print(f"   - {route}")
            if len(routes) > 10:
                print(f"   ... and {len(routes) - 10} more routes")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test 2: FastAPI docs endpoint
    try:
        print("\n2. Testing /docs endpoint...")
        response = requests.get(f"{base_url}/docs")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ FastAPI docs are accessible")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test 3: OpenAPI schema
    try:
        print("\n3. Testing /openapi.json endpoint...")
        response = requests.get(f"{base_url}/openapi.json")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            schema = response.json()
            print(f"   ✅ OpenAPI schema loaded with {len(schema.get('paths', {}))} paths")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test 4: Try a protected endpoint without auth (should fail)
    try:
        print("\n4. Testing protected endpoint without auth (should fail)...")
        response = requests.get(f"{base_url}/system/")
        print(f"   Status: {response.status_code}")
        if response.status_code == 403:
            print("   ✅ Authentication is working (403 Forbidden as expected)")
        else:
            print(f"   Unexpected response: {response.text}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n" + "=" * 40)
    print("🎉 Backend testing completed!")

if __name__ == "__main__":
    test_api()
