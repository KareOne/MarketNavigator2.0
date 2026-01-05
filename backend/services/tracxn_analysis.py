"""
Tracxn Analysis Pipeline Service.
Orchestrates 14-step AI analysis process with progress tracking.

Per FINAL_ARCHITECTURE_SPECIFICATION.md - Panel 2: Tracxn Analysis.

Pipeline Steps (Per Company):
1. Company Overview Report
2. Technology & Product Report
3. Market Demand Report
4. Competitor Identification Report
5. Market & Funding Insights Report
6. Growth Potential Report
7. SWOT Analysis Report

Pipeline Steps (Aggregate Summaries):
8. Company Overview Summary
9. Technology & Product Summary
10. Market Demand Summary
11. Competitor Summary
12. Market & Funding Summary
13. Growth Potential Summary
14. SWOT Summary
"""
import logging
import time
import asyncio
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime

from openai import AsyncOpenAI
from django.conf import settings

from .tracxn_prompts import TracxnPromptTemplates

logger = logging.getLogger(__name__)


class TracxnAnalysisPipeline:
    """
    Main pipeline for analyzing Tracxn startup data through 14 AI steps.
    
    Per-Company Analysis (7 types):
    1. Company Overview
    2. Technology & Product
    3. Market Demand
    4. Competitor Identification
    5. Market & Funding Insights
    6. Growth Potential
    7. SWOT Analysis
    
    Aggregate Summaries (7 summaries):
    8-14. Summaries for each analysis type
    """
    
    def __init__(
        self,
        target_market_description: str = "",
        progress_callback: Optional[Callable] = None,
        model: str = None  # Will use LIARA_MODEL default if not specified
    ):
        """
        Initialize the analysis pipeline.
        
        Args:
            target_market_description: Context for analysis
            progress_callback: Async function to call with progress updates
            model: Model to use (defaults to LIARA_MODEL)
        """
        self.target_market_description = target_market_description
        self.progress_callback = progress_callback
        
        # Use Liara model by default (same as Crunchbase)
        self.model = model or getattr(settings, 'LIARA_MODEL', 'gpt-4o-mini')
        
        # Initialize OpenAI client for Liara
        liara_api_key = getattr(settings, 'LIARA_API_KEY', '')
        liara_base_url = getattr(settings, 'LIARA_BASE_URL', 'https://ai.liara.ir/api/v1')
        
        self.client = AsyncOpenAI(
            api_key=liara_api_key,
            base_url=liara_base_url,
        )
        
        self.prompts = TracxnPromptTemplates()
        
        # Track timing
        self.step_times = {}
        
        logger.info(f"Initialized TracxnAnalysisPipeline with model: {self.model}")
    
    async def _call_ai(self, prompt: str, max_tokens: int = 3000) -> str:
        """Call OpenAI API with the given prompt."""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.7,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"AI call failed: {e}")
            raise
    
    async def _update_progress(self, step: str, message: str, progress: int):
        """Send progress update if callback provided."""
        if self.progress_callback:
            try:
                await self.progress_callback(step, message, progress)
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")
    
    async def analyze(
        self,
        companies: List[Dict[str, Any]],
        max_companies: int = 15
    ) -> Dict[str, Any]:
        """
        Run the complete 14-step analysis pipeline.
        
        Args:
            companies: List of company data dictionaries from Tracxn scraper
            max_companies: Maximum number of companies for detailed analysis
            
        Returns:
            Dictionary containing all analysis results
        """
        start_time = time.time()
        
        # Limit companies for analysis
        companies_to_analyze = companies[:max_companies]
        num_companies = len(companies_to_analyze)
        
        logger.info(f"Starting Tracxn 14-step analysis for {num_companies} companies")
        
        result = {
            'company_count': num_companies,
            # Per-company reports
            'company_overview_reports': [],
            'tech_product_reports': [],
            'market_demand_reports': [],
            'competitor_reports': [],
            'market_funding_reports': [],
            'growth_potential_reports': [],
            'swot_reports': [],
            # Summaries
            'company_overview_summary': '',
            'tech_product_summary': '',
            'market_demand_summary': '',
            'competitor_summary': '',
            'market_funding_summary': '',
            'growth_potential_summary': '',
            'swot_summary': '',
            # Metadata
            'processing_time': 0,
            'generated_at': datetime.now().isoformat(),
        }
        
        try:
            # ===== Per-Company Analysis (Steps 1-7) =====
            
            # Step 1: Company Overview Reports
            logger.info("Step 1/14: Generating company overview reports...")
            await self._update_progress("company_overview", "Generating company overviews", 5)
            
            for i, company in enumerate(companies_to_analyze):
                company_name = company.get('name', company.get('Company Name', f'Company {i+1}'))
                try:
                    prompt = self.prompts.generate_company_overview(
                        company, self.target_market_description
                    )
                    report = await self._call_ai(prompt)
                    result['company_overview_reports'].append({
                        'company_name': company_name,
                        'content': report
                    })
                except Exception as e:
                    logger.error(f"Company overview failed for {company_name}: {e}")
                    result['company_overview_reports'].append({
                        'company_name': company_name,
                        'content': f"Analysis error: {str(e)}"
                    })
            
            # Step 2: Technology & Product Reports
            logger.info("Step 2/14: Generating technology & product reports...")
            await self._update_progress("tech_product", "Analyzing technology and products", 12)
            
            for i, company in enumerate(companies_to_analyze):
                company_name = company.get('name', company.get('Company Name', f'Company {i+1}'))
                try:
                    prompt = self.prompts.generate_tech_product_report(
                        company, self.target_market_description
                    )
                    report = await self._call_ai(prompt)
                    result['tech_product_reports'].append({
                        'company_name': company_name,
                        'content': report
                    })
                except Exception as e:
                    logger.error(f"Tech product report failed for {company_name}: {e}")
                    result['tech_product_reports'].append({
                        'company_name': company_name,
                        'content': f"Analysis error: {str(e)}"
                    })
            
            # Step 3: Market Demand Reports
            logger.info("Step 3/14: Generating market demand reports...")
            await self._update_progress("market_demand", "Analyzing market demand and traction", 19)
            
            for i, company in enumerate(companies_to_analyze):
                company_name = company.get('name', company.get('Company Name', f'Company {i+1}'))
                try:
                    prompt = self.prompts.generate_market_demand_report(
                        company, self.target_market_description
                    )
                    report = await self._call_ai(prompt)
                    result['market_demand_reports'].append({
                        'company_name': company_name,
                        'content': report
                    })
                except Exception as e:
                    logger.error(f"Market demand report failed for {company_name}: {e}")
                    result['market_demand_reports'].append({
                        'company_name': company_name,
                        'content': f"Analysis error: {str(e)}"
                    })
            
            # Step 4: Competitor Identification Reports
            logger.info("Step 4/14: Generating competitor identification reports...")
            await self._update_progress("competitor", "Analyzing competitive landscape", 26)
            
            for i, company in enumerate(companies_to_analyze):
                company_name = company.get('name', company.get('Company Name', f'Company {i+1}'))
                try:
                    prompt = self.prompts.generate_competitor_report(
                        company, self.target_market_description
                    )
                    report = await self._call_ai(prompt)
                    result['competitor_reports'].append({
                        'company_name': company_name,
                        'content': report
                    })
                except Exception as e:
                    logger.error(f"Competitor report failed for {company_name}: {e}")
                    result['competitor_reports'].append({
                        'company_name': company_name,
                        'content': f"Analysis error: {str(e)}"
                    })
            
            # Step 5: Market & Funding Insights Reports
            logger.info("Step 5/14: Generating market & funding insights reports...")
            await self._update_progress("market_funding", "Analyzing funding patterns", 33)
            
            for i, company in enumerate(companies_to_analyze):
                company_name = company.get('name', company.get('Company Name', f'Company {i+1}'))
                try:
                    prompt = self.prompts.generate_market_funding_report(
                        company, self.target_market_description
                    )
                    report = await self._call_ai(prompt)
                    result['market_funding_reports'].append({
                        'company_name': company_name,
                        'content': report
                    })
                except Exception as e:
                    logger.error(f"Market funding report failed for {company_name}: {e}")
                    result['market_funding_reports'].append({
                        'company_name': company_name,
                        'content': f"Analysis error: {str(e)}"
                    })
            
            # Step 6: Growth Potential Reports
            logger.info("Step 6/14: Generating growth potential reports...")
            await self._update_progress("growth_potential", "Evaluating growth potential", 40)
            
            for i, company in enumerate(companies_to_analyze):
                company_name = company.get('name', company.get('Company Name', f'Company {i+1}'))
                try:
                    prompt = self.prompts.generate_growth_potential_report(
                        company, self.target_market_description
                    )
                    report = await self._call_ai(prompt)
                    result['growth_potential_reports'].append({
                        'company_name': company_name,
                        'content': report
                    })
                except Exception as e:
                    logger.error(f"Growth potential report failed for {company_name}: {e}")
                    result['growth_potential_reports'].append({
                        'company_name': company_name,
                        'content': f"Analysis error: {str(e)}"
                    })
            
            # Step 7: SWOT Analysis Reports
            logger.info("Step 7/14: Generating SWOT analysis reports...")
            await self._update_progress("swot", "Performing SWOT analysis", 47)
            
            for i, company in enumerate(companies_to_analyze):
                company_name = company.get('name', company.get('Company Name', f'Company {i+1}'))
                try:
                    prompt = self.prompts.generate_swot_report(
                        company, self.target_market_description
                    )
                    report = await self._call_ai(prompt)
                    result['swot_reports'].append({
                        'company_name': company_name,
                        'content': report
                    })
                except Exception as e:
                    logger.error(f"SWOT report failed for {company_name}: {e}")
                    result['swot_reports'].append({
                        'company_name': company_name,
                        'content': f"Analysis error: {str(e)}"
                    })
            
            # ===== Aggregate Summaries (Steps 8-14) =====
            
            # Step 8: Company Overview Summary
            logger.info("Step 8/14: Generating company overview summary...")
            await self._update_progress("summaries", "Generating executive summaries (1/7)", 54)
            
            overview_texts = [r['content'] for r in result['company_overview_reports']]
            prompt = self.prompts.generate_company_overview_summary(
                overview_texts, num_companies, self.target_market_description
            )
            result['company_overview_summary'] = await self._call_ai(prompt, max_tokens=4000)
            
            # Step 9: Technology & Product Summary
            logger.info("Step 9/14: Generating technology & product summary...")
            await self._update_progress("summaries", "Generating executive summaries (2/7)", 61)
            
            tech_texts = [r['content'] for r in result['tech_product_reports']]
            prompt = self.prompts.generate_tech_product_summary(
                tech_texts, num_companies, self.target_market_description
            )
            result['tech_product_summary'] = await self._call_ai(prompt, max_tokens=4000)
            
            # Step 10: Market Demand Summary
            logger.info("Step 10/14: Generating market demand summary...")
            await self._update_progress("summaries", "Generating executive summaries (3/7)", 68)
            
            demand_texts = [r['content'] for r in result['market_demand_reports']]
            prompt = self.prompts.generate_market_demand_summary(
                demand_texts, num_companies, self.target_market_description
            )
            result['market_demand_summary'] = await self._call_ai(prompt, max_tokens=4000)
            
            # Step 11: Competitor Summary
            logger.info("Step 11/14: Generating competitor summary...")
            await self._update_progress("summaries", "Generating executive summaries (4/7)", 75)
            
            competitor_texts = [r['content'] for r in result['competitor_reports']]
            prompt = self.prompts.generate_competitor_summary(
                competitor_texts, num_companies, self.target_market_description
            )
            result['competitor_summary'] = await self._call_ai(prompt, max_tokens=4000)
            
            # Step 12: Market & Funding Summary
            logger.info("Step 12/14: Generating market & funding summary...")
            await self._update_progress("summaries", "Generating executive summaries (5/7)", 82)
            
            market_texts = [r['content'] for r in result['market_funding_reports']]
            prompt = self.prompts.generate_market_funding_summary(
                market_texts, num_companies, self.target_market_description
            )
            result['market_funding_summary'] = await self._call_ai(prompt, max_tokens=4000)
            
            # Step 13: Growth Potential Summary
            logger.info("Step 13/14: Generating growth potential summary...")
            await self._update_progress("summaries", "Generating executive summaries (6/7)", 89)
            
            growth_texts = [r['content'] for r in result['growth_potential_reports']]
            prompt = self.prompts.generate_growth_potential_summary(
                growth_texts, num_companies, self.target_market_description
            )
            result['growth_potential_summary'] = await self._call_ai(prompt, max_tokens=4000)
            
            # Step 14: SWOT Summary
            logger.info("Step 14/14: Generating SWOT summary...")
            await self._update_progress("summaries", "Generating executive summaries (7/7)", 96)
            
            swot_texts = [r['content'] for r in result['swot_reports']]
            prompt = self.prompts.generate_swot_summary(
                swot_texts, num_companies, self.target_market_description
            )
            result['swot_summary'] = await self._call_ai(prompt, max_tokens=4000)
            
            # Calculate processing time
            result['processing_time'] = time.time() - start_time
            
            logger.info(f"Tracxn 14-step analysis completed in {result['processing_time']:.2f}s")
            
            return result
            
        except Exception as e:
            logger.error(f"Tracxn analysis pipeline failed: {e}")
            raise


def generate_tracxn_html(result: Dict[str, Any], startup_name: str = "Your Startup") -> str:
    """
    Generate HTML report from Tracxn analysis results.
    
    Args:
        result: Analysis result dictionary from pipeline
        startup_name: Name to display in report header
        
    Returns:
        Complete HTML string
    """
    import markdown
    
    def md_to_html(text: str) -> str:
        """Convert markdown to HTML."""
        if not text:
            return ""
        return markdown.markdown(text, extensions=['tables', 'fenced_code'])
    
    # Build HTML sections
    html_parts = []
    
    # Header
    html_parts.append(f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Tracxn Market Analysis - {startup_name}</title>
    <style>
        :root {{
            --primary: #6366f1;
            --primary-dark: #4f46e5;
            --secondary: #10b981;
            --accent: #f59e0b;
            --bg-dark: #0f172a;
            --bg-card: #1e293b;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --border: #334155;
        }}
        
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg-dark);
            color: var(--text-primary);
            line-height: 1.7;
            padding: 2rem;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        
        header {{
            text-align: center;
            margin-bottom: 3rem;
            padding: 2rem;
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
            border-radius: 16px;
        }}
        
        header h1 {{
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
        }}
        
        header .subtitle {{
            color: rgba(255,255,255,0.8);
            font-size: 1.1rem;
        }}
        
        header .stats {{
            display: flex;
            justify-content: center;
            gap: 2rem;
            margin-top: 1.5rem;
            flex-wrap: wrap;
        }}
        
        header .stat {{
            background: rgba(255,255,255,0.1);
            padding: 1rem 1.5rem;
            border-radius: 8px;
        }}
        
        header .stat-value {{
            font-size: 1.5rem;
            font-weight: 700;
        }}
        
        header .stat-label {{
            font-size: 0.85rem;
            opacity: 0.8;
        }}
        
        .section {{
            background: var(--bg-card);
            border-radius: 12px;
            padding: 2rem;
            margin-bottom: 2rem;
            border: 1px solid var(--border);
        }}
        
        .section h2 {{
            color: var(--primary);
            font-size: 1.5rem;
            margin-bottom: 1.5rem;
            padding-bottom: 0.75rem;
            border-bottom: 2px solid var(--primary);
        }}
        
        .section h3 {{
            color: var(--secondary);
            font-size: 1.2rem;
            margin: 1.5rem 0 1rem 0;
        }}
        
        .section h4 {{
            color: var(--accent);
            font-size: 1rem;
            margin: 1rem 0 0.5rem 0;
        }}
        
        .section p {{
            color: var(--text-secondary);
            margin-bottom: 1rem;
        }}
        
        .section ul, .section ol {{
            color: var(--text-secondary);
            padding-left: 1.5rem;
            margin-bottom: 1rem;
        }}
        
        .section li {{
            margin-bottom: 0.5rem;
        }}
        
        .section strong {{
            color: var(--text-primary);
        }}
        
        .company-report {{
            background: rgba(99, 102, 241, 0.1);
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            border-left: 4px solid var(--primary);
        }}
        
        .company-report h4 {{
            color: var(--text-primary);
            margin-bottom: 1rem;
        }}
        
        .summary-section {{
            background: linear-gradient(135deg, rgba(16, 185, 129, 0.1) 0%, rgba(99, 102, 241, 0.1) 100%);
            border-left: 4px solid var(--secondary);
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 1rem 0;
        }}
        
        th, td {{
            padding: 0.75rem;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }}
        
        th {{
            background: rgba(99, 102, 241, 0.2);
            color: var(--text-primary);
        }}
        
        td {{
            color: var(--text-secondary);
        }}
        
        footer {{
            text-align: center;
            padding: 2rem;
            color: var(--text-secondary);
            font-size: 0.9rem;
        }}
        
        @media (max-width: 768px) {{
            body {{
                padding: 1rem;
            }}
            
            header h1 {{
                font-size: 1.8rem;
            }}
            
            header .stats {{
                flex-direction: column;
                gap: 1rem;
            }}
            
            .section {{
                padding: 1.5rem;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🔍 Tracxn Market Analysis</h1>
            <p class="subtitle">Comprehensive startup landscape analysis for {startup_name}</p>
            <div class="stats">
                <div class="stat">
                    <div class="stat-value">{result.get('company_count', 0)}</div>
                    <div class="stat-label">Companies Analyzed</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{result.get('processing_time', 0):.1f}s</div>
                    <div class="stat-label">Processing Time</div>
                </div>
                <div class="stat">
                    <div class="stat-value">14</div>
                    <div class="stat-label">Analysis Steps</div>
                </div>
            </div>
        </header>
""")
    
    # Executive Summaries Section
    html_parts.append("""
        <div class="section summary-section">
            <h2>📋 Executive Summaries</h2>
""")
    
    # Company Overview Summary
    if result.get('company_overview_summary'):
        html_parts.append(f"""
            <h3>📊 Market Overview</h3>
            {md_to_html(result['company_overview_summary'])}
""")
    
    # Tech & Product Summary
    if result.get('tech_product_summary'):
        html_parts.append(f"""
            <h3>💻 Technology & Product Landscape</h3>
            {md_to_html(result['tech_product_summary'])}
""")
    
    # Market Demand Summary
    if result.get('market_demand_summary'):
        html_parts.append(f"""
            <h3>📈 Market Demand & Traction</h3>
            {md_to_html(result['market_demand_summary'])}
""")
    
    # Competitor Summary
    if result.get('competitor_summary'):
        html_parts.append(f"""
            <h3>🎯 Competitive Landscape</h3>
            {md_to_html(result['competitor_summary'])}
""")
    
    # Market & Funding Summary
    if result.get('market_funding_summary'):
        html_parts.append(f"""
            <h3>💰 Funding Insights</h3>
            {md_to_html(result['market_funding_summary'])}
""")
    
    # Growth Potential Summary
    if result.get('growth_potential_summary'):
        html_parts.append(f"""
            <h3>🚀 Growth Potential</h3>
            {md_to_html(result['growth_potential_summary'])}
""")
    
    # SWOT Summary
    if result.get('swot_summary'):
        html_parts.append(f"""
            <h3>⚖️ Strategic SWOT Landscape</h3>
            {md_to_html(result['swot_summary'])}
""")
    
    html_parts.append("</div>")  # Close summaries section
    
    # Per-Company Reports Section
    html_parts.append("""
        <div class="section">
            <h2>📊 Individual Company Analysis</h2>
""")
    
    # Company Overview Reports
    if result.get('company_overview_reports'):
        html_parts.append("<h3>📊 Company Overviews</h3>")
        for report in result['company_overview_reports']:
            html_parts.append(f"""
            <div class="company-report">
                <h4>{report['company_name']}</h4>
                {md_to_html(report['content'])}
            </div>
""")
    
    # Tech & Product Reports
    if result.get('tech_product_reports'):
        html_parts.append("<h3>💻 Technology & Product Reports</h3>")
        for report in result['tech_product_reports']:
            html_parts.append(f"""
            <div class="company-report">
                <h4>{report['company_name']}</h4>
                {md_to_html(report['content'])}
            </div>
""")
    
    # Market Demand Reports
    if result.get('market_demand_reports'):
        html_parts.append("<h3>📈 Market Demand Reports</h3>")
        for report in result['market_demand_reports']:
            html_parts.append(f"""
            <div class="company-report">
                <h4>{report['company_name']}</h4>
                {md_to_html(report['content'])}
            </div>
""")
    
    # Competitor Reports
    if result.get('competitor_reports'):
        html_parts.append("<h3>🎯 Competitive Intelligence Reports</h3>")
        for report in result['competitor_reports']:
            html_parts.append(f"""
            <div class="company-report">
                <h4>{report['company_name']}</h4>
                {md_to_html(report['content'])}
            </div>
""")
    
    # Market & Funding Reports
    if result.get('market_funding_reports'):
        html_parts.append("<h3>💰 Funding Reports</h3>")
        for report in result['market_funding_reports']:
            html_parts.append(f"""
            <div class="company-report">
                <h4>{report['company_name']}</h4>
                {md_to_html(report['content'])}
            </div>
""")
    
    # Growth Potential Reports
    if result.get('growth_potential_reports'):
        html_parts.append("<h3>🚀 Growth Potential Reports</h3>")
        for report in result['growth_potential_reports']:
            html_parts.append(f"""
            <div class="company-report">
                <h4>{report['company_name']}</h4>
                {md_to_html(report['content'])}
            </div>
""")
    
    # SWOT Reports
    if result.get('swot_reports'):
        html_parts.append("<h3>⚖️ SWOT Analysis Reports</h3>")
        for report in result['swot_reports']:
            html_parts.append(f"""
            <div class="company-report">
                <h4>{report['company_name']}</h4>
                {md_to_html(report['content'])}
            </div>
""")
    
    html_parts.append("</div>")  # Close per-company section
    
    # Footer
    html_parts.append(f"""
        <footer>
            <p>Generated by Market Navigator • {result.get('generated_at', datetime.now().isoformat())}</p>
            <p>Powered by Tracxn Data & 14-Step AI Analysis</p>
        </footer>
    </div>
</body>
</html>
""")
    
    return ''.join(html_parts)
