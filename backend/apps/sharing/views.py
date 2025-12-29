"""
Sharing views for public report access.
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.http import HttpResponse

from .models import ShareableLink
from apps.reports.models import Report


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_share_link(request, report_id):
    """Create a shareable link for a report."""
    report = get_object_or_404(Report, id=report_id)
    
    # Check if user has access to this report
    # TODO: Add proper permission check
    
    version_id = request.data.get('version_id')
    expires_at = request.data.get('expires_at')
    
    link = ShareableLink.objects.create(
        report=report,
        report_version_id=version_id,
        created_by=request.user,
        project=report.project,
        expires_at=expires_at
    )
    
    return Response({
        'id': str(link.id),
        'token': link.token,
        'url': f"/share/r/{link.token}",
        'expires_at': link.expires_at,
        'created_at': link.created_at.isoformat()
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_share_links(request, report_id):
    """List all shareable links for a report."""
    report = get_object_or_404(Report, id=report_id)
    
    links = ShareableLink.objects.filter(report=report, is_active=True)
    
    data = [
        {
            'id': str(link.id),
            'token': link.token,
            'url': f"/share/r/{link.token}",
            'view_count': link.view_count,
            'expires_at': link.expires_at,
            'created_at': link.created_at.isoformat()
        }
        for link in links
    ]
    
    return Response(data)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def deactivate_share_link(request, token):
    """Deactivate a shareable link."""
    link = get_object_or_404(ShareableLink, token=token)
    
    # Check ownership
    if link.created_by_id != request.user.id:
        return Response(
            {"error": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN
        )
    
    link.is_active = False
    link.save()
    
    return Response({"message": "Link deactivated"})


@api_view(['GET'])
@permission_classes([AllowAny])
def view_shared_report(request, token):
    """View a shared report (public endpoint)."""
    link = get_object_or_404(ShareableLink, token=token)
    
    if not link.is_valid():
        return Response(
            {"error": "This link has expired or is no longer valid"},
            status=status.HTTP_410_GONE
        )
    
    # Check password if required
    if link.password_hash:
        password = request.query_params.get('password', '')
        from django.contrib.auth.hashers import check_password
        if not check_password(password, link.password_hash):
            return Response(
                {"error": "Password required", "password_protected": True},
                status=status.HTTP_401_UNAUTHORIZED
            )
    
    # Increment view count
    link.increment_view_count()
    
    # Get HTML content
    if link.report_version:
        html_content = link.report_version.html_content
    else:
        html_content = link.report.html_content
    
    # Return data
    return Response({
        'report_type': link.report.report_type,
        'project_name': link.project.name,
        'html_content': html_content,
        'generated_at': link.report.completed_at.isoformat() if link.report.completed_at else None,
        'created_by': link.created_by.full_name or link.created_by.username
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def download_shared_report(request, token):
    """Download shared report as HTML file."""
    link = get_object_or_404(ShareableLink, token=token)
    
    if not link.is_valid():
        return HttpResponse("Link expired", status=410)
    
    # Get HTML content
    if link.report_version:
        html_content = link.report_version.html_content
    else:
        html_content = link.report.html_content
    
    # Create response with download header
    filename = f"{link.project.name}_{link.report.report_type}_report.html"
    response = HttpResponse(html_content, content_type='text/html')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response
