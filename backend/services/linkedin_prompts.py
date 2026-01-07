"""
Linkedin Analysis Pipeline Service.
Orchestrates AI analysis of Linkedin data for Market Reporting.
"""
import logging
import asyncio
import json
from typing import List, Dict, Any, Optional
from django.conf import settings
from openai import AsyncOpenAI

from services.social_prompts import PromptTemplates

logger = logging.getLogger(__name__)


class LinkedinAnalysisPipeline:
    """
    Pipeline for analyzing Linkedin data.
    """
    
    def __init__(self, target_market_description: str = None, model: str = None):
        self.api_key = getattr(settings, 'LIARA_API_KEY', None)
        self.base_url = getattr(settings, 'LIARA_BASE_URL', "https://ai.liara.ir/api/6918348a8376cb0a3e18fdef/v1")
        self.model = model or getattr(settings, 'LIARA_MODEL', "google/gemini-2.0-flash")
        
        if not self.api_key:
            logger.warning("Liara API Key not found. Analysis will fail.")
            
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
        self.prompts = PromptTemplates(target_market_description=target_market_description)

    async def _call_ai(self, prompt: str) -> str:
        """Helper to call AI."""
        try:
            # Construct kwargs dynamically
            kwargs = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.5, # Slightly lower temp for analytical tasks
            }
            
            # Note: Removed JSON mode as new prompts ask for Markdown output

            response = await self.client.chat.completions.create(**kwargs)
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"AI Call failed: {e}")
            return "Error generating content."

    def _prepare_data_context(self, tweets: List[Dict]) -> List[Dict[str, Any]]:
        """
        Format tweets for prompt context. 
        Passes structured data instead of raw string to let prompt handle JSON dump.
        """
        context_data = []
        for t in tweets:
            context_data.append({
                "text": t.get('text', ''),
                "likes": t.get('metrics', {}).get('like_count', 0),
                "retweets": t.get('metrics', {}).get('retweet_count', 0),
                "date": t.get('created_at', ''),
                "author": t.get('author_id', 'unknown')
            })
        # Limit to reasonable size if needed, but for now passing all
        return context_data[:200] # Cap at 200 tweets to avoid token limits if list is huge

    async def analyze(self, tweets: List[Dict], tracker = None) -> Dict[str, Any]:
        """
        Run full analysis pipeline and return FORMATTED markdown content.
        """
        tweet_data = self._prepare_data_context(tweets)
        results = {}
        
        # 1. Run analysis for all 10 categories
        categories = PromptTemplates.get_all_categories()
        
        for category in categories:
            if tracker:
                await tracker.start_step(category)
                await tracker.update_step_message(category, f"Analyzing {category}...")
            
            prompt = self.prompts.generate_category_report(
                category=category,
                data=tweet_data,
                source="linkedin"
            )
            
            # Call AI (returns Markdown)
            content = await self._call_ai(prompt)
            
            # Store result using category as key
            results[category] = content
            
            if tracker:
                 await tracker.complete_step(category)

        # 2. Generate Cross-Cutting Insights
        cross_cutting_key = 'Cross-Cutting Insights'
        if tracker:
            await tracker.start_step(cross_cutting_key)
            await tracker.update_step_message(cross_cutting_key, "Generating Cross-Cutting Insights...")
            
        cross_cutting_prompt = self.prompts.generate_cross_cutting_insights(
            data=tweet_data,
            source="linkedin"
        )
        cross_cutting_content = await self._call_ai(cross_cutting_prompt)
        results['Cross-Cutting Insights'] = cross_cutting_content
        
        if tracker:
            await tracker.complete_step(cross_cutting_key)
        
        return results

