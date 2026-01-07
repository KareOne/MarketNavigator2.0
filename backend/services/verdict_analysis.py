"""
Verdict Analysis Pipeline Service.
Orchestrates Master Prompt v8.3 multi-phase AI analysis for startup viability assessment.

Pipeline Steps:
1. Data Audit & Classification
2. Executive Synthesis
3. Quantitative Scoring (5 axes: Demand, Competition, Differentiation, Economics, Feasibility)
4. Risk Synthesis (FMEA)
5. Verdict Decision (GO/ITERATE/KILL)
6. Actionable Roadmap (7-day and 30-day sprints)
"""
import logging
import time
import json
import asyncio
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime

from openai import AsyncOpenAI
from django.conf import settings

from .verdict_prompts import VerdictPromptTemplates

logger = logging.getLogger(__name__)


class VerdictAnalysisPipeline:
    """
    Main pipeline for Verdict Analysis using Master Prompt v8.3.
    
    Zero-Baseline Assumption: All insights discovered from data.
    Multi-Phase Pipeline with evidence-based scoring.
    """
    
    def __init__(
        self,
        project_description: str = "",
        progress_callback: Optional[Callable] = None,
        model: str = None
    ):
        """
        Initialize the verdict analysis pipeline.
        
        Args:
            project_description: Context about the startup being analyzed
            progress_callback: Async function to call with progress updates
            model: Model to use (defaults to LIARA_MODEL)
        """
        self.project_description = project_description
        self.progress_callback = progress_callback
        
        # Use Liara model by default
        self.model = model or getattr(settings, 'LIARA_MODEL', 'gpt-4o-mini')
        
        # Initialize OpenAI client for Liara
        liara_api_key = getattr(settings, 'LIARA_API_KEY', '')
        liara_base_url = getattr(settings, 'LIARA_BASE_URL', 'https://ai.liara.ir/api/v1')
        
        self.client = AsyncOpenAI(
            api_key=liara_api_key,
            base_url=liara_base_url,
        )
        
        self.prompts = VerdictPromptTemplates()
        
        # Track timing
        self.step_times = {}
        
        logger.info(f"Initialized VerdictAnalysisPipeline with model: {self.model}")
    
    async def _call_ai(self, prompt: str, system_message: str = None, max_tokens: int = 4000) -> str:
        """Call OpenAI API with the given prompt."""
        try:
            messages = []
            if system_message:
                messages.append({"role": "system", "content": system_message})
            messages.append({"role": "user", "content": prompt})
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.7,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"AI call failed: {e}")
            raise
    
    async def _update_progress(self, step: str, message: str, progress: int = 0):
        """Send progress update if callback provided."""
        if self.progress_callback:
            try:
                await self.progress_callback(step, message, progress)
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")
    
    def _parse_json_safely(self, text: str, default: Dict = None) -> Dict[str, Any]:
        """Safely parse JSON from AI response."""
        try:
            # Try to extract JSON from markdown code blocks
            if "```json" in text:
                start = text.find("```json") + 7
                end = text.find("```", start)
                text = text[start:end].strip()
            elif "```" in text:
                start = text.find("```") + 3
                end = text.find("```", start)
                text = text[start:end].strip()
            
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning("Failed to parse JSON from AI response")
            return default if default is not None else {"raw_output": text}
    
    async def analyze(
        self,
        crunchbase_data: List[Dict[str, Any]],
        tracxn_data: List[Dict[str, Any]],
        social_data: List[Dict[str, Any]],
        tracker = None
    ) -> Dict[str, Any]:
        """
        Run the complete Verdict Analysis pipeline.
        
        Args:
            crunchbase_data: Raw data from Crunchbase report
            tracxn_data: Raw data from Tracxn report
            social_data: Raw data from Social report
            tracker: Optional async tracker for progress updates
            
        Returns:
            Dictionary containing all analysis results
        """
        start_time = time.time()
        system_prompt = VerdictPromptTemplates.SYSTEM_PROMPT
        
        logger.info("Starting Verdict Analysis pipeline (Master Prompt v8.3)")
        
        result = {
            'data_classification': {},
            'executive_synthesis': '',
            'scores': {},
            'risks': {},
            'verdict': {},
            'roadmap': {},
            'processing_time': 0,
            'generated_at': datetime.now().isoformat(),
        }
        
        try:
            # ===== Step 1: Data Audit & Classification =====
            logger.info("Step 1/6: Data Audit & Classification...")
            if tracker:
                await tracker.start_step('data_audit')
                await tracker.update_step_message('data_audit', "Classifying and auditing input datasets...")
            
            prompt = self.prompts.generate_data_audit_prompt(
                crunchbase_data, tracxn_data, social_data, self.project_description
            )
            response = await self._call_ai(prompt, system_prompt)
            result['data_classification'] = self._parse_json_safely(response)
            
            if tracker:
                await tracker.add_step_detail('data_audit', 'classification', "Dataset roles identified")
                await tracker.complete_step('data_audit', {'classification': 'completed'})
            
            # ===== Step 2: Executive Synthesis =====
            logger.info("Step 2/6: Executive Synthesis...")
            if tracker:
                await tracker.start_step('executive_synthesis')
                await tracker.update_step_message('executive_synthesis', "Generating executive context overview...")
            
            prompt = self.prompts.generate_executive_synthesis_prompt(
                crunchbase_data, tracxn_data, social_data, 
                self.project_description, result['data_classification']
            )
            result['executive_synthesis'] = await self._call_ai(prompt, system_prompt)
            
            if tracker:
                await tracker.complete_step('executive_synthesis')
            
            # ===== Steps 3-7: Quantitative Scoring (5 Axes) =====
            axis_configs = [
                ('scoring_demand', 'demand', 25),
                ('scoring_competition', 'competition', 20),
                ('scoring_differentiation', 'differentiation', 20),
                ('scoring_economics', 'economics', 20),
                ('scoring_feasibility', 'feasibility', 15),
            ]
            
            for step_key, axis_name, weight in axis_configs:
                logger.info(f"Scoring axis: {axis_name} ({weight}%)...")
                if tracker:
                    await tracker.start_step(step_key)
                    await tracker.update_step_message(step_key, f"Scoring {axis_name.title()} axis ({weight}%)...")
                
                prompt = self.prompts.generate_scoring_prompt(
                    axis_name, weight, crunchbase_data, tracxn_data, social_data, self.project_description
                )
                response = await self._call_ai(prompt, system_prompt)
                score_data = self._parse_json_safely(response, {"score": 50, "confidence": "low"})
                result['scores'][axis_name] = score_data
                
                if tracker:
                    await tracker.add_step_detail(step_key, 'score', f"{axis_name.title()}: {score_data.get('score', 'N/A')}/100")
                    await tracker.complete_step(step_key, {'axis': axis_name, 'score': score_data.get('score', 'N/A')})
            
            # ===== Step 8: Risk Synthesis (FMEA) =====
            logger.info("Step: Risk Synthesis (FMEA)...")
            if tracker:
                await tracker.start_step('risk_synthesis')
                await tracker.update_step_message('risk_synthesis', "Discovering and classifying risks (FMEA)...")
            
            prompt = self.prompts.generate_risk_synthesis_prompt(
                result['scores'], crunchbase_data, tracxn_data, social_data, self.project_description
            )
            response = await self._call_ai(prompt, system_prompt)
            result['risks'] = self._parse_json_safely(response, {"killer_risks": [], "major_risks": [], "minor_risks": []})
            
            killer_count = result['risks'].get('total_killer_risks', len(result['risks'].get('killer_risks', [])))
            major_count = result['risks'].get('total_major_risks', len(result['risks'].get('major_risks', [])))
            
            if tracker:
                await tracker.add_step_detail('risk_synthesis', 'risks_found', f"Killer: {killer_count}, Major: {major_count}")
                await tracker.complete_step('risk_synthesis', {'killer_risks': killer_count, 'major_risks': major_count})
            
            # ===== Step 9: Verdict Decision =====
            logger.info("Step: Verdict Decision...")
            if tracker:
                await tracker.start_step('verdict_decision')
                await tracker.update_step_message('verdict_decision', "Determining GO/ITERATE/KILL verdict...")
            
            prompt = self.prompts.generate_verdict_prompt(result['scores'], result['risks'], self.project_description)
            response = await self._call_ai(prompt, system_prompt)
            result['verdict'] = self._parse_json_safely(response, {"verdict": "ITERATE", "total_score": 50})
            
            if tracker:
                await tracker.add_step_detail(
                    'verdict_decision', 'verdict', 
                    f"Verdict: {result['verdict'].get('verdict', 'UNKNOWN')} (Score: {result['verdict'].get('total_score', 'N/A')})"
                )
                await tracker.complete_step('verdict_decision', {
                    'verdict': result['verdict'].get('verdict'),
                    'score': result['verdict'].get('total_score')
                })
            
            # ===== Step 10: Actionable Roadmap =====
            logger.info("Step: Actionable Roadmap...")
            if tracker:
                await tracker.start_step('roadmap')
                await tracker.update_step_message('roadmap', "Generating 7-day and 30-day sprint roadmap...")
            
            prompt = self.prompts.generate_roadmap_prompt(
                result['verdict'], result['risks'], result['scores'], self.project_description
            )
            response = await self._call_ai(prompt, system_prompt)
            result['roadmap'] = self._parse_json_safely(response)
            
            if tracker:
                await tracker.complete_step('roadmap')
            
            # Calculate processing time
            result['processing_time'] = time.time() - start_time
            
            logger.info(f"Verdict Analysis completed in {result['processing_time']:.2f}s - Verdict: {result['verdict'].get('verdict', 'UNKNOWN')}")
            
            return result
            
        except Exception as e:
            logger.error(f"Verdict analysis pipeline failed: {e}")
            raise


def generate_verdict_html(result: Dict[str, Any], project_name: str = "Your Startup") -> str:
    """
    Generate HTML report from Verdict analysis results.
    
    Args:
        result: Analysis result dictionary from pipeline
        project_name: Name to display in report header
        
    Returns:
        Complete HTML string
    """
    import markdown
    from django.utils import timezone
    
    def md_to_html(text: str) -> str:
        """Convert markdown to HTML."""
        if not text:
            return ""
        try:
            return markdown.markdown(text, extensions=['tables', 'fenced_code'])
        except Exception:
            return str(text)
    
    # Extract data
    executive_synthesis = result.get('executive_synthesis', '')
    scores = result.get('scores', {})
    risks = result.get('risks', {})
    verdict = result.get('verdict', {})
    roadmap = result.get('roadmap', {})
    
    total_score = verdict.get('total_score', 0)
    verdict_value = verdict.get('verdict', 'UNKNOWN')
    
    # Verdict icon and color
    verdict_styles = {
        'GO': ('#10b981', '🟢'),
        'ITERATE': ('#f59e0b', '🟡'),
        'PARK': ('#ef4444', '🔴'),
        'KILL': ('#ef4444', '🔴'),
        'UNKNOWN': ('#6b7280', '⚪'),
    }
    verdict_color, verdict_icon = verdict_styles.get(verdict_value.upper() if verdict_value else '', ('#6b7280', '⚪'))
    
    # Build HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Verdict Analysis - {project_name}</title>
    <style>
        :root {{
            --primary: #6366f1;
            --secondary: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            --bg-dark: #0f172a;
            --bg-card: #1e293b;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --border: #334155;
        }}
        
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg-dark);
            color: var(--text-primary);
            line-height: 1.7;
            padding: 2rem;
        }}
        
        .container {{ max-width: 1200px; margin: 0 auto; }}
        
        header {{
            text-align: center;
            margin-bottom: 3rem;
            padding: 3rem 2rem;
            background: linear-gradient(135deg, {verdict_color}22 0%, var(--primary)22 100%);
            border-radius: 16px;
            border: 2px solid {verdict_color};
        }}
        
        header h1 {{ font-size: 2.5rem; margin-bottom: 1rem; }}
        
        .verdict-banner {{
            font-size: 4rem;
            margin-bottom: 0.5rem;
        }}
        
        .verdict-label {{
            font-size: 2.5rem;
            font-weight: bold;
            color: {verdict_color};
        }}
        
        .verdict-score {{
            font-size: 1.5rem;
            color: var(--text-secondary);
            margin-top: 0.5rem;
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
        
        .section p {{ color: var(--text-secondary); margin-bottom: 1rem; }}
        
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
        
        td {{ color: var(--text-secondary); }}
        
        .score-high {{ color: var(--secondary); font-weight: bold; }}
        .score-mid {{ color: var(--warning); font-weight: bold; }}
        .score-low {{ color: var(--danger); font-weight: bold; }}
        
        .risk-killer {{ color: var(--danger); }}
        .risk-major {{ color: var(--warning); }}
        
        .metrics {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 1rem;
            margin-bottom: 1.5rem;
        }}
        
        .metric {{
            background: rgba(99, 102, 241, 0.1);
            border-radius: 8px;
            padding: 1rem;
            text-align: center;
        }}
        
        .metric-value {{ font-size: 2rem; font-weight: bold; }}
        .metric-label {{ font-size: 0.85rem; color: var(--text-secondary); }}
        
        .sprint-card {{
            background: rgba(16, 185, 129, 0.1);
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 1rem;
            border-left: 4px solid var(--secondary);
        }}
        
        .sprint-card h3 {{ color: var(--secondary); margin-bottom: 0.75rem; }}
        
        footer {{
            text-align: center;
            padding: 2rem;
            color: var(--text-secondary);
            font-size: 0.9rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>⚖️ Verdict Analysis</h1>
            <div class="verdict-banner">{verdict_icon}</div>
            <div class="verdict-label">{verdict_value}</div>
            <div class="verdict-score">Total Score: <strong>{total_score}/100</strong></div>
        </header>
        
        <div class="section">
            <h2>Executive Synthesis</h2>
            {md_to_html(executive_synthesis)}
        </div>
        
        <div class="section">
            <h2>Quantitative Opportunity Assessment</h2>
            <table>
                <thead>
                    <tr><th>Axis</th><th>Weight</th><th>Score</th><th>Confidence</th></tr>
                </thead>
                <tbody>
"""
    
    # Add scoring rows
    axis_weights = {'demand': 25, 'competition': 20, 'differentiation': 20, 'economics': 20, 'feasibility': 15}
    for axis_name, weight in axis_weights.items():
        axis_data = scores.get(axis_name, {})
        score = axis_data.get('score', 'N/A')
        confidence = axis_data.get('confidence', 'low')
        
        score_class = 'score-high' if isinstance(score, (int, float)) and score >= 75 else ('score-mid' if isinstance(score, (int, float)) and score >= 50 else 'score-low')
        
        html += f"""
                    <tr>
                        <td><strong>{axis_name.title()}</strong></td>
                        <td>{weight}%</td>
                        <td class="{score_class}">{score}</td>
                        <td>{confidence.title() if isinstance(confidence, str) else confidence}</td>
                    </tr>
"""
    
    html += f"""
                    <tr style="background: rgba(99, 102, 241, 0.15);">
                        <td><strong>TOTAL WEIGHTED SCORE</strong></td>
                        <td>100%</td>
                        <td colspan="2"><strong style="font-size: 1.25rem;">{total_score}</strong></td>
                    </tr>
                </tbody>
            </table>
        </div>
        
        <div class="section">
            <h2>Risk Synthesis (FMEA)</h2>
            <div class="metrics">
                <div class="metric">
                    <div class="metric-value risk-killer">{risks.get('total_killer_risks', len(risks.get('killer_risks', [])))}</div>
                    <div class="metric-label">Killer Risks</div>
                </div>
                <div class="metric">
                    <div class="metric-value risk-major">{risks.get('total_major_risks', len(risks.get('major_risks', [])))}</div>
                    <div class="metric-label">Major Risks</div>
                </div>
                <div class="metric">
                    <div class="metric-value">{risks.get('total_minor_risks', len(risks.get('minor_risks', [])))}</div>
                    <div class="metric-label">Minor Risks</div>
                </div>
            </div>
"""
    
    # Add killer risks if present
    killer_risks = risks.get('killer_risks', [])
    if killer_risks and isinstance(killer_risks, list):
        html += """
            <h3 class="risk-killer">🚨 Killer Risks</h3>
            <table>
                <thead><tr><th>ID</th><th>Risk</th><th>Sources</th></tr></thead>
                <tbody>
"""
        for risk in killer_risks[:5]:
            if isinstance(risk, dict):
                sources = ', '.join(risk.get('dataset_sources', [])) if isinstance(risk.get('dataset_sources'), list) else 'N/A'
                html += f"""
                    <tr>
                        <td>{risk.get('risk_id', 'K?')}</td>
                        <td><strong>{risk.get('title', 'Unknown')}</strong><br><small>{risk.get('description', '')[:150]}</small></td>
                        <td>{sources}</td>
                    </tr>
"""
        html += "</tbody></table>"
    
    html += "</div>"
    
    # Verdict Reasoning
    verdict_reasoning = verdict.get('verdict_reasoning', '')
    if verdict_reasoning:
        html += f"""
        <div class="section">
            <h2>Verdict Reasoning</h2>
            <p>{verdict_reasoning}</p>
        </div>
"""
    
    # Roadmap
    html += """
        <div class="section">
            <h2>Actionable Roadmap</h2>
"""
    
    seven_day = roadmap.get('seven_day_sprint', {}) if isinstance(roadmap, dict) else {}
    if seven_day and isinstance(seven_day, dict):
        html += f"""
            <div class="sprint-card">
                <h3>🏃 7-Day Sprint</h3>
                <p><strong>Objective:</strong> {seven_day.get('objective', 'N/A')}</p>
                <p><strong>Hypothesis:</strong> {seven_day.get('hypothesis_to_test', 'N/A')}</p>
                <p><strong>Success Criteria:</strong> {seven_day.get('success_criteria', 'N/A')}</p>
            </div>
"""
    
    thirty_day = roadmap.get('thirty_day_sprint', {}) if isinstance(roadmap, dict) else {}
    if thirty_day and isinstance(thirty_day, dict):
        html += f"""
            <div class="sprint-card" style="border-left-color: var(--primary);">
                <h3 style="color: var(--primary);">📅 30-Day Sprint</h3>
                <p><strong>Objective:</strong> {thirty_day.get('objective', 'N/A')}</p>
                <p><strong>Moat Focus:</strong> {thirty_day.get('moat_building_focus', 'N/A')}</p>
            </div>
"""
    
    html += f"""
        </div>
        
        <footer>
            <p>Generated by Market Navigator • {result.get('generated_at', datetime.now().isoformat())}</p>
            <p>Powered by Master Prompt v8.3 Verdict Analysis Engine</p>
        </footer>
    </div>
</body>
</html>
"""
    
    return html
