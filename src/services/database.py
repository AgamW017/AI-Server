import os
import httpx
from typing import Optional
from models import TaskStatus, JobStatus, GenAIBody, TaskData, JobState

class DatabaseService:
    """
    Service for accessing job and task data from the main server via HTTP requests.
    
    This service makes HTTP requests to the main server instead of connecting
    to MongoDB directly. All methods return Pydantic objects.
    """
    def __init__(self):
        self.webhook_url = os.getenv('WEBHOOK_URL')
        self.webhook_secret = os.getenv('WEBHOOK_SECRET', 'default-webhook-secret')
        self._headers = {
            'Content-Type': 'application/json',
            'x-webhook-signature': self.webhook_secret
        }
        
    async def get_job_state(self, job_id: str) -> Optional[JobState]:
        """Get combined job state from main server - returns Pydantic object"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.webhook_url}/job/{job_id}",
                    headers=self._headers
                )
                if response.status_code == 200:
                    return JobState(**response.json())
        except httpx.HTTPStatusError as e:
            print(f"Error fetching job state for {job_id}: {e}")
            return None

# Global database service instance
db_service = DatabaseService()
