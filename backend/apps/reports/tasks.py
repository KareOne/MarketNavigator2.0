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

logger = logging.getLogger(__name__)


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
                logger.info(f"✅ Saved Crunchbase raw data JSON for project {project.id}")
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
            crunchbase_scraper.parse_company_data(c.get('company_data', c)) 
            for c in top_companies[:10]
        ]
        
        # Get final company names
        final_company_names = [c.get('name', 'Unknown') for c in companies_for_analysis if c.get('name')]
        
        # Only add detailed company ranks if NOT using orchestrator (to avoid duplicates)
        # Remote worker already sent these via real-time callbacks
        if not used_orchestrator:
            sorted_top_companies = result.get('metadata', {}).get('sorted_top_companies', [])
            if sorted_top_companies:
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
        
        # ===== Steps 3-10: Run Analysis Pipeline =====
        async def run_analysis_with_tracking():
            """Run analysis pipeline with step-by-step progress updates."""
            from asgiref.sync import sync_to_async
            
            # Wrap tracker methods for async use
            start_step = sync_to_async(tracker.start_step, thread_sensitive=True)
            complete_step = sync_to_async(tracker.complete_step, thread_sensitive=True)
            
            # Create pipeline (uses LIARA_MODEL from settings by default)
            pipeline = CrunchbaseAnalysisPipeline(
                target_market_description=target_description,
                progress_callback=None  # We handle progress via tracker
            )
            
            num_companies = len(companies_for_analysis)
            
            # Step 3: Company Overview
            await start_step('company_overview')
            overview = await pipeline._call_ai(
                pipeline.prompts.generate_company_overview(companies_for_analysis)
            )
            await complete_step('company_overview')
            
            # Save company overview to JSON
            try:
                org_id = str(project.organization_id) if project.organization_id else 'default'
                report_storage.save_analysis_section(
                    project_id=str(project.id),
                    org_id=org_id,
                    version=report.current_version + 1,
                    section_type='company_overview',
                    content=overview
                )
            except Exception as e:
                logger.warning(f"Failed to save company overview JSON: {e}")
            
            # Per-company reports
            per_company = {}
            report_types = [
                ('tech_product', pipeline.prompts.generate_tech_product_report),
                ('market_demand', pipeline.prompts.generate_market_demand_report),
                ('competitor', pipeline.prompts.generate_competitor_report),
                ('market_funding', pipeline.prompts.generate_market_funding_report),
                ('growth_potential', pipeline.prompts.generate_growth_potential_report),
                ('swot', pipeline.prompts.generate_swot_report),
            ]
            
            for step_key, prompt_fn in report_types:
                await start_step(step_key)
                per_company[step_key] = []
                
                for company in companies_for_analysis:
                    company_name = company.get("Company Name", company.get("name", "Unknown"))
                    try:
                        content = await pipeline._call_ai(prompt_fn(company))
                        per_company[step_key].append({
                            'company_name': company_name,
                            'content': content
                        })
                        
                        # Save per-company analysis to JSON
                        try:
                            org_id = str(project.organization_id) if project.organization_id else 'default'
                            report_storage.save_analysis_section(
                                project_id=str(project.id),
                                org_id=org_id,
                                version=report.current_version + 1,
                                section_type=step_key,
                                content=content,
                                company_name=company_name
                            )
                        except Exception as save_err:
                            logger.warning(f"Failed to save {step_key} JSON for {company_name}: {save_err}")
                            
                    except Exception as e:
                        logger.error(f"Analysis failed for {company_name}: {e}")
                        per_company[step_key].append({
                            'company_name': company_name,
                            'content': f"Analysis error: {str(e)}"
                        })
                
                await complete_step(step_key, {'companies_analyzed': len(per_company[step_key])})
            
            # Step 10: Executive Summaries
            await start_step('summaries')
            summaries = {}
            summary_types = [
                ('tech_product_summary', pipeline.prompts.generate_tech_product_summary, 'tech_product'),
                ('market_demand_summary', pipeline.prompts.generate_market_demand_summary, 'market_demand'),
                ('competitor_summary', pipeline.prompts.generate_competitor_summary, 'competitor'),
                ('market_funding_summary', pipeline.prompts.generate_market_funding_summary, 'market_funding'),
                ('growth_potential_summary', pipeline.prompts.generate_growth_potential_summary, 'growth_potential'),
                ('swot_summary', pipeline.prompts.generate_swot_summary, 'swot'),
            ]
            
            for sum_key, prompt_fn, source_key in summary_types:
                reports = [r['content'] for r in per_company.get(source_key, [])]
                if reports:
                    summaries[sum_key] = await pipeline._call_ai(
                        prompt_fn(reports, num_companies),
                        max_tokens=4000
                    )
                    
                    # Save summary to JSON
                    try:
                        org_id = str(project.organization_id) if project.organization_id else 'default'
                        report_storage.save_analysis_summary(
                            project_id=str(project.id),
                            org_id=org_id,
                            version=report.current_version + 1,
                            summary_type=sum_key,
                            content=summaries[sum_key]
                        )
                    except Exception as save_err:
                        logger.warning(f"Failed to save {sum_key} JSON: {save_err}")
            
            await complete_step('summaries', {'summaries_generated': len(summaries)})
            
            return {
                'company_overview': overview,
                'per_company': per_company,
                'summaries': summaries,
                'company_count': num_companies
            }
        
        # Run the analysis
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            analysis_result = loop.run_until_complete(run_analysis_with_tracking())
        finally:
            loop.close()
        
        # ===== Step 11: Generate HTML =====
        tracker.start_step('html_gen')
        
        # Format result for HTML generator
        formatted_result = {
            'company_count': analysis_result['company_count'],
            'processing_time': 0,  # Will be calculated
            'sections': {
                'company_overview': {'content': analysis_result['company_overview'], 'type': 'company_overview'},
                'per_company': analysis_result['per_company'],
            }
        }
        for sum_key, content in analysis_result['summaries'].items():
            formatted_result['sections'][sum_key] = {'content': content, 'type': sum_key}
        
        html_content = generate_analysis_html(
            formatted_result,
            inputs.startup_name or project.name
        )
        
        tracker.complete_step('html_gen', {'html_size': len(html_content)})
        
        # ===== Step 12: Save =====
        tracker.start_step('save')
        
        # Save analysis sections to database
        section_order = 0
        
        # Save overview
        ReportAnalysisSection.objects.create(
            report=report,
            section_type='company_overview',
            content_markdown=analysis_result['company_overview'],
            order=section_order
        )
        section_order += 1
        
        # Save per-company reports
        for section_type, reports in analysis_result['per_company'].items():
            for report_item in reports:
                ReportAnalysisSection.objects.create(
                    report=report,
                    section_type=section_type,
                    company_name=report_item['company_name'],
                    content_markdown=report_item['content'],
                    order=section_order
                )
                section_order += 1
        
        # Save summaries
        for sum_key, content in analysis_result['summaries'].items():
            ReportAnalysisSection.objects.create(
                report=report,
                section_type=sum_key,
                content_markdown=content,
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
            changes_summary=f"Full 13-step analysis: {analysis_result['company_count']} companies",
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
                }
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
def generate_tracxn_report(self, report_id, user_id):
    """
    Generate Tracxn analysis report using 6-step AI pipeline.
    Per FINAL_ARCHITECTURE - Panel 2: Tracxn Analysis
    
    Pipeline Steps:
    1. Initialize & Generate Keywords
    2. Search Tracxn API  
    3. Rank Results by Similarity
    4. Fetch Startup Details
    5. Competitor Analysis (per startup)
    6. Market & Funding Analysis (per startup)
    7. Growth Potential Analysis (per startup)
    8. Executive Summaries
    9. Generate HTML Report
    10. Save Report
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
            # Generate keywords using Liara AI - NO FALLBACK
            from services.keyword_generator import KeywordGenerator
            
            tracker.update_step_message('init', "Generating AI-powered search keywords...")
            logger.info("🔑 Generating search keywords using Liara AI (forced tool calling)...")
            
            generator = KeywordGenerator()
            project_input_dict = get_project_inputs_dict(inputs)
            search_params = generator.generate(project_input_dict)  # Will raise exception if fails
            
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
        tracker.start_step('api_search')
        keywords_list = ', '.join(keywords[:3])
        tracker.update_step_message('api_search', f"Searching Tracxn with {len(keywords)} keywords: {keywords_list}...")
        
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
            company_data = c.get('company_data', c)
            name = company_data.get('name') or company_data.get('Name') or 'Unknown'
            if name and name != 'Unknown':
                top_startup_names.append(name)
        
        if top_startup_names:
            names_preview = ', '.join(top_startup_names[:5])
            if len(top_startup_names) > 5:
                names_preview += f' +{len(top_startup_names) - 5} more'
            tracker.update_step_message('sorting', f"Top {len(top_startup_names)} matches: {names_preview}")
        else:
            tracker.update_step_message('sorting', f"Ranking {len(top_companies)} startups by similarity...")
        
        # Parse company data for analysis
        startups_for_analysis = [
            tracxn_scraper.parse_company_data(c.get('company_data', c)) 
            for c in top_companies[:15]
        ]
        
        # Add sorted startups as step details
        for idx, startup in enumerate(startups_for_analysis, 1):
            name = startup.get('name', 'Unknown')
            score = startup.get('combined_score', startup.get('tracxn_score', 'N/A'))
            tracker.add_step_detail(
                'sorting',
                'startup_rank',
                f"{idx}. {name} (Score: {score})",
                {'rank': idx, 'name': name, 'score': score}
            )
        
        tracker.complete_step('sorting', {'startups_sorted': len(startups_for_analysis)})
        
        if not startups_for_analysis:
            raise Exception("No startups found for analysis")
        
        # ===== Step 4: Fetching Details =====
        tracker.start_step('fetching_details')
        tracker.update_step_message(
            'fetching_details',
            f"Processing {len(startups_for_analysis)} startups...",
            progress_percent=50
        )
        tracker.complete_step('fetching_details', {'startups_processed': len(startups_for_analysis)})
        
        # ===== Steps 5-8: Run AI Analysis Pipeline =====
        async def run_analysis_with_tracking():
            """Run analysis pipeline with step-by-step progress updates."""
            from asgiref.sync import sync_to_async
            
            start_step = sync_to_async(tracker.start_step, thread_sensitive=True)
            complete_step = sync_to_async(tracker.complete_step, thread_sensitive=True)
            
            pipeline = TracxnAnalysisPipeline(
                target_market_description=target_description,
                progress_callback=None
            )
            
            num_startups = len(startups_for_analysis)
            
            # Step 5: Competitor Analysis
            await start_step('competitor')
            competitor_reports = []
            for startup in startups_for_analysis:
                startup_name = startup.get('name', 'Unknown')
                try:
                    prompt = pipeline.prompts.generate_competitor_report(startup, target_description)
                    content = await pipeline._call_ai(prompt)
                    competitor_reports.append({'company_name': startup_name, 'content': content})
                except Exception as e:
                    logger.error(f"Competitor analysis failed for {startup_name}: {e}")
                    competitor_reports.append({'company_name': startup_name, 'content': f"Analysis error: {str(e)}"})
            await complete_step('competitor', {'startups_analyzed': len(competitor_reports)})
            
            # Step 6: Market & Funding Analysis
            await start_step('market_funding')
            market_funding_reports = []
            for startup in startups_for_analysis:
                startup_name = startup.get('name', 'Unknown')
                try:
                    prompt = pipeline.prompts.generate_market_funding_report(startup, target_description)
                    content = await pipeline._call_ai(prompt)
                    market_funding_reports.append({'company_name': startup_name, 'content': content})
                except Exception as e:
                    logger.error(f"Market funding analysis failed for {startup_name}: {e}")
                    market_funding_reports.append({'company_name': startup_name, 'content': f"Analysis error: {str(e)}"})
            await complete_step('market_funding', {'startups_analyzed': len(market_funding_reports)})
            
            # Step 7: Growth Potential Analysis
            await start_step('growth_potential')
            growth_potential_reports = []
            for startup in startups_for_analysis:
                startup_name = startup.get('name', 'Unknown')
                try:
                    prompt = pipeline.prompts.generate_growth_potential_report(startup, target_description)
                    content = await pipeline._call_ai(prompt)
                    growth_potential_reports.append({'company_name': startup_name, 'content': content})
                except Exception as e:
                    logger.error(f"Growth potential analysis failed for {startup_name}: {e}")
                    growth_potential_reports.append({'company_name': startup_name, 'content': f"Analysis error: {str(e)}"})
            await complete_step('growth_potential', {'startups_analyzed': len(growth_potential_reports)})
            
            # Step 8: Executive Summaries
            await start_step('summaries')
            summaries = {}
            
            # Competitor Summary
            competitor_texts = [r['content'] for r in competitor_reports]
            summaries['competitor_summary'] = await pipeline._call_ai(
                pipeline.prompts.generate_competitor_summary(competitor_texts, num_startups, target_description),
                max_tokens=4000
            )
            
            # Market Funding Summary
            market_texts = [r['content'] for r in market_funding_reports]
            summaries['market_funding_summary'] = await pipeline._call_ai(
                pipeline.prompts.generate_market_funding_summary(market_texts, num_startups, target_description),
                max_tokens=4000
            )
            
            # Growth Potential Summary
            growth_texts = [r['content'] for r in growth_potential_reports]
            summaries['growth_potential_summary'] = await pipeline._call_ai(
                pipeline.prompts.generate_growth_potential_summary(growth_texts, num_startups, target_description),
                max_tokens=4000
            )
            
            await complete_step('summaries', {'summaries_generated': len(summaries)})
            
            return {
                'competitor_reports': competitor_reports,
                'market_funding_reports': market_funding_reports,
                'growth_potential_reports': growth_potential_reports,
                'competitor_summary': summaries['competitor_summary'],
                'market_funding_summary': summaries['market_funding_summary'],
                'growth_potential_summary': summaries['growth_potential_summary'],
                'company_count': num_startups,
            }
        
        # Run the analysis
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            analysis_result = loop.run_until_complete(run_analysis_with_tracking())
        finally:
            loop.close()
        
        # ===== Step 9: Generate HTML =====
        tracker.start_step('html_gen')
        
        # Format result for HTML generator
        formatted_result = {
            'company_count': analysis_result['company_count'],
            'processing_time': 0,
            'competitor_reports': analysis_result['competitor_reports'],
            'market_funding_reports': analysis_result['market_funding_reports'],
            'growth_potential_reports': analysis_result['growth_potential_reports'],
            'competitor_summary': analysis_result['competitor_summary'],
            'market_funding_summary': analysis_result['market_funding_summary'],
            'growth_potential_summary': analysis_result['growth_potential_summary'],
        }
        
        html_content = generate_tracxn_html(
            formatted_result,
            inputs.startup_name or project.name
        )
        
        tracker.complete_step('html_gen', {'html_size': len(html_content)})
        
        # ===== Step 10: Save =====
        tracker.start_step('save')
        
        # Save analysis sections to database
        section_order = 0
        
        # Save competitor reports
        for report_item in analysis_result['competitor_reports']:
            ReportAnalysisSection.objects.create(
                report=report,
                section_type='competitor',
                company_name=report_item['company_name'],
                content_markdown=report_item['content'],
                order=section_order
            )
            section_order += 1
        
        # Save market funding reports
        for report_item in analysis_result['market_funding_reports']:
            ReportAnalysisSection.objects.create(
                report=report,
                section_type='market_funding',
                company_name=report_item['company_name'],
                content_markdown=report_item['content'],
                order=section_order
            )
            section_order += 1
        
        # Save growth potential reports
        for report_item in analysis_result['growth_potential_reports']:
            ReportAnalysisSection.objects.create(
                report=report,
                section_type='growth_potential',
                company_name=report_item['company_name'],
                content_markdown=report_item['content'],
                order=section_order
            )
            section_order += 1
        
        # Save summaries
        ReportAnalysisSection.objects.create(
            report=report,
            section_type='competitor_summary',
            content_markdown=analysis_result['competitor_summary'],
            order=section_order
        )
        section_order += 1
        
        ReportAnalysisSection.objects.create(
            report=report,
            section_type='market_funding_summary',
            content_markdown=analysis_result['market_funding_summary'],
            order=section_order
        )
        section_order += 1
        
        ReportAnalysisSection.objects.create(
            report=report,
            section_type='growth_potential_summary',
            content_markdown=analysis_result['growth_potential_summary'],
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
                    report_type='tracxn',
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
            changes_summary=f"6-step Tracxn analysis: {analysis_result['company_count']} startups",
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
def generate_social_report(self, report_id, user_id):
    """
    Generate Social analysis report.
    
    NOTE: This feature is currently DISABLED.
    Twitter and LinkedIn scrapers have been removed from the project.
    """
    from .models import Report
    from apps.users.models import User
    
    try:
        report = Report.objects.get(id=report_id)
        user = User.objects.get(id=user_id)
        project = report.project
        
        # Feature is disabled
        report.status = 'failed'
        report.progress = 0
        report.current_step = 'Feature temporarily disabled'
        report.error_message = (
            'Social Analysis (Twitter/LinkedIn) is currently disabled. '
            'This feature will be available in a future update.'
        )
        report.save()
        
        send_progress_update(
            str(report.project_id), 
            'social', 
            0, 
            'Feature disabled'
        )
        
        logger.info(f"Social report disabled for project {project.id}")
        return {"status": "disabled", "message": "Social Analysis feature is currently disabled"}
        
    except Exception as e:
        logger.error(f"❌ Error in disabled social report: {e}")
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
