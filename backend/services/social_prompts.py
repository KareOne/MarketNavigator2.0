"""
Prompt templates for Social media analysis pipeline.
Based on README.md specifications with strict <ref> tag usage and grounding rules.
"""

import json
from typing import Dict, Any, List, Union


class PromptTemplates:
    """Container for all prompt templates used in the social analysis pipeline."""
    
    # Social analysis category objectives
    SOCIAL_CATEGORY_OBJECTIVES = {
        "Market Segmentation & Needs Analysis": "Identify distinct audience groups, behaviors, and needs surfaced in the posts. Prioritize evidence from reactions, comments, and repeated themes.",
        "Jobs To Be Done (JTBD) Mapping": "Extract functional, emotional, and social jobs that users are trying to accomplish. Focus on verbs and outcome statements.",
        "Pain Points & Friction": "Catalog explicit complaints, workarounds, or frustrations. Include both product-level and workflow-level friction.",
        "Feature & Product Demand Signals": "Identify requests, wishlists, or praise for specific features or integrations. Distinguish between current gaps and future desires.",
        "Willingness to Pay (WTP) & Pricing": "Extract explicit pricing or WTP cues; never invent pricing where none exists.",
        "Competitive Landscape & Alternatives": "Map mentions of competitor tools, switching behavior, and comparison discussions.",
        "Adoption Triggers & Conversion Moments": "Identify moments when users decided to adopt, upgrade, or abandon a tool.",
        "User Roles & Organizational Context": "Detect personas, job titles, team structures, and organizational dynamics.",
        "Use Cases & Application Scenarios": "Describe real-world workflows, integrations, and problem-solving scenarios.",
        "Sentiment & Brand Perception": "Measure tone, trust signals, and brand associations across the sample."
    }
    
    def __init__(self, target_market_description: str = None):
        """
        Initialize prompt templates with optional target market context.
        
        Args:
            target_market_description: Description of the target market for contextual analysis
        """
        self.target_market_description = target_market_description
    
    def _get_target_market_context(self) -> str:
        """Get formatted target market context for prompts."""
        if self.target_market_description:
            return f"""TARGET MARKET CONTEXT:
The user is interested in: {self.target_market_description}

All analysis should be contextualized to how these social signals relate to this target market focus.

"""
        return ""
    
    def generate_category_report(
        self, 
        category: str, 
        data: Union[List[Dict[str, Any]], Dict[str, Any]], 
        source: str
    ) -> str:
        """
        Generate prompt for one of the 10 social analysis categories.
        
        Args:
            category: One of the 10 category names
            data: Twitter posts or LinkedIn keyword posts data
            source: "twitter" or "linkedin"
        
        Returns:
            Formatted prompt string
        """
        source_label = "LinkedIn posts" if source == "linkedin" else "Twitter/X posts"
        target_context = self._get_target_market_context()
        
        if category not in self.SOCIAL_CATEGORY_OBJECTIVES:
            raise ValueError(f"Invalid category: {category}")
        
        objective = self.SOCIAL_CATEGORY_OBJECTIVES[category]
        
        return f"""You are a customer insights lead analyzing {source_label} for reliable market signals. Use ONLY the JSON provided below.

{target_context}ANALYSIS GUIDELINES:
- Never invent geographies, prices, user roles, or needs that are not explicitly present.
- Stay strictly grounded in the data provided.

STRUCTURE:
- Focus on: {objective}
- Provide 3-6 concise bullets with clear insights.
- Tone: analytical, executive-ready, grounded strictly in the provided text and counts.

DATASET SNAPSHOT:
{json.dumps(data, indent=2, ensure_ascii=False)}

---
{category} (Markdown only):
"""
    
    def generate_cross_cutting_insights(
        self, 
        data: Union[List[Dict[str, Any]], Dict[str, Any]], 
        source: str
    ) -> str:
        """
        Generate prompt for cross-cutting insights (10 numbered items).
        
        Args:
            data: Twitter posts or LinkedIn keyword posts data
            source: "twitter" or "linkedin"
        
        Returns:
            Formatted prompt string
        """
        source_label = "LinkedIn posts" if source == "linkedin" else "Twitter/X posts"
        target_context = self._get_target_market_context()
        
        return f"""You are a pattern-spotting analyst distilling {source_label}.
Produce EXACTLY 10 numbered insights (1-10). Each insight must be 1-2 sentences.
- If you cannot find evidence for an insight, write "No evidence in dataset".
- Do not repeat the same finding; make them cross-cutting, contrarian, or surprising where the data allows.
{target_context}Stay strictly grounded in the JSON below - no hallucinated names, prices, or trends.

DATASET SNAPSHOT:
{json.dumps(data, indent=2, ensure_ascii=False)}

---
Cross-cutting insights (Markdown, numbered 1-10):
"""
    
    @staticmethod
    def get_all_categories() -> List[str]:
        """Get list of all 10 analysis categories."""
        return [
            "Market Segmentation & Needs Analysis",
            "Jobs To Be Done (JTBD) Mapping",
            "Pain Points & Friction",
            "Feature & Product Demand Signals",
            "Willingness to Pay (WTP) & Pricing",
            "Competitive Landscape & Alternatives",
            "Adoption Triggers & Conversion Moments",
            "User Roles & Organizational Context",
            "Use Cases & Application Scenarios",
            "Sentiment & Brand Perception"
        ]
