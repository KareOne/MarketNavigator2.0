"""
Report views for 4 panel types.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.utils import timezone
import logging

from .models import Report, ReportVersion
from .serializers import ReportSerializer, ReportListSerializer, ReportVersionSerializer
from .tasks import generate_crunchbase_report, generate_tracxn_report, generate_social_report, generate_pitch_deck
from .progress_tracker import ReportProgressTracker
from apps.projects.models import Project

logger = logging.getLogger(__name__)


class ReportViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for reports."""
    
    permission_classes = [IsAuthenticated]
    serializer_class = ReportSerializer
    
    def get_queryset(self):
        """Get reports for a project."""
        project_id = self.kwargs.get('project_id')
        return Report.objects.filter(project_id=project_id)
    
    def list(self, request, project_id=None):
        """List all reports for a project."""
        project = get_object_or_404(Project, id=project_id)
        
        # Ensure all 4 report types exist
        report_types = ['crunchbase', 'tracxn', 'social', 'pitch_deck']
        for rt in report_types:
            Report.objects.get_or_create(
                project=project,
                report_type=rt
            )
        
        reports = self.get_queryset()
        serializer = ReportListSerializer(reports, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def start(self, request, project_id=None, pk=None):
        """Start generating a report."""
        report = self.get_object()
        project = report.project
        
        # Check inputs are complete
        if project.inputs.completion_status != 'complete':
            return Response(
                {"error": "Please complete all project inputs first"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if already running
        if report.status == 'running':
            return Response(
                {"error": "Report is already being generated"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check dependencies for pitch deck
        if report.report_type == 'pitch_deck':
            crunchbase = Report.objects.filter(
                project=project, report_type='crunchbase', status='completed'
            ).exists()
            tracxn = Report.objects.filter(
                project=project, report_type='tracxn', status='completed'
            ).exists()
            
            if not (crunchbase and tracxn):
                return Response(
                    {"error": "Please complete Crunchbase and Tracxn analyses first"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Update status
        report.status = 'running'
        report.progress = 0
        report.current_step = 'Starting...'
        report.error_message = ''
        report.started_at = timezone.now()
        report.inputs_hash = project.inputs.get_inputs_hash()
        report.save()
        
        # Start background task
        task_map = {
            'crunchbase': generate_crunchbase_report,
            'tracxn': generate_tracxn_report,
            'social': generate_social_report,
            'pitch_deck': generate_pitch_deck,
        }
        
        task = task_map.get(report.report_type)
        if task:
            task.delay(str(report.id), str(request.user.id))
        
        return Response({
            "message": f"{report.get_report_type_display()} generation started",
            "report_id": str(report.id)
        })
    
    @action(detail=True, methods=['get'])
    def versions(self, request, project_id=None, pk=None):
        """Get all versions of a report."""
        report = self.get_object()
        versions = report.versions.all()
        serializer = ReportVersionSerializer(versions, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'], url_path='versions/(?P<version_number>[0-9]+)')
    def get_version(self, request, project_id=None, pk=None, version_number=None):
        """Get a specific version of a report."""
        report = self.get_object()
        version = get_object_or_404(
            ReportVersion,
            report=report,
            version_number=int(version_number)
        )
        serializer = ReportVersionSerializer(version)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def compare(self, request, project_id=None, pk=None):
        """Compare two versions of a report."""
        report = self.get_object()
        
        v1 = request.query_params.get('v1')
        v2 = request.query_params.get('v2')
        
        if not v1 or not v2:
            return Response(
                {"error": "Provide v1 and v2 version numbers"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        version1 = get_object_or_404(ReportVersion, report=report, version_number=int(v1))
        version2 = get_object_or_404(ReportVersion, report=report, version_number=int(v2))
        
        return Response({
            "v1": ReportVersionSerializer(version1).data,
            "v2": ReportVersionSerializer(version2).data,
        })
    
    def _get_sections_with_fallback(self, report):
        """
        Helper to get sections from S3, falling back to DB if missing.
        Preserves the structure expected by frontend (grouping companies).
        """
        from services.report_storage import report_storage
        from .models import ReportAnalysisSection
        
        project = report.project
        org_id = str(project.organization_id) if project.organization_id else 'default'
        
        # 1. Try S3
        try:
            sections_data = report_storage.get_all_sections(
                project_id=str(project.id),
                org_id=org_id,
                version=report.current_version,
                report_type=report.report_type
            )
            if sections_data.get('sections'):
                logger.info(f"✅ Found {len(sections_data['sections'])} sections in S3")
                return sections_data
        except Exception as e:
            logger.warning(f"⚠️ S3 fetch failed: {e}")
            sections_data = {'sections': [], 'metadata': None}

        # 2. Fallback to DB
        logger.info(f"🔄 Falling back to DB for report {report.id}")
        db_sections = ReportAnalysisSection.objects.filter(
            report=report
        ).order_by('order', 'id')
        
        if not db_sections.exists():
            logger.warning("❌ No sections found in DB either")
            return {'sections': [], 'metadata': None}
            
        # Reconstruct structure
        sections_list = []
        titles_map = dict(ReportAnalysisSection.SECTION_TYPE_CHOICES)
        
        # Grouping tracker for company sections
        current_group = None
        current_group_type = None
        
        for section in db_sections:
            # Handle company sections (group them)
            if section.company_name:
                # If simplified grouping key avoids 'summary', use base type
                group_key = section.section_type
                
                if current_group and current_group_type == group_key:
                    # Add to existing group
                    current_group['companies'].append({
                        'name': section.company_name,
                        'content': section.content_markdown
                    })
                else:
                    # Create new group
                    title = titles_map.get(section.section_type, section.section_type.replace('_', ' ').title())
                    current_group = {
                        'id': section.section_type.replace('_', '-'),
                        'title': title,
                        'type': 'company',
                        'companies': [{
                            'name': section.company_name,
                            'content': section.content_markdown
                        }]
                    }
                    current_group_type = group_key
                    sections_list.append(current_group)
            else:
                # Regular section or summary
                current_group = None
                current_group_type = None
                
                title = titles_map.get(section.section_type, section.section_type.replace('_', ' ').title())
                # Determine type: overview, summary, or generic section
                sec_type = 'section'
                if 'overview' in section.section_type:
                    sec_type = 'overview'
                elif 'summary' in section.section_type:
                    sec_type = 'summary'
                
                sections_list.append({
                    'id': section.section_type.replace('_', '-'),
                    'title': title,
                    'type': sec_type,
                    'content': section.content_markdown
                })
        
        logger.info(f"✅ Reconstructed {len(sections_list)} sections from DB")
        return {'sections': sections_list, 'metadata': None}

    @action(detail=True, methods=['get'])
    def sections(self, request, project_id=None, pk=None):
        """
        Get report sections. Tries S3, falls back to DB.
        """
        report = self.get_object()
        logger.info(f"📖 Fetching sections for report {report.id} (v{report.current_version})")
        
        try:
            sections_data = self._get_sections_with_fallback(report)
            return Response(sections_data)
        except Exception as e:
            logger.error(f"❌ Error fetching sections: {e}")
            return Response({"error": str(e), "sections": []})

    @action(detail=True, methods=['get'], url_path='download-markdown')
    def download_markdown(self, request, project_id=None, pk=None):
        """
        Generate markdown download. Tries S3, falls back to DB.
        """
        from django.http import HttpResponse
        
        report = self.get_object()
        project = report.project
        
        try:
            sections_data = self._get_sections_with_fallback(report)
            
            # Build markdown
            report_type_names = {
                'crunchbase': 'Crunchbase Analysis Report',
                'tracxn': 'Tracxn Market Report',
                'social': 'Social Media Analysis Report',
                'pitch_deck': 'Pitch Deck'
            }
            
            md_lines = [
                f"# {report_type_names.get(report.report_type, 'Analysis Report')}",
                f"**Project:** {project.name}",
                f"**Generated:** {report.completed_at.strftime('%Y-%m-%d %H:%M') if report.completed_at else 'N/A'}",
                "",
                "---",
                ""
            ]
            
            for section in sections_data.get('sections', []):
                md_lines.append(f"## {section.get('title', 'Section')}")
                md_lines.append("")
                
                if section.get('type') == 'company' and section.get('companies'):
                    for company in section.get('companies', []):
                        md_lines.append(f"### {company.get('name', 'Unknown Company')}")
                        md_lines.append("")
                        md_lines.append(company.get('content', ''))
                        md_lines.append("")
                else:
                    md_lines.append(section.get('content', ''))
                    md_lines.append("")
                
                md_lines.append("---")
                md_lines.append("")
            
            markdown_content = "\n".join(md_lines)
            
            filename = f"{project.name}_{report.report_type}_report.md".replace(' ', '_')
            response = HttpResponse(markdown_content, content_type='text/markdown; charset=utf-8')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
            
        except Exception as e:
            logger.error(f"❌ Error generating markdown: {e}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'], url_path='download-raw-data')
    def download_raw_data(self, request, project_id=None, pk=None):
        """
        Download raw API data from S3.
        Note: Raw data is NOT stored in DB, so no fallback ensures data integrity.
        """
        from django.http import HttpResponse
        from services.report_storage import report_storage
        import json
        
        report = self.get_object()
        project = report.project
        org_id = str(project.organization_id) if project.organization_id else 'default'
        
        try:
            # Get raw data based on report type
            raw_data = None
            if report.report_type == 'crunchbase':
                raw_data = report_storage.get_crunchbase_raw_data(
                    project_id=str(project.id),
                    org_id=org_id,
                    version=report.current_version
                )
            elif report.report_type == 'tracxn':
                raw_data = report_storage.get_tracxn_raw_data(
                    project_id=str(project.id),
                    org_id=org_id,
                    version=report.current_version
                )
            elif report.report_type == 'social':
                raw_data = report_storage.get_twitter_raw_data(
                    project_id=str(project.id),
                    org_id=org_id,
                    version=report.current_version
                )
            else:
                return Response(
                    {"error": f"Raw data download not supported for {report.report_type}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if not raw_data:
                # Try DB Fallback (ReportRawData)
                try:
                    from .models import ReportRawData
                    record = ReportRawData.objects.filter(
                        report=report, 
                        version=report.current_version,
                        report_type=report.report_type
                    ).first()
                    
                    if record:
                        raw_data = record.data
                        logger.info(f"✅ Retrieved raw data from DB fallback for report {report.id}")
                    else:
                        logger.warning(f"❌ Raw data not found in DB either for report {report.id}")
                except Exception as db_err:
                    logger.warning(f"⚠️ DB fallback error: {db_err}")

            if not raw_data:
                return Response(
                    {"error": "Raw data not found for this report (checked S3 and Database)"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Create JSON response with file download
            json_content = json.dumps(raw_data, indent=2, ensure_ascii=False, default=str)
            filename = f"{project.name}_{report.report_type}_raw_data.json".replace(' ', '_')
            response = HttpResponse(json_content, content_type='application/json; charset=utf-8')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
            
        except Exception as e:
            logger.error(f"❌ Error downloading raw data for report {report.id}: {e}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class StatusUpdateView(APIView):
    """
    Internal API endpoint for receiving real-time status updates from crunchbase_api.
    This is used by the Crunchbase API container to send progress updates during scraping.
    No authentication required since it's internal container-to-container communication.
    """
    permission_classes = [AllowAny]  # Internal API, no auth needed
    throttle_scope = 'status_updates'
    
    def post(self, request):
        """
        Receive status update from crunchbase_api and forward to WebSocket.
        
        Expected payload:
        {
            "report_id": "uuid",
            "step_key": "api_search",
            "detail_type": "search_result",
            "message": "Searched 'keyword' → 20 companies",
            "data": {"keyword": "keyword", "count": 20}  # optional
        }
        """
        report_id = request.data.get('report_id')
        step_key = request.data.get('step_key')
        detail_type = request.data.get('detail_type')
        message = request.data.get('message')
        data = request.data.get('data')
        
        if not report_id or not step_key or not message:
            return Response(
                {"error": "Missing required fields: report_id, step_key, message"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            report = Report.objects.get(id=report_id)
            tracker = ReportProgressTracker(report)
            
            # Add the detail to the appropriate step
            tracker.add_step_detail(step_key, detail_type or 'status', message, data)
            
            logger.info(f"📡 Status update received for report {report_id}: {message[:50]}...")
            return Response({"status": "ok"})
            
        except Report.DoesNotExist:
            logger.warning(f"⚠️ Status update failed: Report {report_id} not found")
            return Response(
                {"error": f"Report {report_id} not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"❌ Status update error: {e}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
