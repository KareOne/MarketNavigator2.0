"""
S3/Object Storage service for MarketNavigator v2.
Per UI_AND_STORAGE_SPECIFICATIONS.md bucket structure.
"""
import boto3
from botocore.exceptions import ClientError
from django.conf import settings
import logging
import mimetypes
from typing import Optional, BinaryIO
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class StorageService:
    """
    S3-compatible storage service.
    
    Bucket Structure (per UI_AND_STORAGE_SPECIFICATIONS.md):
    - organizations/{org_id}/projects/{project_id}/reports/{report_type}/
    - organizations/{org_id}/projects/{project_id}/uploads/
    - organizations/{org_id}/projects/{project_id}/pitch_decks/
    - public/shared/{token}/
    """
    
    def __init__(self):
        self.use_s3 = getattr(settings, 'USE_S3', True)
        
        if self.use_s3:
            self.client = boto3.client(
                's3',
                endpoint_url=settings.AWS_S3_ENDPOINT_URL,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME,
            )
            self.bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    
    def _get_path(self, path_type: str, **kwargs) -> str:
        """
        Get storage path based on type and parameters.
        Uses paths defined in settings.S3_PATHS.
        """
        path_template = settings.S3_PATHS.get(path_type, '')
        return path_template.format(**kwargs)
    
    # =========================================================================
    # Core Upload/Download Operations
    # =========================================================================
    
    def upload_file(
        self,
        file_obj: BinaryIO,
        key: str,
        content_type: str = None,
        metadata: dict = None
    ) -> dict:
        """
        Upload a file to S3.
        
        Args:
            file_obj: File-like object to upload
            key: S3 object key (path)
            content_type: MIME type
            metadata: Additional metadata
        
        Returns:
            dict with file info (key, size, url)
        """
        if not self.use_s3:
            return self._upload_local(file_obj, key)
        
        try:
            extra_args = {}
            if content_type:
                extra_args['ContentType'] = content_type
            if metadata:
                extra_args['Metadata'] = metadata
            
            # Get file size BEFORE upload (boto3 may close file after upload)
            file_obj.seek(0, 2)  # Seek to end
            size = file_obj.tell()
            file_obj.seek(0)  # Reset to beginning for upload
            
            self.client.upload_fileobj(
                file_obj,
                self.bucket_name,
                key,
                ExtraArgs=extra_args
            )
            
            return {
                'key': key,
                'bucket': self.bucket_name,
                'size': size,
                'content_type': content_type,
            }
        except ClientError as e:
            logger.error(f"Failed to upload file to S3: {e}")
            raise
    
    def download_file(self, key: str) -> bytes:
        """Download a file from S3."""
        if not self.use_s3:
            return self._download_local(key)
        
        try:
            response = self.client.get_object(
                Bucket=self.bucket_name,
                Key=key
            )
            return response['Body'].read()
        except ClientError as e:
            logger.error(f"Failed to download file from S3: {e}")
            raise
    
    def delete_file(self, key: str) -> bool:
        """Delete a file from S3."""
        if not self.use_s3:
            return self._delete_local(key)
        
        try:
            self.client.delete_object(
                Bucket=self.bucket_name,
                Key=key
            )
            return True
        except ClientError as e:
            logger.error(f"Failed to delete file from S3: {e}")
            return False
    
    def get_presigned_url(
        self,
        key: str,
        expiration: int = 3600,
        method: str = 'get_object'
    ) -> str:
        """
        Generate a presigned URL for file access.
        
        Args:
            key: S3 object key
            expiration: URL expiration in seconds
            method: 'get_object' for download, 'put_object' for upload
        
        Returns:
            Presigned URL string
        """
        if not self.use_s3:
            return f"/media/{key}"  # Local fallback
        
        try:
            url = self.client.generate_presigned_url(
                method,
                Params={'Bucket': self.bucket_name, 'Key': key},
                ExpiresIn=expiration
            )
            return url
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            raise
    
    # =========================================================================
    # Report Storage (per UI_AND_STORAGE_SPECIFICATIONS.md)
    # =========================================================================
    
    def upload_report(
        self,
        org_id: str,
        project_id: str,
        report_type: str,
        report_id: str,
        content: bytes,
        file_type: str = 'html'
    ) -> dict:
        """
        Upload a report file.
        
        Path: organizations/{org_id}/projects/{project_id}/reports/{report_type}/{report_id}.{file_type}
        """
        path = self._get_path('reports', org_id=org_id, project_id=project_id, report_type=report_type)
        key = f"{path}/{report_id}.{file_type}"
        
        content_types = {
            'html': 'text/html',
            'json': 'application/json',
            'pdf': 'application/pdf',
            'csv': 'text/csv',
        }
        
        from io import BytesIO
        file_obj = BytesIO(content if isinstance(content, bytes) else content.encode())
        
        return self.upload_file(
            file_obj,
            key,
            content_type=content_types.get(file_type, 'application/octet-stream'),
            metadata={'report_id': str(report_id), 'report_type': report_type}
        )
    
    def get_report_url(
        self,
        org_id: str,
        project_id: str,
        report_type: str,
        report_id: str,
        file_type: str = 'html',
        expiration: int = 3600
    ) -> str:
        """Get presigned URL for report download."""
        path = self._get_path('reports', org_id=org_id, project_id=project_id, report_type=report_type)
        key = f"{path}/{report_id}.{file_type}"
        return self.get_presigned_url(key, expiration)
    
    # =========================================================================
    # Shared/Public Storage
    # =========================================================================
    
    def upload_shared_report(self, token: str, content: bytes, file_type: str = 'html') -> dict:
        """
        Upload a report for public sharing.
        
        Path: public/shared/{token}/report.{file_type}
        """
        path = self._get_path('public_shared', token=token)
        key = f"{path}/report.{file_type}"
        
        from io import BytesIO
        file_obj = BytesIO(content if isinstance(content, bytes) else content.encode())
        
        return self.upload_file(
            file_obj,
            key,
            content_type='text/html' if file_type == 'html' else 'application/octet-stream',
        )
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    def ensure_bucket_exists(self):
        """Ensure the S3 bucket exists (for MinIO local dev)."""
        if not self.use_s3:
            return
        
        try:
            self.client.head_bucket(Bucket=self.bucket_name)
        except ClientError:
            try:
                self.client.create_bucket(Bucket=self.bucket_name)
                logger.info(f"Created bucket: {self.bucket_name}")
            except ClientError as e:
                logger.error(f"Failed to create bucket: {e}")
    
    def list_files(self, prefix: str, max_keys: int = 100) -> list:
        """List files with a given prefix."""
        if not self.use_s3:
            return []
        
        try:
            response = self.client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=max_keys
            )
            return response.get('Contents', [])
        except ClientError as e:
            logger.error(f"Failed to list files: {e}")
            return []
    
    # =========================================================================
    # Local Storage Fallback
    # =========================================================================
    
    def _upload_local(self, file_obj: BinaryIO, key: str) -> dict:
        """Upload to local filesystem (dev fallback)."""
        import os
        path = settings.MEDIA_ROOT / key
        os.makedirs(path.parent, exist_ok=True)
        
        with open(path, 'wb') as f:
            f.write(file_obj.read())
        
        return {'key': key, 'bucket': 'local', 'size': path.stat().st_size}
    
    def _download_local(self, key: str) -> bytes:
        """Download from local filesystem."""
        path = settings.MEDIA_ROOT / key
        with open(path, 'rb') as f:
            return f.read()
    
    def _delete_local(self, key: str) -> bool:
        """Delete from local filesystem."""
        import os
        path = settings.MEDIA_ROOT / key
        try:
            os.remove(path)
            return True
        except OSError:
            return False


# Singleton instance
storage_service = StorageService()
