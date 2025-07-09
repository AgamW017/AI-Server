import os
from typing import Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase
from models import TaskStatus, GenAIBody, TaskData, JobState

class DatabaseService:
    """
    Read-only database service for accessing job and task data from MongoDB Atlas.
    
    This service only provides read operations - jobs and tasks are created 
    elsewhere in the system. This server only reads existing job state.
    All methods return Pydantic objects instead of raw dictionaries.
    """
    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None
        self.genai_collection: Optional[AsyncIOMotorCollection] = None
        self.task_data_collection: Optional[AsyncIOMotorCollection] = None
        self._connected = False
        
    async def connect(self):
        """Connect to MongoDB Atlas"""
        if self._connected:
            return
            
        try:
            db_url = os.getenv('DB_URL')
            if not db_url:
                raise ValueError("MONGODB_URL environment variable not set")
            
            self.client = AsyncIOMotorClient(db_url)
            self.db = self.client.get_default_database()
            
            # Collections
            self.genai_collection = self.db.genai_jobs
            self.task_data_collection = self.db.task_data
            
            # Test connection
            await self.client.admin.command('ping')
            self._connected = True
            
        except Exception as e:
            raise
    
    async def ensure_connected(self):
        """Ensure database connection is established"""
        if not self._connected:
            await self.connect()
        
        if not self.genai_collection or not self.task_data_collection:
            raise RuntimeError("Database collections not properly initialized")
    
    async def disconnect(self):
        """Disconnect from MongoDB"""
        if self.client:
            self.client.close()
            self._connected = False
    
    # READ-ONLY OPERATIONS
    
    async def get_genai_job(self, job_id: str) -> Optional[GenAIBody]:
        """Get GenAI job by ID (READ-ONLY) - returns Pydantic object"""
        await self.ensure_connected()
        assert self.genai_collection is not None, "GenAI collection not initialized"
        
        try:
            job_dict = await self.genai_collection.find_one({"_id": job_id})
            if job_dict:
                return GenAIBody(**job_dict)
            return None
        except Exception as e:
            return None
    
    async def get_task_data(self, job_id: str) -> Optional[TaskData]:
        """Get task data for a job (READ-ONLY) - returns Pydantic object"""
        await self.ensure_connected()
        assert self.task_data_collection is not None, "Task data collection not initialized"
        
        try:
            task_dict = await self.task_data_collection.find_one({"jobId": job_id})
            if task_dict:
                return TaskData(**task_dict)
            return None
        except Exception as e:
            return None
    
    async def get_job_state(self, job_id: str) -> Optional[JobState]:
        """Get combined job state from both collections (READ-ONLY) - returns Pydantic object"""
        await self.ensure_connected()
        assert self.genai_collection is not None, "GenAI collection not initialized"
        assert self.task_data_collection is not None, "Task data collection not initialized"
        
        try:
            # Get job info
            job = await self.get_genai_job(job_id)
            if not job:
                return None
            
            # Get task data
            task_data = await self.get_task_data(job_id)
            
            # Create job state
            audio_file_path = None
            transcript = None
            segments = None
            questions = None
            
            if task_data:
                # Extract latest data from task entries
                if task_data.audioExtraction:
                    latest_audio = task_data.audioExtraction[-1]
                    if latest_audio.status == TaskStatus.COMPLETED:
                        audio_file_path = latest_audio.fileName
                
                if task_data.transcriptGeneration:
                    latest_transcript = task_data.transcriptGeneration[-1]
                    if latest_transcript.status == TaskStatus.COMPLETED:
                        # Extract transcript from the data stored in database
                        transcript = getattr(latest_transcript, 'transcript', None)
                
                if task_data.segmentation:
                    latest_segments = task_data.segmentation[-1]
                    if latest_segments.status == TaskStatus.COMPLETED:
                        # Extract segments from the data stored in database
                        segments = getattr(latest_segments, 'segments', None)
                
                if task_data.questionGeneration:
                    latest_questions = task_data.questionGeneration[-1]
                    if latest_questions.status == TaskStatus.COMPLETED:
                        # Extract questions from the data stored in database
                        questions = getattr(latest_questions, 'questions', [])
            
            return JobState(
                job_data=job,
                task_data=task_data,
                current_task=getattr(job, 'currentTask', 'PENDING'),
                task_status=job.jobStatus,
                audio_file_path=audio_file_path,
                transcript=transcript,
                segments=segments,
                questions=questions
            )
            
        except Exception as e:
            return None

# Global database service instance
db_service = DatabaseService()
