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
    
    @action(detail=True, methods=['get'])
    def sections(self, request, project_id=None, pk=None):
        """
        Get report sections as structured JSON data from S3.
        Returns analysis sections for rendering in the React frontend.
        """
        from services.report_storage import report_storage
        
        report = self.get_object()
        project = report.project
        
        # Get org_id
        org_id = str(project.organization_id) if project.organization_id else 'default'
        
        logger.info(f"📖 Fetching sections for report {report.id}")
        logger.info(f"   Project: {project.id}, Org: {org_id}")
        logger.info(f"   Report type: {report.report_type}, Version: {report.current_version}")
        
        try:
            # Get sections from S3
            sections_data = report_storage.get_all_sections(
                project_id=str(project.id),
                org_id=org_id,
                version=report.current_version,
                report_type=report.report_type
            )
            
            logger.info(f"   Sections found: {len(sections_data.get('sections', []))}")
            
            # If no sections found, return empty with debug info
            if not sections_data.get('sections'):
                logger.warning(f"❌ No sections found in S3 for report {report.id}")
                logger.warning(f"   Expected path: organizations/{org_id}/projects/{project.id}/reports/{report.report_type}/v{report.current_version}/")
                return Response({
                    'metadata': None,
                    'sections': [],
                    'debug': {
                        'org_id': org_id,
                        'project_id': str(project.id),
                        'report_type': report.report_type,
                        'version': report.current_version,
                        'expected_path': f"organizations/{org_id}/projects/{project.id}/reports/{report.report_type}/v{report.current_version}/"
                    }
                })
            
            logger.info(f"✅ Returning {len(sections_data.get('sections', []))} sections")
            return Response(sections_data)
            
        except Exception as e:
            logger.error(f"❌ Error fetching sections for report {report.id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return Response(
                {"error": str(e), "sections": []},
                status=status.HTTP_200_OK
            )


class StatusUpdateView(APIView):
    """
    Internal API endpoint for receiving real-time status updates from crunchbase_api.
    This is used by the Crunchbase API container to send progress updates during scraping.
    No authentication required since it's internal container-to-container communication.
    """
    permission_classes = [AllowAny]  # Internal API, no auth needed
    
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
