"""
Celery tasks for chat AI processing using Metis AI with function calling.

Includes:
- process_chat_message: Main chat processing task
- process_chat_summary: Background task for summarizing old messages
"""
from celery import shared_task
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import logging
import json

logger = logging.getLogger(__name__)


@shared_task(bind=True, time_limit=60, soft_time_limit=50)
def process_chat_summary(self, project_id):
    """
    Background task to summarize old chat messages.
    
    Called after new messages are added to check if summarization is needed.
    Uses SummarizationService to compress message batches.
    """
    from services.summarization_service import summarization_service
    
    logger.info(f"📝 Processing chat summary for project {project_id}")
    
    try:
        result = summarization_service.process_project_backlog(project_id)
        
        if result.get('summaries_created', 0) > 0:
            logger.info(
                f"✅ Created {result['summaries_created']} summaries, "
                f"processed {result['messages_processed']} messages, "
                f"saved ~{result['tokens_saved']} tokens"
            )
        else:
            logger.debug(f"No summarization needed: {result.get('reason', 'unknown')}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Chat summary processing failed: {e}", exc_info=True)
        raise


@shared_task(bind=True, time_limit=120, soft_time_limit=100)
def process_chat_message(self, project_id, user_id, message, active_modes=None):
    """Process user message with Metis AI and respond using function calling."""
    from .models import ChatMessage
    from apps.projects.models import Project
    from apps.users.models import User
    from django.conf import settings
    from services.chat_modes import get_active_modes_config, get_system_prompt_for_modes
    from services.ai_functions import process_function_call
    from services.summarization_service import summarization_service
    import openai
    
    # Default to empty list if no modes provided
    if active_modes is None:
        active_modes = []
    
    channel_layer = get_channel_layer()
    room_group = f"project_{project_id}"
    
    try:
        project = Project.objects.get(id=project_id)
        user = User.objects.get(id=user_id)
        inputs = project.inputs
        
        # Check input completion
        is_complete = inputs.completion_status == 'complete'
        
        # Get mode-based configuration
        mode_config = get_active_modes_config(active_modes)
        tools = mode_config.get('tools', [])
        
        # Build system prompt (base + mode-specific additions)
        system_prompt = get_system_prompt_for_modes(inputs, is_complete, active_modes)
        
        logger.info(f"🎯 Active modes: {active_modes}, tools available: {len(tools)}")
        
        # =================================================================
        # TOKEN OPTIMIZATION: Use summaries + recent messages instead of
        # loading all recent messages. This reduces context size for long
        # conversations while preserving important history.
        # =================================================================
        max_recent = getattr(settings, 'CHAT_RECENT_MESSAGES_LIMIT', 10)
        chat_history = summarization_service.build_context_with_summaries(
            project_id=str(project_id),
            max_recent_messages=max_recent
        )
        
        logger.info(f"📊 Context built: {len(chat_history)} items (summaries + recent messages)")
        
        # Use Metis AI (OpenAI-compatible API)
        metis_api_key = getattr(settings, 'METIS_API_KEY', '')
        metis_base_url = getattr(settings, 'METIS_BASE_URL', 'https://api.metisai.ir/openai/v1')
        metis_model = getattr(settings, 'METIS_MODEL', 'gpt-4o-mini')
        
        logger.info(f"🤖 Using Metis AI with function tools: model={metis_model}")
        
        bot_response = None
        extracted_fields = {}
        
        if metis_api_key:
            try:
                # Create OpenAI client with Metis base URL
                client = openai.OpenAI(
                    api_key=metis_api_key,
                    base_url=metis_base_url
                )
                
                # Use tools from active modes (empty list if no modes active)
                # Note: tools variable already set above from mode_config
                
                # Build messages payload
                messages = [
                    {"role": "system", "content": system_prompt},
                    *chat_history,
                    {"role": "user", "content": message}
                ]
                
                # Make API call with function tools
                response = client.chat.completions.create(
                    model=metis_model,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto" if tools else None,
                    max_tokens=500,
                    temperature=0.7
                )
                
                assistant_message = response.choices[0].message
                
                # Check if AI wants to call a function
                if assistant_message.tool_calls:
                    logger.info(f"🔧 AI requested {len(assistant_message.tool_calls)} function call(s)")
                    
                    for tool_call in assistant_message.tool_calls:
                        function_name = tool_call.function.name
                        try:
                            arguments = json.loads(tool_call.function.arguments)
                        except json.JSONDecodeError:
                            arguments = {}
                            logger.warning(f"⚠️ Failed to parse function arguments")
                        
                        logger.info(f"📝 Function call: {function_name} with args: {arguments}")
                        
                        # Process the function call
                        updated_fields = process_function_call(function_name, arguments, inputs)
                        extracted_fields.update(updated_fields)
                        
                        # Broadcast auto_fill events for each updated field
                        for field, value in updated_fields.items():
                            async_to_sync(channel_layer.group_send)(
                                room_group,
                                {
                                    'type': 'auto_fill',
                                    'field': field,
                                    'value': value,
                                    'confidence': 0.95
                                }
                            )
                            logger.info(f"📤 Broadcast auto_fill for {field}")
                    
                    # Get AI's text response (it may have provided one along with function calls)
                    if assistant_message.content:
                        bot_response = assistant_message.content
                    else:
                        # If no text response, make another call to get conversational response
                        # Add the function results to context
                        messages.append({
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": tc.id,
                                    "type": "function",
                                    "function": {
                                        "name": tc.function.name,
                                        "arguments": tc.function.arguments
                                    }
                                }
                                for tc in assistant_message.tool_calls
                            ]
                        })
                        
                        # Add tool results
                        for tool_call in assistant_message.tool_calls:
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": json.dumps({"status": "success", "updated_fields": list(extracted_fields.keys())})
                            })
                        
                        # Get final response
                        final_response = client.chat.completions.create(
                            model=metis_model,
                            messages=messages,
                            max_tokens=300,
                            temperature=0.7
                        )
                        bot_response = final_response.choices[0].message.content
                else:
                    # No function calls, just use the text response
                    bot_response = assistant_message.content
                
                logger.info(f"✅ AI response: {len(bot_response) if bot_response else 0} chars, extracted fields: {list(extracted_fields.keys())}")
                
            except Exception as api_error:
                logger.error(f"❌ Metis AI API error: {api_error}", exc_info=True)
                bot_response = "I'm having trouble connecting to my AI brain right now. Please try again in a moment."
        else:
            # Mock response for development (no API key)
            logger.warning("⚠️ No METIS_API_KEY configured, using mock responses")
            bot_response = generate_mock_response(inputs, message)
        
        # Ensure we have a response
        if not bot_response:
            bot_response = "I've updated your project information. What else can you tell me about your startup?"
        
        # Save bot response with active modes
        bot_msg = ChatMessage.objects.create(
            project_id=project_id,
            user=None,
            message=bot_response,
            is_bot=True,
            message_type='text',
            metadata={'extracted_fields': extracted_fields} if extracted_fields else {},
            active_modes=active_modes  # Save which modes were active
        )
        
        # Broadcast bot response
        async_to_sync(channel_layer.group_send)(
            room_group,
            {
                'type': 'chat_message',
                'message': {
                    'id': str(bot_msg.id),
                    'message': bot_response,
                    'is_bot': True,
                    'user_id': None,
                    'created_at': bot_msg.created_at.isoformat(),
                    'extracted_fields': extracted_fields,
                    'active_modes': active_modes  # Include modes in broadcast
                }
            }
        )
        
        # Clear thinking status
        async_to_sync(channel_layer.group_send)(
            room_group,
            {
                'type': 'status_update',
                'status': 'idle'
            }
        )
        
        # =================================================================
        # TOKEN OPTIMIZATION: Trigger background summarization check
        # This runs async and won't block the response
        # =================================================================
        process_chat_summary.delay(str(project_id))
        
        return {"status": "success", "extracted_fields": extracted_fields}
        
    except Exception as e:
        logger.error(f"❌ Chat processing error: {e}", exc_info=True)
        
        # Send error message
        async_to_sync(channel_layer.group_send)(
            room_group,
            {
                'type': 'chat_message',
                'message': {
                    'id': None,
                    'message': "Sorry, I encountered an error processing your message. Please try again.",
                    'is_bot': True,
                    'user_id': None,
                    'message_type': 'error'
                }
            }
        )
        
        async_to_sync(channel_layer.group_send)(
            room_group,
            {
                'type': 'status_update',
                'status': 'idle'
            }
        )
        
        raise


def generate_mock_response(inputs, user_message: str) -> str:
    """Generate mock AI response when no API key is configured."""
    
    # Check which field to ask about next
    if not inputs.startup_name:
        return f"Hi there! 👋 I'm your MarketNavigator AI assistant. I'll help you set up your market research project.\n\nLet's start with the basics - what's the **name of your startup**?"
    
    if not inputs.startup_description:
        return f"**{inputs.startup_name}** - great name! 🎉\n\nNow, can you tell me what {inputs.startup_name} does? Just a brief description in 2-3 sentences."
    
    if not inputs.target_audience:
        return "Excellent description! Now, **who is your target audience**? Who are the primary customers you're building for?"
    
    if not inputs.current_stage:
        return "Got it! What **stage** is your startup at?\n\n• **Idea** - Still conceptualizing\n• **MVP** - Building minimum viable product\n• **Early-Stage** - Just launched\n• **Growth** - Scaling up\n• **Scale-Up** - Established and expanding"
    
    if not inputs.business_model:
        return "Perfect! How does your startup **make money**? What's your business model?"
    
    if not inputs.geographic_focus:
        return "Great business model! Which **geographic markets** are you focusing on? (e.g., North America, Europe, Global)"
    
    if not inputs.research_goal:
        return "Almost done! What's your main **research goal**? What do you want to learn from this market analysis?"
    
    if not inputs.time_range:
        return "What **time range** should we analyze?\n\n• Last month\n• Last 3 months\n• Last 6 months\n• Last year\n• All time"
    
    # All required fields are complete!
    return f"""🎉 **Excellent!** All your project inputs are complete for **{inputs.startup_name}**!

You can now start generating research reports using the panels on the left:

• **Crunchbase Analysis** - Find competitors and funding data
• **Tracxn Insights** - Startup landscape analysis
• **Social Analysis** - Brand mentions and sentiment
• **Pitch Deck** - Auto-generate investor pitch

Click "Start Analysis" on any panel to begin! 🚀"""
