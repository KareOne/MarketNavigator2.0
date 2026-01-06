"""
Crunchbase Analysis Pipeline Service.
Orchestrates the new 3-Part AI analysis system.
"""
import logging
import time
import asyncio
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime

from openai import AsyncOpenAI
from django.conf import settings

from .crunchbase_prompts import CrunchbasePromptTemplates

logger = logging.getLogger(__name__)


class CrunchbaseAnalysisPipeline:
    """
    Main pipeline for analyzing Crunchbase company data through the new 3-part system.
    
    Pipeline Parts:
    1. Company Deep-Dive (per company) -> generate_company_summary
    2. Strategic Summary (aggregate) -> generate_strategic_summary
    3. Fast Analysis (aggregate) -> generate_fast_analysis
    """
    
    def __init__(
        self,
        target_market_description: str = "",
        progress_callback: Optional[Callable] = None,
        model: str = None
    ):
        """
        Initialize the analysis pipeline.
        
        Args:
            target_market_description: Context for analysis
            progress_callback: Async function to call with progress updates
            model: Model to use (defaults to LIARA_MODEL)
        """
        self.target_description = target_market_description
        self.progress_callback = progress_callback
        
        # Use Liara AI (OpenAI-compatible API)
        api_key = getattr(settings, 'LIARA_API_KEY', None)
        base_url = getattr(settings, 'LIARA_BASE_URL', None)
        
        if not api_key or not base_url:
            # Fallback to OpenAI if Liara not configured
            api_key = getattr(settings, 'OPENAI_API_KEY', None)
            base_url = None
            self.model = model or "gpt-4o-mini"
        else:
            self.model = model or getattr(settings, 'LIARA_MODEL', 'google/gemini-2.5-flash')
        
        if not api_key:
            raise ValueError("No AI API key configured (LIARA_API_KEY or OPENAI_API_KEY)")
        
        # Initialize prompts
        self.prompts = CrunchbasePromptTemplates(target_market_description)
        
        # Initialize client with appropriate base URL
        if base_url:
            self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
            logger.info(f"Initialized CrunchbaseAnalysisPipeline with Liara AI ({self.model})")
        else:
            self.client = AsyncOpenAI(api_key=api_key)
            logger.info(f"Initialized CrunchbaseAnalysisPipeline with OpenAI ({self.model})")
    
    async def _call_ai(self, prompt: str, max_tokens: int = 4000) -> str:
        """Call OpenAI API with the given prompt."""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=0.7
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"AI call failed: {e}")
            return f"Error generating analysis: {str(e)}"
    
    async def _update_progress(self, step: str, message: str, progress: int):
        """Send progress update if callback provided."""
        if self.progress_callback:
            try:
                await self.progress_callback(step, message, progress)
            except Exception as e:
                logger.warning(f"Failed to send progress update: {e}")
    
    async def analyze(
        self,
        companies: List[Dict[str, Any]],
        max_companies: int = 10
    ) -> Dict[str, Any]:
        """
        Run the complete analysis pipeline.
        
        Args:
            companies: List of company data dictionaries from Crunchbase API
            max_companies: Maximum number of companies for detailed analysis
            
        Returns:
            Dictionary containing all analysis results
        """
        start_time = time.time()
        
        # Limit companies for detailed analysis
        companies_for_analysis = companies[:max_companies]
        num_companies = len(companies_for_analysis)
        
        logger.info(f"Starting analysis for {num_companies} companies")
        
        result = {
            "companies": companies_for_analysis,
            "company_count": num_companies,
            "sections": {},
            "generated_at": datetime.utcnow().isoformat()
        }
        
        try:
            # ===== Part 1: Company Deep Dive (Per Company) =====
            await self._update_progress("company_deep_dive", "Starting Company Deep Dive...", 10)
            logger.info("Part 1: Generating Company Deep Dive reports...")
            
            deep_dive_reports = []
            
            for idx, company in enumerate(companies_for_analysis):
                company_name = company.get("Company Name", company.get("name", f"Company {idx + 1}"))
                
                # Update progress
                progress = 10 + int((idx / num_companies) * 60)  # 10% to 70%
                await self._update_progress(
                    "company_deep_dive", 
                    f"Analyzing {company_name} ({idx+1}/{num_companies})", 
                    progress
                )
                
                try:
                    report = await self._call_ai(
                        self.prompts.generate_company_summary(company)
                    )
                    deep_dive_reports.append({
                        "company_name": company_name,
                        "content": report
                    })
                except Exception as e:
                    logger.error(f"Error analyzing {company_name}: {e}")
                    deep_dive_reports.append({
                        "company_name": company_name,
                        "content": f"Analysis failed: {str(e)}"
                    })
            
            result["sections"]["company_deep_dive"] = deep_dive_reports
            
            # ===== Part 2: Strategic Summary (Aggregate) =====
            await self._update_progress("strategic_summary", "Generating Strategic Summary...", 80)
            logger.info("Part 2: Generating Strategic Summary...")
            
            summary_content = await self._call_ai(
                self.prompts.generate_strategic_summary(companies_for_analysis)
            )
            
            result["sections"]["strategic_summary"] = {
                "content": summary_content,
                "type": "strategic_summary"
            }
            
            # ===== Part 3: Fast Analysis (Aggregate) =====
            await self._update_progress("fast_analysis", "Generating Fast Analysis...", 90)
            logger.info("Part 3: Generating Fast Analysis...")
            
            fast_analysis_content = await self._call_ai(
                self.prompts.generate_fast_analysis(companies_for_analysis)
            )
            
            result["sections"]["fast_analysis"] = {
                "content": fast_analysis_content,
                "type": "fast_analysis"
            }
            
            # Calculate total processing time
            result["processing_time"] = time.time() - start_time
            logger.info(f"Analysis completed in {result['processing_time']:.2f} seconds")
            
            return result
            
        except Exception as e:
            logger.error(f"Analysis pipeline failed: {e}")
            result["error"] = str(e)
            result["processing_time"] = time.time() - start_time
            return result


def generate_analysis_html(result: Dict[str, Any], startup_name: str = "Your Startup") -> str:
    """
    Generate HTML report from analysis results (New 3-Part Structure).
    
    Args:
        result: Analysis result dictionary from pipeline
        startup_name: Name to display in report header
        
    Returns:
        Complete HTML string
    """
    import markdown
    
    sections = result.get("sections", {})
    company_count = result.get("company_count", 0)
    processing_time = result.get("processing_time", 0)
    
    # Build navigation and sections
    nav_items = []
    section_html = []
    
    # --- Part 3: Fast Analysis (Placed first for executives) ---
    if "fast_analysis" in sections:
        nav_items.append('<a href="#fast-analysis">⚡ Fast Analysis</a>')
        content = sections["fast_analysis"]["content"]
        html_content = markdown.markdown(content, extensions=['tables', 'fenced_code'])
        section_html.append(f'''
        <section id="fast-analysis" class="report-section summary-section">
            <h2>⚡ Fast Analysis (Board View)</h2>
            <div class="section-content">{html_content}</div>
        </section>
        ''')
        
    # --- Part 2: Strategic Summary ---
    if "strategic_summary" in sections:
        nav_items.append('<a href="#strategic-summary">🧠 Strategic Summary</a>')
        content = sections["strategic_summary"]["content"]
        html_content = markdown.markdown(content, extensions=['tables', 'fenced_code'])
        section_html.append(f'''
        <section id="strategic-summary" class="report-section">
            <h2>🧠 Strategic Summary</h2>
            <div class="section-content">{html_content}</div>
        </section>
        ''')

    # --- Part 1: Company Deep Dives ---
    deep_dive = sections.get("company_deep_dive", [])
    if deep_dive:
        nav_items.append('<span class="nav-divider">Company Deep Dives</span>')
        nav_items.append('<a href="#deep-dives">🏢 Detailed Reports</a>')
        
        companies_html = []
        for report in deep_dive:
            company_name = report["company_name"]
            content = report["content"]
            html_content = markdown.markdown(content, extensions=['tables', 'fenced_code'])
            companies_html.append(f'''
            <details class="company-report">
                <summary>{company_name}</summary>
                <div class="company-content">{html_content}</div>
            </details>
            ''')
        
        section_html.append(f'''
        <section id="deep-dives" class="report-section">
            <h2>🏢 Company Deep Dives</h2>
            <p class="section-desc">Detailed 7-section analysis for each top competitor.</p>
            <div class="companies-list">
                {"".join(companies_html)}
            </div>
        </section>
        ''')
    
    # Build complete HTML
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Crunchbase Analysis - {startup_name}</title>
    <style>
        :root {{
            --primary: #6366f1;
            --bg: #0f0f1a;
            --surface: #1a1a2e;
            --border: #2a2a4a;
            --text: #e5e5e5;
            --muted: #8888aa;
        }}
        
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
        }}
        
        .container {{
            display: flex;
            min-height: 100vh;
        }}
        
        /* Navigation Sidebar */
        nav {{
            width: 280px;
            background: var(--surface);
            border-right: 1px solid var(--border);
            padding: 20px;
            position: sticky;
            top: 0;
            height: 100vh;
            overflow-y: auto;
        }}
        
        nav h1 {{
            font-size: 18px;
            margin-bottom: 5px;
            color: var(--primary);
        }}
        
        nav .meta {{
            font-size: 12px;
            color: var(--muted);
            margin-bottom: 20px;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--border);
        }}
        
        nav a {{
            display: block;
            padding: 8px 12px;
            color: var(--muted);
            text-decoration: none;
            border-radius: 6px;
            font-size: 13px;
            margin-bottom: 4px;
            transition: all 0.2s;
        }}
        
        nav a:hover {{
            background: rgba(99, 102, 241, 0.1);
            color: var(--text);
        }}
        
        nav .nav-divider {{
            display: block;
            font-size: 11px;
            text-transform: uppercase;
            color: var(--muted);
            margin: 20px 0 10px;
            padding-left: 12px;
            letter-spacing: 1px;
        }}
        
        /* Main Content */
        main {{
            flex: 1;
            padding: 40px;
            max-width: 900px;
        }}
        
        .report-section {{
            margin-bottom: 40px;
            padding: 30px;
            background: var(--surface);
            border-radius: 12px;
            border: 1px solid var(--border);
        }}
        
        .report-section h2 {{
            font-size: 20px;
            margin-bottom: 20px;
            color: var(--primary);
            padding-bottom: 15px;
            border-bottom: 1px solid var(--border);
        }}
        
        .section-desc {{
            color: var(--muted);
            margin-bottom: 20px;
            font-size: 14px;
        }}
        
        .section-content {{
            font-size: 14px;
        }}
        
        .section-content h3, .section-content h4 {{ margin: 20px 0 10px; color: var(--text); }}
        .section-content p {{ margin-bottom: 12px; }}
        .section-content ul, .section-content ol {{ margin: 12px 0 12px 20px; }}
        .section-content li {{ margin-bottom: 6px; }}
        
        /* Company Reports */
        .company-report {{
            margin-bottom: 10px;
            border: 1px solid var(--border);
            border-radius: 8px;
            overflow: hidden;
        }}
        
        .company-report summary {{
            padding: 12px 16px;
            background: rgba(99, 102, 241, 0.05);
            cursor: pointer;
            font-weight: 500;
            font-size: 14px;
        }}
        
        .company-report summary:hover {{
            background: rgba(99, 102, 241, 0.1);
        }}
        
        .company-content {{
            padding: 20px;
            font-size: 13px;
            border-top: 1px solid var(--border);
        }}
        
        .summary-section {{
            background: linear-gradient(135deg, var(--surface) 0%, rgba(99, 102, 241, 0.05) 100%);
        }}
        
        /* Tables */
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
            font-size: 13px;
        }}
        
        th, td {{
            padding: 10px;
            border: 1px solid var(--border);
            text-align: left;
        }}
        
        th {{
            background: rgba(99, 102, 241, 0.1);
        }}
        
        /* Code blocks */
        code {{
            background: rgba(99, 102, 241, 0.1);
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 12px;
        }}
        
        pre {{
            background: #0a0a14;
            padding: 15px;
            border-radius: 8px;
            overflow-x: auto;
            margin: 15px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <nav>
            <h1>Crunchbase Analysis</h1>
            <div class="meta">
                {startup_name}<br>
                {company_count} companies analyzed<br>
                Generated in {processing_time:.1f}s
            </div>
            {"".join(nav_items)}
        </nav>
        <main>
            {"".join(section_html)}
        </main>
    </div>
</body>
</html>'''
    
    return html
