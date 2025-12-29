#!/usr/bin/env python3
"""
Test script for the new /scrape-batch-api-with-rank endpoint
This endpoint combines TracXN API search with AI similarity scoring
"""

import requests
import json

# API endpoint
BASE_URL = "http://localhost:8008"
endpoint = f"{BASE_URL}/scrape-batch-api-with-rank"

# Test payload
payload = {
    "company_names": [
        "artificial intelligence",
        "machine learning",
        "data analytics"
    ],
    "num_companies_per_search": 10,  # Get 10 companies per keyword from API
    "freshness_days": 180,
    "top_count": 5,  # Only scrape full data for top 5 companies
    "target_description": "AI-powered data analytics and machine learning platform for business intelligence",
    "similarity_weight": 0.75,  # 75% weight for similarity
    "score_weight": 0.25,  # 25% weight for TracXN score
    "sort_by": "relevance"
}

print("=" * 80)
print("Testing /scrape-batch-api-with-rank endpoint")
print("=" * 80)
print(f"\nPayload:")
print(json.dumps(payload, indent=2))
print("\n" + "=" * 80)
print("Sending request...")
print("=" * 80)

try:
    response = requests.post(endpoint, json=payload, timeout=300)
    
    print(f"\nStatus Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        
        print("\n" + "=" * 80)
        print("RESPONSE SUMMARY")
        print("=" * 80)
        
        # Metadata
        metadata = data.get('metadata', {})
        print(f"\nMetadata:")
        print(f"  Total Keywords Searched: {metadata.get('total_keywords_searched')}")
        print(f"  Total Unique Companies: {metadata.get('total_unique_companies')}")
        print(f"  All Companies Count: {metadata.get('all_companies_count')}")
        print(f"  Top Count Requested: {metadata.get('top_count_requested')}")
        print(f"  Top Count Returned: {metadata.get('top_count_returned')}")
        print(f"  Similarity Weight: {metadata.get('similarity_weight')}")
        print(f"  Score Weight: {metadata.get('score_weight')}")
        print(f"  TracXN Score Range: {metadata.get('tracxn_score_range')}")
        
        # All companies (ranked by combined score)
        all_companies = data.get('all_companies', [])
        print(f"\n" + "=" * 80)
        print(f"ALL COMPANIES (Total: {len(all_companies)}) - Sorted by Combined Score")
        print("=" * 80)
        
        for i, company in enumerate(all_companies[:10]):  # Show top 10
            print(f"\n{i+1}. {company.get('name', 'N/A')}")
            print(f"   Rank: {company.get('rank')}")
            print(f"   Combined Score: {company.get('combined_score', 0):.4f}")
            print(f"   Similarity Score: {company.get('similarity_score', 0):.4f}")
            print(f"   TracXN Score: {company.get('tracxn_score', 0):.2f} (normalized: {company.get('normalized_tracxn_score', 0):.4f})")
            print(f"   Appeared in {company.get('appearance_count', 0)} searches")
            print(f"   Keywords: {', '.join(company.get('keywords', []))}")
            print(f"   Description: {company.get('description', 'N/A')[:100]}...")
        
        if len(all_companies) > 10:
            print(f"\n... and {len(all_companies) - 10} more companies")
        
        # Top companies with full data
        top_companies = data.get('top_companies_full_data', [])
        print(f"\n" + "=" * 80)
        print(f"TOP COMPANIES WITH FULL DATA (Total: {len(top_companies)})")
        print("=" * 80)
        
        for i, company in enumerate(top_companies):
            print(f"\n{i+1}. {company.get('name', 'N/A')}")
            print(f"   Rank: {company.get('rank')}")
            print(f"   Combined Score: {company.get('combined_score', 0):.4f}")
            print(f"   Similarity Score: {company.get('similarity_score', 0):.4f}")
            print(f"   TracXN Score: {company.get('tracxn_score', 0):.2f}")
            print(f"   Source: {company.get('source', 'N/A')}")
            print(f"   Reference: {company.get('reference', 'N/A')}")
            full_data = company.get('full_data', [])
            print(f"   Full Data Fields: {len(full_data)} sections")
            
            # Show some key fields from full data
            for item in full_data[:3]:
                title = item.get('title', 'N/A')
                content = str(item.get('content', 'N/A'))
                print(f"     - {title}: {content[:80]}...")
        
        print("\n" + "=" * 80)
        print("✅ Test completed successfully!")
        print("=" * 80)
        
    else:
        print(f"\n❌ Error: {response.status_code}")
        print(response.text)
        
except requests.exceptions.Timeout:
    print("\n❌ Request timed out (>300s)")
except requests.exceptions.ConnectionError:
    print(f"\n❌ Could not connect to {BASE_URL}")
    print("Make sure the API server is running with: python api.py")
except Exception as e:
    print(f"\n❌ Error: {e}")
