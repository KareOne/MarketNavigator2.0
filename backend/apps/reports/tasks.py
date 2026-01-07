"""
Celery tasks for report generation.
Per FINAL_ARCHITECTURE_SPECIFICATION.md and NEW_REPORT_WORKFLOW_SPECIFICATION.md

Uses MVP Scraper Containers (high-scale wrapped):
- services/scrapers/crunchbase_scraper.py for Panel 1
- services/scrapers/tracxn_scraper.py for Panel 2
- services/scrapers/twitter_scraper.py for Panel 3 (Social)
- services/openai_service.py for AI insights
- services/html_generator.py for HTML output
- core/storage.py for S3 storage
"""
from celery import shared_task
from django.utils import timezone
from django.conf import settings
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import asyncio
import logging

import logging
import functools
from django.db import close_old_connections

logger = logging.getLogger(__name__)

def close_db_wrapper(func):
    """Decorator to ensure DB connections are closed after task execution."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        finally:
            close_old_connections()
    return wrapper


def send_progress_update(project_id, report_type, progress, current_step):
    """Send progress update via WebSocket."""
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"project_{project_id}",
            {
                "type": "report_progress",
                "report_type": report_type,
                "progress": progress,
                "current_step": current_step,
            }
        )
    except Exception as e:
        logger.warning(f"Failed to send progress update: {e}")


def update_report_progress(report, progress, current_step):
    """Update report progress in database and send WebSocket update."""
    report.progress = progress
    report.current_step = current_step
    report.save(update_fields=['progress', 'current_step', 'updated_at'])
    
    send_progress_update(
        str(report.project_id),
        report.report_type,
        progress,
        current_step
    )


def get_project_inputs_dict(inputs):
    """Convert ProjectInput to dict for API calls."""
    return {
        'startup_name': inputs.startup_name or '',
        'startup_description': inputs.startup_description or '',
        'target_audience': inputs.target_audience or '',
        'current_stage': inputs.current_stage or '',
        'business_model': inputs.business_model or '',
        'geographic_focus': inputs.geographic_focus or '',
        'research_goal': inputs.research_goal or '',
        'time_range': inputs.time_range or '',
        'inspiration_sources': inputs.inspiration_sources or '',
    }

@shared_task(bind=True, queue='reports')
@close_db_wrapper
def generate_crunchbase_report(self, report_id, user_id):
    """
    Generate Crunchbase analysis report using 13-step MVP pipeline.
    Per FINAL_ARCHITECTURE - Panel 1: Crunchbase Analysis
    
    Pipeline Steps:
    1. Company Overview
    2-7. Per-company reports (Tech, Market Demand, Competitor, Funding, Growth, SWOT)
    8-13. Executive Summaries
    """
    from .models import Report, ReportVersion, ReportAnalysisSection
    from .progress_tracker import ReportProgressTracker
    from apps.users.models import User
    from services.scrapers.crunchbase_scraper import crunchbase_scraper
    from services.crunchbase_analysis import CrunchbaseAnalysisPipeline, generate_analysis_html
    from services.report_storage import report_storage
    from core.storage import storage_service
    
    report = None
    tracker = None
    
    try:
        report = Report.objects.get(id=report_id)
        user = User.objects.get(id=user_id)
        project = report.project
        inputs = project.inputs
        
        # Mark as running
        report.status = 'running'
        report.started_at = timezone.now()
        report.save()
        
        # Initialize progress tracker
        tracker = ReportProgressTracker(report)
        tracker.initialize_steps()
        
        # ===== Step 1: Initialize & Generate Keywords =====
        tracker.start_step('init')
        
        # Check if we need to generate keywords using AI
        if not inputs.extracted_keywords or len(inputs.extracted_keywords) == 0:
            # Generate keywords using Liara AI - NO FALLBACK
            from services.keyword_generator import KeywordGenerator
            
            tracker.update_step_message('init', "Generating AI-powered search keywords...")
            logger.info("🔑 Generating search keywords using Liara AI (forced tool calling)...")
            
            generator = KeywordGenerator()
            project_input_dict = get_project_inputs_dict(inputs)
            search_params = generator.generate(project_input_dict)  # Will raise exception if fails
            
            keywords = search_params['keywords']
            target_description = search_params['target_description']
            
            # Save generated keywords to project for future use
            inputs.extracted_keywords = keywords
            inputs.target_description = target_description
            inputs.save(update_fields=['extracted_keywords', 'target_description'])
            
            # Add each keyword as a separate step detail for visibility
            for kw in keywords:
                tracker.add_step_detail(
                    'init',
                    'keyword',
                    kw,
                    {'keyword': kw}
                )
            
            # Update step message
            keywords_preview = ', '.join(keywords[:5])
            if len(keywords) > 5:
                keywords_preview += f' +{len(keywords) - 5} more'
            tracker.update_step_message('init', f"Keywords ready: {keywords_preview}")
            logger.info(f"✅ AI generated {len(keywords)} keywords: {keywords[:5]}...")
        else:
            # Use existing keywords
            keywords = inputs.extracted_keywords
            target_description = inputs.target_description or inputs.startup_description or ''
            
            # Add each keyword as a separate step detail for visibility
            for kw in keywords:
                tracker.add_step_detail(
                    'init',
                    'keyword',
                    kw,
                    {'keyword': kw}
                )
            
            keywords_preview = ', '.join(keywords[:5]) if keywords else 'None'
            if len(keywords) > 5:
                keywords_preview += f' +{len(keywords) - 5} more'
            tracker.update_step_message('init', f"Keywords: {keywords_preview}")
            logger.info(f"Using existing keywords: {keywords}")
        
        tracker.complete_step('init', {'keywords_count': len(keywords), 'ai_generated': bool(inputs.extracted_keywords)})
        
        # ===== Step 2: API Search =====
        tracker.start_step('api_search')
        keywords_list = ', '.join(keywords[:3])
        tracker.update_step_message('api_search', f"Searching Crunchbase with {len(keywords)} keywords: {keywords_list}...")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Initialize before try block to prevent undefined var errors on exception
        all_companies = []
        top_companies = []
        metadata = {}
        result = {}
        
        try:
            result = loop.run_until_complete(
                crunchbase_scraper.search_similar_companies(
                    keywords=keywords,
                    target_description=target_description,
                    num_companies=20,
                    top_count=10,
                    report_id=str(report.id),  # For real-time status callbacks
                )
            )
            
            all_companies = result.get('all_companies', [])
            top_companies = result.get('top_companies_full_data', [])
            metadata = result.get('metadata', {})
            
            # Debug: log metadata keys to understand structure
            logger.info(f"🔎 API search metadata keys: {list(metadata.keys())}")
            
            # NOTE: Step details for keyword results are already added by real-time callbacks from crunchbase_api
            # (via send_status_update -> StatusUpdateView). Don't add duplicates here.
            
            # Update with detailed results
            total_unique = metadata.get('total_unique_companies', len(all_companies))
            collection_time = metadata.get('collection_time_seconds', 0)
            similarity_time = metadata.get('similarity_time_seconds', 0)
            
            tracker.update_step_message(
                'api_search', 
                f"Found {total_unique} companies, ranking by similarity to your startup...",
                progress_percent=60
            )
            
            logger.info(f"Found {total_unique} unique companies, top {len(top_companies)} selected")
            
            tracker.complete_step('api_search', {
                'all_companies_found': len(all_companies),
                'top_companies': len(top_companies),
                'collection_time': collection_time,
                'similarity_time': similarity_time
            })
            
            # Save raw Crunchbase data to JSON file
            try:
                org_id = str(project.organization_id) if project.organization_id else 'default'
                report_storage.save_crunchbase_raw_data(
                    project_id=str(project.id),
                    org_id=org_id,
                    version=report.current_version + 1,
                    raw_data={
                        'all_companies': all_companies,
                        'top_companies': top_companies,
                        'metadata': metadata,
                        'keywords': keywords,
                        'target_description': target_description,
                    }
                )
                logger.info(f"✅ Saved raw Crunchbase data to S3")
                
                # Save to DB (Dual-Write)
                from .models import ReportRawData
                ReportRawData.objects.create(
                    report=report,
                    version=report.current_version + 1,
                    report_type='crunchbase',
                    data={
                        'all_companies': all_companies,
                        'top_companies': top_companies,
                        'metadata': metadata,
                        'keywords': keywords,
                        'target_description': target_description,
                    }
                )
                logger.info(f"✅ Saved raw Crunchbase data to DB")
            except Exception as e:
                logger.warning(f"Failed to save Crunchbase raw data JSON: {e}")
            
        except Exception as e:
            logger.warning(f"Crunchbase scraper failed: {e}")
            tracker.fail_step('api_search', str(e))
            all_companies = []
            top_companies = []
        finally:
            loop.close()
        
        # ===== Step 3: Sorting =====
        # NOTE: If orchestrator was used, the remote worker already sent sorting/ranking updates
        # via real-time status callbacks. We still need to start/complete the step locally
        # but skip the detailed progress to avoid duplicates shown after-the-fact.
        used_orchestrator = metadata.get('used_orchestrator', False)
        
        tracker.start_step('sorting')
        
        # Show top company names being analyzed
        top_company_names = []
        for c in top_companies[:10]:
            company_data = c.get('company_data', c)
            # Company name can be 'name' or 'Company Name' depending on source
            name = company_data.get('name') or company_data.get('Company Name') or 'Unknown'
            if name and name != 'Unknown' and name != 'N/A':
                top_company_names.append(name)
        
        if top_company_names:
            names_preview = ', '.join(top_company_names[:5])
            if len(top_company_names) > 5:
                names_preview += f' +{len(top_company_names) - 5} more'
            tracker.update_step_message(
                'sorting', 
                f"Top {len(top_company_names)} matches: {names_preview}",
                progress_percent=50
            )
        else:
            tracker.update_step_message('sorting', f"Ranking {len(top_companies)} companies by similarity...")
        
        # Parse company data for analysis
        companies_for_analysis = [
            c.get('company_data', c)
            for c in top_companies[:10]
        ]
        
        # Get final company names
        final_company_names = [c.get('name', 'Unknown') for c in companies_for_analysis if c.get('name')]
        
        # Add detailed company ranks from sorted_top_companies metadata
        # Check if real-time updates already added these (from remote worker via StatusUpdateView)
        sorted_top_companies = result.get('metadata', {}).get('sorted_top_companies', [])
        if sorted_top_companies:
            # Check existing company_rank details to avoid duplicates
            from .models import ReportProgressStep
            existing_company_ranks = 0
            try:
                sorting_step = ReportProgressStep.objects.filter(report=report, step_key='sorting').first()
                if sorting_step and sorting_step.details:
                    existing_company_ranks = sum(1 for d in sorting_step.details if d.get('type') == 'company_rank')
                logger.info(f"🔍 Deduplication check: {existing_company_ranks} existing company_rank entries, {len(sorted_top_companies)} from result")
            except Exception as e:
                logger.warning(f"⚠️ Error checking existing company_ranks: {e}")
            
            # Add all companies if none exist, or skip if already have enough
            if existing_company_ranks < len(sorted_top_companies):
                logger.info(f"📝 Adding {len(sorted_top_companies)} company_rank entries (existing: {existing_company_ranks})")
                for idx, comp in enumerate(sorted_top_companies, 1):
                    name = comp.get('name', 'Unknown')
                    cb_rank = comp.get('cb_rank', 'N/A')
                    description = comp.get('description', '')  # Full description, no truncation
                    
                    tracker.add_step_detail(
                        'sorting',
                        'company_rank',
                        f"{idx}. {name} (CB Rank: {cb_rank})",  # No # prefix, use period after number
                        {
                            'rank': idx,
                            'name': name,
                            'cb_rank': cb_rank,
                            'description': description
                        }
                    )
            else:
                logger.info(f"⏭️ Skipping company_rank entries - already have {existing_company_ranks}")
        
        tracker.complete_step('sorting', {
            'companies_sorted': len(companies_for_analysis),
            'company_names': final_company_names[:10]
        })
        
        if not companies_for_analysis:
            raise Exception("No companies found for analysis")
        
        # ===== Step 4: Fetching Company Details =====
        # Note: If orchestrator was used, real-time per-company updates already came from remote worker
        tracker.start_step('fetching_details')
        if not used_orchestrator:
            tracker.update_step_message(
                'fetching_details',
                f"Processing {len(companies_for_analysis)} companies...",
                progress_percent=50
            )
        
        # The scraping already happened during API search - this step just confirms completion
        tracker.complete_step('fetching_details', {
            'companies_processed': len(companies_for_analysis),
            'company_names': final_company_names
        })
        
        # ===== Part 1-3: Run Analysis Pipeline =====
        async def run_analysis_with_tracking():
            """Run analysis pipeline with step-by-step progress updates."""
            from asgiref.sync import sync_to_async
            
            # Wrap tracker methods for async use
            start_step = sync_to_async(tracker.start_step, thread_sensitive=True)
            complete_step = sync_to_async(tracker.complete_step, thread_sensitive=True)
            update_step_message = sync_to_async(tracker.update_step_message, thread_sensitive=True)
            
            # Wrap storage methods
            save_section = sync_to_async(report_storage.save_analysis_section, thread_sensitive=True)
            save_summary = sync_to_async(report_storage.save_analysis_summary, thread_sensitive=True)
            
            # Create pipeline (uses LIARA_MODEL from settings by default)
            pipeline = CrunchbaseAnalysisPipeline(
                target_market_description=target_description,
                progress_callback=None  # We handle progress via tracker
            )
            
            num_companies = len(companies_for_analysis)
            
            # Part 1: Company Deep Dive
            await start_step('company_deep_dive')
            
            # --- Part 1: Company Deep Dive ---
            deep_dive_reports = []
            
            for idx, company in enumerate(companies_for_analysis):
                company_name = company.get("Company Name", company.get("name", f"Company {idx + 1}"))
                
                # Update tracker message
                await update_step_message(
                    'company_deep_dive', 
                    f"Analyzing {company_name} ({idx+1}/{num_companies})",
                    progress_percent=int((idx / num_companies) * 100)
                )
                
                try:
                    # Call AI
                    report_content = await pipeline._call_ai(
                        pipeline.prompts.generate_company_summary(company)
                    )
                    
                    deep_dive_reports.append({
                        "company_name": company_name,
                        "content": report_content
                    })
                    
                    # Save per-company analysis to JSON
                    try:
                        org_id = str(project.organization_id) if project.organization_id else 'default'
                        await save_section(
                            project_id=str(project.id),
                            org_id=org_id,
                            version=report.current_version + 1,
                            section_type='company_deep_dive',
                            content=report_content,
                            company_name=company_name
                        )
                    except Exception as save_err:
                        logger.warning(f"Failed to save company_deep_dive JSON for {company_name}: {save_err}")
                        
                except Exception as e:
                    logger.error(f"Analysis failed for {company_name}: {e}")
                    deep_dive_reports.append({
                        "company_name": company_name,
                        "content": f"Analysis error: {str(e)}"
                    })

                # Close DB connections occasionally
                if idx % 3 == 0:
                    await sync_to_async(close_old_connections)()
            
            await complete_step('company_deep_dive', {'companies_analyzed': len(deep_dive_reports)})
            
            # --- Part 2: Strategic Summary ---
            await start_step('strategic_summary')
            await update_step_message('strategic_summary', "Synthesizing strategic trends...")
            
            strategic_summary = await pipeline._call_ai(
                pipeline.prompts.generate_strategic_summary(companies_for_analysis)
            )
            
            # Save summary to JSON
            try:
                org_id = str(project.organization_id) if project.organization_id else 'default'
                await save_summary(
                    project_id=str(project.id),
                    org_id=org_id,
                    version=report.current_version + 1,
                    summary_type='strategic_summary',
                    content=strategic_summary
                )
            except Exception as e:
                 logger.warning(f"Failed to save strategic_summary JSON: {e}")
            
            await complete_step('strategic_summary')

            # --- Part 3: Fast Analysis ---
            await start_step('fast_analysis')
            await update_step_message('fast_analysis', "Generating executive flash report...")
            
            fast_analysis = await pipeline._call_ai(
                pipeline.prompts.generate_fast_analysis(companies_for_analysis)
            )
            
            # Save summary to JSON
            try:
                org_id = str(project.organization_id) if project.organization_id else 'default'
                await save_summary(
                    project_id=str(project.id),
                    org_id=org_id,
                    version=report.current_version + 1,
                    summary_type='fast_analysis',
                    content=fast_analysis
                )
            except Exception as e:
                 logger.warning(f"Failed to save fast_analysis JSON: {e}")
            
            await complete_step('fast_analysis')
            
            return {
                'company_deep_dive': deep_dive_reports,
                'strategic_summary': strategic_summary,
                'fast_analysis': fast_analysis,
                'company_count': num_companies
            }
        
        # Run the analysis
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            analysis_result = loop.run_until_complete(run_analysis_with_tracking())
        finally:
            loop.close()
        
        # ===== Generate HTML =====
        tracker.start_step('html_gen')
        
        # Format result for HTML generator
        formatted_result = {
            'company_count': analysis_result['company_count'],
            'processing_time': 0,
            'sections': {
                'company_deep_dive': analysis_result['company_deep_dive'],
                'strategic_summary': {'content': analysis_result['strategic_summary'], 'type': 'strategic_summary'},
                'fast_analysis': {'content': analysis_result['fast_analysis'], 'type': 'fast_analysis'},
            }
        }
        
        html_content = generate_analysis_html(
            formatted_result,
            inputs.startup_name or project.name
        )
        
        tracker.complete_step('html_gen', {'html_size': len(html_content)})
        
        # ===== Save to DB =====
        tracker.start_step('save')
        
        # Save analysis sections to database
        section_order = 0
        
        # 1. Fast Analysis (First in DB too for easier fetching if ordered)
        ReportAnalysisSection.objects.create(
            report=report,
            section_type='fast_analysis',
            content_markdown=analysis_result['fast_analysis'],
            order=section_order
        )
        section_order += 1
        
        # 2. Strategic Summary
        ReportAnalysisSection.objects.create(
            report=report,
            section_type='strategic_summary',
            content_markdown=analysis_result['strategic_summary'],
            order=section_order
        )
        section_order += 1
        
        # 3. Company Deep Dives
        for report_item in analysis_result['company_deep_dive']:
            ReportAnalysisSection.objects.create(
                report=report,
                section_type='company_deep_dive',
                company_name=report_item['company_name'],
                content_markdown=report_item['content'],
                order=section_order
            )
            section_order += 1
        
        # Save to S3 if enabled
        if getattr(settings, 'USE_S3', False):
            try:
                org_id = str(project.organization_id) if project.organization_id else 'default'
                storage_service.upload_report(
                    org_id=org_id,
                    project_id=str(project.id),
                    report_type='crunchbase',
                    report_id=str(report.id),
                    content=html_content.encode(),
                    file_type='html'
                )
            except Exception as e:
                logger.warning(f"S3 upload failed: {e}")
        
        # Create version
        report.current_version += 1
        ReportVersion.objects.create(
            report=report,
            version_number=report.current_version,
            html_content=html_content,
            data_snapshot={
                'company_count': analysis_result['company_count'],
                'sections_count': section_order
            },
            changes_summary=f"Full 3-Part Analysis: {analysis_result['company_count']} companies",
            generated_by=user
        )
        
        # Finalize report
        report.status = 'completed'
        report.progress = 100
        report.current_step = 'Complete!'
        report.html_content = html_content
        report.data = {
            'company_count': analysis_result['company_count'],
            'keywords': keywords,
            'sections_count': section_order
        }
        report.completed_at = timezone.now()
        report.save()
        
        # Save report metadata JSON
        try:
            org_id = str(project.organization_id) if project.organization_id else 'default'
            report_storage.save_report_metadata(
                project_id=str(project.id),
                org_id=org_id,
                version=report.current_version,
                metadata={
                    'report_id': str(report.id),
                    'project_id': str(project.id),
                    'org_id': org_id,
                    'keywords': keywords,
                    'target_description': target_description,
                    'company_count': analysis_result['company_count'],
                    'sections_count': section_order,
                    'generated_at': report.completed_at.isoformat() if report.completed_at else None,
                    'version': report.current_version,
                    'status': 'success'
                },
                report_type='crunchbase'
            )
            logger.info(f"✅ Saved report metadata JSON for project {project.id}")
        except Exception as e:
            logger.warning(f"Failed to save report metadata JSON: {e}")
        
        tracker.complete_step('save', {'version': report.current_version, 'sections': section_order})
        
        logger.info(f"✅ Crunchbase report generated for project {project.id} with {section_order} sections")
        return {"status": "success", "version": report.current_version, "sections": section_order}
        

    except Exception as e:
        logger.error(f"❌ Failed to generate Crunchbase report: {e}")
        if report:
            report.status = 'failed'
            report.error_message = str(e)
            report.save()
            if tracker:
                from .models import ReportProgressStep
                running_step = ReportProgressStep.objects.filter(
                    report=report, status='running'
                ).first()
                if running_step:
                    tracker.fail_step(running_step.step_key, str(e))
        raise


@shared_task(bind=True, queue='reports')
def generate_social_report(self, report_id, user_id):
    """
    Generate Social Media (Twitter) analysis report.
    Per Task Plan.
    
    Pipeline Steps:
    1. Generate Social Keywords (User needs -> Hashtags/Phrases)
    2. Search Twitter via Orchestrator (Top & Latest)
    3. Analyze Tweets (Segmentation, JTBD, Pain Points, WTP, Competitors, Sentiment)
    4. Generate Executive Summary
    5. Save Report
    """
    from .models import Report, ReportVersion, ReportAnalysisSection
    from .progress_tracker import ReportProgressTracker
    from apps.users.models import User
    from services.keyword_generator import generate_social_keywords_async
    from services.scrapers.twitter_scraper import twitter_scraper
    from services.twitter_analysis import TwitterAnalysisPipeline
    from core.storage import storage_service
    from services.report_storage import report_storage
    
    report = None
    tracker = None
    
    try:
        report = Report.objects.get(id=report_id)
        user = User.objects.get(id=user_id)
        project = report.project
        inputs = project.inputs
        
        # Mark as running
        report.status = 'running'
        report.started_at = timezone.now()
        report.save()
        
        # Initialize progress tracker
        tracker = ReportProgressTracker(report)
        tracker.initialize_steps() # Assumes social steps are defined or generic enough
        
        # ===== Step 1: Generate Social Keywords =====
        tracker.start_step('init')
        tracker.update_step_message('init', "Generating social media search keywords...")
        
        project_input_dict = get_project_inputs_dict(inputs)
        
        # Force fresh generation for social (different from crunchbase keywords)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            kw_result = loop.run_until_complete(generate_social_keywords_async(project_input_dict))
            keywords = kw_result['keywords']
            target_desc = kw_result['target_description']
            
            # Save to report data for reference (keywords used)
            report.data['social_keywords'] = keywords
            report.save()
            
            for kw in keywords:
                tracker.add_step_detail('init', 'keyword', kw, {'keyword': kw})
            
            tracker.complete_step('init', {'keywords_count': len(keywords)})
            
        except Exception as e:
            logger.error(f"Keyword generation failed: {e}")
            tracker.fail_step('init', str(e))
            raise
        
        # ===== Step 2: Search Twitter =====
        tracker.start_step('api_search')
        
        # Search for top keywords
        # Using top 3 keywords as requested
        search_keywords = keywords[:3]
        tracker.update_step_message('api_search', f"Searching Twitter for {len(search_keywords)} topics...")
        
        all_tweets = []
        try:
            # Run searches sequentially with delay to respect rate limit (5s)
            results_list = []
            
            for i, kw in enumerate(search_keywords):
                if i > 0:
                    tracker.update_step_message('api_search', f"Waiting 6s before next search (Rate Limit)...")
                    # Wait 6s between requests
                    loop.run_until_complete(asyncio.sleep(6))
                
                tracker.update_step_message('api_search', f"Searching for '{kw}'...")
                
                try:
                    res = loop.run_until_complete(
                        twitter_scraper.search_tweets(
                            keywords=[kw],
                            limit=10,
                            report_id=str(report.id)
                        )
                    )
                    
                    # Process result immediately
                    if isinstance(res, dict) and 'tweets' in res:
                        found_count = len(res['tweets'])
                        all_tweets.extend(res['tweets'])
                        
                        # Prepare detail message and data
                        message = f"Found {found_count} tweets for '{kw}'"
                        detail_data = {'keyword': kw, 'count': found_count}
                        
                        # Add top tweet info if available (for expandable description)
                        if res['tweets']:
                            top_tweet = res['tweets'][0]
                            author_name = top_tweet.get('author', {}).get('name', 'Unknown')
                            tweet_text = top_tweet.get('text', '')
                            
                            # The frontend likely uses 'description' for expandable content
                            detail_data['description'] = f"@{author_name}: {tweet_text}"
                            detail_data['top_tweet_id'] = top_tweet.get('id')
                            
                            # Update title to include preview
                            preview = tweet_text[:50] + "..." if len(tweet_text) > 50 else tweet_text
                            # Ensure full text is available for frontend expansion
                            if 'full_text' not in detail_data:
                                detail_data['full_text'] = tweet_text

                            message += f" - Top: {preview}"

                        tracker.add_step_detail(
                            'api_search', 
                            'search_result', 
                            message, 
                            detail_data
                        )
                    elif isinstance(res, Exception):
                        logger.warning(f"Search failed for '{kw}': {res}")
                        tracker.add_step_detail('api_search', 'error', f"Search failed for '{kw}': {str(res)}")
                    
                except Exception as e:
                    logger.error(f"Search failed for '{kw}': {e}")
                    tracker.add_step_detail('api_search', 'error', f"Search failed for '{kw}': {str(e)}")
            
            tracker.update_step_message('api_search', f"Found {len(all_tweets)} unique tweets.")
            # Dedup tweets by ID
            seen_ids = set()
            unique_tweets = []
            for t in all_tweets:
                if t['id'] not in seen_ids:
                    seen_ids.add(t['id'])
                    unique_tweets.append(t)
            all_tweets = unique_tweets
            
            tracker.update_step_message('api_search', f"Found {len(all_tweets)} unique tweets.")
            tracker.complete_step('api_search', {'tweets_found': len(all_tweets)})
            
            # Save Raw Data
            try:
                org_id = str(project.organization_id) if project.organization_id else 'default'
                report_storage.save_twitter_raw_data(
                    project_id=str(project.id),
                    org_id=org_id,
                    version=report.current_version + 1,
                    raw_data=all_tweets
                )
                logger.info(f"✅ Saved raw Twitter data to S3")
                
                # Save to DB (Dual-Write)
                from .models import ReportRawData
                ReportRawData.objects.create(
                    report=report,
                    version=report.current_version + 1,
                    report_type='social',
                    data=all_tweets
                )
                logger.info(f"✅ Saved raw Twitter data to DB")
            except Exception as e:
                logger.warning(f"Failed to save raw Twitter data: {e}")
            
        except Exception as e:
            logger.error(f"Twitter search failed: {e}")
            tracker.fail_step('api_search', str(e))
            raise

        # ===== Step 3: Analysis =====
        # ===== Step 3: Analyze Tweets =====
        # Note: Pipeline handles tracking of granular analysis steps internally
        
        analysis_pipeline = TwitterAnalysisPipeline(target_market_description=target_desc)
        
        from asgiref.sync import sync_to_async
        
        class AsyncTracker:
            def __init__(self, tracker):
                self.tracker = tracker
            
            async def start_step(self, *args, **kwargs):
                await sync_to_async(self.tracker.start_step)(*args, **kwargs)

            async def update_step_message(self, *args, **kwargs):
                await sync_to_async(self.tracker.update_step_message)(*args, **kwargs)

            async def add_step_detail(self, *args, **kwargs):
                await sync_to_async(self.tracker.add_step_detail)(*args, **kwargs)

            async def complete_step(self, *args, **kwargs):
                await sync_to_async(self.tracker.complete_step)(*args, **kwargs)
                
            async def fail_step(self, *args, **kwargs):
                await sync_to_async(self.tracker.fail_step)(*args, **kwargs)

        async_tracker = AsyncTracker(tracker)
        
        try:
            analysis_results = loop.run_until_complete(
                analysis_pipeline.analyze(all_tweets, tracker=async_tracker)
            )
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            raise
            raise
        
        # =====
        
        # Search for top keywords
        # Using top 3 keywords as requested
        search_keywords = keywords[:3]
        tracker.update_step_message('api_search', f"Searching Linkedin for {len(search_keywords)} topics...")
        
        all_linkedin_posts = []
        try:
            # Run searches sequentially with delay to respect rate limit (5s)
            results_list = []
            
            for i, kw in enumerate(search_keywords):
                if i > 0:
                    tracker.update_step_message('api_search', f"Waiting 6s before next search (Rate Limit)...")
                    # Wait 6s between requests
                    loop.run_until_complete(asyncio.sleep(6))
                
                tracker.update_step_message('api_search', f"Searching for '{kw}'...")
                
                try:
                    res = loop.run_until_complete(
                        twitter_scraper.search_tweets(
                            keywords=[kw],
                            limit=10,
                            report_id=str(report.id)
                        )
                    )
                    
                    # Process result immediately
                    if isinstance(res, dict) and 'tweets' in res:
                        found_count = len(res['tweets'])
                        all_tweets.extend(res['tweets'])
                        
                        # Prepare detail message and data
                        message = f"Found {found_count} tweets for '{kw}'"
                        detail_data = {'keyword': kw, 'count': found_count}
                        
                        # Add top tweet info if available (for expandable description)
                        if res['tweets']:
                            top_tweet = res['tweets'][0]
                            author_name = top_tweet.get('author', {}).get('name', 'Unknown')
                            tweet_text = top_tweet.get('text', '')
                            
                            # The frontend likely uses 'description' for expandable content
                            detail_data['description'] = f"@{author_name}: {tweet_text}"
                            detail_data['top_tweet_id'] = top_tweet.get('id')
                            
                            # Update title to include preview
                            preview = tweet_text[:50] + "..." if len(tweet_text) > 50 else tweet_text
                            # Ensure full text is available for frontend expansion
                            if 'full_text' not in detail_data:
                                detail_data['full_text'] = tweet_text

                            message += f" - Top: {preview}"

                        tracker.add_step_detail(
                            'api_search', 
                            'search_result', 
                            message, 
                            detail_data
                        )
                    elif isinstance(res, Exception):
                        logger.warning(f"Search failed for '{kw}': {res}")
                        tracker.add_step_detail('api_search', 'error', f"Search failed for '{kw}': {str(res)}")
                    
                except Exception as e:
                    logger.error(f"Search failed for '{kw}': {e}")
                    tracker.add_step_detail('api_search', 'error', f"Search failed for '{kw}': {str(e)}")
            
            tracker.update_step_message('api_search', f"Found {len(all_tweets)} unique tweets.")
            # Dedup tweets by ID
            seen_ids = set()
            unique_tweets = []
            for t in all_tweets:
                if t['id'] not in seen_ids:
                    seen_ids.add(t['id'])
                    unique_tweets.append(t)
            all_tweets = unique_tweets
            
            tracker.update_step_message('api_search', f"Found {len(all_tweets)} unique tweets.")
            tracker.complete_step('api_search', {'tweets_found': len(all_tweets)})
            
            # Save Raw Data
            try:
                org_id = str(project.organization_id) if project.organization_id else 'default'
                report_storage.save_twitter_raw_data(
                    project_id=str(project.id),
                    org_id=org_id,
                    version=report.current_version + 1,
                    raw_data=all_tweets
                )
                logger.info(f"✅ Saved raw Twitter data to S3")
                
                # Save to DB (Dual-Write)
                from .models import ReportRawData
                ReportRawData.objects.create(
                    report=report,
                    version=report.current_version + 1,
                    report_type='social',
                    data=all_tweets
                )
                logger.info(f"✅ Saved raw Twitter data to DB")
            except Exception as e:
                logger.warning(f"Failed to save raw Twitter data: {e}")
            
        except Exception as e:
            logger.error(f"Twitter search failed: {e}")
            tracker.fail_step('api_search', str(e))
            raise


        # ===== Step 4: Save & Generate HTML =====
        
        
        
        tracker.start_step('save')
        
        section_order = 0
        
        # We need to format HTML.
        # Since we don't have a specific `generate_social_html` yet, we can create a simple one or basic formatting.
        # Or store JSON sections and let Frontend render.
        # `generate_crunchbase_report` does both.
        
        # Save sections
        for key, content in analysis_results.items():
            ReportAnalysisSection.objects.create(
                report=report,
                section_type=key,
                content_markdown=str(content), # It returns JSON string often, or markdown
                order=section_order
            )
            section_order += 1
            
            # S3
            try:
                org_id = str(project.organization_id) if project.organization_id else 'default'
                report_storage.save_analysis_section(
                    project_id=str(project.id),
                    org_id=org_id,
                    version=report.current_version + 1,
                    section_type=key,
                    content=str(content),  # Convert to string/markdown if it's a dict/json
                    report_type='social'
                )
            except Exception as e:
                logger.warning(f"S3 save failed: {e}")

        # Finalize
        # Create a simple HTML report for now
        html_content = f"<h1>Social Media Analysis for {project.name}</h1>"
        html_content += f"<h2>Executive Summary</h2><p>{analysis_results.get('executive_summary', '')}</p>"
        
        report.current_version += 1
        ReportVersion.objects.create(
            report=report,
            version_number=report.current_version,
            html_content=html_content,
            data_snapshot={'tweet_count': len(all_tweets)},
            changes_summary=f"Analysis of {len(all_tweets)} tweets",
            generated_by=user
        )
        
        report.status = 'completed'
        report.progress = 100
        report.current_step = 'Complete!'
        report.html_content = html_content
        report.save()
        
        # Save report metadata JSON
        try:
            org_id = str(project.organization_id) if project.organization_id else 'default'
            report_storage.save_report_metadata(
                project_id=str(project.id),
                org_id=org_id,
                version=report.current_version,
                metadata={
                    'report_id': str(report.id),
                    'project_id': str(project.id),
                    'org_id': org_id,
                    'keywords': keywords,
                    'tweets_count': len(all_tweets),
                    'sections_count': section_order,
                    'generated_at': report.completed_at.isoformat() if report.completed_at else None,
                    'version': report.current_version,
                    'status': 'success'
                },
                report_type='social'
            )
            logger.info(f"✅ Saved Social report metadata JSON for project {project.id}")
        except Exception as e:
            logger.warning(f"Failed to save Social report metadata JSON: {e}")
        
        tracker.complete_step('save')
        loop.close()
        
        return {"status": "success", "tweets": len(all_tweets)}

    except Exception as e:
        logger.error(f"❌ Failed to generate Social report: {e}")
        if report:
            report.status = 'failed'
            report.error_message = str(e)
            report.save()
        raise



@shared_task(bind=True, queue='reports')
def generate_tracxn_report(self, report_id, user_id):
    """
    Generate Tracxn analysis report using 3-step institutional-grade AI pipeline.
    
    Pipeline Steps:
    1. Initialize & Generate Tracxn Keywords
    2. Search Tracxn API via Orchestrator
    3. Rank Results by Similarity
    4. Fetch Startup Details
    5. Flash Analysis (2-page market flash report)
    6. Company Deep Dive (comprehensive due diligence per company)
    7. Executive Summary (5-page strategic assessment)
    8. Generate HTML Report
    9. Save Report to DB and S3
    """
    from .models import Report, ReportVersion, ReportAnalysisSection
    from .progress_tracker import ReportProgressTracker
    from apps.users.models import User
    from services.scrapers.tracxn_scraper import tracxn_scraper
    from services.tracxn_analysis import TracxnAnalysisPipeline, generate_tracxn_html
    from core.storage import storage_service
    
    report = None
    tracker = None
    
    try:
        report = Report.objects.get(id=report_id)
        user = User.objects.get(id=user_id)
        project = report.project
        inputs = project.inputs
        
        # Mark as running
        report.status = 'running'
        report.started_at = timezone.now()
        report.save()
        
        # Initialize progress tracker
        tracker = ReportProgressTracker(report)
        tracker.initialize_steps()
        
        # ===== Step 1: Initialize & Generate Keywords =====
        tracker.start_step('init')
        
        # Check if we need to generate keywords using AI
        if not inputs.extracted_keywords or len(inputs.extracted_keywords) == 0:
            # Generate Tracxn-specific keywords using Liara AI - NO FALLBACK
            from services.keyword_generator import KeywordGenerator
            
            tracker.update_step_message('init', "Generating AI-powered Tracxn search keywords...")
            logger.info("🔑 Generating Tracxn keywords using Liara AI (forced tool calling)...")
            
            generator = KeywordGenerator()
            project_input_dict = get_project_inputs_dict(inputs)
            # Use Tracxn-specific keyword generation for better startup ecosystem terms
            search_params = generator.generate_tracxn_keywords(project_input_dict)  # Will raise exception if fails
            
            keywords = search_params['keywords']
            target_description = search_params['target_description']
            
            # Save generated keywords
            inputs.extracted_keywords = keywords
            inputs.target_description = target_description
            inputs.save(update_fields=['extracted_keywords', 'target_description'])
            
            # Add keywords as step details
            for kw in keywords:
                tracker.add_step_detail('init', 'keyword', kw, {'keyword': kw})
            
            keywords_preview = ', '.join(keywords[:5])
            if len(keywords) > 5:
                keywords_preview += f' +{len(keywords) - 5} more'
            tracker.update_step_message('init', f"Keywords ready: {keywords_preview}")
            logger.info(f"✅ AI generated {len(keywords)} keywords")
        else:
            keywords = inputs.extracted_keywords
            target_description = inputs.target_description or inputs.startup_description or ''
            
            for kw in keywords:
                tracker.add_step_detail('init', 'keyword', kw, {'keyword': kw})
            
            keywords_preview = ', '.join(keywords[:5]) if keywords else 'None'
            if len(keywords) > 5:
                keywords_preview += f' +{len(keywords) - 5} more'
            tracker.update_step_message('init', f"Keywords: {keywords_preview}")
            logger.info(f"Using existing keywords: {keywords}")
        
        tracker.complete_step('init', {'keywords_count': len(keywords)})
        
        # ===== Step 2: API Search =====
        # Note: The Tracxn API also sends status updates for 'sorting' and 'fetching_details'
        # during the search_with_ranking call. We start those steps now so updates flow correctly.
        tracker.start_step('api_search')
        keywords_list = ', '.join(keywords[:3])
        tracker.update_step_message('api_search', f"Searching Tracxn with {len(keywords)} keywords: {keywords_list}...")
        
        # Pre-start sorting and fetching_details so API status updates appear in real-time
        # These steps happen inside search_with_ranking() and send status updates via callback
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                tracxn_scraper.search_with_ranking(
                    company_names=keywords,
                    target_description=target_description,
                    num_companies_per_search=30,
                    top_count=15,
                    report_id=str(report.id),  # Enable real-time status callbacks
                )
            )
            
            all_companies = result.get('all_companies', [])
            top_companies = result.get('top_companies_full_data', [])
            metadata = result.get('metadata', {})
            
            # Close old DB connections to prevent timeouts after long blocking call
            from django.db import close_old_connections
            close_old_connections()
            
            total_unique = metadata.get('total_unique_companies', len(all_companies))
            tracker.update_step_message(
                'api_search', 
                f"Found {total_unique} startups from Tracxn",
                progress_percent=70
            )
            
            logger.info(f"Found {total_unique} unique companies, top {len(top_companies)} selected")
            
            tracker.complete_step('api_search', {
                'all_companies_found': len(all_companies),
                'top_companies': len(top_companies),
            })
            
            # Save raw data to S3/MinIO
            try:
                from services.report_storage import report_storage
                org_id = str(project.organization_id) if project.organization_id else 'default'
                report_storage.save_tracxn_raw_data(
                    project_id=str(project.id),
                    org_id=org_id,
                    version=report.current_version + 1,
                    raw_data=top_companies
                )
                logger.info(f"✅ Saved raw Tracxn data to S3")
                
                # Save to DB (Dual-Write)
                from .models import ReportRawData
                ReportRawData.objects.create(
                    report=report,
                    version=report.current_version + 1,
                    report_type='tracxn',
                    data=top_companies
                )
                logger.info(f"✅ Saved raw Tracxn data to DB")
            except Exception as e:
                logger.warning(f"Failed to save raw Tracxn data: {e}")
            
        except Exception as e:
            logger.warning(f"Tracxn scraper failed: {e}")
            tracker.fail_step('api_search', str(e))
            all_companies = []
            top_companies = []
            result = {}
        finally:
            loop.close()
        
        # ===== Step 3: Sorting =====
        tracker.start_step('sorting')
        
        top_startup_names = []
        for c in top_companies[:15]:
            # Use name from wrapper directly
            name = c.get('name') or 'Unknown'
            if name and name != 'Unknown':
                top_startup_names.append(name)
        
        if top_startup_names:
            names_preview = ', '.join(top_startup_names[:5])
            if len(top_startup_names) > 5:
                names_preview += f' +{len(top_startup_names) - 5} more'
            tracker.update_step_message('sorting', f"Top {len(top_startup_names)} matches: {names_preview}")
        else:
            tracker.update_step_message('sorting', f"Ranking {len(top_companies)} startups by similarity...")
        
        # Use raw company data for analysis (skipped normalization as requested)
        # We need to inject 'name' so downstream logic (logs, report headers) works
        startups_for_analysis = []
        for c in top_companies[:15]:
            raw_data = c.get('full_data', c)
            # Ensure it's a dict
            if not isinstance(raw_data, dict):
                raw_data = {'raw_content': str(raw_data)}
            
            # Inject name from wrapper if missing in top level
            if 'name' not in raw_data and c.get('name'):
                raw_data['name'] = c.get('name')
                
            startups_for_analysis.append(raw_data)
        
        # Add sorted startups as step details
        for idx, c in enumerate(top_companies[:15], 1):
            name = c.get('name', 'Unknown')
            # Use scores from the wrapper object (c)
            score = c.get('combined_score', c.get('tracxn_score', 'N/A'))
            
            if isinstance(score, float):
                score = f"{score:.2f}"
                
            tracker.add_step_detail(
                'sorting',
                'startup_rank',
                f"{idx}. {name} (Score: {score})",
                {'rank': idx, 'name': name, 'score': score}
            )
        
        tracker.complete_step('sorting', {'startups_sorted': len(startups_for_analysis)})
        
        if not startups_for_analysis:
            raise Exception("No startups found for analysis")
        
        # ===== Step 4: Gathering Full Data =====
        tracker.start_step('fetching_details')
        tracker.update_step_message(
            'fetching_details',
            f"Gathering full data for {len(startups_for_analysis)} startups...",
            progress_percent=50
        )
        tracker.complete_step('fetching_details', {'startups_processed': len(startups_for_analysis)})
        
        # ===== Steps 5-7: Run 3-Step Institutional AI Analysis Pipeline =====
        async def run_analysis_with_tracking():
            """Run 3-step institutional analysis pipeline with progress updates."""
            from asgiref.sync import sync_to_async
            
            start_step = sync_to_async(tracker.start_step, thread_sensitive=True)
            complete_step = sync_to_async(tracker.complete_step, thread_sensitive=True)
            
            pipeline = TracxnAnalysisPipeline(
                target_market_description=target_description,
                progress_callback=None
            )
            
            num_startups = len(startups_for_analysis)
            
            # Step 5: Company Deep Dive (per company comprehensive analysis)
            await start_step('company_deep_dive')
            company_reports = []
            for startup in startups_for_analysis:
                startup_name = startup.get('name', 'Unknown')
                try:
                    prompt = pipeline.prompts.generate_comprehensive_company_analysis(
                        startup, target_description
                    )
                    content = await pipeline._call_ai(prompt, max_tokens=4000)
                    company_reports.append({'company_name': startup_name, 'content': content})
                except Exception as e:
                    logger.error(f"Company deep dive failed for {startup_name}: {e}")
                    company_reports.append({'company_name': startup_name, 'content': f"Analysis error: {str(e)}"})
            await complete_step('company_deep_dive', {'startups_analyzed': len(company_reports)})
            
            # Step 6: Executive Summary (5-page strategic assessment)
            await start_step('executive_summary')
            try:
                report_texts = [r['content'] for r in company_reports]
                prompt = pipeline.prompts.generate_executive_summary(
                    report_texts, num_startups, target_description
                )
                executive_summary = await pipeline._call_ai(prompt, max_tokens=5000)
            except Exception as e:
                logger.error(f"Executive summary failed: {e}")
                executive_summary = f"Analysis error: {str(e)}"
            await complete_step('executive_summary', {'summary_generated': True})
            
            # Step 7: Flash Analysis (2-page market flash report - synthesizing all analysis)
            await start_step('flash_analysis')
            try:
                # Pass company reports to flash analysis so it can synthesize the findings
                prompt = pipeline.prompts.generate_flash_analysis_report(
                    company_reports, executive_summary, target_description
                )
                flash_analysis = await pipeline._call_ai(prompt, max_tokens=3000)
            except Exception as e:
                logger.error(f"Flash analysis failed: {e}")
                flash_analysis = f"Analysis error: {str(e)}"
            await complete_step('flash_analysis', {'report_generated': True})
            
            return {
                'company_count': num_startups,
                'company_reports': company_reports,
                'executive_summary': executive_summary,
                'flash_analysis': flash_analysis,
            }
        
        # Run the analysis
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            analysis_result = loop.run_until_complete(run_analysis_with_tracking())
        finally:
            loop.close()
        
        # ===== Step 8: Generate HTML =====
        tracker.start_step('html_gen')
        
        # Format result for HTML generator (new 3-step structure)
        formatted_result = {
            'company_count': analysis_result['company_count'],
            'processing_time': 0,
            'flash_analysis': analysis_result['flash_analysis'],
            'company_reports': analysis_result['company_reports'],
            'executive_summary': analysis_result['executive_summary'],
        }
        
        html_content = generate_tracxn_html(
            formatted_result,
            inputs.startup_name or project.name
        )
        
        tracker.complete_step('html_gen', {'html_size': len(html_content)})
        
        # ===== Step 9: Save =====
        tracker.start_step('save')
        
        # Save analysis sections to database
        section_order = 0
        
        # Save Flash Analysis (Dual-Write: DB + S3)
        if analysis_result.get('flash_analysis'):
            ReportAnalysisSection.objects.create(
                report=report,
                section_type='flash_analysis',
                content_markdown=analysis_result['flash_analysis'],
                order=section_order
            )
            section_order += 1
            
            if getattr(settings, 'USE_S3', False):
                try:
                    org_id = str(project.organization_id) if project.organization_id else 'default'
                    report_storage.save_analysis_section(
                        project_id=str(project.id),
                        org_id=org_id,
                        version=report.current_version + 1,
                        section_type='flash_analysis',
                        content=analysis_result['flash_analysis'],
                        report_type='tracxn'
                    )
                except Exception as e:
                    logger.warning(f"S3 flash analysis save failed: {e}")
        
        # Save Company Deep Dive Reports (Dual-Write: DB + S3)
        for report_item in analysis_result.get('company_reports', []):
            ReportAnalysisSection.objects.create(
                report=report,
                section_type='company_deep_dive',
                company_name=report_item['company_name'],
                content_markdown=report_item['content'],
                order=section_order
            )
            section_order += 1
            
            if getattr(settings, 'USE_S3', False):
                try:
                    org_id = str(project.organization_id) if project.organization_id else 'default'
                    report_storage.save_analysis_section(
                        project_id=str(project.id),
                        org_id=org_id,
                        version=report.current_version + 1,
                        section_type='company_deep_dive',
                        content=report_item['content'],
                        company_name=report_item['company_name'],
                        report_type='tracxn'
                    )
                except Exception as e:
                    logger.warning(f"S3 company deep dive save failed for {report_item['company_name']}: {e}")
        
        # Save Executive Summary (Dual-Write: DB + S3)
        if analysis_result.get('executive_summary'):
            ReportAnalysisSection.objects.create(
                report=report,
                section_type='executive_summary',
                content_markdown=analysis_result['executive_summary'],
                order=section_order
            )
            section_order += 1
            
            if getattr(settings, 'USE_S3', False):
                try:
                    org_id = str(project.organization_id) if project.organization_id else 'default'
                    report_storage.save_analysis_summary(
                        project_id=str(project.id),
                        org_id=org_id,
                        version=report.current_version + 1,
                        summary_type='executive_summary',
                        content=analysis_result['executive_summary'],
                        report_type='tracxn'
                    )
                except Exception as e:
                    logger.warning(f"S3 executive summary save failed: {e}")
        
        # Save to S3 if enabled
        if getattr(settings, 'USE_S3', False):
            try:
                org_id = str(project.organization_id) if project.organization_id else 'default'
                storage_service.upload_report(
                    org_id=org_id,
                    project_id=str(project.id),
                    report_type='tracxn',
                    content=html_content.encode(),
                    file_type='html'
                )
            except Exception as e:
                logger.warning(f"S3 upload failed: {e}")
        
        # Create version
        report.current_version += 1
        ReportVersion.objects.create(
            report=report,
            version_number=report.current_version,
            html_content=html_content,
            data_snapshot={
                'company_count': analysis_result['company_count'],
                'sections_count': section_order
            },
            changes_summary=f"3-step Institutional Tracxn analysis: {analysis_result['company_count']} startups",
            generated_by=user
        )
        
        # Finalize report
        report.status = 'completed'
        report.progress = 100
        report.current_step = 'Complete!'
        report.html_content = html_content
        report.data = {
            'company_count': analysis_result['company_count'],
            'keywords': keywords,
            'sections_count': section_order
        }
        report.completed_at = timezone.now()
        report.save()
        
        # Save report metadata JSON
        try:
            org_id = str(project.organization_id) if project.organization_id else 'default'
            report_storage.save_report_metadata(
                project_id=str(project.id),
                org_id=org_id,
                version=report.current_version,
                metadata={
                    'report_id': str(report.id),
                    'project_id': str(project.id),
                    'org_id': org_id,
                    'keywords': keywords,
                    'target_description': target_description,
                    'company_count': analysis_result['company_count'],
                    'sections_count': section_order,
                    'generated_at': report.completed_at.isoformat() if report.completed_at else None,
                    'version': report.current_version,
                    'status': 'success'
                },
                report_type='tracxn'
            )
            logger.info(f"✅ Saved Tracxn report metadata JSON for project {project.id}")
        except Exception as e:
            logger.warning(f"Failed to save Tracxn report metadata JSON: {e}")
            
        tracker.complete_step('save', {'version': report.current_version, 'sections': section_order})
        
        logger.info(f"✅ Tracxn report generated for project {project.id} with {section_order} sections")
        return {"status": "success", "version": report.current_version, "sections": section_order}
        
    except Exception as e:
        logger.error(f"❌ Failed to generate Tracxn report: {e}")
        if report:
            report.status = 'failed'
            report.error_message = str(e)
            report.save()
            if tracker:
                from .models import ReportProgressStep
                running_step = ReportProgressStep.objects.filter(
                    report=report, status='running'
                ).first()
                if running_step:
                    tracker.fail_step(running_step.step_key, str(e))
        raise


@shared_task(bind=True, queue='reports')
def generate_pitch_deck(self, report_id, user_id):
    """
    Generate Pitch Deck report.
    Per FINAL_ARCHITECTURE - Panel 4: Pitch Deck
    """
    from .models import Report, ReportVersion
    from apps.users.models import User
    from services.openai_service import openai_service
    from services.html_generator import HTMLReportGenerator
    from core.storage import storage_service
    
    try:
        report = Report.objects.get(id=report_id)
        user = User.objects.get(id=user_id)
        project = report.project
        inputs = project.inputs
        inputs_dict = get_project_inputs_dict(inputs)
        
        report.status = 'running'
        report.started_at = timezone.now()
        report.save()
        
        update_report_progress(report, 15, "Gathering project data...")
        
        # Get other reports for context
        crunchbase_data = {}
        tracxn_data = {}
        
        from .models import Report as ReportModel
        try:
            cr_report = ReportModel.objects.filter(
                project=project, 
                report_type='crunchbase', 
                status='completed'
            ).first()
            if cr_report:
                crunchbase_data = cr_report.data or {}
        except:
            pass
        
        update_report_progress(report, 35, "Generating slide content with AI...")
        
        slides = {}
        
        # Generate with AI if available
        if getattr(settings, 'OPENAI_API_KEY', ''):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                slides = loop.run_until_complete(
                    openai_service.generate_pitch_deck_content(
                        inputs_dict,
                        crunchbase_data,
                        tracxn_data
                    )
                )
            except Exception as e:
                logger.warning(f"AI pitch deck generation failed: {e}")
            finally:
                loop.close()
        
        # Fallback content if AI fails
        if not slides:
            slides = {
                'title': {'bullets': [inputs.startup_name or project.name, inputs.startup_description or '']},
                'problem': {'bullets': ['Problem description to be defined']},
                'solution': {'bullets': [f'{inputs.startup_name or "Our solution"} provides...']},
                'market': {'bullets': [f'Target: {inputs.target_audience or "Various markets"}']},
                'business_model': {'bullets': [inputs.business_model or 'Revenue model to be defined']},
                'competition': {'bullets': ['Competitive analysis from research']},
                'traction': {'bullets': ['Key milestones']},
                'team': {'bullets': ['Founding team']},
                'financials': {'bullets': ['Financial projections']},
                'ask': {'bullets': ['Investment ask']},
            }
        
        update_report_progress(report, 70, "Generating HTML slides...")
        
        report_data = {
            'slides': slides,
            'startup_info': inputs_dict,
        }
        
        html_content = HTMLReportGenerator.generate_pitch_deck(
            report_data,
            inputs.startup_name or project.name
        )
        
        # Save to S3
        update_report_progress(report, 90, "Saving pitch deck...")
        
        if getattr(settings, 'USE_S3', False):
            try:
                org_id = str(project.organization_id) if project.organization_id else 'default'
                storage_service.upload_report(
                    org_id=org_id,
                    project_id=str(project.id),
                    report_type='pitch_deck',
                    report_id=str(report.id),
                    content=html_content.encode(),
                    file_type='html'
                )
            except Exception as e:
                logger.warning(f"S3 upload failed: {e}")
        
        # Save version
        report.current_version += 1
        ReportVersion.objects.create(
            report=report,
            version_number=report.current_version,
            html_content=html_content,
            data_snapshot=report_data,
            changes_summary="AI-generated pitch deck",
            generated_by=user
        )
        
        report.status = 'completed'
        report.progress = 100
        report.html_content = html_content
        report.data = report_data
        report.completed_at = timezone.now()
        report.save()
        
        send_progress_update(str(report.project_id), 'pitch_deck', 100, 'Complete!')
        return {"status": "success", "slides_count": len(slides)}
        
    except Exception as e:
        logger.error(f"❌ Failed to generate Pitch Deck: {e}")
        report.status = 'failed'
        report.error_message = str(e)
        report.save()
        raise


@shared_task(bind=True, queue='reports')
@close_db_wrapper
def generate_quick_report(self, report_id, user_id):
    """
    Generate Quick Report using AI.
    Uses comprehensive system prompt to generate market research report.
    
    Pipeline Steps:
    1. Initialize & Build Prompt
    2. Call AI for Report Generation
    3. Parse and Save Sections
    """
    from .models import Report, ReportVersion, ReportAnalysisSection
    from .progress_tracker import ReportProgressTracker
    from apps.users.models import User
    from services.openai_service import openai_service
    from services.quick_report_prompts import (
        get_quick_report_system_prompt,
        build_user_prompt,
        parse_report_sections
    )
    from services.report_storage import report_storage
    
    report = None
    tracker = None
    
    try:
        report = Report.objects.get(id=report_id)
        user = User.objects.get(id=user_id)
        project = report.project
        inputs = project.inputs
        
        # Mark as running
        report.status = 'running'
        report.started_at = timezone.now()
        report.save()
        
        # Initialize progress tracker
        tracker = ReportProgressTracker(report)
        tracker.initialize_steps()
        
        # ===== Step 1: Initialize & Build Prompt =====
        tracker.start_step('init')
        tracker.update_step_message('init', "Preparing market research request...")
        
        inputs_dict = get_project_inputs_dict(inputs)
        
        # Build the prompts
        system_prompt = get_quick_report_system_prompt()
        user_prompt = build_user_prompt(inputs_dict)
        
        tracker.add_step_detail('init', 'info', f"Startup: {inputs_dict.get('startup_name', 'Unknown')}")
        tracker.complete_step('init', {'startup_name': inputs_dict.get('startup_name')})
        
        # ===== Step 2: AI Generation =====
        tracker.start_step('api_search')  # Using api_search step key for progress consistency
        tracker.update_step_message('api_search', "Generating comprehensive market research with AI...")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Call the AI service
            report_content = loop.run_until_complete(
                openai_service.chat_completion(
                    messages=[{"role": "user", "content": user_prompt}],
                    system_prompt=system_prompt,
                    temperature=0.7,
                    max_tokens=8000  # Large response for comprehensive report
                )
            )
            
            if not report_content or report_content.startswith("AI service is not configured"):
                raise Exception("AI service unavailable or not configured")
            
            tracker.update_step_message('api_search', "AI analysis complete, processing results...")
            tracker.complete_step('api_search', {'response_length': len(report_content)})
            
        except Exception as e:
            logger.error(f"Quick Report AI generation failed: {e}")
            tracker.fail_step('api_search', str(e))
            raise
        finally:
            loop.close()
        
        # ===== Step 3: Parse and Save Sections =====
        tracker.start_step('save')
        tracker.update_step_message('save', "Saving report sections...")
        
        # Parse markdown into sections
        sections = parse_report_sections(report_content)
        
        # Delete old sections if any
        ReportAnalysisSection.objects.filter(report=report).delete()
        
        # Save sections to database
        section_order = 0
        for section_data in sections:
            ReportAnalysisSection.objects.create(
                report=report,
                section_type=section_data['section_type'],
                content_markdown=section_data['content'],
                order=section_order
            )
            section_order += 1
            
            # Also save to S3
            try:
                org_id = str(project.organization_id) if project.organization_id else 'default'
                report_storage.save_analysis_section(
                    project_id=str(project.id),
                    org_id=org_id,
                    version=report.current_version + 1,
                    section_type=section_data['section_type'],
                    content=section_data['content'],
                    report_type='quick_report'
                )
            except Exception as e:
                logger.warning(f"S3 save failed for section {section_data['section_type']}: {e}")
        
        # Create simple HTML content for legacy support
        html_content = f"<h1>Quick Market Research Report</h1>"
        html_content += f"<h2>{inputs_dict.get('startup_name', 'Startup')}</h2>"
        html_content += f"<div class='report-content'>{report_content}</div>"
        
        # Finalize report
        report.current_version += 1
        ReportVersion.objects.create(
            report=report,
            version_number=report.current_version,
            html_content=html_content,
            data_snapshot={'sections_count': len(sections)},
            changes_summary=f"AI-generated market research with {len(sections)} sections",
            generated_by=user
        )
        
        report.status = 'completed'
        report.progress = 100
        report.current_step = 'Complete!'
        report.html_content = html_content
        report.completed_at = timezone.now()
        report.save()
        
        # Save report metadata to S3
        try:
            org_id = str(project.organization_id) if project.organization_id else 'default'
            report_storage.save_report_metadata(
                project_id=str(project.id),
                org_id=org_id,
                version=report.current_version,
                metadata={
                    'report_id': str(report.id),
                    'project_id': str(project.id),
                    'org_id': org_id,
                    'startup_name': inputs_dict.get('startup_name'),
                    'sections_count': len(sections),
                    'generated_at': report.completed_at.isoformat() if report.completed_at else None,
                    'version': report.current_version,
                    'status': 'success'
                },
                report_type='quick_report'
            )
            logger.info(f"✅ Saved Quick Report metadata for project {project.id}")
        except Exception as e:
            logger.warning(f"Failed to save Quick Report metadata: {e}")
        
        tracker.complete_step('save', {'sections_saved': len(sections)})
        
        logger.info(f"✅ Quick Report generated for project {project.id} with {len(sections)} sections")
        return {"status": "success", "sections": len(sections)}
        
    except Exception as e:
        logger.error(f"❌ Failed to generate Quick Report: {e}")
        if report:
            report.status = 'failed'
            report.error_message = str(e)
            report.save()
            if tracker:
                from .models import ReportProgressStep
                running_step = ReportProgressStep.objects.filter(
                    report=report, status='running'
                ).first()
                if running_step:
                    tracker.fail_step(running_step.step_key, str(e))
        raise

