"""
Keyword Generator Service using Liara AI.

Generates search keywords and target descriptions for Crunchbase reports
based on project inputs. Uses Liara's Gemini 2.5 Flash model.
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional

from openai import OpenAI

logger = logging.getLogger(__name__)

# Liara AI Configuration
LIARA_API_KEY = os.getenv("LIARA_API_KEY")
LIARA_BASE_URL = os.getenv("LIARA_BASE_URL", "https://ai.liara.ir/api/6918348a8376cb0a3e18fdef/v1")
LIARA_MODEL = os.getenv("LIARA_MODEL", "google/gemini-2.5-flash")


KEYWORD_GENERATION_PROMPT = """You are a market research expert specializing in startup and company analysis. Your task is to analyze the project inputs and generate optimal search parameters for finding similar companies in Crunchbase.

## PROJECT INPUTS:
Startup Name: {startup_name}
Description: {startup_description}
Target Audience: {target_audience}
Business Model: {business_model}
Current Stage: {current_stage}
Geographic Focus: {geographic_focus}
Research Goal: {research_goal}
Competitors/Inspiration: {inspiration_sources}

## YOUR TASK:

Generate two things:

### 1. SEARCH KEYWORDS (8-12 keywords)
Create a diverse set of search keywords that will help find similar companies:
- **Technology terms**: Core technologies, platforms, tools used
- **Industry/Sector**: Market categories, verticals, segments
- **Business model**: Revenue model, customer type (B2B, B2C, SaaS)
- **Problem/Solution**: Key problems solved, value propositions
- **Target market**: Demographics, geography, use cases

Mix broad terms (high coverage) with specific terms (high precision).
Prioritize terms that would appear in company descriptions on Crunchbase.

### 2. TARGET DESCRIPTION (2-3 sentences)
Write a concise description optimized for semantic similarity search:
- Capture the core value proposition
- Include key differentiators
- Mention target market and use case
- Use language similar to how companies describe themselves

## OUTPUT FORMAT:
Respond with ONLY valid JSON (no markdown, no code blocks):
{
  "keywords": ["keyword1", "keyword2", "keyword3", ...],
  "target_description": "A 2-3 sentence description..."
}"""


class KeywordGenerator:
    """
    Service for generating search keywords and target descriptions
    using Liara AI (Gemini 2.5 Flash).
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the Liara AI client."""
        self.api_key = api_key or LIARA_API_KEY
        
        if not self.api_key:
            raise ValueError(
                "Liara API key is required. Set LIARA_API_KEY environment variable."
            )
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=LIARA_BASE_URL
        )
        
        logger.info(f"KeywordGenerator initialized with Liara AI ({LIARA_MODEL})")
    
    def generate(self, project_inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate keywords and target description from project inputs.
        
        Args:
            project_inputs: Dict containing project input fields
            
        Returns:
            Dict with 'keywords' (list) and 'target_description' (str)
        """
        try:
            # Format the prompt with project inputs
            prompt = KEYWORD_GENERATION_PROMPT.format(
                startup_name=project_inputs.get('startup_name', 'N/A'),
                startup_description=project_inputs.get('startup_description', 'N/A'),
                target_audience=project_inputs.get('target_audience', 'N/A'),
                business_model=project_inputs.get('business_model', 'N/A'),
                current_stage=project_inputs.get('current_stage', 'N/A'),
                geographic_focus=project_inputs.get('geographic_focus', 'N/A'),
                research_goal=project_inputs.get('research_goal', 'N/A'),
                inspiration_sources=project_inputs.get('inspiration_sources', 'N/A')
            )
            
            logger.info("Calling Liara AI to generate search keywords...")
            
            # Call Liara API
            response = self.client.chat.completions.create(
                model=LIARA_MODEL,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            if not response.choices or not response.choices[0].message.content:
                raise Exception("Empty response from Liara AI")
            
            content = response.choices[0].message.content.strip()
            
            # Parse JSON response
            try:
                # Handle potential markdown code blocks
                if content.startswith("```"):
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:]
                    content = content.strip()
                
                result = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse AI response as JSON: {content}")
                raise Exception(f"Invalid JSON from AI: {e}")
            
            # Validate response structure
            keywords = result.get('keywords', [])
            target_description = result.get('target_description', '')
            
            if not keywords:
                logger.warning("No keywords generated, using fallback")
                keywords = self._fallback_keywords(project_inputs)
            
            if not target_description:
                logger.warning("No target description generated, using fallback")
                target_description = self._fallback_description(project_inputs)
            
            # Ensure we have 8-12 keywords
            keywords = keywords[:12]  # Cap at 12
            if len(keywords) < 8:
                # Add some generic terms if needed
                generic = ['startup', 'technology', 'innovation', 'platform', 'solution']
                for term in generic:
                    if term not in keywords and len(keywords) < 8:
                        keywords.append(term)
            
            logger.info(f"Generated {len(keywords)} keywords: {keywords[:5]}...")
            logger.info(f"Generated target description: {target_description[:100]}...")
            
            return {
                'keywords': keywords,
                'target_description': target_description
            }
            
        except Exception as e:
            logger.error(f"Keyword generation failed: {e}")
            # Return fallback values instead of failing
            return {
                'keywords': self._fallback_keywords(project_inputs),
                'target_description': self._fallback_description(project_inputs)
            }
    
    def _fallback_keywords(self, inputs: Dict[str, Any]) -> List[str]:
        """Generate fallback keywords from project inputs."""
        keywords = []
        
        # Add startup name
        if inputs.get('startup_name'):
            keywords.append(inputs['startup_name'])
        
        # Extract words from description
        if inputs.get('startup_description'):
            words = inputs['startup_description'].split()
            keywords.extend([w for w in words[:15] if len(w) > 4])
        
        # Add business model
        if inputs.get('business_model'):
            keywords.append(inputs['business_model'])
        
        # Add research goal
        if inputs.get('research_goal'):
            keywords.append(inputs['research_goal'])
        
        # Add inspiration sources
        if inputs.get('inspiration_sources'):
            sources = inputs['inspiration_sources'].split(',')
            keywords.extend([s.strip() for s in sources[:3]])
        
        # Deduplicate and limit
        keywords = list(dict.fromkeys(keywords))[:12]
        
        return keywords if keywords else ['startup', 'technology', 'innovation']
    
    def _fallback_description(self, inputs: Dict[str, Any]) -> str:
        """Generate fallback target description from project inputs."""
        parts = []
        
        if inputs.get('startup_name'):
            parts.append(inputs['startup_name'])
        
        if inputs.get('startup_description'):
            parts.append(inputs['startup_description'][:200])
        
        if inputs.get('target_audience'):
            parts.append(f"targeting {inputs['target_audience']}")
        
        return '. '.join(parts) if parts else "Innovative technology startup."


# Async wrapper for use in async contexts
async def generate_keywords_async(project_inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Async wrapper for keyword generation."""
    import asyncio
    from functools import partial
    
    generator = KeywordGenerator()
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        partial(generator.generate, project_inputs)
    )
