#!/usr/bin/env python3
"""Test the actual response time of cluster endpoints"""

import time
import sys
import requests

BASE_URL = "http://127.0.0.1:4000"

def test_endpoint(endpoint, name):
    """Test an endpoint and return timing info"""
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"Endpoint: {endpoint}")
    print(f"{'='*60}")
    
    try:
        start = time.time()
        response = requests.get(f"{BASE_URL}{endpoint}", timeout=30)
        elapsed = time.time() - start
        
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                count = len(data)
                print(f"✓ SUCCESS: {response.status_code}")
                print(f"  Response time: {elapsed:.3f} seconds")
                print(f"  Items returned: {count}")
            else:
                print(f"✓ SUCCESS: {response.status_code}")
                print(f"  Response time: {elapsed:.3f} seconds")
                print(f"  Data keys: {list(data.keys())}")
            
            # Performance assessment
            if elapsed < 0.5:
                print(f"  Performance: ⚡ EXCELLENT (< 0.5s)")
            elif elapsed < 1.0:
                print(f"  Performance: ✓ GOOD (< 1s)")
            elif elapsed < 3.0:
                print(f"  Performance: ⚠ ACCEPTABLE (< 3s)")
            else:
                print(f"  Performance: ✗ SLOW (> 3s) - NEEDS OPTIMIZATION")
                return False
            
            return True
        else:
            print(f"✗ FAILED: {response.status_code}")
            print(f"  Response: {response.text[:200]}")
            return False
            
    except requests.exceptions.Timeout:
        print(f"✗ TIMEOUT: Request took longer than 30 seconds")
        return False
    except Exception as e:
        print(f"✗ ERROR: {e}")
        return False

def main():
    print("\n" + "="*60)
    print("CLUSTER ENDPOINT PERFORMANCE TEST")
    print("="*60)
    
    tests = [
        ("/api/clusters/summary", "Cluster Summary"),
        ("/api/clusters?limit=50", "Cluster List (50 items)"),
        ("/api/clusters?limit=200", "Cluster List (200 items)"),
    ]
    
    results = []
    for endpoint, name in tests:
        success = test_endpoint(endpoint, name)
        results.append((name, success))
        time.sleep(0.5)  # Brief pause between tests
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    all_passed = True
    for name, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{status}: {name}")
        if not success:
            all_passed = False
    
    print("="*60)
    
    if all_passed:
        print("\n✓ All tests passed! Cluster page should load quickly.")
        sys.exit(0)
    else:
        print("\n✗ Some tests failed. Performance needs improvement.")
        sys.exit(1)

if __name__ == "__main__":
    main()
