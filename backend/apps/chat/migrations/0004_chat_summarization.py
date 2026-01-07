# Generated for chat summarization feature (token optimization)

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    """
    Migration for the Segmented Chat Summarization feature.
    
    Creates:
    - ChatSummary model for storing compressed message batches
    - Adds sequence field to ChatMessage for ordering
    - Adds summary FK to ChatMessage for linking to summaries
    - Adds indexes for efficient querying
    """

    dependencies = [
        ('chat', '0003_add_active_modes_field'),
        ('projects', '0001_initial'),
    ]

    operations = [
        # Create ChatSummary table
        migrations.CreateModel(
            name='ChatSummary',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('summary_text', models.TextField()),
                ('start_sequence', models.IntegerField(help_text='Starting message sequence number in this batch')),
                ('end_sequence', models.IntegerField(help_text='Ending message sequence number in this batch')),
                ('message_count', models.IntegerField(default=0, help_text='Number of messages summarized')),
                ('input_tokens', models.IntegerField(default=0, help_text='Estimated input tokens before summarization')),
                ('output_tokens', models.IntegerField(default=0, help_text='Tokens in the summary')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chat_summaries', to='projects.project')),
            ],
            options={
                'db_table': 'chat_summaries',
                'ordering': ['start_sequence'],
            },
        ),
        
        # Add sequence field to ChatMessage
        migrations.AddField(
            model_name='chatmessage',
            name='sequence',
            field=models.IntegerField(default=0, help_text='Message sequence number within project'),
        ),
        
        # Add summary FK to ChatMessage
        migrations.AddField(
            model_name='chatmessage',
            name='summary',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='messages',
                to='chat.chatsummary'
            ),
        ),
        
        # Add indexes for efficient querying
        migrations.AddIndex(
            model_name='chatmessage',
            index=models.Index(fields=['project', 'sequence'], name='chat_msg_proj_seq_idx'),
        ),
        migrations.AddIndex(
            model_name='chatmessage',
            index=models.Index(fields=['project', 'summary'], name='chat_msg_proj_sum_idx'),
        ),
    ]
