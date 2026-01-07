"""
Summarization Service - Standalone AI service for chat message compression.

This service handles the "Segmented Summary" optimization:
- Batches of N messages are compressed into single summary messages
- Uses a fast/cheap model (gemini-2.0-flash) for summarization
- Reduces token usage for long conversations while preserving context

Example: For 73 messages with batch_size=10:
- Summaries: [1-10], [11-20], ..., [61-70] (7 summaries)
- Raw messages: 71, 72, 73 (3 messages)
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from django.conf import settings
from openai import OpenAI
import json
import requests

logger = logging.getLogger(__name__)


class SummarizationService:
    """
    Standalone AI service for summarizing chat message batches.
    
    Uses a fast, cost-effective model (gemini-2.0-flash by default) to compress
    older conversation history into concise summaries.
    """
    
    def __init__(self):
        # Get summarization-specific settings
        self.model = getattr(settings, 'SUMMARIZATION_MODEL', 'gemini-2.0-flash')
        self.batch_size = getattr(settings, 'CHAT_SUMMARY_BATCH_SIZE', 10)
        
        # Try Google AI Studio first (direct API)
        self.google_api_key = getattr(settings, 'GOOGLE_AI_API_KEY', None)
        self.google_base_url = getattr(settings, 'GOOGLE_AI_BASE_URL', None)
        
        if self.google_api_key and self.google_base_url:
            self.client = None  # We'll use requests directly
            self.provider = 'google'
            logger.info(f"SummarizationService initialized with Google AI Studio ({self.model})")
        else:
            # Try Liara AI (OpenAI-compatible)
            self.api_key = getattr(settings, 'LIARA_API_KEY', None)
            self.base_url = getattr(settings, 'LIARA_BASE_URL', None)
            
            if self.api_key and self.base_url:
                self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
                self.provider = 'liara'
                logger.info(f"SummarizationService initialized with Liara AI ({self.model})")
            else:
                # Fallback to OpenAI
                self.api_key = getattr(settings, 'OPENAI_API_KEY', '')
                self.base_url = None
                
                if self.api_key:
                    self.client = OpenAI(api_key=self.api_key)
                    self.provider = 'openai'
                    logger.info(f"SummarizationService initialized with OpenAI ({self.model})")
                else:
                    self.client = None
                    self.provider = None
                    logger.warning("SummarizationService: No API key configured")
    
    def summarize_messages(self, messages: List[Dict[str, Any]], project_context: str = "") -> Tuple[str, int, int]:
        """
        Summarize a batch of messages into a concise summary.
        
        Args:
            messages: List of message dicts with 'role' (user/assistant) and 'content'
            project_context: Optional context about the project for better summaries
            
        Returns:
            Tuple of (summary_text, input_tokens_estimate, output_tokens_estimate)
        """
        if not self.client:
            logger.error("SummarizationService: No client available")
            return "", 0, 0
        
        if not messages:
            return "", 0, 0
        
        # Format messages for summarization
        conversation_text = self._format_messages_for_summary(messages)
        
        # Estimate input tokens (rough: 4 chars = 1 token)
        input_tokens = len(conversation_text) // 4
        
        system_prompt = """You are a conversation summarizer. Your job is to compress chat conversations into concise summaries that preserve:

1. Key information shared (names, descriptions, decisions)
2. Important questions asked and answered
3. Any project inputs or configurations mentioned
4. The overall flow and context of the discussion

Rules:
- Be concise but complete - aim for 100-200 words
- Use bullet points for clarity
- Preserve specific names, numbers, and technical details
- Format: Start with "Previous conversation summary:" followed by the summary
- Do NOT include pleasantries or filler content
- Focus on information that would be useful for continuing the conversation"""

        user_prompt = f"""Summarize this conversation segment:

{conversation_text}

{f"Project Context: {project_context}" if project_context else ""}"""

        try:
            # Use Google AI Studio API if configured
            if self.provider == 'google':
                summary = self._call_google_ai(system_prompt, user_prompt)
            else:
                # Use OpenAI-compatible API (Liara or OpenAI)
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.3,
                    max_tokens=500
                )
                summary = response.choices[0].message.content
            
            output_tokens = len(summary) // 4  # Rough estimate
            
            logger.info(f"Summarized {len(messages)} messages: {input_tokens} -> {output_tokens} tokens")
            return summary, input_tokens, output_tokens
            
        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            # Fallback: create a simple concatenated summary
            fallback = self._create_fallback_summary(messages)
            return fallback, input_tokens, len(fallback) // 4
    
    def _call_google_ai(self, system_prompt: str, user_prompt: str) -> str:
        """Call Google AI Studio API directly."""
        url = f"{self.google_base_url}/models/{self.model}:generateContent"
        headers = {
            'Content-Type': 'application/json',
            'X-goog-api-key': self.google_api_key
        }
        
        # Combine system and user prompts for Google AI format
        combined_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": combined_prompt}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 500
            }
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        summary = result['candidates'][0]['content']['parts'][0]['text']
        return summary
    
    def _format_messages_for_summary(self, messages: List[Dict[str, Any]]) -> str:
        """Format messages into a readable conversation transcript."""
        lines = []
        for msg in messages:
            role = "User" if msg.get('role') == 'user' else "Assistant"
            content = msg.get('content', msg.get('message', ''))
            # Truncate very long messages
            if len(content) > 500:
                content = content[:500] + "..."
            lines.append(f"{role}: {content}")
        return "\n\n".join(lines)
    
    def _create_fallback_summary(self, messages: List[Dict[str, Any]]) -> str:
        """Create a simple fallback summary if AI summarization fails."""
        user_msgs = [m for m in messages if m.get('role') == 'user']
        bot_msgs = [m for m in messages if m.get('role') != 'user']
        
        summary_parts = ["Previous conversation summary:"]
        
        if user_msgs:
            first_user = user_msgs[0].get('content', '')[:200]
            summary_parts.append(f"- User discussed: {first_user}...")
        
        if bot_msgs:
            topics = len(bot_msgs)
            summary_parts.append(f"- {topics} assistant responses covering various topics")
        
        return "\n".join(summary_parts)
    
    def process_project_backlog(self, project_id: str) -> Dict[str, Any]:
        """
        Process unsummarized messages for a project and create summaries.
        
        This is the main entry point for the summarization pipeline.
        Called after new messages are added to check if summarization is needed.
        
        Args:
            project_id: The project UUID
            
        Returns:
            Dict with 'summaries_created', 'messages_processed', 'tokens_saved'
        """
        from apps.chat.models import ChatMessage, ChatSummary
        from apps.projects.models import Project
        
        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            logger.error(f"Project {project_id} not found")
            return {'error': 'Project not found'}
        
        # Get unsummarized messages (summary=NULL), ordered by sequence
        unsummarized = ChatMessage.objects.filter(
            project_id=project_id,
            summary__isnull=True
        ).order_by('sequence')
        
        total_unsummarized = unsummarized.count()
        
        # Only process if we have enough messages to create at least one summary
        # while leaving some recent messages unsummarized
        if total_unsummarized < self.batch_size + 3:  # batch_size + buffer
            logger.info(f"Project {project_id}: Only {total_unsummarized} unsummarized messages, skipping")
            return {
                'summaries_created': 0,
                'messages_processed': 0,
                'tokens_saved': 0,
                'reason': 'Not enough messages'
            }
        
        # Calculate how many complete batches we can create
        # Leave at least 3 messages unsummarized for recent context
        messages_to_summarize = total_unsummarized - 3
        batches_to_create = messages_to_summarize // self.batch_size
        
        if batches_to_create == 0:
            return {
                'summaries_created': 0,
                'messages_processed': 0,
                'tokens_saved': 0,
                'reason': 'Not enough complete batches'
            }
        
        # Get project context for better summaries
        project_context = self._get_project_context(project)
        
        results = {
            'summaries_created': 0,
            'messages_processed': 0,
            'tokens_saved': 0
        }
        
        # Process each batch
        messages_list = list(unsummarized[:batches_to_create * self.batch_size])
        
        for batch_num in range(batches_to_create):
            batch_start = batch_num * self.batch_size
            batch_end = batch_start + self.batch_size
            batch_messages = messages_list[batch_start:batch_end]
            
            if not batch_messages:
                continue
            
            # Format for summarization
            formatted = [
                {
                    'role': 'assistant' if m.is_bot else 'user',
                    'content': m.message
                }
                for m in batch_messages
            ]
            
            # Generate summary
            summary_text, input_tokens, output_tokens = self.summarize_messages(
                formatted,
                project_context
            )
            
            if not summary_text:
                logger.warning(f"Empty summary for batch {batch_num}, skipping")
                continue
            
            # Create ChatSummary record
            start_seq = batch_messages[0].sequence
            end_seq = batch_messages[-1].sequence
            
            chat_summary = ChatSummary.objects.create(
                project=project,
                summary_text=summary_text,
                start_sequence=start_seq,
                end_sequence=end_seq,
                message_count=len(batch_messages),
                input_tokens=input_tokens,
                output_tokens=output_tokens
            )
            
            # Link messages to this summary
            message_ids = [m.id for m in batch_messages]
            ChatMessage.objects.filter(id__in=message_ids).update(summary=chat_summary)
            
            results['summaries_created'] += 1
            results['messages_processed'] += len(batch_messages)
            results['tokens_saved'] += (input_tokens - output_tokens)
            
            logger.info(f"Created summary {chat_summary.id} for messages {start_seq}-{end_seq}")
        
        return results
    
    def _get_project_context(self, project) -> str:
        """Get brief project context for better summaries."""
        try:
            inputs = project.inputs
            parts = []
            if inputs.startup_name:
                parts.append(f"Startup: {inputs.startup_name}")
            if inputs.startup_description:
                parts.append(f"Description: {inputs.startup_description[:100]}")
            return "; ".join(parts) if parts else ""
        except Exception:
            return ""
    
    def build_context_with_summaries(self, project_id: str, max_recent_messages: int = 10) -> List[Dict[str, str]]:
        """
        Build conversation context using summaries + recent messages.
        
        This is used when constructing the prompt for the chat AI.
        
        Args:
            project_id: The project UUID
            max_recent_messages: Maximum number of recent unsummarized messages to include
            
        Returns:
            List of message dicts ready for the AI API
        """
        from apps.chat.models import ChatMessage, ChatSummary
        
        context = []
        
        # Get all summaries for this project, ordered chronologically
        summaries = ChatSummary.objects.filter(
            project_id=project_id
        ).order_by('start_sequence')
        
        # Add summaries as system context
        for summary in summaries:
            context.append({
                'role': 'system',
                'content': f"[Conversation history {summary.start_sequence}-{summary.end_sequence}]\n{summary.summary_text}"
            })
        
        # Get recent unsummarized messages
        recent_messages = ChatMessage.objects.filter(
            project_id=project_id,
            summary__isnull=True
        ).order_by('sequence')[:max_recent_messages]
        
        # Add recent messages as regular conversation
        for msg in recent_messages:
            context.append({
                'role': 'assistant' if msg.is_bot else 'user',
                'content': msg.message
            })
        
        return context


# Singleton instance
summarization_service = SummarizationService()
