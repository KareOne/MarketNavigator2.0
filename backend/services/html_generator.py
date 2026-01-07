"""
HTML Report Generator service.
Per FINAL_ARCHITECTURE_SPECIFICATION.md - All Reports as HTML.

Generates interactive HTML reports for:
- Crunchbase Analysis
- Tracxn Analysis
- Social Analysis (Twitter + LinkedIn)
- Pitch Deck
"""
from django.template import Template, Context
from django.utils import timezone
from typing import Dict, Any, List
import json
import logging

logger = logging.getLogger(__name__)


class HTMLReportGenerator:
    """
    Generate interactive HTML reports for each panel type.
    """
    
    # =========================================================================
    # Base Template
    # =========================================================================
    
    BASE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }} - MarketNavigator</title>
    <style>
        :root {
            --color-primary: #183661;
            --color-secondary: #c7b299;
            --color-bg: #1e1e1e;
            --color-surface: #252526;
            --color-text: #f3f4f6;
            --color-text-muted: #a6acb5;
            --color-border: rgba(230, 230, 230, 0.12);
            --color-success: #34d399;
            --color-warning: #fbbf24;
            --color-danger: #f87171;
        }
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--color-bg);
            color: var(--color-text);
            line-height: 1.6;
            padding: 40px;
        }
        
        .report-container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        .report-header {
            margin-bottom: 40px;
            padding-bottom: 24px;
            border-bottom: 1px solid var(--color-border);
        }
        
        .report-header h1 {
            font-size: 32px;
            color: var(--color-primary);
            margin-bottom: 8px;
        }
        
        .report-meta {
            color: var(--color-text-muted);
            font-size: 14px;
        }
        
        .section {
            background: var(--color-surface);
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 24px;
            border: 1px solid var(--color-border);
        }
        
        .section h2 {
            font-size: 20px;
            margin-bottom: 16px;
            color: var(--color-secondary);
        }
        
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }
        
        .metric-card {
            background: rgba(24, 54, 97, 0.1);
            border-radius: 8px;
            padding: 16px;
            text-align: center;
        }
        
        .metric-value {
            font-size: 28px;
            font-weight: 700;
            color: var(--color-primary);
        }
        
        .metric-label {
            font-size: 12px;
            color: var(--color-text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .company-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 16px;
        }
        
        .company-card {
            background: var(--color-surface);
            border: 1px solid var(--color-border);
            border-radius: 8px;
            padding: 16px;
            transition: transform 0.2s;
        }
        
        .company-card:hover {
            transform: translateY(-2px);
            border-color: var(--color-primary);
        }
        
        .company-name {
            font-weight: 600;
            font-size: 16px;
            margin-bottom: 4px;
        }
        
        .company-description {
            font-size: 13px;
            color: var(--color-text-muted);
            margin-bottom: 8px;
        }
        
        .company-stats {
            display: flex;
            gap: 12px;
            font-size: 12px;
        }
        
        .company-stat {
            background: rgba(24, 54, 97, 0.1);
            padding: 4px 8px;
            border-radius: 4px;
        }
        
        .insights-list {
            list-style: none;
        }
        
        .insight-item {
            padding: 12px 16px;
            margin-bottom: 8px;
            background: rgba(24, 54, 97, 0.08);
            border-left: 3px solid var(--color-secondary);
            border-radius: 0 8px 8px 0;
        }
        
        .insight-title {
            font-weight: 600;
            margin-bottom: 4px;
        }
        
        .insight-description {
            font-size: 14px;
            color: var(--color-text-muted);
        }
        
        .chart-container {
            background: rgba(24, 54, 97, 0.05);
            border-radius: 8px;
            padding: 24px;
            margin: 16px 0;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
        }
        
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid var(--color-border);
        }
        
        th {
            background: rgba(24, 54, 97, 0.1);
            font-weight: 600;
            font-size: 12px;
            text-transform: uppercase;
        }
        
        .badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
        }
        
        .badge-success { background: rgba(52, 211, 153, 0.2); color: var(--color-success); }
        .badge-warning { background: rgba(251, 191, 36, 0.2); color: var(--color-warning); }
        .badge-danger { background: rgba(248, 113, 113, 0.2); color: var(--color-danger); }
        
        .footer {
            margin-top: 40px;
            padding-top: 24px;
            border-top: 1px solid var(--color-border);
            text-align: center;
            color: var(--color-text-muted);
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="report-container">
        {{ content }}
        
        <div class="footer">
            Generated by MarketNavigator | {{ generated_at }}
        </div>
    </div>
</body>
</html>
"""
    
    # =========================================================================
    # Crunchbase Report Template
    # =========================================================================
    
    @classmethod
    def generate_crunchbase_report(cls, data: Dict[str, Any], project_name: str) -> str:
        """
        Generate Crunchbase Analysis HTML report.
        Per FINAL_ARCHITECTURE - Panel 1.
        """
        companies = data.get('companies', [])
        insights = data.get('insights', [])
        summary = data.get('summary', {})
        
        content = f"""
        <div class="report-header">
            <h1>🔍 Crunchbase Competitor Analysis</h1>
            <div class="report-meta">
                Project: {project_name} | Analysis Date: {timezone.now().strftime('%B %d, %Y')}
            </div>
        </div>
        
        <div class="section">
            <h2>Executive Summary</h2>
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-value">{summary.get('total_companies', len(companies))}</div>
                    <div class="metric-label">Companies Analyzed</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{summary.get('total_funding', '$0')}</div>
                    <div class="metric-label">Total Funding</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{summary.get('avg_employees', '0')}</div>
                    <div class="metric-label">Avg. Employees</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{summary.get('top_round', 'N/A')}</div>
                    <div class="metric-label">Top Funding Round</div>
                </div>
            </div>
        </div>
        
        <div class="section">
            <h2>Top Competitors</h2>
            <div class="company-grid">
        """
        
        for company in companies[:10]:
            content += f"""
                <div class="company-card">
                    <div class="company-name">{company.get('name', 'Unknown')}</div>
                    <div class="company-description">{company.get('description', '')[:120]}...</div>
                    <div class="company-stats">
                        <span class="company-stat">💰 {company.get('funding_total', 'N/A')}</span>
                        <span class="company-stat">👥 {company.get('employee_count', 'N/A')}</span>
                    </div>
                </div>
            """
        
        content += """
            </div>
        </div>
        
        <div class="section">
            <h2>Key Insights</h2>
            <ul class="insights-list">
        """
        
        for insight in insights[:5]:
            content += f"""
                <li class="insight-item">
                    <div class="insight-title">{insight.get('title', '')}</div>
                    <div class="insight-description">{insight.get('description', '')}</div>
                </li>
            """
        
        content += """
            </ul>
        </div>
        """
        
        return cls._render_base(content, f"Crunchbase Analysis - {project_name}")
    
    # =========================================================================
    # Tracxn Report Template
    # =========================================================================
    
    @classmethod
    def generate_tracxn_report(cls, data: Dict[str, Any], project_name: str) -> str:
        """
        Generate Tracxn Analysis HTML report.
        Per FINAL_ARCHITECTURE - Panel 2.
        """
        startups = data.get('startups', [])
        sector_analysis = data.get('sector_analysis', {})
        summary = data.get('summary', {})
        
        content = f"""
        <div class="report-header">
            <h1>📊 Tracxn Startup Landscape</h1>
            <div class="report-meta">
                Project: {project_name} | Analysis Date: {timezone.now().strftime('%B %d, %Y')}
            </div>
        </div>
        
        <div class="section">
            <h2>Landscape Overview</h2>
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-value">{summary.get('total_startups', len(startups))}</div>
                    <div class="metric-label">Startups Found</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{summary.get('funding_range', 'N/A')}</div>
                    <div class="metric-label">Funding Range</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{summary.get('avg_valuation', 'N/A')}</div>
                    <div class="metric-label">Avg. Valuation</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{summary.get('top_sector', 'N/A')}</div>
                    <div class="metric-label">Top Sector</div>
                </div>
            </div>
        </div>
        
        <div class="section">
            <h2>Startup Directory</h2>
            <table>
                <thead>
                    <tr>
                        <th>Startup</th>
                        <th>Sector</th>
                        <th>Stage</th>
                        <th>Funding</th>
                        <th>Location</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for startup in startups[:15]:
            stage_badge = cls._get_stage_badge(startup.get('funding_stage', ''))
            content += f"""
                    <tr>
                        <td><strong>{startup.get('name', 'Unknown')}</strong></td>
                        <td>{startup.get('sector', 'N/A')}</td>
                        <td>{stage_badge}</td>
                        <td>{startup.get('total_funding', 'N/A')}</td>
                        <td>{startup.get('location', 'N/A')}</td>
                    </tr>
            """
        
        content += """
                </tbody>
            </table>
        </div>
        """
        
        return cls._render_base(content, f"Tracxn Analysis - {project_name}")
    
    # =========================================================================
    # Social Analysis Report Template
    # =========================================================================
    
    @classmethod
    def generate_social_report(cls, data: Dict[str, Any], project_name: str) -> str:
        """
        Generate Social Analysis HTML report.
        Per FINAL_ARCHITECTURE - Panel 3: Twitter + LinkedIn.
        """
        twitter_data = data.get('twitter', {})
        linkedin_data = data.get('linkedin', {})
        sentiment = data.get('sentiment', {})
        trending = data.get('trending_topics', [])
        
        content = f"""
        <div class="report-header">
            <h1>📱 Social Media Analysis</h1>
            <div class="report-meta">
                Project: {project_name} | Analysis Date: {timezone.now().strftime('%B %d, %Y')}
            </div>
        </div>
        
        <div class="section">
            <h2>Overview Dashboard</h2>
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-value">{twitter_data.get('total_mentions', 0) + linkedin_data.get('total_mentions', 0)}</div>
                    <div class="metric-label">Total Mentions</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{sentiment.get('overall', 'Neutral').title()}</div>
                    <div class="metric-label">Overall Sentiment</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{sentiment.get('positive', 0)}%</div>
                    <div class="metric-label">Positive</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{len(trending)}</div>
                    <div class="metric-label">Trending Topics</div>
                </div>
            </div>
        </div>
        
        <div class="section">
            <h2>Twitter/X Analysis</h2>
            <p style="color: var(--color-text-muted); margin-bottom: 16px;">
                Analyzed {twitter_data.get('total_tweets', 0)} tweets mentioning your keywords.
            </p>
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-value">{twitter_data.get('total_tweets', 0)}</div>
                    <div class="metric-label">Tweets</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{twitter_data.get('total_engagement', 0)}</div>
                    <div class="metric-label">Engagements</div>
                </div>
            </div>
        </div>
        
        <div class="section">
            <h2>Trending Topics</h2>
            <div style="display: flex; flex-wrap: wrap; gap: 8px;">
        """
        
        for topic in trending[:10]:
            trend_icon = '📈' if topic.get('trend') == 'up' else '📉' if topic.get('trend') == 'down' else '➡️'
            content += f"""
                <div class="badge badge-success" style="font-size: 14px; padding: 8px 16px;">
                    {trend_icon} {topic.get('topic', '')} ({topic.get('mentions', 0)})
                </div>
            """
        
        content += """
            </div>
        </div>
        """
        
        return cls._render_base(content, f"Social Analysis - {project_name}")
    
    # =========================================================================
    # Pitch Deck Report Template
    # =========================================================================
    
    @classmethod
    def generate_pitch_deck(cls, data: Dict[str, Any], project_name: str) -> str:
        """
        Generate Pitch Deck HTML (interactive slides).
        Per FINAL_ARCHITECTURE - Panel 4.
        """
        slides = data.get('slides', {})
        startup_info = data.get('startup_info', {})
        
        content = f"""
        <div class="report-header">
            <h1>🎯 Pitch Deck</h1>
            <div class="report-meta">
                {startup_info.get('name', project_name)} | Generated: {timezone.now().strftime('%B %d, %Y')}
            </div>
        </div>
        
        <style>
            .slide {{
                background: var(--color-surface);
                border-radius: 12px;
                padding: 40px;
                margin-bottom: 24px;
                border: 1px solid var(--color-border);
                min-height: 400px;
            }}
            .slide-number {{
                font-size: 12px;
                color: var(--color-text-muted);
                margin-bottom: 8px;
            }}
            .slide h2 {{
                font-size: 28px;
                color: var(--color-secondary);
                margin-bottom: 24px;
            }}
            .slide ul {{
                list-style: none;
                padding: 0;
            }}
            .slide li {{
                padding: 12px 0;
                padding-left: 24px;
                position: relative;
                border-bottom: 1px solid var(--color-border);
            }}
            .slide li:before {{
                content: "→";
                position: absolute;
                left: 0;
                color: var(--color-secondary);
            }}
        </style>
        """
        
        slide_titles = [
            ('title', 'Title'),
            ('problem', 'The Problem'),
            ('solution', 'Our Solution'),
            ('market', 'Market Opportunity'),
            ('business_model', 'Business Model'),
            ('competition', 'Competitive Landscape'),
            ('traction', 'Traction'),
            ('team', 'Team'),
            ('financials', 'Financial Projections'),
            ('ask', 'The Ask'),
        ]
        
        for i, (key, title) in enumerate(slide_titles, 1):
            slide_content = slides.get(key, {})
            bullets = slide_content.get('bullets', []) if isinstance(slide_content, dict) else []
            
            content += f"""
            <div class="slide">
                <div class="slide-number">Slide {i} of {len(slide_titles)}</div>
                <h2>{title}</h2>
                <ul>
            """
            
            for bullet in bullets[:5]:
                content += f"<li>{bullet}</li>"
            
            if not bullets:
                content += f"<li>Content for {title} slide</li>"
            
            content += """
                </ul>
            </div>
            """
        
        return cls._render_base(content, f"Pitch Deck - {project_name}")
    
    # =========================================================================
    # Verdict Report Template
    # =========================================================================
    
    @classmethod
    def generate_verdict_report(cls, data: Dict[str, Any], project_name: str) -> str:
        """
        Generate Verdict Analysis HTML report.
        Structures output from Master Prompt v8.3 analysis.
        """
        import markdown
        
        executive_synthesis = data.get('executive_synthesis', '')
        scores = data.get('scores', {})
        risks = data.get('risks', {})
        verdict = data.get('verdict', {})
        roadmap = data.get('roadmap', {})
        
        # Calculate total weighted score
        total_score = verdict.get('total_score', 0)
        verdict_value = verdict.get('verdict', 'UNKNOWN')
        
        # Get verdict badge color
        verdict_colors = {
            'GO': ('success', '🟢'),
            'ITERATE': ('warning', '🟡'),
            'PARK': ('danger', '🔴'),
            'KILL': ('danger', '🔴'),
            'UNKNOWN': ('', '⚪'),
        }
        badge_class, verdict_icon = verdict_colors.get(verdict_value.upper() if verdict_value else '', ('', '⚪'))
        
        # Convert markdown to HTML for executive synthesis
        try:
            exec_html = markdown.markdown(executive_synthesis) if executive_synthesis else ''
        except Exception:
            exec_html = executive_synthesis
        
        content = f"""
        <div class="report-header">
            <h1>⚖️ Verdict Analysis</h1>
            <div class="report-meta">
                Project: {project_name} | Analysis Date: {timezone.now().strftime('%B %d, %Y')}
            </div>
        </div>
        
        <!-- Verdict Decision Banner -->
        <div class="section" style="text-align: center; padding: 40px;">
            <div style="font-size: 64px; margin-bottom: 16px;">{verdict_icon}</div>
            <h2 style="font-size: 36px; margin-bottom: 8px;">{verdict_value}</h2>
            <div style="font-size: 24px; color: var(--color-text-muted);">
                Total Score: <strong>{total_score}/100</strong>
            </div>
        </div>
        
        <!-- Executive Synthesis -->
        <div class="section">
            <h2>Executive Synthesis</h2>
            <div style="line-height: 1.8;">
                {exec_html}
            </div>
        </div>
        
        <!-- Quantitative Scoring -->
        <div class="section">
            <h2>Quantitative Opportunity Assessment</h2>
            <table>
                <thead>
                    <tr>
                        <th>Axis</th>
                        <th>Weight</th>
                        <th>Score</th>
                        <th>Confidence</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        axis_weights = {
            'demand': 25,
            'competition': 20,
            'differentiation': 20,
            'economics': 20,
            'feasibility': 15,
        }
        
        for axis_name, weight in axis_weights.items():
            axis_data = scores.get(axis_name, {})
            score = axis_data.get('score', 'N/A')
            confidence = axis_data.get('confidence', 'low')
            
            # Score color
            if isinstance(score, (int, float)):
                if score >= 75:
                    score_badge = f'<span class="badge badge-success">{score}</span>'
                elif score >= 50:
                    score_badge = f'<span class="badge badge-warning">{score}</span>'
                else:
                    score_badge = f'<span class="badge badge-danger">{score}</span>'
            else:
                score_badge = str(score)
            
            content += f"""
                    <tr>
                        <td><strong>{axis_name.title()}</strong></td>
                        <td>{weight}%</td>
                        <td>{score_badge}</td>
                        <td>{confidence.title() if isinstance(confidence, str) else confidence}</td>
                    </tr>
            """
        
        content += f"""
                    <tr style="background: rgba(24, 54, 97, 0.15); font-weight: bold;">
                        <td>TOTAL WEIGHTED SCORE</td>
                        <td>100%</td>
                        <td><span style="font-size: 18px;">{total_score}</span></td>
                        <td>-</td>
                    </tr>
                </tbody>
            </table>
        </div>
        
        <!-- Risk Synthesis -->
        <div class="section">
            <h2>Risk Synthesis (FMEA)</h2>
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-value" style="color: var(--color-danger);">{risks.get('total_killer_risks', len(risks.get('killer_risks', [])))}</div>
                    <div class="metric-label">Killer Risks</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value" style="color: var(--color-warning);">{risks.get('total_major_risks', len(risks.get('major_risks', [])))}</div>
                    <div class="metric-label">Major Risks</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{risks.get('total_minor_risks', len(risks.get('minor_risks', [])))}</div>
                    <div class="metric-label">Minor Risks</div>
                </div>
            </div>
        """
        
        # Killer Risks table
        killer_risks = risks.get('killer_risks', [])
        if killer_risks and isinstance(killer_risks, list):
            content += """
            <h3 style="color: var(--color-danger); margin-top: 24px;">🚨 Killer Risks</h3>
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Risk</th>
                        <th>Sources</th>
                    </tr>
                </thead>
                <tbody>
            """
            for risk in killer_risks[:5]:
                if isinstance(risk, dict):
                    sources = ', '.join(risk.get('dataset_sources', [])) if isinstance(risk.get('dataset_sources'), list) else 'N/A'
                    desc = risk.get('description', '')[:150]
                    content += f"""
                    <tr>
                        <td>{risk.get('risk_id', 'K?')}</td>
                        <td><strong>{risk.get('title', 'Unknown')}</strong><br><small>{desc}</small></td>
                        <td>{sources}</td>
                    </tr>
                    """
            content += "</tbody></table>"
        
        content += "</div>"
        
        # Verdict Reasoning
        verdict_reasoning = verdict.get('verdict_reasoning', '')
        if verdict_reasoning:
            content += f"""
            <div class="section">
                <h2>Verdict Reasoning</h2>
                <p style="line-height: 1.8;">{verdict_reasoning}</p>
            </div>
            """
        
        # Actionable Roadmap
        content += """
        <div class="section">
            <h2>Actionable Roadmap</h2>
        """
        
        # 7-Day Sprint
        seven_day = roadmap.get('seven_day_sprint', {}) if isinstance(roadmap, dict) else {}
        if seven_day and isinstance(seven_day, dict):
            content += f"""
            <div style="background: rgba(52, 211, 153, 0.1); border-radius: 8px; padding: 20px; margin-bottom: 16px;">
                <h3 style="margin-bottom: 12px;">🏃 7-Day Sprint</h3>
                <p><strong>Objective:</strong> {seven_day.get('objective', 'N/A')}</p>
                <p><strong>Hypothesis:</strong> {seven_day.get('hypothesis_to_test', 'N/A')}</p>
                <p><strong>Success Criteria:</strong> {seven_day.get('success_criteria', 'N/A')}</p>
            </div>
            """
        
        # 30-Day Sprint
        thirty_day = roadmap.get('thirty_day_sprint', {}) if isinstance(roadmap, dict) else {}
        if thirty_day and isinstance(thirty_day, dict):
            content += f"""
            <div style="background: rgba(24, 54, 97, 0.1); border-radius: 8px; padding: 20px;">
                <h3 style="margin-bottom: 12px;">📅 30-Day Sprint</h3>
                <p><strong>Objective:</strong> {thirty_day.get('objective', 'N/A')}</p>
                <p><strong>Moat Focus:</strong> {thirty_day.get('moat_building_focus', 'N/A')}</p>
            </div>
            """
        
        content += "</div>"
        
        return cls._render_base(content, f"Verdict Analysis - {project_name}")
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    @classmethod
    def _render_base(cls, content: str, title: str) -> str:
        """Render content into base template."""
        template = Template(cls.BASE_TEMPLATE)
        context = Context({
            'title': title,
            'content': content,
            'generated_at': timezone.now().strftime('%B %d, %Y at %H:%M UTC'),
        })
        return template.render(context)
    
    @classmethod
    def _get_stage_badge(cls, stage: str) -> str:
        """Get badge HTML for funding stage."""
        stage_lower = stage.lower() if stage else ''
        if 'seed' in stage_lower or 'pre' in stage_lower:
            return f'<span class="badge badge-warning">{stage}</span>'
        elif 'series' in stage_lower:
            return f'<span class="badge badge-success">{stage}</span>'
        else:
            return f'<span class="badge">{stage}</span>'


# Singleton instance
html_generator = HTMLReportGenerator()
