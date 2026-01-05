"""
Tracxn Analysis Prompt Templates.
Ported from MCP Server tracxn_flow/prompts.py for high-scale platform.

Per FINAL_ARCHITECTURE_SPECIFICATION.md - Panel 2: Tracxn Analysis.
Provides prompt templates for:
- Competitor Identification Reports
- Market & Funding Insights Reports  
- Growth Potential Reports
- Category Summaries
"""

import json
from typing import List, Dict, Any


class TracxnPromptTemplates:
    """Container for all prompt templates used in the Tracxn analysis pipeline."""
    
    # Base prompt template (NO reference instructions, with Analytics Note)
    BASE_PROMPT_TEMPLATE = """You are a top-tier market intelligence analyst. Your analysis is sharp, data-driven, and brutally honest, designed for a high-stakes executive audience.
Analyze the provided Tracxn JSON data for the company and generate a professional report for the specified section.
Your entire analysis MUST be grounded exclusively in the data provided. Do not invent information or make assumptions beyond what the data supports.
{target_market_context}
STRUCTURE REQUIREMENT:
The report must follow this exact section order:

## Overview
## Market Relevance
## Metrics and Rankings
## Key Strengths
## Key Weaknesses
## Final Verdict

All sections must appear even when data is missing. If data is unavailable for a section, explicitly say so.

Always specify which exact field is missing rather than just writing "N/A".

Add a closing sentence labeled **Analytics Note** explicitly stating that Diagnostic analytics and Prescriptive analytics have been performed to arrive at these conclusions.

Output the entire report in Markdown format. Do not add a title or heading, just the analysis content itself.

**Company Data (JSON):**
{company_data}

---

**Your Analysis Section:**
{category_instructions}"""
    
    # Summary prompts (with Analytics Note and sample size support)
    SUMMARY_BASE_TEMPLATE = """You are a senior partner at a top-tier consulting firm, synthesizing field reports into a high-level executive summary for a board of directors. Your summary must be strategic, insightful, and concise.
{target_market_context}Based ONLY on the following individual company reports, generate a cohesive summary for the specified category.
Your task is to identify sample-based trends, patterns, common strengths or weaknesses, and significant outliers based strictly on the companies included in these reports.

IMPORTANT: This analysis covers {sample_size} companies. Mention this sample size ONCE at the beginning of your summary, then refer to it simply as "the sample" or "these companies" throughout. Do NOT repeat "N={sample_size}" in every sentence or heading.

Always clarify that these insights reflect only the analyzed sample, not the entire market.
Do not extrapolate beyond the provided data or reference total market size unless explicitly provided in the JSON.

Add a final **Analytics Note** sentence explicitly stating that Diagnostic analytics and Prescriptive analytics have been performed to arrive at these conclusions.

**Individual Company Reports:**
{reports_text}

---

**Your Summary for: {category_name}**"""
    
    @staticmethod
    def _format_company_data(company: Dict[str, Any]) -> str:
        """Format company data as JSON string for prompt."""
        return json.dumps(company, indent=2, ensure_ascii=False, default=str)
    
    @staticmethod
    def generate_competitor_report(company: Dict[str, Any], target_market_context: str = "") -> str:
        """
        Generate prompt for competitor identification analysis.
        
        Persona: Ruthless Competitive Intelligence Strategist
        Purpose: Map the competitive battlefield and identify threats.
        """
        formatted_context = ""
        if target_market_context:
            formatted_context = f"**TARGET MARKET CONTEXT:** {target_market_context}\n\n"
        
        category_instructions = """**Persona: A ruthless Competitive Intelligence Strategist from a top-tier firm. Your job is to map the battlefield and identify threats. No sugar-coating.**

**IMPORTANT: Before listing competitors or metrics, provide a brief qualitative explanation of how each competitor's product or domain overlaps with the user's target market focus. This qualitative relevance must appear before any rankings, metrics, or funding comparisons. If overlap is weak or indirect, explicitly state so.**

**CRITICAL: Do not reference or estimate total competitor counts unless they appear directly in the JSON. Never extrapolate beyond the provided data.**

- Analyze the `competitor_summary` and `competitor_list` sections if present.
- Identify the company's rank among its competitors.
- Detail the top 3-5 competitors listed. For each, provide their name, funding stage, and a concise summary of their business from the 'description' field.
- Deliver a direct, no-nonsense verdict on the company's current standing. Based on the data, is it a market leader, a strong contender, or an irrelevant laggard?"""
        
        return TracxnPromptTemplates.BASE_PROMPT_TEMPLATE.format(
            target_market_context=formatted_context,
            company_data=TracxnPromptTemplates._format_company_data(company),
            category_instructions=category_instructions
        )
    
    @staticmethod
    def generate_market_funding_report(company: Dict[str, Any], target_market_context: str = "") -> str:
        """
        Generate prompt for market & funding insights analysis.
        
        Persona: Sharp, skeptical Venture Capital Analyst
        Purpose: Assess financial viability and funding health.
        """
        formatted_context = ""
        if target_market_context:
            formatted_context = f"**TARGET MARKET CONTEXT:** {target_market_context}\n\n"
        
        category_instructions = """**Persona: A sharp, skeptical Venture Capital Analyst. You're looking for signs of a financially sound, high-growth business. Every dollar must be justified.**
- Scrutinize the funding details, total equity funding, and investor information.
- State the Total Equity Funding and Latest Funding Round if available.
- If a valuation is present, state it clearly.
- List any named investors. If none, state that funding has not been raised.
- Assess the company's financial viability based on the numbers. Is it well-capitalized or running on fumes? What do the funding benchmarks suggest for its next capital raise?"""
        
        return TracxnPromptTemplates.BASE_PROMPT_TEMPLATE.format(
            target_market_context=formatted_context,
            company_data=TracxnPromptTemplates._format_company_data(company),
            category_instructions=category_instructions
        )
    
    @staticmethod
    def generate_growth_potential_report(company: Dict[str, Any], target_market_context: str = "") -> str:
        """
        Generate prompt for growth potential analysis.
        
        Persona: Discerning Growth Equity Investor
        Purpose: Identify scalable growth signals and competitive differentiation.
        """
        formatted_context = ""
        if target_market_context:
            formatted_context = f"**TARGET MARKET CONTEXT:** {target_market_context}\n\n"
        
        category_instructions = """**Persona: A discerning Growth Equity Investor looking for the next unicorn. You are focused on scalable growth signals and competitive differentiation.**

- Focus on employee count, growth indicators, and any ranking data available.
- Analyze the employee headcount and growth trend if data is available.
- State the company's Growth Rank or scoring if present and what it implies.
- Based on growth indicators and any employee data, deliver a final, data-backed verdict on the company's growth potential. Is it poised for significant scaling, or are there clear red flags?"""
        
        return TracxnPromptTemplates.BASE_PROMPT_TEMPLATE.format(
            target_market_context=formatted_context,
            company_data=TracxnPromptTemplates._format_company_data(company),
            category_instructions=category_instructions
        )
    
    @staticmethod
    def generate_competitor_summary(reports: List[str], sample_size: int, target_market_context: str = "") -> str:
        """Generate prompt for competitor identification summary."""
        reports_text = "\n\n---\n\n".join([
            f"Report {i+1}:\n{report}"
            for i, report in enumerate(reports)
        ])
        
        formatted_context = ""
        if target_market_context:
            formatted_context = f"**TARGET MARKET CONTEXT:** {target_market_context}\n\n"
        
        return TracxnPromptTemplates.SUMMARY_BASE_TEMPLATE.format(
            target_market_context=formatted_context,
            sample_size=sample_size,
            reports_text=reports_text,
            category_name="Competitive Landscape Summary"
        )
    
    @staticmethod
    def generate_market_funding_summary(reports: List[str], sample_size: int, target_market_context: str = "") -> str:
        """Generate prompt for market & funding summary."""
        reports_text = "\n\n---\n\n".join([
            f"Report {i+1}:\n{report}"
            for i, report in enumerate(reports)
        ])
        
        formatted_context = ""
        if target_market_context:
            formatted_context = f"**TARGET MARKET CONTEXT:** {target_market_context}\n\n"
        
        return TracxnPromptTemplates.SUMMARY_BASE_TEMPLATE.format(
            target_market_context=formatted_context,
            sample_size=sample_size,
            reports_text=reports_text,
            category_name="Market & Funding Insights Summary"
        )
    
    @staticmethod
    def generate_growth_potential_summary(reports: List[str], sample_size: int, target_market_context: str = "") -> str:
        """Generate prompt for growth potential summary."""
        reports_text = "\n\n---\n\n".join([
            f"Report {i+1}:\n{report}"
            for i, report in enumerate(reports)
        ])
        
        formatted_context = ""
        if target_market_context:
            formatted_context = f"**TARGET MARKET CONTEXT:** {target_market_context}\n\n"
        
        return TracxnPromptTemplates.SUMMARY_BASE_TEMPLATE.format(
            target_market_context=formatted_context,
            sample_size=sample_size,
            reports_text=reports_text,
            category_name="Growth Potential Summary"
        )
    
    # ========== New Analysis Types for 13-Step Pipeline ==========
    
    @staticmethod
    def generate_company_overview(company: Dict[str, Any], target_market_context: str = "") -> str:
        """
        Generate prompt for company overview analysis.
        
        Persona: Strategic Business Analyst
        Purpose: Provide a snapshot of the startup's core business and market positioning.
        """
        formatted_context = ""
        if target_market_context:
            formatted_context = f"**TARGET MARKET CONTEXT:** {target_market_context}\n\n"
        
        category_instructions = """**Persona: A strategic Business Analyst providing a high-level executive snapshot.**

- Summarize the company's core business in 2-3 sentences based on the 'Overview' or 'description' field.
- Identify the primary sector(s) and market(s) the company operates in.
- State the company's founding year, headquarters location, and current stage (if available).
- Highlight the company's key value proposition and target customer segment.
- Provide a quick assessment of the company's market relevance and positioning within its sector."""
        
        return TracxnPromptTemplates.BASE_PROMPT_TEMPLATE.format(
            target_market_context=formatted_context,
            company_data=TracxnPromptTemplates._format_company_data(company),
            category_instructions=category_instructions
        )
    
    @staticmethod
    def generate_tech_product_report(company: Dict[str, Any], target_market_context: str = "") -> str:
        """
        Generate prompt for technology & product analysis.
        
        Persona: Technical Due Diligence Expert
        Purpose: Assess technology stack, product capabilities, and technical moat.
        """
        formatted_context = ""
        if target_market_context:
            formatted_context = f"**TARGET MARKET CONTEXT:** {target_market_context}\n\n"
        
        category_instructions = """**Persona: A Technical Due Diligence Expert evaluating the company's technology and product.**

- Analyze any technology or product information available in the company data.
- Identify the core product or service offering described in the overview.
- Look for technology keywords (AI, ML, Cloud, SaaS, etc.) in the description or sectors.
- Assess the technical sophistication based on available information.
- Identify any platform capabilities, integrations, or technical differentiators mentioned.
- If the company is in a tech-heavy sector, comment on likely technical requirements.
- Provide a verdict on the company's product maturity and technical positioning."""
        
        return TracxnPromptTemplates.BASE_PROMPT_TEMPLATE.format(
            target_market_context=formatted_context,
            company_data=TracxnPromptTemplates._format_company_data(company),
            category_instructions=category_instructions
        )
    
    @staticmethod
    def generate_market_demand_report(company: Dict[str, Any], target_market_context: str = "") -> str:
        """
        Generate prompt for market demand & traction analysis.
        
        Persona: Market Research Analyst
        Purpose: Assess market demand signals and company traction.
        """
        formatted_context = ""
        if target_market_context:
            formatted_context = f"**TARGET MARKET CONTEXT:** {target_market_context}\n\n"
        
        category_instructions = """**Persona: A Market Research Analyst assessing demand signals and company traction.**

- Analyze any indicators of market demand or traction from the company data.
- Look at employee count growth as a proxy for business growth.
- Examine the company's ranking scores (Tracxn score, growth rank) as market signals.
- Identify the company's target market size based on its sector and geography.
- Assess the company's competitive ranking within its sector.
- Comment on any revenue, customer, or traction indicators if available.
- Provide a verdict on the company's market demand and traction status."""
        
        return TracxnPromptTemplates.BASE_PROMPT_TEMPLATE.format(
            target_market_context=formatted_context,
            company_data=TracxnPromptTemplates._format_company_data(company),
            category_instructions=category_instructions
        )
    
    @staticmethod
    def generate_swot_report(company: Dict[str, Any], target_market_context: str = "") -> str:
        """
        Generate prompt for SWOT analysis.
        
        Persona: Strategic Planning Consultant
        Purpose: Comprehensive SWOT assessment for strategic decision-making.
        """
        formatted_context = ""
        if target_market_context:
            formatted_context = f"**TARGET MARKET CONTEXT:** {target_market_context}\n\n"
        
        category_instructions = """**Persona: A Strategic Planning Consultant conducting a comprehensive SWOT analysis.**

**STRUCTURE REQUIREMENT:**
Override the standard section order and use this SWOT-specific structure:

## Strengths
- List 3-5 key internal strengths based on the company data (technology, team, funding, market position).

## Weaknesses
- List 3-5 internal weaknesses or limitations evident from the data (gaps, risks, resource constraints).

## Opportunities
- List 3-5 external opportunities the company could capitalize on based on its sector and market.

## Threats
- List 3-5 external threats or competitive risks the company faces.

## Strategic Implications
- Provide a concise summary of how strengths can address threats and capitalize on opportunities.
- Highlight the most critical weakness that needs addressing.

Base your analysis ONLY on the provided company data. Do not speculate beyond what the data supports."""
        
        return TracxnPromptTemplates.BASE_PROMPT_TEMPLATE.format(
            target_market_context=formatted_context,
            company_data=TracxnPromptTemplates._format_company_data(company),
            category_instructions=category_instructions
        )
    
    # ========== New Summary Methods ==========
    
    @staticmethod
    def generate_company_overview_summary(reports: List[str], sample_size: int, target_market_context: str = "") -> str:
        """Generate prompt for company overview summary."""
        reports_text = "\n\n---\n\n".join([
            f"Report {i+1}:\n{report}"
            for i, report in enumerate(reports)
        ])
        
        formatted_context = ""
        if target_market_context:
            formatted_context = f"**TARGET MARKET CONTEXT:** {target_market_context}\n\n"
        
        return TracxnPromptTemplates.SUMMARY_BASE_TEMPLATE.format(
            target_market_context=formatted_context,
            sample_size=sample_size,
            reports_text=reports_text,
            category_name="Market Overview Summary"
        )
    
    @staticmethod
    def generate_tech_product_summary(reports: List[str], sample_size: int, target_market_context: str = "") -> str:
        """Generate prompt for technology & product summary."""
        reports_text = "\n\n---\n\n".join([
            f"Report {i+1}:\n{report}"
            for i, report in enumerate(reports)
        ])
        
        formatted_context = ""
        if target_market_context:
            formatted_context = f"**TARGET MARKET CONTEXT:** {target_market_context}\n\n"
        
        return TracxnPromptTemplates.SUMMARY_BASE_TEMPLATE.format(
            target_market_context=formatted_context,
            sample_size=sample_size,
            reports_text=reports_text,
            category_name="Technology & Product Landscape Summary"
        )
    
    @staticmethod
    def generate_market_demand_summary(reports: List[str], sample_size: int, target_market_context: str = "") -> str:
        """Generate prompt for market demand summary."""
        reports_text = "\n\n---\n\n".join([
            f"Report {i+1}:\n{report}"
            for i, report in enumerate(reports)
        ])
        
        formatted_context = ""
        if target_market_context:
            formatted_context = f"**TARGET MARKET CONTEXT:** {target_market_context}\n\n"
        
        return TracxnPromptTemplates.SUMMARY_BASE_TEMPLATE.format(
            target_market_context=formatted_context,
            sample_size=sample_size,
            reports_text=reports_text,
            category_name="Market Demand & Traction Summary"
        )
    
    @staticmethod
    def generate_swot_summary(reports: List[str], sample_size: int, target_market_context: str = "") -> str:
        """Generate prompt for SWOT summary across all analyzed companies."""
        reports_text = "\n\n---\n\n".join([
            f"Report {i+1}:\n{report}"
            for i, report in enumerate(reports)
        ])
        
        formatted_context = ""
        if target_market_context:
            formatted_context = f"**TARGET MARKET CONTEXT:** {target_market_context}\n\n"
        
        return TracxnPromptTemplates.SUMMARY_BASE_TEMPLATE.format(
            target_market_context=formatted_context,
            sample_size=sample_size,
            reports_text=reports_text,
            category_name="Strategic SWOT Landscape Summary"
        )

