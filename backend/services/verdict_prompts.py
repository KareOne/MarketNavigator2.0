"""
Verdict Analysis Prompt Templates.
Based on Master Prompt v8.3: High-Fidelity Idea Viability Synthesis Engine.

Key Features:
1. Zero-Baseline Assumption: All insights must be discovered from data
2. Multi-Phase Pipeline: Data Audit → Scoring → Risk Synthesis → Verdict → Roadmap
3. Evidence-Based Analysis: Every claim must reference dataset role
"""

import json
from typing import Dict, Any, List, Optional


def safe_slice(data: Any, count: int) -> List:
    """Safely slice data, handling non-list types and empty data."""
    if not data:
        return []
    if isinstance(data, list):
        return data[:count]
    if isinstance(data, dict):
        return [data]  # Wrap dict in list
    return []


def safe_json_dump(data: Any, max_chars: int = 3000) -> str:
    """Safely dump data to JSON with character limit."""
    try:
        if not data:
            return "No data available"
        result = json.dumps(data, indent=2, default=str)
        if len(result) > max_chars:
            return result[:max_chars] + "\n... (truncated)"
        return result
    except Exception as e:
        return f"Error serializing data: {str(e)}"


class VerdictPromptTemplates:
    """
    Container for Verdict Analysis prompts.
    Implements Master Prompt v8.3 phases with strict data adherence.
    """
    
    # =========================================================================
    # System Identity & Core Policy
    # =========================================================================
    
    SYSTEM_PROMPT = """You are a Lead Strategic Architect and Venture Partner.

**Strict Policy**: You operate on a **Zero-Baseline Assumption**.
You do not possess predefined knowledge of the project's risks, market conditions, or necessary actions.
Every single insight, risk factor, score, verdict, and roadmap milestone MUST be **discovered and synthesized exclusively from the provided structured inputs**.

Generic startup advice, intuition, or pattern-matching is **strictly forbidden** unless it is **explicitly triggered by evidence** inside the inputs.

**Evidence Requirement**: Every analytical claim MUST begin with:
"Based on [Dataset Role] evidence..."

**Zero Hallucination**: Missing data → zero score + explicit risk

**Tone**: Clinical, objective, investigative."""

    # =========================================================================
    # Phase I: Data Audit & Classification (Internal)
    # =========================================================================
    
    @staticmethod
    def generate_data_audit_prompt(
        crunchbase_data: List[Dict[str, Any]],
        tracxn_data: List[Dict[str, Any]],
        social_data: List[Dict[str, Any]],
        project_description: str = ""
    ) -> str:
        """
        Generate prompt for internal data audit and classification.
        This phase classifies datasets into their functional roles.
        """
        # Safely get data lengths
        cb_count = len(crunchbase_data) if isinstance(crunchbase_data, list) else (1 if crunchbase_data else 0)
        tx_count = len(tracxn_data) if isinstance(tracxn_data, list) else (1 if tracxn_data else 0)
        sc_count = len(social_data) if isinstance(social_data, list) else (1 if social_data else 0)
        
        return f"""You are performing an internal data audit for a venture viability analysis.

**PROJECT CONTEXT**:
{project_description if project_description else "No explicit project description provided. Discover the idea from the intake data."}

**DATASETS PROVIDED**:

1. CRUNCHBASE DATA ({cb_count} companies):
{safe_json_dump(safe_slice(crunchbase_data, 3), 3000)}

2. TRACXN DATA ({tx_count} startups):
{safe_json_dump(safe_slice(tracxn_data, 3), 3000)}

3. SOCIAL DATA ({sc_count} posts):
{safe_json_dump(safe_slice(social_data, 5), 2000)}

**TASK**:
Classify each dataset by its functional role:

A. **Concept/Idea Intake**: Contains proposed product, value propositions, user workflows
B. **Demand & Social Signal**: Contains social posts, pain expressions, sentiment
C. **Competitive Landscape**: Contains company records, rankings, feature descriptions
D. **Market Context**: Contains macro signals, technology shifts, infrastructure dynamics

For each dataset, provide:
1. Primary Role Classification
2. Secondary Role (if hybrid)
3. Key evidence fields that drove the classification
4. Axes this dataset may influence (Demand, Competition, Differentiation, Economics, Feasibility)

Output as structured JSON:
{{
    "crunchbase_classification": {{
        "primary_role": "...",
        "secondary_role": null or "...",
        "key_fields": ["..."],
        "influences_axes": ["..."]
    }},
    "tracxn_classification": {{ ... }},
    "social_classification": {{ ... }},
    "idea_source": "identified from ... dataset",
    "data_gaps": ["list any critical missing data types"]
}}"""

    # =========================================================================
    # Phase II: Executive Synthesis
    # =========================================================================
    
    @staticmethod
    def generate_executive_synthesis_prompt(
        crunchbase_data: List[Dict[str, Any]],
        tracxn_data: List[Dict[str, Any]],
        social_data: List[Dict[str, Any]],
        project_description: str = "",
        data_classification: Dict[str, Any] = None
    ) -> str:
        """
        Generate prompt for Executive Synthesis (user-visible Phase I).
        Establishes analytical scope without exposing internal audits.
        """
        return f"""You are generating an Executive Synthesis for a startup viability analysis.

**PROJECT CONTEXT**:
{project_description if project_description else "Discover the opportunity from the datasets."}

**DATA OVERVIEW**:
- Crunchbase: {len(crunchbase_data)} competitor companies analyzed
- Tracxn: {len(tracxn_data)} startup ecosystem entities
- Social: {len(social_data) if isinstance(social_data, list) else 'Aggregated'} demand signals

**CLASSIFICATION CONTEXT** (from internal audit):
{safe_json_dump(data_classification, 2000) if data_classification else "Not available"}

**TASK**:
Write a compelling Executive Synthesis (300-500 words) that:

1. **Title**: Give this analysis a clear, descriptive title
2. **Opportunity Statement**: What type of opportunity is being evaluated?
3. **Data Signals Present**: What key signals were discovered in the data?
4. **Data Signals Missing**: What critical data is absent? (be explicit)
5. **Analysis Scope**: What constraints shape this evaluation?
6. **Key Themes**: 3-5 major themes discovered across datasets

**FORMAT**: Markdown with clear headers. No tables in this section.

**CRITICAL**: Do NOT include dataset lists, audit tables, or internal reasoning.
This section sets the framing for executive readers."""

    # =========================================================================
    # Phase III: Quantitative Scoring (5 Axes)
    # =========================================================================
    
    @staticmethod
    def generate_scoring_prompt(
        axis: str,
        weight: int,
        crunchbase_data: List[Dict[str, Any]],
        tracxn_data: List[Dict[str, Any]],
        social_data: List[Dict[str, Any]],
        project_description: str = ""
    ) -> str:
        """
        Generate prompt for quantitative scoring of a specific axis.
        """
        axis_instructions = {
            "demand": """**MARKET DEMAND (25%)**

Logic: Cross-reference pain and sentiment signals (Social data) with growth or momentum indicators (Crunchbase/Tracxn).

Classification Rule:
- High pain + low observable intent → **Latent Demand**
- High pain + high intent → **Acute Demand**

Score Drivers:
- Explicit pain expressions in social data
- Feature requests and wishlist items
- User adoption triggers and conversion moments
- Sentiment polarity and volume""",

            "competition": """**COMPETITION (20%)**

Logic: Evaluate market noise by counting and weighting competitive entities.

Penalty Rule: Apply penalty if:
- Capital-dense incumbents exist ($50M+ funding)
- AND evidence suggests recent feature convergence or market entry

Score Drivers:
- Number of direct competitors
- Funding concentration (top 3 vs rest)
- Feature overlap density
- Geographic/segment fragmentation""",

            "differentiation": """**DIFFERENTIATION (20%)**

Logic: Isolate the unique value proposition and compare against Top 3 most similar competitors.

Moat Classification:
- **Commodity Moat**: UI/UX/packaging (weak)
- **Structural Moat**: proprietary data, logic loops, compounding advantage (strong)

Score Drivers:
- Unique capability not replicated
- Data or network effects
- Switching cost indicators
- Technology or process differentiation""",

            "economics": """**ECONOMICS (20%)**

Logic: Assess economic viability by contrasting:
- Pricing/revenue mechanics (if discoverable)
- Cost-driver signals (compute, operations, infrastructure)
- Monetization patterns from competitors

Scoring Framework:
- Explicit pricing + cost signals → score on margin plausibility
- Missing pricing but competitor patterns exist → score with confidence penalty
- Both missing → cap at 25/100, flag as low-confidence

Hard Rule: If no pricing signal AND market context shows structurally impossible economics → Killer Risk""",

            "feasibility": """**FEASIBILITY (15%)**

Logic: Compare claimed technical ambition with:
- Current APIs and platform primitives
- Available models and infrastructure
- Discovered technology patterns in competitors

Penalty Rule: If feasibility relies on undeclared breakthroughs → heavy penalty

Score Drivers:
- Technology stack maturity
- Build vs buy vs integrate options
- Regulatory or compliance barriers
- Team capability signals (if present)"""
        }
        
        return f"""You are scoring the **{axis.upper()}** axis for a startup viability analysis.

{axis_instructions.get(axis.lower(), "Unknown axis")}

**WEIGHT**: {weight}% of total score

**PROJECT CONTEXT**:
{project_description if project_description else "Discover from datasets."}

**COMPETITIVE DATA (Crunchbase - {len(crunchbase_data) if isinstance(crunchbase_data, list) else 0} companies)**:
{safe_json_dump(safe_slice(crunchbase_data, 5), 4000)}

**STARTUP ECOSYSTEM DATA (Tracxn - {len(tracxn_data) if isinstance(tracxn_data, list) else 0} startups)**:
{safe_json_dump(safe_slice(tracxn_data, 5), 4000)}

**DEMAND SIGNALS (Social - {len(social_data) if isinstance(social_data, list) else 0} items)**:
{safe_json_dump(safe_slice(social_data, 10), 3000)}

**TASK**:
Provide a score from 0-100 for this axis with detailed reasoning.

**OUTPUT FORMAT** (JSON):
{{
    "axis": "{axis}",
    "score": <0-100>,
    "confidence": "high" | "medium" | "low",
    "classification": "<specific classification if applicable>",
    "key_evidence": [
        {{"source": "crunchbase|tracxn|social", "finding": "...", "impact": "positive|negative|neutral"}}
    ],
    "reasoning": "<2-3 paragraph explanation of score>",
    "data_gaps": ["<missing data that would improve confidence>"],
    "implications": "<what this score means for the venture>"
}}"""

    # =========================================================================
    # Phase IV: Risk Synthesis (FMEA)
    # =========================================================================
    
    @staticmethod
    def generate_risk_synthesis_prompt(
        scores: Dict[str, Any],
        crunchbase_data: List[Dict[str, Any]],
        tracxn_data: List[Dict[str, Any]],
        social_data: List[Dict[str, Any]],
        project_description: str = ""
    ) -> str:
        """
        Generate prompt for FMEA-style risk discovery.
        """
        return f"""You are performing a Discovery-Based Risk Synthesis using FMEA methodology.

**CRITICAL RULE**: Do NOT use a generic risk list.
You must **discover risks** by identifying contradictions across datasets.

**AXIS SCORES** (from previous analysis):
{safe_json_dump(scores, 2000)}

**PROJECT CONTEXT**:
{project_description if project_description else "Discover from datasets."}

**COMPETITIVE DATA (Crunchbase)**:
{safe_json_dump(safe_slice(crunchbase_data, 3), 2500)}

**STARTUP ECOSYSTEM DATA (Tracxn)**:
{safe_json_dump(safe_slice(tracxn_data, 3), 2500)}

**DEMAND SIGNALS (Social)**:
{safe_json_dump(safe_slice(social_data, 5), 2000)}

**RISK CLASSES**:
1. **Killer Risks**: Structural blockers that make success nearly impossible
2. **Major Risks**: Survivable but growth-limiting constraints
3. **Minor Risks**: Execution friction that can be managed

**TASK**:
Discover 5-10 risks by analyzing contradictions between:
- Demand signals vs competitive reality
- Scoring gaps vs market requirements
- Economics assumptions vs cost evidence
- Differentiation claims vs competitor features

**OUTPUT FORMAT** (JSON):
{{
    "killer_risks": [
        {{
            "risk_id": "K1",
            "title": "...",
            "description": "...",
            "dataset_sources": ["crunchbase", "social"],
            "contradiction_discovered": "...",
            "mitigation_possible": true|false
        }}
    ],
    "major_risks": [...],
    "minor_risks": [...],
    "risk_heatmap": {{
        "demand_risks": <count>,
        "competition_risks": <count>,
        "differentiation_risks": <count>,
        "economics_risks": <count>,
        "feasibility_risks": <count>
    }},
    "total_killer_risks": <count>,
    "total_major_risks": <count>,
    "total_minor_risks": <count>
}}"""

    # =========================================================================
    # Phase V: Verdict Determination
    # =========================================================================
    
    @staticmethod
    def generate_verdict_prompt(
        scores: Dict[str, Any],
        risks: Dict[str, Any],
        project_description: str = ""
    ) -> str:
        """
        Generate prompt for mechanical verdict determination.
        """
        return f"""You are determining the final verdict for a startup viability analysis.

**VERDICT RULES** (mechanical, non-negotiable):

1. **GO**:
   - Total weighted score > 75
   - Zero Killer Risks
   - Demand classified as "Acute"

2. **ITERATE**:
   - Total weighted score 50-75
   - OR one Major structural/economic risk present

3. **PARK / KILL**:
   - Total weighted score < 50
   - OR ≥ 1 Killer Risk present

**AXIS SCORES**:
{safe_json_dump(scores, 2000)}

**RISK SUMMARY**:
{safe_json_dump(risks, 2000)}

**PROJECT CONTEXT**:
{project_description if project_description else "From datasets."}

**TASK**:
1. Calculate the total weighted score
2. Apply verdict rules mechanically
3. Provide clear reasoning for the verdict

**WEIGHTING**:
- Market Demand: 25%
- Competition: 20%
- Differentiation: 20%
- Economics: 20%
- Feasibility: 15%

**OUTPUT FORMAT** (JSON):
{{
    "weighted_scores": {{
        "demand": {{"raw": <0-100>, "weighted": <0-25>}},
        "competition": {{"raw": <0-100>, "weighted": <0-20>}},
        "differentiation": {{"raw": <0-100>, "weighted": <0-20>}},
        "economics": {{"raw": <0-100>, "weighted": <0-20>}},
        "feasibility": {{"raw": <0-100>, "weighted": <0-15>}}
    }},
    "total_score": <0-100>,
    "verdict": "GO" | "ITERATE" | "PARK",
    "verdict_reasoning": "<2-3 paragraphs explaining WHY this verdict was reached>",
    "verdict_confidence": "high" | "medium" | "low",
    "key_factors": [
        {{"factor": "...", "impact": "positive|negative", "weight": "critical|significant|minor"}}
    ],
    "next_decision_point": "<what would change this verdict>"
}}"""

    # =========================================================================
    # Phase VI: Actionable Roadmap
    # =========================================================================
    
    @staticmethod
    def generate_roadmap_prompt(
        verdict: Dict[str, Any],
        risks: Dict[str, Any],
        scores: Dict[str, Any],
        project_description: str = ""
    ) -> str:
        """
        Generate prompt for customized actionable roadmap.
        """
        return f"""You are generating a Customized Actionable Roadmap based on discovered weaknesses and risks.

**VERDICT**: {verdict.get('verdict', 'UNKNOWN')}
**TOTAL SCORE**: {verdict.get('total_score', 'N/A')}

**LOWEST SCORING AXES** (prioritize these):
{safe_json_dump(scores, 2000)}

**HIGHEST PRIORITY RISKS**:
{safe_json_dump(risks, 2000)}

**PROJECT CONTEXT**:
{project_description if project_description else "From datasets."}

**ROADMAP RULES**:
- Items must map **directly** to discovered weaknesses and risks
- No generic MVPs or filler milestones
- Be specific about what to test and how

**TASK**:
Generate two focused sprints:

**7-DAY SPRINT**:
A single, sharply defined experiment designed to:
- Close the highest-impact information gap
- OR invalidate a Killer / Major Risk

**30-DAY SPRINT**:
Focused exclusively on:
- Building the discovered moat
- OR engineering around the strongest constraint

**OUTPUT FORMAT** (JSON):
{{
    "seven_day_sprint": {{
        "objective": "...",
        "hypothesis_to_test": "...",
        "specific_actions": [
            {{"day": "1-2", "action": "...", "deliverable": "..."}},
            {{"day": "3-4", "action": "...", "deliverable": "..."}},
            {{"day": "5-7", "action": "...", "deliverable": "..."}}
        ],
        "success_criteria": "...",
        "risk_addressed": "K1" | "M1" | etc,
        "resource_requirements": ["..."]
    }},
    "thirty_day_sprint": {{
        "objective": "...",
        "moat_building_focus": "...",
        "weekly_milestones": [
            {{"week": 1, "milestone": "...", "metrics": "..."}},
            {{"week": 2, "milestone": "...", "metrics": "..."}},
            {{"week": 3, "milestone": "...", "metrics": "..."}},
            {{"week": 4, "milestone": "...", "metrics": "..."}}
        ],
        "constraint_addressed": "...",
        "decision_gates": ["..."]
    }},
    "critical_dependencies": ["..."],
    "abort_conditions": ["..."]
}}"""

    # =========================================================================
    # Utility: Get All Section Types
    # =========================================================================
    
    @staticmethod
    def get_all_section_types() -> List[str]:
        """Get list of all verdict analysis section types."""
        return [
            "data_audit",
            "executive_synthesis",
            "scoring_demand",
            "scoring_competition",
            "scoring_differentiation",
            "scoring_economics",
            "scoring_feasibility",
            "risk_synthesis",
            "verdict_decision",
            "roadmap"
        ]
