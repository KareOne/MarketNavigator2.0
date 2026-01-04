"""
Report Storage Service.
Handles JSON file storage for report data and AI analysis responses using S3/MinIO.

File Structure in S3:
organizations/{org_id}/projects/{project_id}/reports/{report_type}/v{version}/
├── raw_data.json               # Raw API response from scraper
├── analysis/
│   ├── company_overview.json   # Overview analysis
│   ├── {section_type}/
│   │   ├── {company_name}.json # Per-company analysis
│   └── summaries/
│       └── {summary_type}.json # Executive summaries
└── metadata.json               # Report metadata
"""
import json
import logging
import re
from datetime import datetime
from typing import Dict, Any, Optional, List
from io import BytesIO

from django.conf import settings
from core.storage import storage_service

logger = logging.getLogger(__name__)


class ReportStorageService:
    """
    Service for storing and retrieving report JSON data using S3/MinIO.
    Leverages the existing storage_service for S3 operations.
    """
    
    def __init__(self):
        self.storage = storage_service
        logger.info("Report storage initialized (using S3/MinIO)")
    
    def _sanitize_filename(self, name: str) -> str:
        """Sanitize a string for use as a filename."""
        # Replace spaces and special chars with underscores
        sanitized = re.sub(r'[^\w\-]', '_', name)
        # Remove multiple underscores
        sanitized = re.sub(r'_+', '_', sanitized)
        # Remove leading/trailing underscores
        sanitized = sanitized.strip('_')
        # Limit length and lowercase
        return (sanitized[:100] if sanitized else 'unknown').lower()
    
    def _get_base_path(
        self, 
        org_id: str,
        project_id: str, 
        report_type: str, 
        version: int
    ) -> str:
        """Get the S3 base path for a report version."""
        return f"organizations/{org_id}/projects/{project_id}/reports/{report_type}/v{version}"
    
    def _upload_json(self, key: str, data: Any, metadata: dict = None) -> str:
        """Upload JSON data to S3."""
        json_bytes = json.dumps(data, indent=2, ensure_ascii=False, default=str).encode('utf-8')
        file_obj = BytesIO(json_bytes)
        
        result = self.storage.upload_file(
            file_obj=file_obj,
            key=key,
            content_type='application/json',
            metadata=metadata
        )
        
        logger.info(f"Uploaded JSON to S3: {key}")
        return key
    
    def _download_json(self, key: str) -> Optional[Dict]:
        """Download and parse JSON from S3."""
        try:
            content = self.storage.download_file(key)
            return json.loads(content.decode('utf-8'))
        except Exception as e:
            logger.warning(f"Failed to download JSON from S3: {key} - {e}")
            return None
    
    # ===== Crunchbase Report Methods =====
    
    def save_crunchbase_raw_data(
        self, 
        project_id: str,
        org_id: str,
        version: int, 
        raw_data: Dict[str, Any]
    ) -> str:
        """
        Save raw Crunchbase API response data to S3.
        
        Args:
            project_id: UUID of the project
            org_id: UUID of the organization
            version: Report version number
            raw_data: Dictionary containing:
                - all_companies: List of all companies found
                - top_companies: Top ranked companies with full data
                - metadata: Search metadata (timing, counts, etc.)
                - keywords: Search keywords used
        
        Returns:
            S3 key of saved file
        """
        base_path = self._get_base_path(org_id, project_id, 'crunchbase', version)
        key = f"{base_path}/raw_data.json"
        
        # Add timestamp
        raw_data['saved_at'] = datetime.utcnow().isoformat()
        
        return self._upload_json(key, raw_data, {'type': 'raw_data', 'version': str(version)})
    
    def save_analysis_section(
        self, 
        project_id: str,
        org_id: str,
        version: int, 
        section_type: str,
        content: str,
        company_name: Optional[str] = None,
        metadata: Optional[Dict] = None,
        report_type: str = 'crunchbase'
    ) -> str:
        """
        Save an AI analysis section response to S3.
        
        Args:
            project_id: UUID of the project
            org_id: UUID of the organization
            version: Report version number
            section_type: Type of analysis (tech_product, market_demand, etc.)
            content: AI-generated content (markdown)
            company_name: Company name for per-company sections
            metadata: Optional metadata (processing time, model used, etc.)
            report_type: Type of report (crunchbase, social, etc.)
        
        Returns:
            S3 key of saved file
        """
        base_path = self._get_base_path(org_id, project_id, report_type, version)
        
        data = {
            'section_type': section_type,
            'content': content,
            'saved_at': datetime.utcnow().isoformat(),
        }
        
        if company_name:
            data['company_name'] = company_name
        
        if metadata:
            data['metadata'] = metadata
        
        if section_type == 'company_overview':
            # Overview is a single file
            key = f"{base_path}/analysis/company_overview.json"
        elif company_name:
            # Per-company sections go in subdirectories
            sanitized_name = self._sanitize_filename(company_name)
            key = f"{base_path}/analysis/{section_type}/{sanitized_name}.json"
        else:
            # Fallback for unknown structure
            key = f"{base_path}/analysis/{section_type}.json"
        
        return self._upload_json(key, data, {'type': 'analysis', 'section': section_type})
    
    def save_analysis_summary(
        self, 
        project_id: str,
        org_id: str,
        version: int, 
        summary_type: str,
        content: str,
        metadata: Optional[Dict] = None,
        report_type: str = 'crunchbase'
    ) -> str:
        """
        Save an executive summary AI response to S3.
        
        Args:
            project_id: UUID of the project
            org_id: UUID of the organization
            version: Report version number
            summary_type: Type of summary (tech_product_summary, etc.)
            content: AI-generated content (markdown)
            metadata: Optional metadata
            report_type: Type of report (crunchbase, social, etc.)
        
        Returns:
            S3 key of saved file
        """
        base_path = self._get_base_path(org_id, project_id, report_type, version)
        
        data = {
            'summary_type': summary_type,
            'content': content,
            'saved_at': datetime.utcnow().isoformat(),
        }
        
        if metadata:
            data['metadata'] = metadata
        
        key = f"{base_path}/analysis/summaries/{summary_type}.json"
        return self._upload_json(key, data, {'type': 'summary', 'summary': summary_type})
    
    def save_report_metadata(
        self, 
        project_id: str,
        org_id: str,
        version: int, 
        metadata: Dict[str, Any],
        report_type: str = 'crunchbase'
    ) -> str:
        """
        Save report metadata to S3.
        
        Args:
            project_id: UUID of the project
            org_id: UUID of the organization
            version: Report version number
            metadata: Dictionary containing report metadata
            report_type: Type of report (crunchbase, social, etc.)
        
        Returns:
            S3 key of saved file
        """
        base_path = self._get_base_path(org_id, project_id, report_type, version)
        key = f"{base_path}/metadata.json"
        
        metadata['saved_at'] = datetime.utcnow().isoformat()
        
        return self._upload_json(key, metadata, {'type': 'metadata', 'version': str(version)})
    
    def get_all_report_files(
        self, 
        project_id: str,
        org_id: str,
        report_type: str, 
        version: int
    ) -> Dict[str, Any]:
        """
        List all JSON files for a report version from S3.
        
        Returns:
            Dictionary with file keys and metadata
        """
        base_path = self._get_base_path(org_id, project_id, report_type, version)
        
        files = self.storage.list_files(prefix=base_path)
        
        result = {
            'base_path': base_path,
            'files': []
        }
        
        for f in files:
            if f['Key'].endswith('.json'):
                result['files'].append({
                    'key': f['Key'],
                    'size': f.get('Size', 0),
                    'last_modified': f.get('LastModified', '').isoformat() if f.get('LastModified') else None
                })
        
        return result
    
    def get_crunchbase_raw_data(
        self, 
        project_id: str,
        org_id: str,
        version: int
    ) -> Optional[Dict]:
        """Load the raw Crunchbase data for a report from S3."""
        base_path = self._get_base_path(org_id, project_id, 'crunchbase', version)
        key = f"{base_path}/raw_data.json"
        return self._download_json(key)
    
    def get_presigned_url(
        self,
        project_id: str,
        org_id: str,
        report_type: str,
        version: int,
        file_path: str,
        expiration: int = 3600
    ) -> str:
        """Get a presigned URL for downloading a specific JSON file."""
        base_path = self._get_base_path(org_id, project_id, report_type, version)
        key = f"{base_path}/{file_path}"
        return self.storage.get_presigned_url(key, expiration)
    
    def save_twitter_raw_data(
        self,
        project_id: str,
        org_id: str,
        version: int,
        raw_data: List[Dict[str, Any]]
    ) -> str:
        """
        Save raw Twitter API response/tweets to S3.
        """
        base_path = self._get_base_path(org_id, project_id, 'social', version)
        key = f"{base_path}/raw_data.json"
        
        data = {
            'tweets': raw_data,
            'count': len(raw_data),
            'saved_at': datetime.utcnow().isoformat()
        }
        
        return self._upload_json(key, data, {'type': 'raw_data', 'version': str(version)})

    def get_all_sections(
        self,
        project_id: str,
        org_id: str,
        version: int,
        report_type: str = 'crunchbase'
    ) -> Dict[str, Any]:
        """
        Get all analysis sections for a report from S3.
        """
        base_path = self._get_base_path(org_id, project_id, report_type, version)
        logger.info(f"📂 get_all_sections: base_path = {base_path}")
        
        result = {
            'metadata': None,
            'sections': []
        }
        
        # Get metadata
        metadata_key = f"{base_path}/metadata.json"
        logger.info(f"   Looking for metadata: {metadata_key}")
        metadata = self._download_json(metadata_key)
        if metadata:
            result['metadata'] = metadata
            logger.info(f"   ✅ Found metadata")
        else:
            logger.warning(f"   ❌ No metadata found")
        
        # Get company overview (Crunchbase specific, but harmless to check or skip)
        if report_type == 'crunchbase':
            overview_key = f"{base_path}/analysis/company_overview.json"
            overview = self._download_json(overview_key)
            if overview:
                result['sections'].append({
                    'id': 'overview',
                    'title': '📊 Company Overview',
                    'type': 'overview',
                    'content': overview.get('content', '')
                })
        
        # Define sections based on report type
        if report_type == 'crunchbase':
            section_types = [
                ('tech_product', '💻 Technology & Product'),
                ('market_demand', '📈 Market Demand & Web Insights'),
                ('competitor', '🎯 Competitor Identification'),
                ('market_funding', '💰 Market & Funding Insights'),
                ('growth_potential', '🚀 Growth Potential'),
                ('swot', '⚖️ SWOT Analysis'),
            ]
            summary_types = [
                ('tech_product_summary', '💻 Technology & Product Summary'),
                ('market_demand_summary', '📈 Market Demand Summary'),
                ('competitor_summary', '🎯 Competitor Summary'),
                ('market_funding_summary', '💰 Funding Summary'),
                ('growth_potential_summary', '🚀 Growth Summary'),
                ('swot_summary', '⚖️ SWOT Summary'),
            ]
        elif report_type == 'social':
            section_types = [
                ('market_segmentation', '👥 Market Segmentation'),
                ('jtbd', '🔨 Jobs to be Done'),
                ('pain_points', '😫 Pain Points & Frustrations'),
                ('willingness_to_pay', '💸 Willingness to Pay'),
                ('competitive_landscape', '⚔️ Competitive Landscape'),
                ('sentiment', '❤️ Sentiment Analysis'),
            ]
            # Social report currently stores Executive Summary as a regular section or summary?
            # In `tasks.py` I saved 'executive_summary' as a section, but `TwitterAnalysisPipeline` returns it in `analysis_results`.
            # I should create a mapping for it.
            summary_types = [] 
            # Note: In tasks.py I saved everything via loop over `analysis_results`. 
            # `results['executive_summary']` was added to the dict.
            # So `executive_summary` is treated as a section type.
            # I'll add it to section_types or handle it separately.
            section_types.append(('executive_summary', '📝 Executive Summary'))

        elif report_type == 'tracxn':
             # Placeholder for Tracxn sections if needed, assuming similarity to CB
             section_types = []
             summary_types = []
        else:
            section_types = []
            summary_types = []
        
        # Get analysis sections
        for section_type, title in section_types:
            # For Social, we saved them as single files (no company subdirs), unless I logic change in tasks.py
            # In tasks.py: `section_type=key, content=content`.
            # `save_analysis_section` implementation:
            # if `company_name` is None: `key = f"{base_path}/analysis/{section_type}.json"` (Fallback)
            # So for Social, they are single files.
            
            # Check for single file first
            key = f"{base_path}/analysis/{section_type}.json"
            data = self._download_json(key)
            if data:
                 result['sections'].append({
                    'id': section_type.replace('_', '-'),
                    'title': title,
                    'type': 'section', # Generic type
                    'content': data.get('content', '')
                })
                 continue

            # Check for subdirectories (Per Company) - mostly for Crunchbase
            if report_type == 'crunchbase':
                section_prefix = f"{base_path}/analysis/{section_type}/"
                files = self.storage.list_files(prefix=section_prefix)
                companies = []
                for f in files:
                    if f['Key'].endswith('.json'):
                        company_data = self._download_json(f['Key'])
                        if company_data:
                            companies.append({
                                'name': company_data.get('company_name', 'Unknown'),
                                'content': company_data.get('content', '')
                            })
                
                if companies:
                    section_id = section_type.replace('_', '-')
                    result['sections'].append({
                        'id': section_id,
                        'title': title,
                        'type': 'company',
                        'companies': companies
                    })
        
        # Get summaries (mostly for Crunchbase)
        for summary_type, title in summary_types:
            summary_key = f"{base_path}/analysis/summaries/{summary_type}.json"
            summary = self._download_json(summary_key)
            if summary:
                section_id = summary_type.replace('_', '-')
                result['sections'].append({
                    'id': section_id,
                    'title': title,
                    'type': 'summary',
                    'content': summary.get('content', '')
                })
        
        logger.info(f"📊 Total sections found: {len(result['sections'])}")
        return result


# Singleton instance
report_storage = ReportStorageService()
