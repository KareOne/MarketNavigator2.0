"""
Crunchbase Analysis Pipeline Service.
Orchestrates 13-step AI analysis process with progress tracking.
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
    Main pipeline for analyzing Crunchbase company data through 13 AI steps.
    
    Pipeline Steps:
    1. Generate Company Overview (all companies)
    2. Generate Technology & Product Reports (per company)
    3. Generate Market Demand & Web Insights Reports (per company)
    4. Generate Competitor Identification Reports (per company)
    5. Generate Market & Funding Insights Reports (per company)
    6. Generate Growth Potential Reports (per company)
    7. Generate SWOT Analysis Reports (per company)
    8. Generate Technology & Product Summary (aggregate)
    9. Generate Market Demand Summary (aggregate)
    10. Generate Competitor Summary (aggregate)
    11. Generate Market & Funding Summary (aggregate)
    12. Generate Growth Potential Summary (aggregate)
    13. Generate SWOT Summary (aggregate)
    """
    
    def __init__(
        self,
        target_market_description: str = "",
        progress_callback: Optional[Callable] = None,
        model: str = None  # Will use Liara default if not specified
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
    
    async def _call_ai(self, prompt: str, max_tokens: int = 3000) -> str:
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
        Run the complete 13-step analysis pipeline.
        
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
            # ===== Step 1: Company Overview =====
            await self._update_progress("company_overview", "Generating company overview", 5)
            logger.info("Step 1: Generating company overview...")
            
            overview = await self._call_ai(
                self.prompts.generate_company_overview(companies_for_analysis)
            )
            result["sections"]["company_overview"] = {
                "content": overview,
                "type": "company_overview"
            }
            
            # ===== Steps 2-7: Per-Company Reports =====
            # Store per-company reports organized by type
            per_company_reports = {
                "tech_product": [],
                "market_demand": [],
                "competitor": [],
                "market_funding": [],
                "growth_potential": [],
                "swot": []
            }
            
            # Define report types and their prompt generators
            report_types = [
                ("tech_product", self.prompts.generate_tech_product_report, "Technology & Product"),
                ("market_demand", self.prompts.generate_market_demand_report, "Market Demand"),
                ("competitor", self.prompts.generate_competitor_report, "Competitor"),
                ("market_funding", self.prompts.generate_market_funding_report, "Market & Funding"),
                ("growth_potential", self.prompts.generate_growth_potential_report, "Growth Potential"),
                ("swot", self.prompts.generate_swot_report, "SWOT"),
            ]
            
            base_progress = 10
            progress_per_type = 10  # 6 types × 10 = 60% for per-company reports
            
            for type_idx, (report_key, prompt_fn, display_name) in enumerate(report_types):
                step_progress = base_progress + (type_idx * progress_per_type)
                await self._update_progress(
                    report_key, 
                    f"Analyzing {display_name} ({type_idx + 2}/7)", 
                    step_progress
                )
                logger.info(f"Step {type_idx + 2}: Generating {display_name} reports...")
                
                for company_idx, company in enumerate(companies_for_analysis):
                    company_name = company.get("Company Name", company.get("name", f"Company {company_idx + 1}"))
                    
                    try:
                        report = await self._call_ai(prompt_fn(company))
                        per_company_reports[report_key].append({
                            "company_name": company_name,
                            "content": report
                        })
                    except Exception as e:
                        logger.error(f"Error generating {report_key} for {company_name}: {e}")
                        per_company_reports[report_key].append({
                            "company_name": company_name,
                            "content": f"Analysis failed: {str(e)}"
                        })
            
            result["sections"]["per_company"] = per_company_reports
            
            # ===== Steps 8-13: Executive Summaries =====
            summary_types = [
                ("tech_product_summary", self.prompts.generate_tech_product_summary, "tech_product", "Tech & Product Summary"),
                ("market_demand_summary", self.prompts.generate_market_demand_summary, "market_demand", "Market Demand Summary"),
                ("competitor_summary", self.prompts.generate_competitor_summary, "competitor", "Competitor Summary"),
                ("market_funding_summary", self.prompts.generate_market_funding_summary, "market_funding", "Funding Summary"),
                ("growth_potential_summary", self.prompts.generate_growth_potential_summary, "growth_potential", "Growth Summary"),
                ("swot_summary", self.prompts.generate_swot_summary, "swot", "SWOT Summary"),
            ]
            
            base_progress = 70
            progress_per_summary = 5  # 6 summaries × 5 = 30%
            
            for sum_idx, (sum_key, prompt_fn, source_key, display_name) in enumerate(summary_types):
                step_progress = base_progress + (sum_idx * progress_per_summary)
                await self._update_progress(
                    sum_key,
                    f"Generating {display_name} ({sum_idx + 8}/13)",
                    step_progress
                )
                logger.info(f"Step {sum_idx + 8}: Generating {display_name}...")
                
                try:
                    # Get the individual reports for this category
                    individual_reports = [r["content"] for r in per_company_reports[source_key]]
                    
                    summary = await self._call_ai(
                        prompt_fn(individual_reports, num_companies),
                        max_tokens=4000
                    )
                    result["sections"][sum_key] = {
                        "content": summary,
                        "type": sum_key
                    }
                except Exception as e:
                    logger.error(f"Error generating {sum_key}: {e}")
                    result["sections"][sum_key] = {
                        "content": f"Summary generation failed: {str(e)}",
                        "type": sum_key
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
    Generate simple HTML report from analysis results.
    
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
    
    # Add overview section
    if "company_overview" in sections:
        nav_items.append('<a href="#overview">Company Overview</a>')
        content = sections["company_overview"]["content"]
        html_content = markdown.markdown(content, extensions=['tables', 'fenced_code'])
        section_html.append(f'''
        <section id="overview" class="report-section">
            <h2>📊 Company Overview</h2>
            <div class="section-content">{html_content}</div>
        </section>
        ''')
    
    # Per-company report types
    report_type_labels = {
        "tech_product": ("💻", "Technology & Product"),
        "market_demand": ("📈", "Market Demand & Web Insights"),
        "competitor": ("🎯", "Competitor Identification"),
        "market_funding": ("💰", "Market & Funding Insights"),
        "growth_potential": ("🚀", "Growth Potential"),
        "swot": ("⚖️", "SWOT Analysis")
    }
    
    per_company = sections.get("per_company", {})
    
    for report_key, (icon, label) in report_type_labels.items():
        if report_key in per_company and per_company[report_key]:
            section_id = report_key.replace("_", "-")
            nav_items.append(f'<a href="#{section_id}">{label}</a>')
            
            companies_html = []
            for report in per_company[report_key]:
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
            <section id="{section_id}" class="report-section">
                <h2>{icon} {label}</h2>
                <div class="companies-list">
                    {"".join(companies_html)}
                </div>
            </section>
            ''')
    
    # Executive Summaries
    summary_labels = {
        "tech_product_summary": ("💻", "Technology & Product Summary"),
        "market_demand_summary": ("📈", "Market Demand Summary"),
        "competitor_summary": ("🎯", "Competitor Summary"),
        "market_funding_summary": ("💰", "Funding Summary"),
        "growth_potential_summary": ("🚀", "Growth Summary"),
        "swot_summary": ("⚖️", "SWOT Summary")
    }
    
    # Add divider before summaries
    nav_items.append('<span class="nav-divider">Executive Summaries</span>')
    
    for sum_key, (icon, label) in summary_labels.items():
        if sum_key in sections:
            section_id = sum_key.replace("_", "-")
            nav_items.append(f'<a href="#{section_id}">{label}</a>')
            
            content = sections[sum_key]["content"]
            html_content = markdown.markdown(content, extensions=['tables', 'fenced_code'])
            
            section_html.append(f'''
            <section id="{section_id}" class="report-section summary-section">
                <h2>{icon} {label}</h2>
                <div class="section-content">{html_content}</div>
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
        
        .section-content {{
            font-size: 14px;
        }}
        
        .section-content h3 {{ margin: 20px 0 10px; color: var(--text); }}
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
