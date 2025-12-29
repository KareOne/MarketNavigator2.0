"""
OpenAI service for AI-powered features.
Per FINAL_ARCHITECTURE_SPECIFICATION.md - Chat System and Report Generation.

Features:
- Chat assistance for input collection
- Report follow-up questions
- Input extraction from chat
- HTML report generation
"""
from openai import OpenAI, AsyncOpenAI
from django.conf import settings
import logging
from typing import Optional, List, Dict, Any
import json

logger = logging.getLogger(__name__)


class OpenAIService:
    """
    AI integration for chat and content generation.
    Uses Liara AI (OpenAI-compatible) with fallback to OpenAI.
    """
    
    def __init__(self):
        # Try Liara AI first (OpenAI-compatible)
        self.api_key = getattr(settings, 'LIARA_API_KEY', None)
        self.base_url = getattr(settings, 'LIARA_BASE_URL', None)
        
        if self.api_key and self.base_url:
            self.model = getattr(settings, 'LIARA_MODEL', 'google/gemini-2.5-flash')
            self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
            logger.info(f"OpenAIService initialized with Liara AI ({self.model})")
        else:
            # Fallback to OpenAI
            self.api_key = getattr(settings, 'OPENAI_API_KEY', '')
            self.model = getattr(settings, 'OPENAI_MODEL', 'gpt-4o-mini')
            self.base_url = None
            
            if self.api_key:
                self.client = AsyncOpenAI(api_key=self.api_key)
                logger.info(f"OpenAIService initialized with OpenAI ({self.model})")
            else:
                self.client = None
                logger.warning("No AI API key configured (LIARA or OPENAI)")
    
    # =========================================================================
    # Chat Assistance (per FINAL_ARCHITECTURE Chat System)
    # =========================================================================
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> str:
        """
        Generate a chat completion.
        """
        if not self.client:
            return "AI service is not configured. Please set OPENAI_API_KEY."
        
        try:
            full_messages = []
            
            if system_prompt:
                full_messages.append({"role": "system", "content": system_prompt})
            
            full_messages.extend(messages)
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=full_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI chat completion failed: {e}")
            return f"I'm sorry, I encountered an error: {str(e)}"
    
    async def extract_project_inputs(
        self,
        user_message: str,
        existing_inputs: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Extract project input fields from user's chat message.
        Per FINAL_ARCHITECTURE - AI Chat Extraction for 9 questions.
        """
        if not self.client:
            return {}
        
        system_prompt = """You are an AI assistant helping extract startup information from user messages.
        
Extract the following fields from the user's message and return a JSON object:
- startup_name: The name of the startup
- startup_description: A 2-3 sentence description
- target_audience: Who the product/service is for
- current_stage: One of: idea, mvp, early, growth, scale
- business_model: How the startup makes money
- geographic_focus: Target markets/regions
- research_goal: What the user wants to research
- time_range: One of: 1mo, 3mo, 6mo, 1yr, all
- inspiration_sources: Similar companies or competitors

For each field you extract, include a confidence score (0.0 to 1.0).
Only include fields you can confidently extract from the message.

Return JSON format:
{
  "extracted_fields": {
    "field_name": {"value": "extracted value", "confidence": 0.9}
  },
  "follow_up_questions": ["question if more info needed"]
}"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"User message: {user_message}\n\nExisting inputs: {json.dumps(existing_inputs or {})}"}
                ],
                temperature=0.3,
                max_tokens=1000,
                response_format={"type": "json_object"},
            )
            
            result = json.loads(response.choices[0].message.content)
            return result
        except Exception as e:
            logger.error(f"Input extraction failed: {e}")
            return {"extracted_fields": {}, "follow_up_questions": []}
    
    # =========================================================================
    # Report Generation (per FINAL_ARCHITECTURE)
    # =========================================================================
    
    async def generate_report_insights(
        self,
        report_type: str,
        data: Dict[str, Any],
        project_inputs: Dict[str, Any]
    ) -> str:
        """
        Generate AI insights for a report.
        """
        if not self.client:
            return "AI insights not available."
        
        system_prompt = f"""You are a market research analyst generating insights for a {report_type} report.
        
Based on the provided data and project context, generate clear, actionable insights.
Focus on:
- Key findings and patterns
- Market opportunities
- Competitive positioning
- Recommendations

Be concise and business-focused. Use bullet points for clarity."""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Project context: {json.dumps(project_inputs)}\n\nData: {json.dumps(data)}"}
                ],
                temperature=0.5,
                max_tokens=1500,
            )
            
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Report insights generation failed: {e}")
            return "Unable to generate insights at this time."
    
    async def generate_pitch_deck_content(
        self,
        project_inputs: Dict[str, Any],
        crunchbase_data: Dict[str, Any] = None,
        tracxn_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Generate pitch deck slide content.
        Per FINAL_ARCHITECTURE - Panel 4: Pitch Deck.
        """
        if not self.client:
            return {}
        
        system_prompt = """You are an expert pitch deck consultant. Generate content for a startup pitch deck.
        
Create content for these slides:
1. Title Slide - Company name, tagline
2. Problem - What problem are you solving?
3. Solution - How do you solve it?
4. Market Opportunity - Market size, growth
5. Business Model - How you make money
6. Competitive Landscape - Key competitors and differentiation
7. Traction - Key milestones and metrics
8. Team - Why your team can execute
9. Financial Projections - Revenue forecast
10. Ask - What you're asking for

Return JSON with slide content for each.
Be concise - max 3-5 bullet points per slide."""

        context = {
            "startup": project_inputs,
            "market_research": {
                "crunchbase": crunchbase_data or {},
                "tracxn": tracxn_data or {},
            }
        }

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(context)}
                ],
                temperature=0.6,
                max_tokens=2000,
                response_format={"type": "json_object"},
            )
            
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"Pitch deck generation failed: {e}")
            return {}
    
    # =========================================================================
    # Report Follow-up (per FINAL_ARCHITECTURE Chat Mode 2)
    # =========================================================================
    
    async def answer_report_question(
        self,
        question: str,
        report_type: str,
        report_content: str,
        chat_history: List[Dict[str, str]] = None
    ) -> str:
        """
        Answer questions about a generated report.
        Per FINAL_ARCHITECTURE - Chat Mode 2: Report Follow-up.
        """
        if not self.client:
            return "AI service is not configured."
        
        system_prompt = f"""You are an AI assistant helping users understand their {report_type} market research report.
        
Answer questions about the report content accurately and helpfully.
If asked to modify the report, explain what changes would be made.
Be concise but thorough."""

        messages = [{"role": "system", "content": system_prompt}]
        
        # Add context about report
        messages.append({
            "role": "user",
            "content": f"Here is the report content:\n\n{report_content[:4000]}"
        })
        messages.append({
            "role": "assistant",
            "content": "I've reviewed the report. What would you like to know?"
        })
        
        # Add chat history
        if chat_history:
            messages.extend(chat_history[-10:])  # Last 10 messages
        
        # Add current question
        messages.append({"role": "user", "content": question})
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=1000,
            )
            
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Report Q&A failed: {e}")
            return "I couldn't process your question. Please try again."


# Singleton instance
openai_service = OpenAIService()
