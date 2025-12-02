"""
Google Cloud Storage Service for MegaDoc.

Provides optional GCS integration for:
- Batch processing results storage
- Audit log persistence
- Large file handling

This service is disabled by default and can be enabled via environment variables.
All operations are designed to work within GCS free tier limits (5GB).
"""
import os
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from functools import wraps

logger = logging.getLogger(__name__)


def requires_gcs(func):
    """Decorator to check if GCS is enabled before executing."""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self.enabled:
            logger.debug(f"GCS disabled, skipping {func.__name__}")
            return None
        return func(self, *args, **kwargs)
    return wrapper


class GCSService:
    """
    Google Cloud Storage service for MegaDoc.

    Configuration via environment variables:
        GCS_ENABLED: Set to 'true' to enable GCS integration
        GCS_BUCKET_NAME: Name of the GCS bucket
        GOOGLE_APPLICATION_CREDENTIALS: Path to service account key (optional)

    Usage:
        gcs = GCSService()
        if gcs.enabled:
            url = gcs.upload_batch_result(job_id, data)
    """

    def __init__(self):
        """Initialize GCS service."""
        self.enabled = os.environ.get('GCS_ENABLED', 'false').lower() == 'true'
        self.bucket_name = os.environ.get('GCS_BUCKET_NAME', '')
        self.client = None
        self.bucket = None

        # Prefixes for organizing objects
        self.batch_prefix = 'batch/'
        self.audit_prefix = 'audit/'
        self.temp_prefix = 'temp/'

        # Signed URL expiration (1 hour by default)
        self.signed_url_expiration = int(os.environ.get('GCS_URL_EXPIRATION', 3600))

        if self.enabled:
            self._initialize_client()

    def _initialize_client(self):
        """Initialize GCS client."""
        try:
            from google.cloud import storage
            self.client = storage.Client()
            self.bucket = self.client.bucket(self.bucket_name)
            logger.info(f"GCS service initialized with bucket: {self.bucket_name}")
        except ImportError:
            logger.warning("google-cloud-storage not installed. GCS features disabled.")
            self.enabled = False
        except Exception as e:
            logger.error(f"Failed to initialize GCS client: {e}")
            self.enabled = False

    @requires_gcs
    def upload_batch_result(self, job_id: str, data: bytes, content_type: str = 'application/zip') -> Optional[str]:
        """
        Upload batch processing result to GCS.

        Args:
            job_id: Unique identifier for the batch job
            data: Binary data to upload
            content_type: MIME type of the data

        Returns:
            Signed URL for downloading the result, or None if failed
        """
        try:
            blob_path = f"{self.batch_prefix}{job_id}/result.zip"
            blob = self.bucket.blob(blob_path)

            blob.upload_from_string(data, content_type=content_type)

            # Generate signed URL for download
            url = blob.generate_signed_url(
                expiration=timedelta(seconds=self.signed_url_expiration),
                method='GET'
            )

            logger.info(f"Uploaded batch result for job {job_id}")
            return url

        except Exception as e:
            logger.error(f"Failed to upload batch result: {e}")
            return None

    @requires_gcs
    def download_batch_result(self, job_id: str) -> Optional[bytes]:
        """
        Download batch processing result from GCS.

        Args:
            job_id: Unique identifier for the batch job

        Returns:
            Binary data of the result, or None if not found
        """
        try:
            blob_path = f"{self.batch_prefix}{job_id}/result.zip"
            blob = self.bucket.blob(blob_path)

            if not blob.exists():
                logger.warning(f"Batch result not found for job {job_id}")
                return None

            return blob.download_as_bytes()

        except Exception as e:
            logger.error(f"Failed to download batch result: {e}")
            return None

    @requires_gcs
    def get_batch_result_url(self, job_id: str) -> Optional[str]:
        """
        Get a signed URL for downloading batch result.

        Args:
            job_id: Unique identifier for the batch job

        Returns:
            Signed URL or None if not found
        """
        try:
            blob_path = f"{self.batch_prefix}{job_id}/result.zip"
            blob = self.bucket.blob(blob_path)

            if not blob.exists():
                return None

            return blob.generate_signed_url(
                expiration=timedelta(seconds=self.signed_url_expiration),
                method='GET'
            )

        except Exception as e:
            logger.error(f"Failed to generate signed URL: {e}")
            return None

    @requires_gcs
    def delete_batch_result(self, job_id: str) -> bool:
        """
        Delete batch processing result from GCS.

        Args:
            job_id: Unique identifier for the batch job

        Returns:
            True if deleted, False otherwise
        """
        try:
            blob_path = f"{self.batch_prefix}{job_id}/result.zip"
            blob = self.bucket.blob(blob_path)

            if blob.exists():
                blob.delete()
                logger.info(f"Deleted batch result for job {job_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to delete batch result: {e}")
            return False

    @requires_gcs
    def log_audit_event(self, event: Dict[str, Any]) -> bool:
        """
        Log an audit event to GCS.

        Events are stored in daily log files for efficient retrieval.

        Args:
            event: Audit event data (will be JSON serialized)

        Returns:
            True if logged successfully, False otherwise
        """
        try:
            # Add timestamp if not present
            if 'timestamp' not in event:
                event['timestamp'] = datetime.utcnow().isoformat()

            # Create daily log file path
            date_str = datetime.utcnow().strftime('%Y/%m/%d')
            blob_path = f"{self.audit_prefix}{date_str}/events.jsonl"
            blob = self.bucket.blob(blob_path)

            # Append to existing log or create new
            existing_content = ""
            if blob.exists():
                existing_content = blob.download_as_text()

            new_line = json.dumps(event) + "\n"
            blob.upload_from_string(existing_content + new_line, content_type='application/jsonl')

            return True

        except Exception as e:
            logger.error(f"Failed to log audit event: {e}")
            return False

    @requires_gcs
    def get_audit_events(self, date: datetime = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Retrieve audit events for a specific date.

        Args:
            date: Date to retrieve events for (defaults to today)
            limit: Maximum number of events to return

        Returns:
            List of audit events
        """
        try:
            if date is None:
                date = datetime.utcnow()

            date_str = date.strftime('%Y/%m/%d')
            blob_path = f"{self.audit_prefix}{date_str}/events.jsonl"
            blob = self.bucket.blob(blob_path)

            if not blob.exists():
                return []

            content = blob.download_as_text()
            events = []

            for line in content.strip().split('\n'):
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

                if len(events) >= limit:
                    break

            return events

        except Exception as e:
            logger.error(f"Failed to retrieve audit events: {e}")
            return []

    @requires_gcs
    def upload_temp_file(self, filename: str, data: bytes, content_type: str = 'application/octet-stream') -> Optional[str]:
        """
        Upload a temporary file to GCS.

        Temp files are automatically deleted after 24 hours via lifecycle policy.

        Args:
            filename: Name for the file
            data: Binary data to upload
            content_type: MIME type of the data

        Returns:
            Signed URL for accessing the file
        """
        try:
            blob_path = f"{self.temp_prefix}{filename}"
            blob = self.bucket.blob(blob_path)

            blob.upload_from_string(data, content_type=content_type)

            url = blob.generate_signed_url(
                expiration=timedelta(hours=24),
                method='GET'
            )

            return url

        except Exception as e:
            logger.error(f"Failed to upload temp file: {e}")
            return None

    @requires_gcs
    def file_exists(self, path: str) -> bool:
        """
        Check if a file exists in the bucket.

        Args:
            path: Path to the file in the bucket

        Returns:
            True if exists, False otherwise
        """
        try:
            blob = self.bucket.blob(path)
            return blob.exists()
        except Exception as e:
            logger.error(f"Failed to check file existence: {e}")
            return False

    @requires_gcs
    def list_files(self, prefix: str = '', limit: int = 100) -> List[str]:
        """
        List files in the bucket with a given prefix.

        Args:
            prefix: Prefix to filter files
            limit: Maximum number of files to return

        Returns:
            List of file paths
        """
        try:
            blobs = self.bucket.list_blobs(prefix=prefix, max_results=limit)
            return [blob.name for blob in blobs]
        except Exception as e:
            logger.error(f"Failed to list files: {e}")
            return []

    @requires_gcs
    def get_storage_usage(self) -> Dict[str, Any]:
        """
        Get storage usage statistics.

        Returns:
            Dictionary with usage statistics
        """
        try:
            total_size = 0
            file_count = 0

            for blob in self.bucket.list_blobs():
                total_size += blob.size or 0
                file_count += 1

            return {
                'total_size_bytes': total_size,
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'file_count': file_count,
                'bucket_name': self.bucket_name,
                'free_tier_limit_gb': 5,
                'usage_percentage': round((total_size / (5 * 1024 * 1024 * 1024)) * 100, 2)
            }

        except Exception as e:
            logger.error(f"Failed to get storage usage: {e}")
            return {'error': str(e)}

    def get_status(self) -> Dict[str, Any]:
        """
        Get GCS service status.

        Returns:
            Status information dictionary
        """
        return {
            'enabled': self.enabled,
            'bucket_name': self.bucket_name if self.enabled else None,
            'prefixes': {
                'batch': self.batch_prefix,
                'audit': self.audit_prefix,
                'temp': self.temp_prefix
            } if self.enabled else None
        }


# Singleton instance
_gcs_service = None


def get_gcs_service() -> GCSService:
    """Get the singleton GCS service instance."""
    global _gcs_service
    if _gcs_service is None:
        _gcs_service = GCSService()
    return _gcs_service
