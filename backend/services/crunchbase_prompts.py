"""
Crunchbase Analysis Prompts - Re-engineered for 3-Part Pipeline.
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
    # PART 1: The Deep Dive (Per Company)
    # =========================================================================

    def generate_company_summary(self, company: Dict[str, Any]) -> str:
        """
        Generate the 7-section Deep Dive report for a single company.
        Combines all previous individual steps into one cohesive analysis.
        """
        target_context = self._get_target_market_context()
        company_name = company.get("Company Name", company.get("name", "Unknown"))
        
        return f"""
You are a top-tier Venture Capital Analyst preparing a Deep Dive Investment Memo.
Your goal is to dissect this company with surgical precision. No marketing fluff.
{target_context}

### INPUT DATA:
Company: {company_name}
Data: {json.dumps(company, indent=2)}

### OUTPUT:
Generate a **comprehensive 7-section report** in Markdown.
You MUST output all 7 sections below. If data is missing for a section, explicitly state what is missing and provide a qualitative assessment based on what IS available (e.g., "Seed stage company, no traffic data yet").

#### SECTION 1: EXECUTIVE SUMMARY
*   **Persona:** The Partner who has 30 seconds.
*   **Task:** One paragraph summary of what they do, their key differentiator, and their threat level to the target market.

#### SECTION 2: TECHNOLOGY & PRODUCT CORE
*   **Persona:** Application Architect / CTO.
*   **Focus:** Technical complexity and "Moat".
*   **Task:** Analyze `Active Tech Count`, `Tech Details summary`, and `Total Products Active`.
    *   Assess the sophistication of their stack (e.g., AI/ML, Cloud Infrastructure, Security).
    *   Identify key technical strengths (e.g., "Proprietary Data Pipeline") and weaknesses (e.g., "Low tech count suggests manual processes").
    *   *Constraint:* Do not analyze funding here. Focus only on product/tech.

#### SECTION 3: MARKET TRACTION & DEMAND
*   **Persona:** Data-Driven Market Research Analyst.
*   **Focus:** Quantifying traction.
*   **Task:** Analyze `Monthly Visits`, `Bounce Rate`, `Visit Duration`, `Global Traffic Rank`, and their growth percentages.
    *   **Create a Markdown Table** summarizing these metrics.
    *   Interpret the data: Is the audience growing? Is engagement high (low bounce, high duration)? What does this signal about product-market fit?
    *   *Constraint:* If web data is missing, skip the table and provide a qualitative assessment based on brand presence (e.g., App downloads, social footprint).

#### SECTION 4: FUNDING & FINANCIAL HEALTH
*   **Persona:** Skeptical Venture Capital Analyst.
*   **Focus:** Financial soundness and capital efficiency.
*   **Task:** Analyze `Total Funding Amount`, `Investors Table`, and `Number of Funding Rounds`.
    *   **Create a Markdown Table** summarizing the key funding rounds (Date, Amount, Lead Investor) IF data exists.
    *   Analyze the investor quality (Top tier VCs vs. unknown).
    *   Assess capital efficiency: Are they achieving high traffic/growth relative to their funding?

#### SECTION 5: GROWTH & COMPETITIVE POSITIONING
*   **Persona:** Discerning Growth Equity Investor.
*   **Focus:** Scalable growth signals.
*   **Task:** Analyze `Growth Score`, `Growth Prediction`, `Headcount`, and `Contacts count`.
    *   Are they hiring aggressively? Is the growth score trending up?
    *   Compare them to the "Market Navigator" concept. Are they a massive incumbent or a nimble challenger?

#### SECTION 6: STRATEGIC SWOT
*   **Persona:** Senior Partner at a Consulting Firm.
*   **Task:** Synthesize all above insights into a strategic SWOT.
    *   **Strengths:** Internal attributes (Tech, Funding, Talent).
    *   **Weaknesses:** Internal liabilities (High bounce rate, technical debt, lack of transparency).
    *   **Opportunities:** External chances for *Market Navigator* to capitalize on (e.g., "Partner with them for data").
    *   **Threats:** External risks they pose to *Market Navigator* (e.g., "They own the mobile intelligence niche").

#### SECTION 7: FINAL VERDICT
*   **Actionable Takeaway:** One bold paragraph. Should Market Navigator fear them, copy them, or ignore them?
"""

    # =========================================================================
    # PART 2: The Strategic Summary (Topic-Centric Analysis)
    # =========================================================================

    def generate_strategic_summary(self, companies: List[Dict[str, Any]]) -> str:
        """
        Generate a trend analysis across the top companies.
        Synthesizes the specific "Summary" prompts into one document.
        """
        target_context = self._get_target_market_context()
        
        # Prepare data summary to avoid token limits
        summary_data = []
        for i, c in enumerate(companies):
            summary_data.append({
                "rank": i + 1,
                "name": c.get("Company Name", c.get("name")),
                "funding": c.get("Total Funding Amount"),
                "visits": c.get("Monthly Visits"),
                "growth_score": c.get("Growth Score"),
                "tech_count": c.get("Active Tech Count"),
                "industry_tags": c.get("Industry Tags", [])
            })

        return f"""
You are writing **Part 2: Strategic Summary** (Executive Report).
This section synthesizes trends across the Top {len(companies)} companies to guide Market Navigator's strategy.
{target_context}

### INPUT DATA (Top {len(companies)}):
{json.dumps(summary_data, indent=2)}

### OUTPUT STRUCTURE & REQUIREMENTS:

**1. EXECUTIVE MARKET MAP**
*   Create a categorization framework. Group the companies into logical buckets (e.g., "Direct Competitors," "Data Utilities," "Enterprise Legacy").
*   Present this as a **Markdown Table**: | Category | Companies | Threat Level |
*   Analyze the market density. Is it crowded with direct competitors, or fragmented?

**2. TECHNOLOGY LANDSCAPE (The CTO View)**
*   Synthesize technical trends. Are the top players relying on proprietary AI, or standard aggregators?
*   Analyze "Active Tech Counts". Does technical complexity correlate with market dominance in this sample?
*   Identify the "Table Stakes" features that Market Navigator *must* build to compete.

**3. CAPITAL & TRACTION DYNAMICS (The VC View)**
*   Analyze the relationship between Funding and Traffic.
*   Identify **Capital Efficient Outliers:** Who is getting high traffic with low/no funding? (These are models to emulate).
*   Identify **Capital Inefficient Incumbents:** Who has raised millions but has low engagement? (These are vulnerable).

**4. GROWTH VECTORS & GAPS (The Strategist View)**
*   Where is the "Blue Ocean"? Look at the "Industry Tags" and descriptions. What specific niches are underserved by these players?
*   Discuss the "Real-time" aspect. How many actually offer *real-time* insights vs. static reports?

**5. STRATEGIC RECOMMENDATION FOR MARKET NAVIGATOR**
*   Based on these profiles, define the optimal entry point.
*   Should Market Navigator be a low-cost disruptor, a premium AI-first tool, or a vertical specialist?
"""

    # =========================================================================
    # PART 3: The Fast Analysis (Board-Level Dashboard)
    # =========================================================================

    def generate_fast_analysis(self, companies: List[Dict[str, Any]]) -> str:
        """
        Generate a "Flash Report" for executive decision making.
        Focuses purely on high-signal data tables and direct "Buy/Build/Partner" calls.
        """
        target_context = self._get_target_market_context()
        
        # Dashboard data preparation
        dashboard_data = []
        for i, c in enumerate(companies):
            dashboard_data.append({
                "rank": i + 1,
                "name": c.get("Company Name", c.get("name")),
                "funding": c.get("Total Funding Amount"),
                "traffic": c.get("Monthly Visits"),
                "growth": c.get("Growth Score"),
                "tags": c.get("Industry Tags", [])[:3]
            })

        return f"""
You are writing **Part 3: Fast Analysis** (Flash Report).
This document is for the Board of Directors who have 5 minutes to read.
**Constraint:** Be ruthless. No fluff. Use tables and bullet points only.
{target_context}

### INPUT DATA:
{json.dumps(dashboard_data, indent=2)}

### OUTPUT REQUIREMENTS:

**1. THE COMPETITIVE LANDSCAPE AT A GLANCE**
*   Create a single **Master Comparison Table** with the following columns:
    *   **Rank**
    *   **Company**
    *   **Core Focus** (3 words max)
    *   **Funding**
    *   **Web Visits**
    *   **Growth Score**
    *   **Threat Status** (High/Med/Low)

**2. CRITICAL THREATS (Red Flags)**
*   Identify the top 1-2 companies that could kill Market Navigator.
*   **Why?** (1 sentence).
*   **Mitigation Strategy:** (1 sentence).

**3. GOLDEN OPPORTUNITIES (Green Flags)**
*   Identify 1-2 companies that represent a massive opportunity (e.g., to acquire, to partner with, or a gap they are leaving open).
*   **Why?** (1 sentence).

**4. BUILD vs. BUY vs. PARTNER**
*   **BUILD:** List 3 features seen in these competitors that Market Navigator MUST build internally to survive.
*   **PARTNER:** List 1-2 types of companies (or specific names from the list) where partnering for data makes more sense than building.
*   **IGNORE:** List companies that look big but are actually irrelevant to Market Navigator's startup focus.

**5. FINAL GO/NO-GO SIGNAL**
*   One sentence: Is the market too crowded, or is the timing perfect?
"""
