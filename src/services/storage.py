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
        
        print(f"GCS Storage Service initializing with bucket: {self.bucket_name}, project: {self.project_id}")
        
        self.client = None
        self.bucket = None
        
        if not GCLOUD_AVAILABLE:
            print("Google Cloud Storage library not available")
            return
        
        # Initialize Google Cloud Storage client
        try:
            # If running in GCP, credentials are automatically detected
            if storage:
                print("Attempting to initialize GCS client...")
                self.client = storage.Client(project=self.project_id)
                print("GCS client initialized successfully")
        except Exception as e:
            print(f"Error initializing GCS client: {e}")
            # For development, you might want to use service account key
            credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            if credentials_path and os.path.exists(credentials_path) and storage:
                print(f"Trying to initialize GCS client with service account: {credentials_path}")
                self.client = storage.Client.from_service_account_json(credentials_path, project=self.project_id)
                print("GCS client initialized with service account")
        
        if self.client:
            try:
                print(f"Accessing GCS bucket: {self.bucket_name}")
                self.bucket = self.client.bucket(self.bucket_name)
                print("GCS bucket accessed successfully")
            except Exception as e:
                print(f"Error accessing GCS bucket {self.bucket_name}: {e}")
        else:
            print("GCS client is None, bucket will not be available")

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
        print(f"GCS upload_file called: file_path={file_path}, destination_name={destination_name}")
        
        if not self.bucket:
            print("GCS bucket not initialized")
            return None
            
        if not os.path.exists(file_path):
            print(f"File does not exist: {file_path}")
            return None
            
        try:
            print(f"Creating blob for destination: {destination_name}")
            blob = self.bucket.blob(destination_name)
            
            # Upload file
            print(f"Uploading file to GCS...")
            with open(file_path, 'rb') as file_data:
                blob.upload_from_file(file_data, content_type=content_type)
            
            print(f"File uploaded successfully")
            
            # Return the public URL
            public_url = blob.public_url
            print(f"Public URL generated: {public_url}")
            return public_url
            
        except Exception as e:
            print(f"Error uploading file to GCS: {str(e)}")
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
            
            # Skip make_public() since bucket has uniform bucket-level access enabled
            # blob.make_public()
            
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
        json_content = json.dumps(data)
        return await self.upload_text_content(json_content, destination_name, 'application/json')

    def get_file_url(self, file_name: str) -> str:
        """Get the public URL for a file in the bucket"""
        if not self.bucket:
            return f"gs://{self.bucket_name}/{file_name}"
        
        blob = self.bucket.blob(file_name)
        return blob.public_url
