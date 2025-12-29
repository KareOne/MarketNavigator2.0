"""
Tracxn Analysis Pipeline Service.
Orchestrates 6-step AI analysis process with progress tracking.

Per FINAL_ARCHITECTURE_SPECIFICATION.md - Panel 2: Tracxn Analysis.

Pipeline Steps:
1. Generate Competitor Identification Reports (per company)
2. Generate Market & Funding Insights Reports (per company)
3. Generate Growth Potential Reports (per company)
4. Generate Competitor Identification Summary (aggregate)
5. Generate Market & Funding Insights Summary (aggregate)
6. Generate Growth Potential Summary (aggregate)
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
    Main pipeline for analyzing Tracxn startup data through 6 AI steps.
    
    Pipeline Steps:
    1. Generate Competitor Identification Reports (all companies)
    2. Generate Market & Funding Insights Reports (all companies)
    3. Generate Growth Potential Reports (all companies)
    4. Generate Competitor Identification Summary (aggregate)
    5. Generate Market & Funding Insights Summary (aggregate)
    6. Generate Growth Potential Summary (aggregate)
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
        Run the complete 6-step analysis pipeline.
        
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
        
        logger.info(f"Starting Tracxn analysis for {num_companies} companies")
        
        result = {
            'company_count': num_companies,
            'competitor_reports': [],
            'market_funding_reports': [],
            'growth_potential_reports': [],
            'competitor_summary': '',
            'market_funding_summary': '',
            'growth_potential_summary': '',
            'processing_time': 0,
            'generated_at': datetime.now().isoformat(),
        }
        
        try:
            # Step 1: Competitor Identification Reports
            logger.info("Step 1: Generating competitor identification reports...")
            await self._update_progress("competitor", "Analyzing competitive landscape", 15)
            
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
            
            # Step 2: Market & Funding Insights Reports
            logger.info("Step 2: Generating market & funding insights reports...")
            await self._update_progress("market_funding", "Analyzing funding patterns", 30)
            
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
            
            # Step 3: Growth Potential Reports
            logger.info("Step 3: Generating growth potential reports...")
            await self._update_progress("growth_potential", "Evaluating growth potential", 45)
            
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
            
            # Step 4: Competitor Identification Summary
            logger.info("Step 4: Generating competitor identification summary...")
            await self._update_progress("summaries", "Generating executive summaries", 60)
            
            competitor_texts = [r['content'] for r in result['competitor_reports']]
            prompt = self.prompts.generate_competitor_summary(
                competitor_texts, num_companies, self.target_market_description
            )
            result['competitor_summary'] = await self._call_ai(prompt, max_tokens=4000)
            
            # Step 5: Market & Funding Summary
            logger.info("Step 5: Generating market & funding summary...")
            await self._update_progress("summaries", "Generating market funding summary", 75)
            
            market_texts = [r['content'] for r in result['market_funding_reports']]
            prompt = self.prompts.generate_market_funding_summary(
                market_texts, num_companies, self.target_market_description
            )
            result['market_funding_summary'] = await self._call_ai(prompt, max_tokens=4000)
            
            # Step 6: Growth Potential Summary
            logger.info("Step 6: Generating growth potential summary...")
            await self._update_progress("summaries", "Generating growth potential summary", 90)
            
            growth_texts = [r['content'] for r in result['growth_potential_reports']]
            prompt = self.prompts.generate_growth_potential_summary(
                growth_texts, num_companies, self.target_market_description
            )
            result['growth_potential_summary'] = await self._call_ai(prompt, max_tokens=4000)
            
            # Calculate processing time
            result['processing_time'] = time.time() - start_time
            
            logger.info(f"Tracxn analysis completed in {result['processing_time']:.2f}s")
            
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
                    <div class="stat-value">6</div>
                    <div class="stat-label">Analysis Steps</div>
                </div>
            </div>
        </header>
""")
    
    # Competitor Summary Section
    if result.get('competitor_summary'):
        html_parts.append(f"""
        <div class="section summary-section">
            <h2>🎯 Competitive Landscape Summary</h2>
            {md_to_html(result['competitor_summary'])}
        </div>
""")
    
    # Market & Funding Summary Section
    if result.get('market_funding_summary'):
        html_parts.append(f"""
        <div class="section summary-section">
            <h2>💰 Market & Funding Insights Summary</h2>
            {md_to_html(result['market_funding_summary'])}
        </div>
""")
    
    # Growth Potential Summary Section
    if result.get('growth_potential_summary'):
        html_parts.append(f"""
        <div class="section summary-section">
            <h2>📈 Growth Potential Summary</h2>
            {md_to_html(result['growth_potential_summary'])}
        </div>
""")
    
    # Per-Company Reports Section
    html_parts.append("""
        <div class="section">
            <h2>📊 Individual Company Analysis</h2>
""")
    
    # Competitor Reports
    if result.get('competitor_reports'):
        html_parts.append("<h3>Competitive Intelligence Reports</h3>")
        for report in result['competitor_reports']:
            html_parts.append(f"""
            <div class="company-report">
                <h4>{report['company_name']}</h4>
                {md_to_html(report['content'])}
            </div>
""")
    
    # Market & Funding Reports
    if result.get('market_funding_reports'):
        html_parts.append("<h3>Market & Funding Reports</h3>")
        for report in result['market_funding_reports']:
            html_parts.append(f"""
            <div class="company-report">
                <h4>{report['company_name']}</h4>
                {md_to_html(report['content'])}
            </div>
""")
    
    # Growth Potential Reports
    if result.get('growth_potential_reports'):
        html_parts.append("<h3>Growth Potential Reports</h3>")
        for report in result['growth_potential_reports']:
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
            <p>Powered by Tracxn Data & AI Analysis</p>
        </footer>
    </div>
</body>
</html>
""")
    
    return ''.join(html_parts)
