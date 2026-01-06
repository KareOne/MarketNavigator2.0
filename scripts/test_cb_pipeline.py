
import os
import sys
import asyncio
import logging
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure Django settings (minimal)
import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        LIARA_API_KEY="test-key",
        INSTALLED_APPS=['apps.reports'],
        USE_S3=False,
        OPENAI_API_KEY="test-key",
    )
    django.setup()

from services.crunchbase_analysis import CrunchbaseAnalysisPipeline, generate_analysis_html

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def mock_call_ai(self, prompt: str, max_tokens: int = 4000) -> str:
    """Mock AI response based on prompt content."""
    if "Part 1" in prompt or "Company Deep Dive" in prompt or "Executive Summary" in prompt:
        return f"# Deep Dive Report\n\n## Executive Summary\nMock analysis based on prompt length {len(prompt)}..."
    elif "Part 2" in prompt or "Strategic Summary" in prompt:
        return "# Strategic Summary\n\n## Market Map\nMock strategic summary..."
    elif "Part 3" in prompt or "Fast Analysis" in prompt:
        return "# Fast Analysis\n\n## Flash Report\nMock fast analysis..."
    else:
        return "Generic mock response"

async def run_test():
    print("🚀 Starting Crunchbase Pipeline Test...")
    
    # Mock data
    companies = [
        {"name": "Test Company A", "description": "AI analytics platform", "funding_total": 1000000},
        {"name": "Test Company B", "description": "Blockchain verification", "funding_total": 5000000},
    ]
    
    # Initialize pipeline
    pipeline = CrunchbaseAnalysisPipeline(target_market_description="AI and Blockchain market")
    
    # Monkey patch _call_ai to avoid real API calls
    with patch.object(CrunchbaseAnalysisPipeline, '_call_ai', side_effect=mock_call_ai, autospec=True):
        
        # Run analysis
        print("📊 Running analysis...")
        result = await pipeline.analyze(companies, max_companies=2)
        
        # Verify structure
        print("\n🔍 Verifying Result Structure:")
        
        # Check Deep Dive
        if "company_deep_dive" in result["sections"]:
            deep_dives = result["sections"]["company_deep_dive"]
            print(f"✅ Company Deep Dive: Found {len(deep_dives)} reports")
            for dd in deep_dives:
                print(f"   - {dd['company_name']}")
        else:
            print("❌ Company Deep Dive: Missing!")

        # Check Strategic Summary
        if "strategic_summary" in result["sections"]:
            print("✅ Strategic Summary: Found")
        else:
            print("❌ Strategic Summary: Missing!")
            
        # Check Fast Analysis
        if "fast_analysis" in result["sections"]:
            print("✅ Fast Analysis: Found")
        else:
            print("❌ Fast Analysis: Missing!")
            
        # Generate HTML
        print("\n📝 Generating HTML...")
        html = generate_analysis_html(result, startup_name="Test Startup")
        
        if "Fast Analysis (Board View)" in html:
            print("✅ HTML: Contains 'Fast Analysis'")
        else:
            print("❌ HTML: Missing 'Fast Analysis'")
            
        if "Strategic Summary" in html:
            print("✅ HTML: Contains 'Strategic Summary'")
        else:
            print("❌ HTML: Missing 'Strategic Summary'")

        if "Company Deep Dives" in html:
            print("✅ HTML: Contains 'Company Deep Dives'")
        else:
            print("❌ HTML: Missing 'Company Deep Dives'")
            
        print("\n🎉 Test Complete!")

if __name__ == "__main__":
    asyncio.run(run_test())
