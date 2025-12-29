"""
AI Function Tools for project input auto-fill.
Uses OpenAI function calling to extract project inputs from natural conversation.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# OpenAI Function Tool Schema for extracting project inputs
FILL_PROJECT_INPUTS_TOOL = {
    "type": "function",
    "function": {
        "name": "fill_project_inputs",
        "description": """Extract and fill project input fields from the user's conversation. 
Call this function whenever the user provides information about their startup that can fill any of the project input fields.
Only include fields that were explicitly mentioned or can be clearly inferred from the conversation.""",
        "parameters": {
            "type": "object",
            "properties": {
                "startup_name": {
                    "type": "string",
                    "description": "The name of the startup/company"
                },
                "startup_description": {
                    "type": "string",
                    "description": "A 2-3 sentence description of what the startup does"
                },
                "target_audience": {
                    "type": "string",
                    "description": "Who are the primary customers or target users"
                },
                "current_stage": {
                    "type": "string",
                    "enum": ["idea", "mvp", "early_stage", "growth", "scale_up"],
                    "description": "Current stage of the startup"
                },
                "business_model": {
                    "type": "string",
                    "description": "How the startup makes money"
                },
                "geographic_focus": {
                    "type": "string",
                    "description": "Target geographic markets or regions"
                },
                "research_goal": {
                    "type": "string",
                    "description": "What the user wants to learn from market research"
                },
                "time_range": {
                    "type": "string",
                    "enum": ["1mo", "3mo", "6mo", "1yr", "all"],
                    "description": "Time range for analysis: 1mo (last month), 3mo (last 3 months), 6mo (last 6 months), 1yr (last year), all (all time)"
                },
                "inspiration_sources": {
                    "type": "string",
                    "description": "Similar companies or competitors to analyze (optional)"
                }
            },
            "additionalProperties": False
        }
    }
}

# OpenAI Function Tool Schema for generating Crunchbase search parameters
GENERATE_CRUNCHBASE_PARAMS_TOOL = {
    "type": "function",
    "function": {
        "name": "generate_crunchbase_params",
        "description": """Generate optimized keywords and target description for Crunchbase company similarity search.
Based on the startup's information, generate:
1. 8-12 diverse keywords covering: core technology, industry vertical, business model, target market
2. A 2-3 sentence target description optimized for semantic similarity matching

KEYWORD FORMAT RULES:
- Use SPACE-SEPARATED compound words (never camelCase or joined words)
- Include both broad category terms and specific niche terms
- Cover multiple aspects: technology, industry, business model, target audience

EXAMPLES:
- AI storytelling startup → ['AI Storytelling', 'Generative AI', 'Digital Storytelling', 'Creative AI', 'Narrative Tech', 'AI Content Creation', 'Story Generator', 'Entertainment AI']
- Pet services platform → ['Pet Care', 'Pet Products', 'AI for Pets', 'Pet Health', 'Pet Subscription', 'Animal Wellness', 'Pet Training', 'Smart Pet Care']""",
        "parameters": {
            "type": "object",
            "properties": {
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "8-12 diverse search keywords for finding similar companies"
                },
                "target_description": {
                    "type": "string",
                    "description": "2-3 sentence description optimized for semantic similarity search"
                }
            },
            "required": ["keywords", "target_description"],
            "additionalProperties": False
        }
    }
}

# All available tools for the chat AI
AI_TOOLS = [FILL_PROJECT_INPUTS_TOOL]

# Tools specifically for generating Crunchbase parameters
CRUNCHBASE_TOOLS = [GENERATE_CRUNCHBASE_PARAMS_TOOL]


def get_ai_tools():
    """Get all AI function tools for chat completion."""
    return AI_TOOLS


def process_function_call(function_name: str, arguments: dict, project_inputs) -> dict:
    """
    Process an AI function call and update project inputs.
    
    Args:
        function_name: Name of the function called
        arguments: Function arguments from AI
        project_inputs: ProjectInputs model instance
        
    Returns:
        Dict with updated fields and their values
    """
    if function_name != "fill_project_inputs":
        logger.warning(f"Unknown function call: {function_name}")
        return {}
    
    updated_fields = {}
    
    # Map of field names to their database fields
    field_mapping = {
        "startup_name": "startup_name",
        "startup_description": "startup_description",
        "target_audience": "target_audience",
        "current_stage": "current_stage",
        "business_model": "business_model",
        "geographic_focus": "geographic_focus",
        "research_goal": "research_goal",
        "time_range": "time_range",
        "inspiration_sources": "inspiration_sources"
    }
    
    # Get current ai_generated_fields or initialize
    ai_generated = project_inputs.ai_generated_fields or {}
    logger.info(f"📋 Current ai_generated_fields before update: {ai_generated}")
    
    for arg_name, db_field in field_mapping.items():
        if arg_name in arguments and arguments[arg_name]:
            value = arguments[arg_name].strip() if isinstance(arguments[arg_name], str) else arguments[arg_name]
            
            # Only update if value is meaningful
            if value and len(str(value)) > 0:
                # Always update the field when AI provides a value (allows updates/changes)
                setattr(project_inputs, db_field, value)
                updated_fields[db_field] = value
                # Mark this field as AI-generated
                ai_generated[db_field] = True
                logger.info(f"✅ Auto-filled {db_field}: {value[:50]}..." if len(str(value)) > 50 else f"✅ Auto-filled {db_field}: {value}")
    
    if updated_fields:
        # Save the ai_generated_fields tracking
        project_inputs.ai_generated_fields = ai_generated
        project_inputs.filled_via = 'ai_chat' if not project_inputs.filled_via else 'mixed'
        project_inputs.save()
        logger.info(f"💾 Saved {len(updated_fields)} fields. ai_generated_fields now: {project_inputs.ai_generated_fields}")
    
    return updated_fields


def get_system_prompt_with_tools(inputs, is_complete: bool) -> str:
    """
    Generate system prompt that encourages tool usage for input extraction.
    """
    if not is_complete:
        return f"""You are a friendly AI assistant helping entrepreneurs set up their market research project.

Your primary job is to collect and UPDATE project information through the fill_project_inputs function.

**CRITICAL RULES - READ CAREFULLY:**
1. When the user provides ANY information about their startup, you MUST call the fill_project_inputs function to save it.
2. When the user asks to UPDATE, CHANGE, or MODIFY any field, you MUST call the fill_project_inputs function with the new value.
3. NEVER just respond with text saying you've updated something - you MUST actually call the function.
4. If user says "change startup name to X" or "update the description to Y" - CALL THE FUNCTION, don't just say you did it.

**Fields you can fill/update:**
- startup_name: The name of the startup
- startup_description: What the startup does
- target_audience: Who are the customers
- current_stage: idea, mvp, early_stage, growth, or scale_up
- business_model: How they make money
- geographic_focus: Target markets/regions
- research_goal: What they want to learn
- time_range: 1mo, 3mo, 6mo, 1yr, or all
- inspiration_sources: Similar companies/competitors

**Current collected information:**
- Startup Name: {inputs.startup_name or '❌ Not set'}
- Description: {inputs.startup_description or '❌ Not set'}
- Target Audience: {inputs.target_audience or '❌ Not set'}
- Stage: {inputs.current_stage or '❌ Not set'}
- Business Model: {inputs.business_model or '❌ Not set'}
- Geographic Focus: {inputs.geographic_focus or '❌ Not set'}
- Research Goal: {inputs.research_goal or '❌ Not set'}
- Time Range: {inputs.time_range or '❌ Not set'}
- Competitors: {inputs.inspiration_sources or '(Optional) Not set'}

**Guidelines:**
1. Be conversational and encouraging
2. ALWAYS call fill_project_inputs when extracting OR updating information
3. Confirm what you've saved after calling the function
4. Ask ONE follow-up question at a time

Start by greeting the user and asking about their startup."""

    else:
        return f"""You are an AI assistant helping entrepreneurs with their market research project.

The user has completed their project inputs, but they can still update them anytime.

**CRITICAL**: If the user asks to UPDATE, CHANGE, or MODIFY any field, you MUST call the fill_project_inputs function.
DON'T just say you've updated something - ACTUALLY CALL THE FUNCTION.

**Current project information:**
- Startup Name: {inputs.startup_name}
- Description: {inputs.startup_description[:100] + '...' if len(inputs.startup_description) > 100 else inputs.startup_description}
- Target Audience: {inputs.target_audience}
- Stage: {inputs.current_stage}
- Business Model: {inputs.business_model}
- Geographic Focus: {inputs.geographic_focus}
- Research Goal: {inputs.research_goal}
- Time Range: {inputs.time_range}
- Competitors: {inputs.inspiration_sources}

You can:
- Update/modify any project input fields (MUST use fill_project_inputs function)
- Answer questions about their reports
- Explain research findings
- Help interpret competitor analysis
- Suggest next steps

Be helpful, concise, and actionable."""


async def generate_crunchbase_params_from_inputs(inputs) -> dict:
    """
    Generate optimized Crunchbase search parameters (keywords + target_description)
    from project inputs using AI.
    
    Args:
        inputs: ProjectInput model instance
        
    Returns:
        Dict with 'keywords' (list of strings) and 'target_description' (string)
    """
    import json
    from openai import AsyncOpenAI
    from django.conf import settings
    
    api_key = getattr(settings, 'OPENAI_API_KEY', None)
    if not api_key:
        logger.error("OpenAI API key not configured")
        return {"keywords": [], "target_description": "", "error": "OpenAI API key not configured"}
    
    client = AsyncOpenAI(api_key=api_key)
    
    # Build context from project inputs
    context = f"""Startup Information:
- Name: {inputs.startup_name or 'Not specified'}
- Description: {inputs.startup_description or 'Not specified'}
- Target Audience: {inputs.target_audience or 'Not specified'}
- Current Stage: {inputs.current_stage or 'Not specified'}
- Business Model: {inputs.business_model or 'Not specified'}
- Geographic Focus: {inputs.geographic_focus or 'Not specified'}
- Research Goal: {inputs.research_goal or 'Not specified'}
- Competitors/Inspiration: {inputs.inspiration_sources or 'Not specified'}

Based on this startup information, generate optimized search parameters for finding similar companies on Crunchbase."""

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert at analyzing startups and generating search keywords for competitive research."},
                {"role": "user", "content": context}
            ],
            tools=CRUNCHBASE_TOOLS,
            tool_choice={"type": "function", "function": {"name": "generate_crunchbase_params"}}
        )
        
        if response.choices and response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0]
            arguments = json.loads(tool_call.function.arguments)
            
            keywords = arguments.get("keywords", [])
            target_description = arguments.get("target_description", "")
            
            logger.info(f"✅ Generated {len(keywords)} keywords for Crunchbase search")
            logger.info(f"📝 Target description: {target_description[:100]}...")
            
            return {
                "keywords": keywords,
                "target_description": target_description,
                "success": True
            }
        else:
            logger.warning("No tool call in AI response")
            return {"keywords": [], "target_description": "", "error": "No tool call in response"}
            
    except Exception as e:
        logger.error(f"❌ Error generating Crunchbase params: {e}")
        return {"keywords": [], "target_description": "", "error": str(e)}

