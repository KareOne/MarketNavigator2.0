"""
Twitter Analysis Pipeline Service.
Orchestrates AI analysis of Twitter data for Market Reporting.
"""
import logging
import asyncio
from typing import List, Dict, Any, Optional
from django.conf import settings
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# =============================================================================
# Prompt Templates
# =============================================================================

class PromptTemplates:
    """Prompt templates for Social Media Analysis."""
    
    @staticmethod
    def market_segmentation(tweets_text: str) -> str:
        return f"""Analyze these tweets to identify key User Segments and Personas.
        
        TWEETS:
        {tweets_text}
        
        OUTPUT JSON:
        {{
            "segments": [
                {{
                    "name": "Segment Name",
                    "description": "Description of who they are",
                    "needs": ["need 1", "need 2"],
                    "evidence": "Quote from tweet"
                }}
            ]
        }}
        """

    @staticmethod
    def jobs_to_be_done(tweets_text: str) -> str:
        return f"""Identify "Jobs to be Done" (JTBD) from these tweets.
        What are users trying to accomplish?
        
        TWEETS:
        {tweets_text}
        
        OUTPUT JSON:
        {{
            "jtbd": [
                {{
                    "job": "To [action] so that [outcome]",
                    "context": "When [situation]",
                    "pain_level": "High/Medium/Low"
                }}
            ]
        }}
        """

    @staticmethod
    def pain_points(tweets_text: str) -> str:
        return f"""Extract specific Pain Points and Frustrations.
        Focus on specific complaints, not general negativity.
        
        TWEETS:
        {tweets_text}
        
        OUTPUT JSON:
        {{
            "pains": [
                {{
                    "pain": "Description of pain point",
                    "frequency": "High/Low",
                    "sentiment": "Angry/Frustrated/Annoyed",
                    "quotes": ["tweet snippet 1"]
                }}
            ]
        }}
        """

    @staticmethod
    def willingness_to_pay(tweets_text: str) -> str:
        return f"""Analyze comments about Pricing and Value.
        Are users complaining about price? Mentioning competitors' prices?
        
        TWEETS:
        {tweets_text}
        
        OUTPUT JSON:
        {{
            "pricing_sentiment": "Expensive/Fair/Cheap",
            "competitor_pricing": ["Competitor A is cheaper", "Competitor B is worth more"],
            "value_drivers": ["users pay for X", "users hate paying for Y"]
        }}
        """
        
    @staticmethod
    def competitive_landscape(tweets_text: str) -> str:
        return f"""Identify Competitors mentioned and how they compare.
        
        TWEETS:
        {tweets_text}
        
        OUTPUT JSON:
        {{
            "competitors": [
                {{
                    "name": "Competitor Name",
                    "sentiment": "Positive/Negative",
                    "strengths": ["feature A", "support"],
                    "weaknesses": ["price", "bugs"]
                }}
            ]
        }}
        """
        
    @staticmethod
    def sentiment_analysis(tweets_text: str) -> str:
        return f"""Analyze overall Sentiment and Trends.
        
        TWEETS:
        {tweets_text}
        
        OUTPUT JSON:
        {{
            "overall_sentiment": "Positive/Neutral/Negative",
            "score": 0.0 to 10.0,
            "key_themes": ["theme 1", "theme 2"],
            "emerging_trends": ["trend A"]
        }}
        """
        
    @staticmethod
    def executive_summary(all_insights: str) -> str:
        return f"""Write an Executive Summary for a Market Report based on these insights.
        
        INSIGHTS:
        {all_insights}
        
        Format as Markdown. Include:
        - Key Opportunities
        - Critical Risks
        - Strategic Recommendations
        """


import json

# =============================================================================
# Result Formatter
# =============================================================================

class ResultFormatter:
    """Formats JSON analysis results into Markdown."""
    
    @staticmethod
    def format_market_segmentation(data: Dict) -> str:
        try:
            segments = data.get("segments", [])
            output = ["## Market Segmentation\n"]
            
            if not segments:
                return "## Market Segmentation\n\nNo segments identified."
                
            for segment in segments:
                name = segment.get("name", "Unknown Segment")
                desc = segment.get("description", "")
                evidence = segment.get("evidence", "")
                needs = segment.get("needs", [])
                
                output.append(f"### {name}\n")
                if desc:
                    output.append(f"**Description:** {desc}\n")
                
                if needs:
                    output.append("\n**Key Needs:**")
                    for need in needs:
                        output.append(f"- {need}")
                    output.append("")
                
                if evidence:
                    output.append(f"\n> *\"{evidence}\"*\n")
                
                output.append("---\n")
                
            return "\n".join(output)
        except Exception as e:
            return f"Error formatting Market Segmentation: {e}\n\nRaw Data:\n{json.dumps(data, indent=2)}"

    @staticmethod
    def format_jobs_to_be_done(data: Dict) -> str:
        try:
            jtbd_list = data.get("jtbd", [])
            output = ["## Jobs to be Done\n"]
            
            if not jtbd_list:
                return "## Jobs to be Done\n\nNo key jobs identified."
            
            for item in jtbd_list:
                job = item.get("job", "")
                context = item.get("context", "")
                pain_level = item.get("pain_level", "Unknown")
                
                emoji = "🔴" if pain_level.lower() == "high" else "🟡" if pain_level.lower() == "medium" else "🟢"
                
                output.append(f"### {emoji} {job}\n")
                if context:
                    output.append(f"**Context:** {context}\n")
                output.append(f"**Pain Level:** {pain_level}\n")
                output.append("")
                
            return "\n".join(output)
        except Exception:
             return f"Error formatting Jobs to be Done.\n\nRaw Data:\n{json.dumps(data, indent=2)}"

    @staticmethod
    def format_pain_points(data: Dict) -> str:
        try:
            pains = data.get("pains", [])
            output = ["## Pain Points & Frustrations\n"]
            
            if not pains:
                return "## Pain Points & Frustrations\n\nNo specific pain points identified."
                
            for item in pains:
                pain = item.get("pain", "")
                frequency = item.get("frequency", "")
                sentiment = item.get("sentiment", "")
                quotes = item.get("quotes", [])
                
                output.append(f"### {pain}")
                meta = []
                if frequency: meta.append(f"**Freq:** {frequency}")
                if sentiment: meta.append(f"**Sentiment:** {sentiment}")
                
                if meta:
                    output.append(" | ".join(meta) + "\n")
                
                if quotes:
                    output.append("\n**User Voices:**")
                    for q in quotes:
                        output.append(f"> \"{q}\"")
                    output.append("")
                output.append("")
                
            return "\n".join(output)
        except Exception:
             return f"Error formatting Pain Points.\n\nRaw Data:\n{json.dumps(data, indent=2)}"

    @staticmethod
    def format_willingness_to_pay(data: Dict) -> str:
        try:
            sentiment = data.get("pricing_sentiment", "")
            competitors = data.get("competitor_pricing", [])
            drivers = data.get("value_drivers", [])
            
            output = ["## Willingness to Pay & Value Perception\n"]
            
            if sentiment:
                output.append(f"**Overall Sentiment:** {sentiment}\n")
            
            if drivers:
                output.append("### Value Drivers (What users pay for)")
                for d in drivers:
                    output.append(f"- {d}")
                output.append("")
                
            if competitors:
                output.append("### Competitor Pricing Mentions")
                for c in competitors:
                    output.append(f"- {c}")
                output.append("")
                
            return "\n".join(output)
        except Exception:
             return f"Error formatting WTP.\n\nRaw Data:\n{json.dumps(data, indent=2)}"

    @staticmethod
    def format_competitive_landscape(data: Dict) -> str:
        try:
            competitors = data.get("competitors", [])
            output = ["## Competitive Landscape\n"]
            
            if not competitors:
                return "## Competitive Landscape\n\nNo competitors explicitly mentioned."
                
            for comp in competitors:
                name = comp.get("name", "Unknown")
                sentiment = comp.get("sentiment", "")
                strengths = comp.get("strengths", [])
                weaknesses = comp.get("weaknesses", [])
                
                output.append(f"### {name}")
                if sentiment:
                    output.append(f"**Sentiment:** {sentiment}\n")
                
                if strengths:
                    output.append("**✅ Strengths / Praises:**")
                    for s in strengths:
                        output.append(f"- {s}")
                    output.append("")
                    
                if weaknesses:
                    output.append("**⚠️ Weaknesses / Complaints:**")
                    for w in weaknesses:
                        output.append(f"- {w}")
                    output.append("")
                    
                output.append("---\n")
                
            return "\n".join(output)
        except Exception:
             return f"Error formatting Competitive Landscape.\n\nRaw Data:\n{json.dumps(data, indent=2)}"

    @staticmethod
    def format_sentiment(data: Dict) -> str:
        try:
            overall = data.get("overall_sentiment", "")
            score = data.get("score", 0)
            themes = data.get("key_themes", [])
            trends = data.get("emerging_trends", [])
            
            output = ["## Sentiment Analysis\n"]
            
            output.append(f"### Overall Sentiment: {overall} ({score}/10)\n")
            
            if themes:
                output.append("### Key Conversation Themes")
                for t in themes:
                    output.append(f"- {t}")
                output.append("")
                
            if trends:
                output.append("### Emerging Trends")
                for t in trends:
                    output.append(f"- {t}")
                output.append("")
                
            return "\n".join(output)
        except Exception:
             return f"Error formatting Sentiment.\n\nRaw Data:\n{json.dumps(data, indent=2)}"


# =============================================================================
# Pipeline
# =============================================================================

class TwitterAnalysisPipeline:
    """
    Pipeline for analyzing Twitter data.
    """
    
    def __init__(self, model: str = None):
        self.api_key = getattr(settings, 'LIARA_API_KEY', None)
        self.base_url = getattr(settings, 'LIARA_BASE_URL', "https://ai.liara.ir/api/6918348a8376cb0a3e18fdef/v1")
        self.model = model or getattr(settings, 'LIARA_MODEL', "google/gemini-2.0-flash")
        
        if not self.api_key:
            logger.warning("Liara API Key not found. Analysis will fail.")
            
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
        self.prompts = PromptTemplates()

    async def _call_ai(self, prompt: str, json_mode: bool = True) -> str:
        """Helper to call AI."""
        try:
            # Construct kwargs dynamically
            kwargs = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
            }
            
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            response = await self.client.chat.completions.create(**kwargs)
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"AI Call failed: {e}")
            return "{}" if json_mode else "Error generating content."

    def _format_tweets(self, tweets: List[Dict]) -> str:
        """Format tweets for prompt context."""
        text = ""
        for t in tweets:
            content = t.get('text', '')
            metrics = t.get('metrics', {})
            likes = metrics.get('like_count', 0)
            text += f"- [{likes} likes] {content}\n"
        return text[:50000] # Cap context

    async def analyze(self, tweets: List[Dict], tracker = None) -> Dict[str, Any]:
        """
        Run full analysis pipeline and return FORMATTED markdown content.
        """
        tweets_text = self._format_tweets(tweets)
        results = {}
        
        # Mapping of (key, prompt_func, formatter_func)
        steps = [
            ("market_segmentation", self.prompts.market_segmentation, ResultFormatter.format_market_segmentation),
            ("jobs to be done", self.prompts.jobs_to_be_done, ResultFormatter.format_jobs_to_be_done),
            ("pain_points", self.prompts.pain_points, ResultFormatter.format_pain_points),
            ("willingness_to_pay", self.prompts.willingness_to_pay, ResultFormatter.format_willingness_to_pay),
            ("competitive_landscape", self.prompts.competitive_landscape, ResultFormatter.format_competitive_landscape),
            ("sentiment", self.prompts.sentiment_analysis, ResultFormatter.format_sentiment),
        ]
        
        for key, prompt_fn, formatter_fn in steps:
            if tracker:
                await tracker.update_step_message('analysis', f"Analyzing {key.replace('_', ' ').title()}...")
            
            prompt = prompt_fn(tweets_text)
            
            # 1. Get JSON from AI
            json_content_str = await self._call_ai(prompt, json_mode=True)
            
            # 2. Parse JSON
            try:
                data = json.loads(json_content_str)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse JSON for {key}: {json_content_str[:100]}...")
                data = {}

            # 3. Format to Markdown
            formatted_content = formatter_fn(data)
            
            results[key] = formatted_content
            
            if tracker:
                 await tracker.add_step_detail('analysis', 'insight', f"Completed {key}", {'type': key})

        # Summary - this one returns Markdown directly
        if tracker:
            await tracker.update_step_message('analysis', "Generating Executive Summary...")
            
        # We need to serialize results back to string for the summary prompt, 
        # but the summary prompt expects the INSIGHTS (which were JSON). 
        # Passing the Markdown is arguably BETTER for the summary AI to read anyway.
        all_insights = str(results) 
        
        summary = await self._call_ai(self.prompts.executive_summary(all_insights), json_mode=False)
        results['executive_summary'] = summary
        
        return results
