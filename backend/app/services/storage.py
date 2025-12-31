"""
Storage service for ML models and file uploads.
Supports both local filesystem and Supabase Storage.
"""
import os
import logging
from pathlib import Path
from typing import Optional
import tempfile

logger = logging.getLogger(__name__)

# Check if Supabase is configured
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
USE_SUPABASE = bool(SUPABASE_URL and SUPABASE_KEY)

if USE_SUPABASE:
    try:
        from supabase import create_client, Client
        supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    except ImportError:
        logger.warning("Supabase package not installed. Using local storage.")
        USE_SUPABASE = False


class StorageService:
    """Unified storage service for files and ML models."""

    def __init__(self, bucket_name: str = "ml-models"):
        self.bucket_name = bucket_name
        self.use_supabase = USE_SUPABASE

        # Local storage fallback
        if not self.use_supabase:
            self.local_dir = Path(__file__).parent.parent.parent / "data" / bucket_name
            self.local_dir.mkdir(parents=True, exist_ok=True)

    def upload_file(self, file_path: str, destination_name: str) -> bool:
        """Upload a file to storage."""
        try:
            if self.use_supabase:
                with open(file_path, 'rb') as f:
                    supabase_client.storage.from_(self.bucket_name).upload(
                        destination_name,
                        f.read(),
                        {"content-type": "application/octet-stream"}
                    )
                logger.info(f"Uploaded {destination_name} to Supabase")
            else:
                # Local copy
                dest_path = self.local_dir / destination_name
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                with open(file_path, 'rb') as src, open(dest_path, 'wb') as dst:
                    dst.write(src.read())
                logger.info(f"Copied {destination_name} to local storage")
            return True
        except Exception as e:
            logger.error(f"Failed to upload {destination_name}: {e}")
            return False

    def download_file(self, source_name: str) -> Optional[bytes]:
        """Download a file from storage."""
        try:
            if self.use_supabase:
                response = supabase_client.storage.from_(self.bucket_name).download(source_name)
                logger.info(f"Downloaded {source_name} from Supabase")
                return response
            else:
                # Local read
                file_path = self.local_dir / source_name
                if file_path.exists():
                    with open(file_path, 'rb') as f:
                        logger.info(f"Read {source_name} from local storage")
                        return f.read()
                else:
                    logger.warning(f"File {source_name} not found in local storage")
                    return None
        except Exception as e:
            logger.error(f"Failed to download {source_name}: {e}")
            return None

    def file_exists(self, file_name: str) -> bool:
        """Check if a file exists in storage."""
        try:
            if self.use_supabase:
                files = supabase_client.storage.from_(self.bucket_name).list()
                return any(f['name'] == file_name for f in files)
            else:
                return (self.local_dir / file_name).exists()
        except Exception as e:
            logger.error(f"Failed to check if {file_name} exists: {e}")
            return False

    def get_temp_path(self, file_name: str) -> str:
        """Get a temporary file path for downloads."""
        temp_dir = Path(tempfile.gettempdir()) / "finance_portal"
        temp_dir.mkdir(exist_ok=True)
        return str(temp_dir / file_name)


# Global storage instances
ml_models_storage = StorageService("ml-models")
uploads_storage = StorageService("uploads")
