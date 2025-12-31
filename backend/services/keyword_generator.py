"""
Keyword Generator Service using Liara AI with Function Calling.

Forces AI to use the generate_keywords tool - NO FALLBACK.
Uses Liara's Gemini 2.5 Flash model with tool_choice="required".
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


# System prompt for the keyword generation AI
KEYWORD_AI_SYSTEM_PROMPT = """You are a specialized Keyword Generation AI for Crunchbase competitive research.

YOUR ONLY JOB: Analyze startup information and generate industry-specific search keywords using the generate_keywords tool.

## CRITICAL RULES:

1. YOU MUST ALWAYS call the generate_keywords tool - no exceptions
2. NEVER extract single words from the description like "strategic", "platform", "designed"
3. Generate 2-3 word INDUSTRY TERMS like "Market Intelligence", "Business Analytics"
4. Think about: What industry? What technology? Who are the customers? What problem is solved?

## KEYWORD CATEGORIES TO INCLUDE:
- Industry verticals: "FinTech", "MarTech", "EdTech", "HealthTech"
- Technology terms: "AI Analytics", "Machine Learning Platform", "Data Intelligence"
- Business models: "B2B SaaS", "Enterprise Software", "Marketplace Platform"
- Use cases: "Market Research", "Competitive Intelligence", "Investor Tools"
- Market segments: "Startup Tools", "SMB Software", "Enterprise Solutions"

## EXAMPLES:

Input: "Strategic research platform for startups with analytics"
Good output: ["Market Intelligence", "Competitive Analysis", "Startup Research", "Business Analytics SaaS", "B2B Data Platform", "Investor Tools", "Market Research Software", "Business Strategy Platform"]

Input: "AI-powered pet care subscription service"
Good output: ["Pet Tech", "Pet Care Platform", "AI Pet Health", "Pet Subscription", "Animal Wellness", "D2C Pet Products", "Smart Pet Care", "Pet E-commerce"]

ALWAYS use the generate_keywords tool with your output."""


# Tool definition for keyword generation
KEYWORD_GENERATION_TOOL = {
    "type": "function",
    "function": {
        "name": "generate_keywords",
        "description": "Generate industry-specific search keywords for Crunchbase competitive research. Each keyword should be 2-3 words representing an industry category, technology term, or market segment.",
        "parameters": {
            "type": "object",
            "properties": {
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "8-12 industry-specific multi-word search terms. Examples: 'Market Intelligence', 'B2B SaaS', 'Competitive Analysis'. NEVER single generic words.",
                    "minItems": 8,
                    "maxItems": 12
                },
                "target_description": {
                    "type": "string",
                    "description": "2-3 sentence description of the startup focusing on industry, technology, and target market for semantic similarity matching."
                }
            },
            "required": ["keywords", "target_description"],
            "additionalProperties": False
        }
    }
}


class KeywordGenerator:
    """
    Service for generating search keywords using Liara AI with forced tool calling.
    NO FALLBACK - AI must always use the tool.
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
        Generate keywords using AI with forced tool calling.
        
        Args:
            project_inputs: Dict containing project input fields
            
        Returns:
            Dict with 'keywords' (list) and 'target_description' (str)
            
        Raises:
            Exception: If AI fails to generate keywords (NO FALLBACK)
        """
        # Build user message with project inputs
        user_message = f"""Analyze this startup and generate search keywords using the generate_keywords tool:

STARTUP INFORMATION:
- Name: {project_inputs.get('startup_name', 'N/A')}
- Description: {project_inputs.get('startup_description', 'N/A')}
- Target Audience: {project_inputs.get('target_audience', 'N/A')}
- Business Model: {project_inputs.get('business_model', 'N/A')}
- Current Stage: {project_inputs.get('current_stage', 'N/A')}
- Geographic Focus: {project_inputs.get('geographic_focus', 'N/A')}
- Research Goal: {project_inputs.get('research_goal', 'N/A')}
- Competitors/Inspiration: {project_inputs.get('inspiration_sources', 'N/A')}

Use the generate_keywords tool to output 8-12 industry-specific search terms."""

        logger.info("🔑 Calling Liara AI with forced tool calling for keyword generation...")
        
        # Call Liara API with tool_choice to force tool usage
        response = self.client.chat.completions.create(
            model=LIARA_MODEL,
            messages=[
                {"role": "system", "content": KEYWORD_AI_SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ],
            tools=[KEYWORD_GENERATION_TOOL],
            tool_choice={"type": "function", "function": {"name": "generate_keywords"}},
            temperature=0.7,
            max_tokens=1000
        )
        
        # Extract tool call from response
        if not response.choices or not response.choices[0].message.tool_calls:
            raise Exception("AI did not call the generate_keywords tool - this should not happen with tool_choice=required")
        
        tool_call = response.choices[0].message.tool_calls[0]
        
        if tool_call.function.name != "generate_keywords":
            raise Exception(f"AI called wrong tool: {tool_call.function.name}")
        
        # Parse the tool arguments
        try:
            arguments = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse tool arguments as JSON: {e}")
        
        keywords = arguments.get('keywords', [])
        target_description = arguments.get('target_description', '')
        
        # Validate we got keywords
        if not keywords or len(keywords) < 3:
            raise Exception(f"AI generated insufficient keywords: {keywords}")
        
        # Validate keyword quality - reject if they're just single words extracted from description
        bad_keywords = ['strategic', 'platform', 'designed', 'support', 'making', 'using', 'through']
        bad_count = sum(1 for kw in keywords if kw.lower() in bad_keywords)
        if bad_count > 2:
            raise Exception(f"AI generated low-quality keywords with generic words: {keywords}")
        
        logger.info(f"✅ AI generated {len(keywords)} keywords: {keywords}")
        logger.info(f"📝 Target description: {target_description[:100]}...")
        
        return {
            'keywords': keywords[:12],  # Cap at 12
            'target_description': target_description
        }


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
