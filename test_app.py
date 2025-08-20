#!/usr/bin/env python3
"""
Simple test script to verify the Revenue Ops Lead Router & Enricher application.
"""

import json
import requests
import time
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_health_endpoint(base_url="http://localhost:8000"):
    """Test the health check endpoint."""
    try:
        response = requests.get(f"{base_url}/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health check passed: {data}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Health check error: {e}")
        return False

def test_lead_webhook(base_url="http://localhost:8000"):
    """Test the lead webhook endpoint with a sample lead."""
    sample_lead = {
        "email": "test.user@example.com",
        "company": "Test Company Inc",
        "full_name": "Test User",
        "title": "Director of Engineering",
        "source": "test",
        "country": "US",
        "website": "https://example.com"
    }
    
    try:
        response = requests.post(
            f"{base_url}/webhooks/lead",
            json=sample_lead,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Lead webhook test passed: {data}")
            return True
        else:
            print(f"❌ Lead webhook test failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Lead webhook test error: {e}")
        return False

def test_duplicate_lead(base_url="http://localhost:8000"):
    """Test idempotency by sending the same lead twice."""
    sample_lead = {
        "email": "duplicate.test@example.com",
        "company": "Duplicate Test Corp",
        "full_name": "Duplicate User",
        "title": "VP Engineering",
        "source": "test",
        "country": "CA"
    }
    
    try:
        # First request
        response1 = requests.post(
            f"{base_url}/webhooks/lead",
            json=sample_lead,
            timeout=30
        )
        
        if response1.status_code != 200:
            print(f"❌ First lead request failed: {response1.status_code}")
            return False
        
        # Second request (should be duplicate)
        response2 = requests.post(
            f"{base_url}/webhooks/lead",
            json=sample_lead,
            timeout=30
        )
        
        if response2.status_code == 200:
            data = response2.json()
            if data.get("status") == "duplicate_ignored":
                print("✅ Duplicate lead test passed - idempotency working")
                return True
            else:
                print(f"❌ Duplicate lead not properly handled: {data}")
                return False
        else:
            print(f"❌ Second lead request failed: {response2.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Duplicate lead test error: {e}")
        return False

def test_metrics_endpoint(base_url="http://localhost:8000"):
    """Test the metrics endpoint."""
    try:
        response = requests.get(f"{base_url}/metrics", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Metrics endpoint test passed: {data}")
            return True
        else:
            print(f"❌ Metrics endpoint test failed: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Metrics endpoint test error: {e}")
        return False

def main():
    """Run all tests."""
    print("🚀 Testing Revenue Ops Lead Router & Enricher")
    print("=" * 50)
    
    base_url = "http://localhost:8000"
    
    # Wait for app to start
    print("⏳ Waiting for application to start...")
    time.sleep(5)
    
    tests = [
        ("Health Check", lambda: test_health_endpoint(base_url)),
        ("Lead Webhook", lambda: test_lead_webhook(base_url)),
        ("Duplicate Lead (Idempotency)", lambda: test_duplicate_lead(base_url)),
        ("Metrics Endpoint", lambda: test_metrics_endpoint(base_url))
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🧪 Running {test_name}...")
        if test_func():
            passed += 1
        else:
            print(f"❌ {test_name} failed")
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Application is working correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Check the application logs for details.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
