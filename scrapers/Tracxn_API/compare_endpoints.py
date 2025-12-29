#!/usr/bin/env python3
"""
Comparison script: /scrape-batch vs /scrape-batch-api
This script compares the performance of UI-based vs API-based scraping
"""

import requests
import json
import time

API_BASE_URL = "http://localhost:8008"

def compare_endpoints():
    """Compare the two endpoints with the same search criteria"""
    
    test_data = {
        "company_names": ["artificial intelligence"],
        "num_companies_per_search": 3,
        "freshness_days": 0  # Force fresh scraping for fair comparison
    }
    
    print("=" * 80)
    print("Performance Comparison: /scrape-batch vs /scrape-batch-api")
    print("=" * 80)
    print(f"\nTest Configuration:")
    print(f"  - Keywords: {test_data['company_names']}")
    print(f"  - Companies per search: {test_data['num_companies_per_search']}")
    print(f"  - Freshness: {test_data['freshness_days']} days (force fresh)")
    
    # Test 1: Original UI-based endpoint
    print("\n" + "-" * 80)
    print("Test 1: UI-Based Scraping (/scrape-batch)")
    print("-" * 80)
    
    ui_start = time.time()
    try:
        print("Sending request to /scrape-batch...")
        ui_response = requests.post(
            f"{API_BASE_URL}/scrape-batch",
            json=test_data,
            headers={"Content-Type": "application/json"},
            timeout=600
        )
        ui_elapsed = time.time() - ui_start
        
        if ui_response.status_code == 200:
            ui_data = ui_response.json()
            print(f"✅ Success!")
            print(f"⏱️  Time: {ui_elapsed:.2f} seconds")
            print(f"📊 Results:")
            print(f"   - Total Companies: {ui_data['total_companies']}")
            print(f"   - Newly Scraped: {ui_data['newly_scraped']}")
            ui_success = True
        else:
            print(f"❌ Failed with status {ui_response.status_code}")
            ui_elapsed = None
            ui_success = False
    except Exception as e:
        print(f"❌ Exception: {e}")
        ui_elapsed = None
        ui_success = False
    
    # Small delay between tests
    time.sleep(2)
    
    # Test 2: New API-based endpoint
    print("\n" + "-" * 80)
    print("Test 2: API-Based Scraping (/scrape-batch-api)")
    print("-" * 80)
    
    api_start = time.time()
    try:
        # Add sort_by parameter for API endpoint
        api_test_data = {**test_data, "sort_by": "relevance"}
        
        print("Sending request to /scrape-batch-api...")
        api_response = requests.post(
            f"{API_BASE_URL}/scrape-batch-api",
            json=api_test_data,
            headers={"Content-Type": "application/json"},
            timeout=600
        )
        api_elapsed = time.time() - api_start
        
        if api_response.status_code == 200:
            api_data = api_response.json()
            print(f"✅ Success!")
            print(f"⏱️  Time: {api_elapsed:.2f} seconds")
            print(f"📊 Results:")
            print(f"   - Total Companies: {api_data['total_companies']}")
            print(f"   - Newly Scraped: {api_data['newly_scraped']}")
            api_success = True
        else:
            print(f"❌ Failed with status {api_response.status_code}")
            api_elapsed = None
            api_success = False
    except Exception as e:
        print(f"❌ Exception: {e}")
        api_elapsed = None
        api_success = False
    
    # Comparison Summary
    print("\n" + "=" * 80)
    print("COMPARISON SUMMARY")
    print("=" * 80)
    
    if ui_success and api_success:
        print(f"\n⏱️  Performance:")
        print(f"   UI-Based:  {ui_elapsed:.2f} seconds")
        print(f"   API-Based: {api_elapsed:.2f} seconds")
        
        if api_elapsed < ui_elapsed:
            speedup = (ui_elapsed / api_elapsed)
            savings = ui_elapsed - api_elapsed
            print(f"\n🚀 API-Based is {speedup:.2f}x FASTER!")
            print(f"   Time Saved: {savings:.2f} seconds ({(savings/ui_elapsed)*100:.1f}% faster)")
        else:
            print(f"\n⚠️  UI-Based was faster in this test")
        
        print(f"\n📊 Features Comparison:")
        print(f"   {'Feature':<25} {'UI-Based':<15} {'API-Based':<15}")
        print(f"   {'-'*25} {'-'*15} {'-'*15}")
        print(f"   {'Speed':<25} {'Slower':<15} {'Faster':<15}")
        print(f"   {'Reliability':<25} {'UI-dependent':<15} {'API-stable':<15}")
        print(f"   {'Scalability':<25} {'Limited':<15} {'Better':<15}")
        print(f"   {'Resource Usage':<25} {'High':<15} {'Lower':<15}")
        
    else:
        print("\n⚠️  Could not complete comparison due to failures")
        if not ui_success:
            print("   - UI-Based endpoint failed")
        if not api_success:
            print("   - API-Based endpoint failed")
    
    print("\n" + "=" * 80)

def main():
    print("\n" + "=" * 80)
    print("TracXN Scraping Endpoint Comparison Tool")
    print("=" * 80)
    
    # Check if API is running
    print("\nChecking API availability...")
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ API is running and healthy!")
        else:
            print(f"⚠️  API health check returned: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"❌ API is not reachable: {e}")
        print(f"Please start the API server first: python api.py")
        return
    
    # Run comparison
    print("\nStarting comparison test...")
    print("⚠️  This test will force fresh scraping (may take a few minutes)")
    
    input("\nPress Enter to continue or Ctrl+C to cancel...")
    
    compare_endpoints()
    
    print("\nComparison completed!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Test cancelled by user")
