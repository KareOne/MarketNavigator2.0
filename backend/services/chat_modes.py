"""
Chat Modes Registry - Extensible system for chat mode configurations.

Each mode defines:
- System prompt additions
- Available tools/functions
- UI metadata (name, icon, description)
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class ChatMode:
    """Definition of a chat mode."""
    id: str
    name: str
    description: str
    icon: str
    system_prompt: str
    tools: List[Dict[str, Any]] = field(default_factory=list)
    enabled: bool = True
    priority: int = 0  # Higher priority modes' prompts come first


# Import the editing tools
from services.ai_functions import FILL_PROJECT_INPUTS_TOOL


# ============================================================================
# MODE DEFINITIONS - Add new modes here
# ============================================================================

EDITING_MODE_PROMPT = """You are in EDITING MODE. You have the ability to modify project input fields.

**CRITICAL RULES:**
1. When the user provides ANY information about their startup, CALL the fill_project_inputs function.
2. When the user asks to UPDATE, CHANGE, or MODIFY any field, CALL the fill_project_inputs function.
3. NEVER just respond with text saying you've updated something - you MUST actually call the function.
4. If user says "change startup name to X" or "update the description to Y" - CALL THE FUNCTION.

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

Always confirm what you've saved after calling the function."""


CHAT_MODES: Dict[str, ChatMode] = {
    "editing": ChatMode(
        id="editing",
        name="Editing Mode",
        description="AI can modify project input fields",
        icon="✏️",
        system_prompt=EDITING_MODE_PROMPT,
        tools=[FILL_PROJECT_INPUTS_TOOL],
        enabled=True,
        priority=10
    ),
    # Future modes can be added here, e.g.:
    # "research": ChatMode(
    #     id="research",
    #     name="Research Mode",
    #     description="AI can search and analyze market data",
    #     icon="🔍",
    #     system_prompt="...",
    #     tools=[...],
    #     enabled=True,
    #     priority=5
    # ),
}


# ============================================================================
# PUBLIC API FUNCTIONS
# ============================================================================

def get_available_modes() -> List[Dict[str, Any]]:
    """
    Get all available chat modes for frontend display.
    
    Returns:
        List of mode configurations (without internal details like full prompts)
    """
    return [
        {
            "id": mode.id,
            "name": mode.name,
            "description": mode.description,
            "icon": mode.icon,
            "enabled": mode.enabled
        }
        for mode in CHAT_MODES.values()
        if mode.enabled
    ]


def get_mode_config(mode_id: str) -> Optional[ChatMode]:
    """Get a specific mode configuration."""
    return CHAT_MODES.get(mode_id)


def get_active_modes_config(active_mode_ids: List[str]) -> Dict[str, Any]:
    """
    Get combined configuration for multiple active modes.
    
    Args:
        active_mode_ids: List of mode IDs that are currently active
        
    Returns:
        Dict with combined 'system_prompt_addition' and 'tools' from all active modes
    """
    if not active_mode_ids:
        return {
            "system_prompt_addition": "",
            "tools": []
        }
    
    # Filter to valid, enabled modes and sort by priority
    active_modes = [
        CHAT_MODES[mode_id] 
        for mode_id in active_mode_ids 
        if mode_id in CHAT_MODES and CHAT_MODES[mode_id].enabled
    ]
    active_modes.sort(key=lambda m: -m.priority)  # Higher priority first
    
    # Combine system prompts
    prompt_parts = [mode.system_prompt for mode in active_modes if mode.system_prompt]
    combined_prompt = "\n\n".join(prompt_parts)
    
    # Combine tools (deduplicate by function name)
    seen_tools = set()
    combined_tools = []
    for mode in active_modes:
        for tool in mode.tools:
            tool_name = tool.get("function", {}).get("name", "")
            if tool_name and tool_name not in seen_tools:
                seen_tools.add(tool_name)
                combined_tools.append(tool)
    
    logger.info(f"📦 Active modes: {[m.id for m in active_modes]}, tools: {list(seen_tools)}")
    
    return {
        "system_prompt_addition": combined_prompt,
        "tools": combined_tools
    }


def get_base_system_prompt(inputs, is_complete: bool) -> str:
    """
    Get the base system prompt (without mode-specific additions).
    This is used when NO modes are active.
    """
    if not is_complete:
        return f"""You are a friendly AI assistant helping entrepreneurs with their market research project.

**Current project information:**
- Startup Name: {inputs.startup_name or '(Not set)'}
- Description: {inputs.startup_description or '(Not set)'}
- Target Audience: {inputs.target_audience or '(Not set)'}
- Stage: {inputs.current_stage or '(Not set)'}
- Business Model: {inputs.business_model or '(Not set)'}
- Geographic Focus: {inputs.geographic_focus or '(Not set)'}
- Research Goal: {inputs.research_goal or '(Not set)'}
- Time Range: {inputs.time_range or '(Not set)'}
- Competitors: {inputs.inspiration_sources or '(Not set)'}

You can answer questions about their project and research, but you are currently in a read-only mode.
To modify project inputs, the user needs to enable "Editing Mode".

Be helpful, concise, and conversational."""

    else:
        return f"""You are an AI assistant helping entrepreneurs with their market research project.

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
- Answer questions about their project
- Explain research findings
- Help interpret competitor analysis
- Suggest next steps

Note: To modify project inputs, the user needs to enable "Editing Mode".

Be helpful, concise, and actionable."""


def get_system_prompt_for_modes(inputs, is_complete: bool, active_mode_ids: List[str]) -> str:
    """
    Get the full system prompt combining base prompt with any active mode prompts.
    """
    base_prompt = get_base_system_prompt(inputs, is_complete)
    
    if not active_mode_ids:
        return base_prompt
    
    mode_config = get_active_modes_config(active_mode_ids)
    mode_addition = mode_config.get("system_prompt_addition", "")
    
    if mode_addition:
        return f"{base_prompt}\n\n---\n\n{mode_addition}"
    
    return base_prompt
