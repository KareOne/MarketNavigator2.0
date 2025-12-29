"""
Crunchbase Analysis Prompts - Ported from MVP.
Contains the exact AI prompts for 13-step analysis pipeline.
"""
import json
from typing import List, Dict, Any, Optional


class CrunchbasePromptTemplates:
    """Container for all prompt templates used in the Crunchbase analysis pipeline."""
    
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

All analysis should be contextualized to how these companies relate to and overlap with this target market focus.

"""
        return ""
    
    # =========================================================================
    # STEP 1: Company Overview
    # =========================================================================
    
    def generate_company_overview(self, companies: List[Dict[str, Any]]) -> str:
        """
        Generate prompt for company overview (Step 1).
        
        Persona: Neutral analyst
        Purpose: Create a quick, high-level summary of the top companies.
        """
        company_data_for_prompt = [
            {
                "company_name": c.get("Company Name", c.get("name", "Unknown")),
                "data": c
            }
            for c in companies
        ]
        
        company_count_context = f"This analysis covers {len(companies)} companies.\n\n"
        target_context = self._get_target_market_context()
        
        return f"""{company_count_context}{target_context}Analyze the following data for the top companies. For each company:
1. Provide its name
2. A concise, one-sentence summary of its business
3. How it relates to and overlaps with the user's target market

Format the output as a Markdown bulleted list. Do not add any introductory text, titles, or concluding remarks. Just the list.

Data:
{json.dumps(company_data_for_prompt, indent=2)}"""
    
    # =========================================================================
    # STEP 2: Technology & Product Analysis (Per Company)
    # =========================================================================
    
    def generate_tech_product_report(self, company: Dict[str, Any]) -> str:
        """
        Generate prompt for Technology & Product Analysis (Individual Company).
        
        Persona: Seasoned Chief Technology Officer (CTO)
        Focus: Product viability and technical foundation
        """
        target_context = self._get_target_market_context()
        company_name = company.get("Company Name", company.get("name", "Unknown"))
        
        return f"""You are a seasoned Chief Technology Officer (CTO) evaluating the company for a potential acquisition. You care about product viability and technical foundation, not marketing fluff. Your tone is direct, technical, and focused on engineering excellence.
Analyze the technology and product aspects of the following company based on the provided data. Your analysis should be a deep-dive, providing a comprehensive report focusing ONLY on technology and product metrics.
{target_context}
STRUCTURE REQUIREMENT:
The report must follow this exact section order:

## Overview
## Market Relevance
## Technology & Product Metrics
## Key Technical Strengths
## Key Technical Weaknesses
## Final Verdict

All sections must appear even when data is missing. If data is unavailable for a section, explicitly say so.

**METRICS RESTRICTION:** This section focuses ONLY on technology and product metrics. Analyze: About/description, Industry Tags, Active Tech Count, Tech Details summary, Total Products Active. DO NOT analyze funding, growth scores, or web traffic here - those belong in other sections.

Always specify which exact field is missing (e.g., 'Monthly Visits', 'Total Funding Amount', 'Investors Table', 'Employee Profiles count', 'Tech Details summary') rather than just writing "N/A" multiple times without context.

Do not mention the data is limited or that you are using proxies. Present your analysis with conviction.
Output the entire report in Markdown format, using headings and bullet points for clarity.

Company: {company_name}
Data:
{json.dumps(company, indent=2)}"""
    
    # =========================================================================
    # STEP 3: Market Demand & Web Insights (Per Company)
    # =========================================================================
    
    def generate_market_demand_report(self, company: Dict[str, Any]) -> str:
        """
        Generate prompt for Market Demand & Web Insights (Individual Company).
        
        Persona: Data-driven Market Research Analyst
        Focus: Market traction and demand quantification
        """
        target_context = self._get_target_market_context()
        company_name = company.get("Company Name", company.get("name", "Unknown"))
        
        return f"""You are a data-driven Market Research Analyst. Your focus is quantifying market traction and demand. You are allergic to vague statements and demand precision in your metrics.
Analyze the market demand and web insights of the following company based on the provided data. Your analysis should be a deep-dive, providing a comprehensive report focusing ONLY on market demand and web traffic metrics.
{target_context}
STRUCTURE REQUIREMENT:
The report must follow this exact section order:

## Overview
## Market Relevance
## Market Demand & Web Metrics
## Key Demand Strengths
## Key Demand Weaknesses
## Final Verdict

All sections must appear even when data is missing. If data is unavailable for a section, explicitly say so.

**METRICS RESTRICTION:** This section focuses ONLY on market demand and web traffic metrics. Analyze: Monthly Visits, Monthly Visits Growth, Global Traffic Rank, Monthly Rank Growth, Bounce Rate, Bounce Rate Growth, Page Views / Visit, Page Views / Visit Growth, Visit Duration, Visit Duration Growth. DO NOT analyze funding, growth scores, or technology metrics here - those belong in other sections.

Always specify which exact field is missing (e.g., 'Monthly Visits', 'Total Funding Amount', 'Investors Table', 'Employee Profiles count', 'Tech Details summary') rather than just writing "N/A" multiple times without context.

Do not mention the data is limited or that you are using proxies. Present your analysis with conviction.
Output the entire report in Markdown format, using headings and bullet points for clarity.

Company: {company_name}
Data:
{json.dumps(company, indent=2)}"""
    
    # =========================================================================
    # STEP 4: Competitor Identification (Per Company)
    # =========================================================================
    
    def generate_competitor_report(self, company: Dict[str, Any]) -> str:
        """
        Generate prompt for Competitor Identification (Individual Company).
        
        Persona: Ruthless Competitive Intelligence Strategist
        Focus: Mapping the competitive battlefield
        """
        target_context = self._get_target_market_context()
        company_name = company.get("Company Name", company.get("name", "Unknown"))
        
        return f"""You are a ruthless Competitive Intelligence Strategist from a top-tier firm. Your job is to map the battlefield and identify threats. No sugar-coating. Your analysis cuts through the noise to reveal the true competitive landscape.
Analyze the competitive positioning of the following company based on the provided data. Your analysis should be a deep-dive, providing a comprehensive report focusing ONLY on competitive intelligence and positioning metrics.
{target_context}
STRUCTURE REQUIREMENT:
The report must follow this exact section order:

## Overview
## Market Relevance
## Competitive Metrics & Positioning
## Key Competitive Strengths
## Key Competitive Weaknesses
## Final Verdict

All sections must appear even when data is missing. If data is unavailable for a section, explicitly say so.

**METRICS RESTRICTION:** This section focuses ONLY on competitive intelligence metrics. Analyze: Growth Score, Growth Score update date, Growth Prediction, Growth Prediction update date, IPO Prediction, Acquisition Prediction. DO NOT analyze funding, web traffic, or technology metrics here - those belong in other sections.

Always specify which exact field is missing (e.g., 'Monthly Visits', 'Total Funding Amount', 'Investors Table', 'Employee Profiles count', 'Tech Details summary') rather than just writing "N/A" multiple times without context.

Do not mention the data is limited or that you are using proxies. Present your analysis with conviction.
Output the entire report in Markdown format, using headings and bullet points for clarity.

Company: {company_name}
Data:
{json.dumps(company, indent=2)}"""
    
    # =========================================================================
    # STEP 5: Market & Funding Insights (Per Company)
    # =========================================================================
    
    def generate_market_funding_report(self, company: Dict[str, Any]) -> str:
        """
        Generate prompt for Market & Funding Insights (Individual Company).
        
        Persona: Sharp, skeptical Venture Capital Analyst
        Focus: Financial soundness and capital efficiency
        """
        target_context = self._get_target_market_context()
        company_name = company.get("Company Name", company.get("name", "Unknown"))
        
        return f"""You are a sharp, skeptical Venture Capital Analyst. You're looking for signs of a financially sound, high-growth business. Every dollar must be justified. Your analysis is forward-looking and focused on capital efficiency and market positioning.
Analyze the market and funding insights of the following company based on the provided data. Your analysis should be a deep-dive, providing a comprehensive report focusing ONLY on market positioning and funding metrics.
{target_context}
STRUCTURE REQUIREMENT:
The report must follow this exact section order:

## Overview
## Market Relevance
## Market & Funding Metrics
## Key Market Strengths
## Key Market Weaknesses
## Final Verdict

All sections must appear even when data is missing. If data is unavailable for a section, explicitly say so.

**METRICS RESTRICTION:** This section focuses ONLY on market positioning and funding metrics. Analyze: Total Funding Amount, Number of Funding Rounds, Number of Investors, Number of Lead Investors, Investors Table, Funding Table, Funding Prediction. DO NOT analyze growth scores, web traffic, or technology metrics here - those belong in other sections.

Always specify which exact field is missing (e.g., 'Monthly Visits', 'Total Funding Amount', 'Investors Table', 'Employee Profiles count', 'Tech Details summary') rather than just writing "N/A" multiple times without context.

Do not mention the data is limited or that you are using proxies. Present your analysis with conviction.
Output the entire report in Markdown format, using headings and bullet points for clarity.

Company: {company_name}
Data:
{json.dumps(company, indent=2)}"""
    
    # =========================================================================
    # STEP 6: Growth Potential (Per Company)
    # =========================================================================
    
    def generate_growth_potential_report(self, company: Dict[str, Any]) -> str:
        """
        Generate prompt for Growth Potential (Individual Company).
        
        Persona: Discerning Growth Equity Investor
        Focus: Scalable growth signals and competitive differentiation
        """
        target_context = self._get_target_market_context()
        company_name = company.get("Company Name", company.get("name", "Unknown"))
        
        return f"""You are a discerning Growth Equity Investor looking for the next unicorn. You are focused on scalable growth signals and competitive differentiation. Your analysis identifies true growth potential versus hype.
Analyze the growth potential of the following company based on the provided data. Your analysis should be a deep-dive, providing a comprehensive report focusing ONLY on growth and expansion metrics.
{target_context}
STRUCTURE REQUIREMENT:
The report must follow this exact section order:

## Overview
## Market Relevance
## Growth & Expansion Metrics
## Key Growth Strengths
## Key Growth Weaknesses
## Final Verdict

All sections must appear even when data is missing. If data is unavailable for a section, explicitly say so.

**METRICS RESTRICTION:** This section focuses ONLY on growth and expansion metrics. Analyze: Headcount, Employee Profiles count, Contacts count, Current Employees Table, Growth Insight. DO NOT analyze funding, web traffic, or technology metrics here - those belong in other sections.

Always specify which exact field is missing (e.g., 'Monthly Visits', 'Total Funding Amount', 'Investors Table', 'Employee Profiles count', 'Tech Details summary') rather than just writing "N/A" multiple times without context.

Do not mention the data is limited or that you are using proxies. Present your analysis with conviction.
Output the entire report in Markdown format, using headings and bullet points for clarity.

Company: {company_name}
Data:
{json.dumps(company, indent=2)}"""
    
    # =========================================================================
    # STEP 7: SWOT Analysis (Per Company)
    # =========================================================================
    
    def generate_swot_report(self, company: Dict[str, Any]) -> str:
        """
        Generate prompt for SWOT Analysis (Individual Company).
        
        Persona: Senior partner at top-tier consulting firm
        Focus: Strategic analysis for investors and executives
        """
        target_context = self._get_target_market_context()
        company_name = company.get("Company Name", company.get("name", "Unknown"))
        
        return f"""You are a senior partner at a top-tier consulting firm, specializing in strategic analysis. Your SWOT is a weapon for investors and executives. Be direct, concise, and focus on high-impact factors.
Conduct a comprehensive SWOT analysis for the following company based on the provided data. Your analysis should synthesize insights from all available metrics to provide a balanced strategic assessment.
{target_context}
STRUCTURE REQUIREMENT:
The report must follow this exact section order:

## Overview
## Market Relevance
## Strengths
## Weaknesses
## Opportunities
## Threats
## Final Strategic Verdict

All sections must appear even when data is missing. If data is unavailable for a section, explicitly say so.

Always specify which exact field is missing (e.g., 'Monthly Visits', 'Total Funding Amount', 'Investors Table', 'Employee Profiles count', 'Tech Details summary') rather than just writing "N/A" multiple times without context.

Do not mention the data is limited or that you are using proxies. Present your analysis with conviction.
Output the entire report in Markdown format, using headings and bullet points for clarity.

Company: {company_name}
Data:
{json.dumps(company, indent=2)}"""
    
    # =========================================================================
    # STEP 8: Technology & Product Summary
    # =========================================================================
    
    def generate_tech_product_summary(self, reports: List[str], sample_size: int) -> str:
        """Generate executive summary for Technology & Product category."""
        target_context = self._get_target_market_context()
        reports_text = "\n\n---\n\n".join([f"Report {i+1}:\n{report}" for i, report in enumerate(reports)])
        
        return f"""You are a senior partner at a top-tier consulting firm, synthesizing field reports into a high-level executive summary for a board of directors. Your summary must be strategic, insightful, and concise.
{target_context}Based ONLY on the following individual company reports, generate a cohesive summary for Technology & Product Analysis.
Your task is to identify sample-based trends, patterns, common strengths or weaknesses, and significant outliers based strictly on the companies included in these reports.

IMPORTANT: This analysis covers {sample_size} companies. Mention this sample size ONCE at the beginning of your summary, then refer to it simply as "the sample" or "these companies" throughout. DO NOT repeat "N={sample_size}" or "sample of {sample_size} companies" in every sentence or heading.

Always clarify that these insights reflect only the analyzed sample, not the entire market.
Do not extrapolate beyond the provided data or reference total market size unless explicitly provided in the reports.

**Individual Company Reports:**
{reports_text}

---
**Your Executive Summary for Technology & Product Analysis:**
(Output in Markdown format)"""
    
    # =========================================================================
    # STEP 9: Market Demand Summary
    # =========================================================================
    
    def generate_market_demand_summary(self, reports: List[str], sample_size: int) -> str:
        """Generate executive summary for Market Demand & Web Insights category."""
        target_context = self._get_target_market_context()
        reports_text = "\n\n---\n\n".join([f"Report {i+1}:\n{report}" for i, report in enumerate(reports)])
        
        return f"""You are a senior partner at a top-tier consulting firm, synthesizing field reports into a high-level executive summary for a board of directors. Your summary must be strategic, insightful, and concise.
{target_context}Based ONLY on the following individual company reports, generate a cohesive summary for Market Demand & Web Insights.
Your task is to identify sample-based trends, patterns, common strengths or weaknesses, and significant outliers based strictly on the companies included in these reports.

IMPORTANT: This analysis covers {sample_size} companies. Mention this sample size ONCE at the beginning of your summary, then refer to it simply as "the sample" or "these companies" throughout. DO NOT repeat "N={sample_size}" or "sample of {sample_size} companies" in every sentence or heading.

Always clarify that these insights reflect only the analyzed sample, not the entire market.
Do not extrapolate beyond the provided data or reference total market size unless explicitly provided in the reports.

**Individual Company Reports:**
{reports_text}

---
**Your Executive Summary for Market Demand & Web Insights:**
(Output in Markdown format)"""
    
    # =========================================================================
    # STEP 10: Competitor Summary
    # =========================================================================
    
    def generate_competitor_summary(self, reports: List[str], sample_size: int) -> str:
        """Generate executive summary for Competitor Identification category."""
        target_context = self._get_target_market_context()
        reports_text = "\n\n---\n\n".join([f"Report {i+1}:\n{report}" for i, report in enumerate(reports)])
        
        return f"""You are a senior partner at a top-tier consulting firm, synthesizing field reports into a high-level executive summary for a board of directors. Your summary must be strategic, insightful, and concise.
{target_context}Based ONLY on the following individual company reports, generate a cohesive summary for Competitor Identification.
Your task is to identify sample-based trends, patterns, common strengths or weaknesses, and significant outliers based strictly on the companies included in these reports.

IMPORTANT: This analysis covers {sample_size} companies. Mention this sample size ONCE at the beginning of your summary, then refer to it simply as "the sample" or "these companies" throughout. DO NOT repeat "N={sample_size}" or "sample of {sample_size} companies" in every sentence or heading.

Always clarify that these insights reflect only the analyzed sample, not the entire market.
Do not extrapolate beyond the provided data or reference total market size unless explicitly provided in the reports.

**Individual Company Reports:**
{reports_text}

---
**Your Executive Summary for Competitor Identification:**
(Output in Markdown format)"""
    
    # =========================================================================
    # STEP 11: Market & Funding Summary
    # =========================================================================
    
    def generate_market_funding_summary(self, reports: List[str], sample_size: int) -> str:
        """Generate executive summary for Market & Funding Insights category."""
        target_context = self._get_target_market_context()
        reports_text = "\n\n---\n\n".join([f"Report {i+1}:\n{report}" for i, report in enumerate(reports)])
        
        return f"""You are a senior partner at a top-tier consulting firm, synthesizing field reports into a high-level executive summary for a board of directors. Your summary must be strategic, insightful, and concise.
{target_context}Based ONLY on the following individual company reports, generate a cohesive summary for Market & Funding Insights.
Your task is to identify sample-based trends, patterns, common strengths or weaknesses, and significant outliers based strictly on the companies included in these reports.

IMPORTANT: This analysis covers {sample_size} companies. Mention this sample size ONCE at the beginning of your summary, then refer to it simply as "the sample" or "these companies" throughout. DO NOT repeat "N={sample_size}" or "sample of {sample_size} companies" in every sentence or heading.

Always clarify that these insights reflect only the analyzed sample, not the entire market.
Do not extrapolate beyond the provided data or reference total market size unless explicitly provided in the reports.

**Individual Company Reports:**
{reports_text}

---
**Your Executive Summary for Market & Funding Insights:**
(Output in Markdown format)"""
    
    # =========================================================================
    # STEP 12: Growth Potential Summary
    # =========================================================================
    
    def generate_growth_potential_summary(self, reports: List[str], sample_size: int) -> str:
        """Generate executive summary for Growth Potential category."""
        target_context = self._get_target_market_context()
        reports_text = "\n\n---\n\n".join([f"Report {i+1}:\n{report}" for i, report in enumerate(reports)])
        
        return f"""You are a senior partner at a top-tier consulting firm, synthesizing field reports into a high-level executive summary for a board of directors. Your summary must be strategic, insightful, and concise.
{target_context}Based ONLY on the following individual company reports, generate a cohesive summary for Growth Potential.
Your task is to identify sample-based trends, patterns, common strengths or weaknesses, and significant outliers based strictly on the companies included in these reports.

IMPORTANT: This analysis covers {sample_size} companies. Mention this sample size ONCE at the beginning of your summary, then refer to it simply as "the sample" or "these companies" throughout. DO NOT repeat "N={sample_size}" or "sample of {sample_size} companies" in every sentence or heading.

Always clarify that these insights reflect only the analyzed sample, not the entire market.
Do not extrapolate beyond the provided data or reference total market size unless explicitly provided in the reports.

**Individual Company Reports:**
{reports_text}

---
**Your Executive Summary for Growth Potential:**
(Output in Markdown format)"""
    
    # =========================================================================
    # STEP 13: SWOT Summary
    # =========================================================================
    
    def generate_swot_summary(self, reports: List[str], sample_size: int) -> str:
        """Generate executive summary for SWOT Analysis category."""
        target_context = self._get_target_market_context()
        reports_text = "\n\n---\n\n".join([f"Report {i+1}:\n{report}" for i, report in enumerate(reports)])
        
        return f"""You are a senior partner at a top-tier consulting firm, synthesizing field reports into a high-level executive summary for a board of directors. Your summary must be strategic, insightful, and concise.
{target_context}Based ONLY on the following individual company reports, generate a cohesive summary for SWOT Analysis.
Your task is to identify sample-based trends, patterns, common strengths or weaknesses, and significant outliers based strictly on the companies included in these reports.

IMPORTANT: This analysis covers {sample_size} companies. Mention this sample size ONCE at the beginning of your summary, then refer to it simply as "the sample" or "these companies" throughout. DO NOT repeat "N={sample_size}" or "sample of {sample_size} companies" in every sentence or heading.

Always clarify that these insights reflect only the analyzed sample, not the entire market.
Do not extrapolate beyond the provided data or reference total market size unless explicitly provided in the reports.

**Individual Company Reports:**
{reports_text}

---
**Your Executive Summary for SWOT Analysis:**
(Output in Markdown format)"""
