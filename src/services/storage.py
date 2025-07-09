import os
import json
from typing import Optional, Any

try:
    from google.cloud import storage
    GCLOUD_AVAILABLE = True
except ImportError:
    GCLOUD_AVAILABLE = False
    storage = None

class GCloudStorageService:
    """Google Cloud Storage service for uploading files"""
    
    def __init__(self):
        self.bucket_name = os.getenv('GCLOUD_BUCKET_NAME', 'ai-server-uploads')
        self.project_id = os.getenv('GCLOUD_PROJECT', 'your-project-id')
        
        self.client = None
        self.bucket = None
        
        if not GCLOUD_AVAILABLE:
            return
        
        # Initialize Google Cloud Storage client
        try:
            # If running in GCP, credentials are automatically detected
            if storage:
                self.client = storage.Client(project=self.project_id)
        except Exception as e:
            # For development, you might want to use service account key
            credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            if credentials_path and os.path.exists(credentials_path) and storage:
                self.client = storage.Client.from_service_account_json(credentials_path, project=self.project_id)
        
        if self.client:
            try:
                self.bucket = self.client.bucket(self.bucket_name)
            except Exception as e:
                print(f"Error accessing GCS bucket {self.bucket_name}: {e}")

    async def upload_file(self, file_path: str, destination_name: str, content_type: str = 'application/octet-stream') -> Optional[str]:
        """
        Upload a file to Google Cloud Storage
        
        Args:
            file_path: Local path to the file to upload
            destination_name: Name for the file in the bucket
            content_type: MIME type of the file
            
        Returns:
            Public URL of the uploaded file or None if upload failed
        """
        if not self.bucket:
            return None
            
        if not os.path.exists(file_path):
            return None
            
        try:
            blob = self.bucket.blob(destination_name)
            
            # Upload file
            with open(file_path, 'rb') as file_data:
                blob.upload_from_file(file_data, content_type=content_type)
            
            # Make the blob publicly readable (optional)
            blob.make_public()
            
            # Return the public URL
            public_url = blob.public_url
            return public_url
            
        except Exception as e:
            return None

    async def upload_text_content(self, content: str, destination_name: str, content_type: str = 'text/plain') -> Optional[str]:
        """
        Upload text content directly to Google Cloud Storage
        
        Args:
            content: Text content to upload
            destination_name: Name for the file in the bucket
            content_type: MIME type of the content
            
        Returns:
            Public URL of the uploaded content or None if upload failed
        """
        if not self.bucket:
            return None
            
        try:
            blob = self.bucket.blob(destination_name)
            
            # Upload content
            blob.upload_from_string(content, content_type=content_type)
            
            # Make the blob publicly readable (optional)
            blob.make_public()
            
            # Return the public URL
            public_url = blob.public_url
            return public_url
            
        except Exception as e:
            return None

    async def upload_json_content(self, data: Any, destination_name: str) -> Optional[str]:
        """
        Upload JSON data to Google Cloud Storage
        
        Args:
            data: Data to upload as JSON (dict, list, etc.)
            destination_name: Name for the file in the bucket
            
        Returns:
            Public URL of the uploaded JSON or None if upload failed
        """
        json_content = json.dumps(data, indent=2, ensure_ascii=False)
        return await self.upload_text_content(json_content, destination_name, 'application/json')

    def get_file_url(self, file_name: str) -> str:
        """Get the public URL for a file in the bucket"""
        if not self.bucket:
            return f"gs://{self.bucket_name}/{file_name}"
        
        blob = self.bucket.blob(file_name)
        return blob.public_url
