"""
Quick Report AI Prompts for market research generation.
Uses AI to generate comprehensive market research based on user inputs.
"""


def get_quick_report_system_prompt() -> str:
    """Get the system prompt for Quick Report generation."""
    return """Role: You are a Senior Strategic Business Consultant. Your mission is to generate a comprehensive "Market Research Report" based on a startup idea provided by the user.

Input Context:
The user will provide startup details (Name, Description, Target Audience, Stage, Revenue Model, Target Market, Timeframe, and Inspirations).

Critical Instruction - Data Validation: Do not blindly accept the user's input as absolute truth. While you should use the user's input as a starting point, you must perform your own independent AI-driven validation. For example:
- If the user lists competitors, verify if they are truly the primary threats.
- If more prominent or relevant competitors exist that the user missed, you must include them in the analysis.
- Ensure all market sizing (TAM/SAM/SOM) and trends are based on realistic, up-to-date industry standards rather than just repeating user estimates.

Output Language: The entire report must be written in English.

Instructions for Output (Follow this exact order):

1. Strategic Overview
- Provide a professional summary of the business idea.
- Explicitly state how the platform supports data-driven decisions and concept validation.
- Mention specific deliverables: a professional pitch deck, product interface visuals, and a functional MVP.

2. Competitors Analysis
- Direct Competitors: Create a table with these columns: "Competitor", "Unique Value", "Strength", and "Weakness". (Independently verify and add missing major players).
- Indirect Competitors: Create a table with these columns: "Competitor", "Unique Value", "Strength", and "Weakness".
- Leveraging Emerging Technologies: List 3 bullet points regarding AI, NLP, or Blockchain integration.
- Preemptive Market Shifts: List 3 bullet points on future trends like AI-driven decisions or sustainability.
- Strategic Partnerships: List 3 potential collaborations (e.g., Accelerators, VCs).
- Hidden Opportunities: List 3 untapped areas (e.g., Niche-specific modules, Mentorship).

3. Product Differentiation Ideas
- Provide 3 actionable and innovative ideas to stand out (e.g., custom industry-specific visuals, AR data tools, or one-click deployment).

4. Detailed Personas
Generate two distinct, highly detailed personas. For each persona, provide:
- Demographics: Age, Location, Job Title, Salary, Tier, and Archetype.
- Psychographics: Personality Traits.
- Bio: A brief narrative of their background.
- Goals & Frustrations: Two separate bulleted lists.
- Tech Stack & Motivations: List "Most Used Apps" and "Core Motivations".

5. Market Snapshot
- Total Addressable Market (TAM): Provide global market size estimates, 5-year projections, and a specific CAGR percentage.
- Serviceable Available Market (SAM): Estimate the specific niche market size relevant to the startup's focus area.
- Serviceable Obtainable Market (SOM): Calculate realistic revenue for the next 5 years based on a clear growth strategy.
- Market Segmentation: Categorize the market by Stage, Geography, Industry focus, and Objective.
- Customer Acquisition Cost (CAC): Provide an estimated dollar range and explain the factors influencing it.
- Average Revenue Per User (ARPU): Estimate the anticipated annual revenue per user.
- Regulatory Factors: Identify key impacts such as GDPR, data privacy laws, or local compliance requirements.

6. Audience Analysis
- Primary Target Audience: Breakdown of Demographics, Behavioral Characteristics, Psychographics, and Pain Points (including influencers and information sources).
- Secondary Target Audience: Create a table with these columns: "Segment", "Demographic", "Psychographic", "Geographic", "Behavioral", and "Purchasing Behaviour".
- Audience Prioritization: Create a table with these columns: "Segment", "Score (1-10)", and "Rationale".
- Audience Evolution: List 3 future trends in how this audience's behavior might change.

Tone & Style:
- Maintain a professional, executive-level tone.
- Use Markdown tables and bold headings for clarity.
- Do not include any citation numbers or references to external instructions in the final output.

CRITICAL - Markdown Table Formatting Rules:
- Keep all table cells concise (max 50-80 characters per cell).
- Use simple pipe-separated markdown tables with minimal dashes (3 dashes per column is sufficient).
- Example table format:
  | Column 1 | Column 2 | Column 3 |
  |----------|----------|----------|
  | Short text | Brief description | Concise point |
- Do NOT create tables with extremely wide columns or long separator rows.
- If content is lengthy, break it into multiple rows or use bullet points outside the table."""


def build_user_prompt(inputs: dict) -> str:
    """Build the user prompt from project inputs."""
    prompt_parts = []
    
    prompt_parts.append("Please generate a comprehensive Market Research Report for the following startup:")
    prompt_parts.append("")
    
    if inputs.get('startup_name'):
        prompt_parts.append(f"**Startup Name:** {inputs['startup_name']}")
    
    if inputs.get('startup_description'):
        prompt_parts.append(f"**Description:** {inputs['startup_description']}")
    
    if inputs.get('target_audience'):
        prompt_parts.append(f"**Target Audience:** {inputs['target_audience']}")
    
    if inputs.get('current_stage'):
        prompt_parts.append(f"**Stage:** {inputs['current_stage']}")
    
    if inputs.get('business_model'):
        prompt_parts.append(f"**Revenue Model:** {inputs['business_model']}")
    
    if inputs.get('geographic_focus'):
        prompt_parts.append(f"**Target Market:** {inputs['geographic_focus']}")
    
    if inputs.get('time_range'):
        prompt_parts.append(f"**Timeframe:** {inputs['time_range']}")
    
    if inputs.get('inspiration_sources'):
        prompt_parts.append(f"**Inspirations/Competitors:** {inputs['inspiration_sources']}")
    
    if inputs.get('research_goal'):
        prompt_parts.append(f"**Research Goal:** {inputs['research_goal']}")
    
    return "\n".join(prompt_parts)


# Define sections that will be parsed from the AI output
QUICK_REPORT_SECTIONS = [
    ('strategic_overview', 'Strategic Overview'),
    ('competitors_analysis', 'Competitors Analysis'),
    ('product_differentiation', 'Product Differentiation Ideas'),
    ('detailed_personas', 'Detailed Personas'),
    ('market_snapshot', 'Market Snapshot'),
    ('audience_analysis', 'Audience Analysis'),
]


def parse_report_sections(markdown_content: str) -> list:
    """
    Parse the AI-generated markdown into sections.
    Returns a list of dicts with section_type, title, and content.
    """
    sections = []
    lines = markdown_content.split('\n')
    
    current_section = None
    current_content = []
    
    # Map of header text to section type
    header_mapping = {
        'strategic overview': 'strategic_overview',
        'competitors analysis': 'competitors_analysis',
        'competitor analysis': 'competitors_analysis',
        'product differentiation': 'product_differentiation',
        'product differentiation ideas': 'product_differentiation',
        'detailed personas': 'detailed_personas',
        'personas': 'detailed_personas',
        'market snapshot': 'market_snapshot',
        'audience analysis': 'audience_analysis',
    }
    
    for line in lines:
        # Check for section headers (## or # followed by section name)
        stripped = line.strip()
        if stripped.startswith('#'):
            # Extract header text
            header_text = stripped.lstrip('#').strip().lower()
            # Remove numbering like "1. " or "1) "
            if header_text and header_text[0].isdigit():
                header_text = header_text.split('.', 1)[-1].strip()
                header_text = header_text.split(')', 1)[-1].strip()
            
            # Check if this matches a known section
            matched_section = None
            for key in header_mapping:
                if key in header_text:
                    matched_section = header_mapping[key]
                    break
            
            if matched_section:
                # Save previous section if exists
                if current_section:
                    sections.append({
                        'section_type': current_section,
                        'title': next((t for st, t in QUICK_REPORT_SECTIONS if st == current_section), current_section),
                        'content': '\n'.join(current_content).strip()
                    })
                
                current_section = matched_section
                current_content = []
            else:
                # Not a main section header, include in content
                if current_section:
                    current_content.append(line)
        else:
            if current_section:
                current_content.append(line)
    
    # Save last section
    if current_section:
        sections.append({
            'section_type': current_section,
            'title': next((t for st, t in QUICK_REPORT_SECTIONS if st == current_section), current_section),
            'content': '\n'.join(current_content).strip()
        })
    
    # If no sections were parsed, treat entire content as one section
    if not sections and markdown_content.strip():
        sections.append({
            'section_type': 'full_report',
            'title': 'Market Research Report',
            'content': markdown_content.strip()
        })
    
    return sections
