"""
Tracxn Analysis Prompt Templates - INSTITUTIONAL GRADE.
Refactored for maximum depth, professional rigor, and strict data adherence.

Key Features:
1.  **Deep-Dive Due Diligence:** Comprehensive profiling connecting Funding, Growth, and Tech.
2.  **Anti-Hallucination Protocols:** Strict handling of null metrics ($##) and data anomalies.
3.  **Strategic Synthesis:** Hierarchical reporting (Flash -> Executive -> Comprehensive).
"""

import json
from typing import List, Dict, Any


class TracxnPromptTemplates:
    """
    Container for high-precision analysis prompts. 
    Designed to extract every ounce of value from the JSON while remaining strictly factual.
    """

    @staticmethod
    def _format_company_data(company: Dict[str, Any]) -> str:
        """Format company data as JSON string for prompt."""
        return json.dumps(company, indent=2, ensure_ascii=False, default=str)

    # =========================================================================
    # 1. THE 2-PAGE FLASH ANALYSIS (Outliers, Red Flags & Signal Detection)
    # =========================================================================
    @staticmethod
    def generate_flash_analysis_report(company_reports: List[Dict], executive_summary: str, target_market_context: str = "") -> str:
        """
        Generates a high-velocity 'Red Flag / Green Light' report.
        Focus: Outlier detection, data integrity checks, and immediate market signals.
        This is generated AFTER company deep dives and executive summary to synthesize findings.
        """
        # Format company reports for prompt
        reports_text = "\n\n".join([
            f"### {r['company_name']}\n{r['content'][:2000]}..." if len(r['content']) > 2000 else f"### {r['company_name']}\n{r['content']}"
            for r in company_reports
        ])
        
        return f"""You are a Lead Investment Screener at a top Venture Capital firm. 
Your task is to produce a **2-Page Flash Analysis Report** synthesizing the detailed analysis below.
{target_market_context}

**OBJECTIVE:** 
Identify the highest-potential targets and the highest-risk assets immediately. Cut through the noise. Do not summarize every company. Focus ONLY on outliers and critical signals.

**EXECUTIVE SUMMARY (Already Analyzed):**
{executive_summary[:3000]}

**INDIVIDUAL COMPANY REPORTS:**
{reports_text}

**STRICT ANALYSIS GUIDELINES:**
1.  **No Fluff:** Use bullet points, bold metrics, and concise executive language.
2.  **Data Integrity Check:** Immediately flag anomalies (e.g., Public companies with <50 employees, Unicorns with no funding data).
3.  **Relative Performance:** Compare companies against the cohort average.
4.  **Synthesize:** Pull the most critical insights from the detailed reports above.

**REPORT STRUCTURE (Markdown):**

# ⚡ Market Flash Report: High-Signal Analysis

## 1. The Alpha Cohort (Top 3 Performers)
*Select the 3 strongest companies based on a synthesis of Revenue Scale, Market Share, and Execution Rank.*
*   **[Company Name]**: 
    *   *The Signal:* Why they win (e.g., "Dominant 50% Market Share," "2000% Revenue Growth").
    *   *The Metric:* Cite the specific data point driving this conclusion.

## 2. Critical Red Flags & Anomalies 🚩
*Identify companies with dangerous signals or data inconsistencies that require immediate verification.*
*   **Operational Distress:** Companies with negative employee growth or stale funding (no rounds >3 years).
*   **Data Anomalies:** Logic breaks (e.g., High Revenue but tiny headcount).
*   **Opacity Risks:** Companies hiding critical financial data despite high rankings.

## 3. Undervalued / Sleeper Picks
*Identify 1-2 companies ranked lower (outside top 5) but showing explosive leading indicators (e.g., massive News/Review growth, recent strategic hires).*

## 4. Market Pulse Statistics
*   **Capital Flow:** Which specific sub-sector is attracting the most *recent* capital?
*   **Maturity Index:** What % of this cohort is Public/Acquired vs. Early Stage?

**Analytics Note:** Diagnostic analytics and Prescriptive analytics have been performed to arrive at these conclusions."""

    # =========================================================================
    # 2. THE 5-PAGE EXECUTIVE SUMMARY (Macro-Strategic Synthesis)
    # =========================================================================
    @staticmethod
    def generate_executive_summary(reports: List[str], sample_size: int, target_market_context: str = "") -> str:
        """
        Generates a strategic market overview synthesizing all individual reports.
        Focus: Market maturity, consolidation trends, and capital efficiency.
        """
        # Concatenate summaries carefully to manage context window while retaining key insights
        reports_text = "\n\n".join([f"--- Company Report {i+1} ---\n{report[:4000]}" for i, report in enumerate(reports)])

        return f"""You are a Senior Partner at a Strategy Consulting Firm (e.g., McKinsey, BCG). 
Write a **5-Page Executive Strategic Assessment** of the provided market landscape.
{target_market_context}

**CONTEXT:** This analysis covers a sample of {sample_size} companies.

**INPUT DATA:**
{reports_text}

**TONE & STYLE:** 
Professional, authoritative, forward-looking, and rigorously objective. Avoid generic statements; anchor every insight in the provided company data.

**REPORT STRUCTURE (Markdown):**

# 🦅 Executive Strategic Landscape Assessment

## 1. Executive Abstract
*   High-level synthesis of the market's current state (e.g., "Consolidating Mature Market" vs. "Fragmented High-Growth Phase").
*   Key thesis statement regarding the investment viability of this sector.

## 2. Market Maturity & Competitive Structure
*   **Concentration Analysis:** Is this a "Winner-Take-All" market? (Reference market share dominance of leaders like Robinhood/Adobe vs. the long tail).
*   **Exit Liquidity:** Analyze the ratio of Public/Acquired companies to Private ones. What does this say about the exit horizon?

## 3. Technology & Innovation Frontier
*   **The Tech Stack:** Synthesize the "Technology" sections. What are the non-negotiable tech capabilities (e.g., AI/ML, Mobile-First)?
*   **Differentiation:** How are the leaders differentiating? (e.g., Comprehensive Platforms vs. Point Solutions).

## 4. Capital Efficiency & Funding Heatmap
*   **Funding Velocity:** Where is the smart money going? (Analyze recent rounds).
*   **The "War Chest" vs. "Runway" Split:** Contrast well-capitalized leaders against companies with stale funding. 
*   **Valuation Trends:** If valuation data exists, analyze the multiples or trends.

## 5. Strategic SWOT (Aggregated)
*   **Sector Strengths:** Systemic advantages of this market.
*   **Systemic Weaknesses:** Common vulnerabilities (e.g., lack of profitability transparency, over-reliance on ad-tech).
*   **External Opportunities:** Emerging global markets or tech shifts.
*   **Macro Threats:** Regulatory headwinds or saturation risks.

## 6. Strategic Recommendations
*   **For Entrants:** Where is the white space?
*   **For Investors:** Where is the risk/reward ratio optimized?

**Analytics Note:** Diagnostic analytics and Prescriptive analytics have been performed to arrive at these conclusions."""

    # =========================================================================
    # 3. THE COMPREHENSIVE COMPANY PROFILE (Deep Due Diligence)
    # =========================================================================
    @staticmethod
    def generate_comprehensive_company_analysis(company: Dict[str, Any], target_market_context: str = "") -> str:
        """
        Generates a detailed, institutional-grade Due Diligence Report for a single company.
        Includes handling for missing data, specific anomalies, and deep cross-metric analysis.
        """
        formatted_context = ""
        if target_market_context:
            formatted_context = f"**TARGET MARKET CONTEXT:** {target_market_context}\n\n"

        return f"""You are an Expert Equity Research Analyst conducting deep due diligence.
Produce a **Comprehensive Institutional Investment Memo** for the company below.
{formatted_context}

**COMPANY DATA (JSON):**
{TracxnPromptTemplates._format_company_data(company)}

**CRITICAL INSTRUCTIONS FOR PROFESSIONALISM:**
1.  **Data Integrity:** If a field contains "$## (##)", "##.##%", or "Cannot be curated", explicitly state: *"Metric undisclosed/unavailable in dataset"* and discuss the implications (e.g., lack of transparency). **DO NOT** hallucinate numbers.
2.  **Contextual Logic:** 
    *   If "Employee Count" is dropping, flag as a restructuring/efficiency risk.
    *   If "Rank" is high but "Funding" is low/stale, investigate operational efficiency or potential stagnation.
    *   If "Employee Count" is unusually low (e.g., <50) for a Public company, flag as a **Critical Data Anomaly**.
3.  **Pedigree Analysis:** When analyzing "Key People," highlight universities and past employers to assess management quality.

**REPORT STRUCTURE (Markdown):**

# 📊 {company.get('name', 'Company')} - Due Diligence Report

## 1. Executive Snapshot
*   **Business Definition:** Precise summary of what they do, their sector, and business model (SaaS, Consumption, etc.).
*   **Market Positioning:** Where do they sit in the food chain? (Market Leader, Niche Specialist, Distressed Asset).
*   **Verdict:** (Bullish / Neutral / Bearish / Data Insufficient) based strictly on available evidence.

## 2. Operational & Human Capital Assessment
*   **Scale:** Analyze Employee Count and Location footprint (Subsidiaries, Legal Entities).
*   **Growth Trajectory:** Analyze Employee Growth History (YoY). Is the company hiring or firing?
*   **Leadership Pedigree:** Assess the background of Key People (Education, Ex-Companies). Are they serial entrepreneurs?

## 3. Technology & Product Moat
*   **Core Offering:** Technical breakdown of the platform/service.
*   **Innovation:** Keywords indicating tech depth (AI, ML, Cloud-Native, API-First).
*   **Product Maturity:** Evidence of adoption via Mobile Apps (Downloads, Ratings, Reviews).

## 4. Competitive Landscape & Market Share
*   **Ranking:** {company.get('name')} ranks **#{company.get('rank', 'N/A')}** among peers. Contextualize this.
*   **Benchmarking:** Compare against the "Competitor List". Who are the primary threats?
*   **Market Traction:** Analyze "Market Share" and "News/Review Growth" metrics if available.

## 5. Financial Health & Capital Structure
*   **Capitalization:** Analyze Total Equity Funding, Latest Round (Date & Amount), and Valuation.
*   **Runway Assessment:** *Crucial Step:* Look at the date of the latest funding. If >2 years ago and no IPO/Acquisition, flag as "Potential Runway Risk."
*   **Investor Quality:** Assess the names of Institutional Investors (Tier-1 VCs vs. unknown).
*   **Profitability Signals:** State Revenue/EBITDA availability. If missing, comment on the opacity.

## 6. Strategic SWOT Analysis
*   **Strengths:** (Internal - Tech, Team, Capital).
*   **Weaknesses:** (Internal - Data gaps, Stale funding, Low growth).
*   **Opportunities:** (External - Market trends, M&A).
*   **Threats:** (External - Competitors, Regulation).

**Analytics Note:** Diagnostic analytics and Prescriptive analytics have been performed to arrive at these conclusions."""

    # =========================================================================
    # LEGACY / MAPPING METHODS (For pipeline compatibility)
    # =========================================================================
    
    @staticmethod
    def generate_company_overview(company: Dict[str, Any], target_market_context: str = "") -> str:
        """Legacy: Maps to comprehensive company analysis."""
        return TracxnPromptTemplates.generate_comprehensive_company_analysis(company, target_market_context)

    @staticmethod
    def generate_competitor_report(company: Dict[str, Any], target_market_context: str = "") -> str:
        """Legacy: Maps to comprehensive company analysis."""
        return TracxnPromptTemplates.generate_comprehensive_company_analysis(company, target_market_context)

    @staticmethod
    def generate_market_funding_report(company: Dict[str, Any], target_market_context: str = "") -> str:
        """Legacy: Maps to comprehensive company analysis."""
        return TracxnPromptTemplates.generate_comprehensive_company_analysis(company, target_market_context)

    @staticmethod
    def generate_growth_potential_report(company: Dict[str, Any], target_market_context: str = "") -> str:
        """Legacy: Maps to comprehensive company analysis."""
        return TracxnPromptTemplates.generate_comprehensive_company_analysis(company, target_market_context)

    @staticmethod
    def generate_tech_product_report(company: Dict[str, Any], target_market_context: str = "") -> str:
        """Legacy: Maps to comprehensive company analysis."""
        return TracxnPromptTemplates.generate_comprehensive_company_analysis(company, target_market_context)

    @staticmethod
    def generate_market_demand_report(company: Dict[str, Any], target_market_context: str = "") -> str:
        """Legacy: Maps to comprehensive company analysis."""
        return TracxnPromptTemplates.generate_comprehensive_company_analysis(company, target_market_context)

    @staticmethod
    def generate_swot_report(company: Dict[str, Any], target_market_context: str = "") -> str:
        """Legacy: Maps to comprehensive company analysis."""
        return TracxnPromptTemplates.generate_comprehensive_company_analysis(company, target_market_context)

    # Legacy Summary Mappings (Point all specific summaries to the main Executive Summary)
    @staticmethod
    def generate_competitor_summary(reports: List[str], sample_size: int, target_market_context: str = "") -> str:
        """Legacy: Maps to executive summary."""
        return TracxnPromptTemplates.generate_executive_summary(reports, sample_size, target_market_context)

    @staticmethod
    def generate_market_funding_summary(reports: List[str], sample_size: int, target_market_context: str = "") -> str:
        """Legacy: Maps to executive summary."""
        return TracxnPromptTemplates.generate_executive_summary(reports, sample_size, target_market_context)

    @staticmethod
    def generate_growth_potential_summary(reports: List[str], sample_size: int, target_market_context: str = "") -> str:
        """Legacy: Maps to executive summary."""
        return TracxnPromptTemplates.generate_executive_summary(reports, sample_size, target_market_context)

    @staticmethod
    def generate_company_overview_summary(reports: List[str], sample_size: int, target_market_context: str = "") -> str:
        """Legacy: Maps to executive summary."""
        return TracxnPromptTemplates.generate_executive_summary(reports, sample_size, target_market_context)

    @staticmethod
    def generate_tech_product_summary(reports: List[str], sample_size: int, target_market_context: str = "") -> str:
        """Legacy: Maps to executive summary."""
        return TracxnPromptTemplates.generate_executive_summary(reports, sample_size, target_market_context)

    @staticmethod
    def generate_market_demand_summary(reports: List[str], sample_size: int, target_market_context: str = "") -> str:
        """Legacy: Maps to executive summary."""
        return TracxnPromptTemplates.generate_executive_summary(reports, sample_size, target_market_context)

    @staticmethod
    def generate_swot_summary(reports: List[str], sample_size: int, target_market_context: str = "") -> str:
        """Legacy: Maps to executive summary."""
        return TracxnPromptTemplates.generate_executive_summary(reports, sample_size, target_market_context)
