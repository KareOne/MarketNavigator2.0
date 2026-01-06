"""
Tracxn Analysis Pipeline Service.
Orchestrates 3-step institutional-grade AI analysis with progress tracking.

Pipeline Steps:
1. Flash Analysis (2-page) - High-signal market flash report
2. Company Deep Dive (per company) - Comprehensive due diligence 
3. Executive Summary (5-page) - Strategic landscape assessment
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
    Main pipeline for analyzing Tracxn startup data through 3 institutional-grade AI steps.
    
    Pipeline Steps:
    1. Flash Analysis - 2-page market flash report with outliers and signals
    2. Company Deep Dive - Comprehensive due diligence per company
    3. Executive Summary - 5-page strategic landscape assessment
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
    
    async def _call_ai(self, prompt: str, max_tokens: int = 4000) -> str:
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
        Run the complete 3-step analysis pipeline.
        
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
        
        logger.info(f"Starting Tracxn 3-step institutional analysis for {num_companies} companies")
        
        result = {
            'company_count': num_companies,
            # New 3-step structure
            'flash_analysis': '',
            'company_reports': [],
            'executive_summary': '',
            # Metadata
            'processing_time': 0,
            'generated_at': datetime.now().isoformat(),
        }
        
        try:
            # ===== Step 1: Flash Analysis (2-page) =====
            logger.info("Step 1/3: Generating Flash Analysis Report...")
            await self._update_progress("flash_analysis", "Generating 2-page market flash report", 10)
            
            prompt = self.prompts.generate_flash_analysis_report(
                companies_to_analyze, 
                self.target_market_description
            )
            result['flash_analysis'] = await self._call_ai(prompt, max_tokens=3000)
            
            # ===== Step 2: Company Deep Dive (per company) =====
            logger.info("Step 2/3: Generating Company Deep Dive Reports...")
            await self._update_progress("company_deep_dive", "Generating comprehensive due diligence", 25)
            
            for i, company in enumerate(companies_to_analyze):
                company_name = company.get('name', company.get('Company Name', f'Company {i+1}'))
                try:
                    prompt = self.prompts.generate_comprehensive_company_analysis(
                        company, self.target_market_description
                    )
                    report = await self._call_ai(prompt, max_tokens=4000)
                    result['company_reports'].append({
                        'company_name': company_name,
                        'content': report
                    })
                except Exception as e:
                    logger.error(f"Company deep dive failed for {company_name}: {e}")
                    result['company_reports'].append({
                        'company_name': company_name,
                        'content': f"Analysis error: {str(e)}"
                    })
            
            # ===== Step 3: Executive Summary (5-page) =====
            logger.info("Step 3/3: Generating Executive Summary...")
            await self._update_progress("executive_summary", "Generating 5-page strategic assessment", 85)
            
            report_texts = [r['content'] for r in result['company_reports']]
            prompt = self.prompts.generate_executive_summary(
                report_texts, num_companies, self.target_market_description
            )
            result['executive_summary'] = await self._call_ai(prompt, max_tokens=5000)
            
            # Calculate processing time
            result['processing_time'] = time.time() - start_time
            
            logger.info(f"Tracxn 3-step analysis completed in {result['processing_time']:.2f}s")
            
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
        
        .flash-section {{
            background: linear-gradient(135deg, rgba(245, 158, 11, 0.1) 0%, rgba(99, 102, 241, 0.1) 100%);
            border-left: 4px solid var(--accent);
        }}
        
        .executive-section {{
            background: linear-gradient(135deg, rgba(16, 185, 129, 0.1) 0%, rgba(99, 102, 241, 0.1) 100%);
            border-left: 4px solid var(--secondary);
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
            <p class="subtitle">Institutional-Grade Startup Landscape Analysis for {startup_name}</p>
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
                    <div class="stat-value">3</div>
                    <div class="stat-label">Analysis Steps</div>
                </div>
            </div>
        </header>
""")
    
    # Flash Analysis Section
    if result.get('flash_analysis'):
        html_parts.append(f"""
        <div class="section flash-section">
            <h2>⚡ Flash Analysis Report</h2>
            {md_to_html(result['flash_analysis'])}
        </div>
""")
    
    # Executive Summary Section
    if result.get('executive_summary'):
        html_parts.append(f"""
        <div class="section executive-section">
            <h2>🦅 Executive Strategic Assessment</h2>
            {md_to_html(result['executive_summary'])}
        </div>
""")
    
    # Company Deep Dive Reports Section
    if result.get('company_reports'):
        html_parts.append("""
        <div class="section">
            <h2>📊 Company Deep Dive Reports</h2>
""")
        for report in result['company_reports']:
            html_parts.append(f"""
            <div class="company-report">
                <h4>{report['company_name']}</h4>
                {md_to_html(report['content'])}
            </div>
""")
        html_parts.append("</div>")
    
    # Footer
    html_parts.append(f"""
        <footer>
            <p>Generated by Market Navigator • {result.get('generated_at', datetime.now().isoformat())}</p>
            <p>Powered by Tracxn Data & 3-Step Institutional AI Analysis</p>
        </footer>
    </div>
</body>
</html>
""")
    
    return ''.join(html_parts)
