import os
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, List
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING
import logging
from enum import Enum

from models import JobCreateRequest, TaskStatus

logger = logging.getLogger(__name__)

class JobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ABORTED = "ABORTED"

class DatabaseService:
    """
    Read-only database service for accessing job and task data from MongoDB Atlas.
    
    This service only provides read operations - jobs and tasks are created 
    elsewhere in the system. This server only reads existing job state.
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
            db_url = os.getenv('MONGODB_URL')
            if not db_url:
                logger.error("MONGODB_URL environment variable not set")
                raise ValueError("MONGODB_URL environment variable not set")
            
            self.client = AsyncIOMotorClient(db_url)
            self.db = self.client.get_default_database()
            
            # Collections
            self.genai_collection = self.db.genai_jobs
            self.task_data_collection = self.db.task_data
            
            # Test connection
            await self.client.admin.command('ping')
            logger.info("Connected to MongoDB Atlas successfully")
            self._connected = True
            
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
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
            logger.info("Disconnected from MongoDB")
    
    # READ-ONLY OPERATIONS
    
    async def get_genai_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get GenAI job by ID (READ-ONLY)"""
        await self.ensure_connected()
        assert self.genai_collection is not None, "GenAI collection not initialized"
        
        try:
            job = await self.genai_collection.find_one({"_id": job_id})
            return job
        except Exception as e:
            logger.error(f"Error getting GenAI job {job_id}: {e}")
            return None
    
    async def get_task_data(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get task data for a job (READ-ONLY)"""
        await self.ensure_connected()
        assert self.task_data_collection is not None, "Task data collection not initialized"
        
        try:
            task_data = await self.task_data_collection.find_one({"jobId": job_id})
            return task_data
        except Exception as e:
            logger.error(f"Error getting task data for job {job_id}: {e}")
            return None
    
    async def get_job_state(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get combined job state from both collections (READ-ONLY)"""
        await self.ensure_connected()
        assert self.genai_collection is not None, "GenAI collection not initialized"
        assert self.task_data_collection is not None, "Task data collection not initialized"
        
        try:
            # Get job info
            job = await self.get_genai_job(job_id)
            if not job:
                logger.warning(f"No job found with ID: {job_id}")
                return None
            
            # Get task data
            task_data = await self.get_task_data(job_id)
            if not task_data:
                logger.warning(f"No task data found for job: {job_id}")
                # Return basic state without task data
                return {
                    "job_data": job,
                    "current_task": job.get("currentTask", "PENDING"),
                    "task_status": job.get("jobStatus", JobStatus.PENDING),
                    "audio_file_path": None,
                    "transcript": None,
                    "segments": None,
                    "questions": None,
                    "task_data": None
                }
            
            # Combine into a state object similar to the old in-memory format
            state = {
                "job_data": job,
                "current_task": job.get("currentTask", "PENDING"),
                "task_status": job.get("jobStatus", JobStatus.PENDING),
                "audio_file_path": None,
                "transcript": None,
                "segments": None,
                "questions": None,
                "task_data": task_data
            }
            
            # Extract latest data from task entries
            if task_data.get("audioExtraction"):
                latest_audio = task_data["audioExtraction"][-1]
                if latest_audio.get("status") == "COMPLETED":
                    state["audio_file_path"] = latest_audio.get("fileName")
            
            if task_data.get("transcriptGeneration"):
                latest_transcript = task_data["transcriptGeneration"][-1]
                if latest_transcript.get("status") == "COMPLETED":
                    state["transcript"] = latest_transcript.get("transcript")
            
            if task_data.get("segmentation"):
                latest_segments = task_data["segmentation"][-1]
                if latest_segments.get("status") == "COMPLETED":
                    state["segments"] = latest_segments.get("segments")
            
            if task_data.get("questionGeneration"):
                latest_questions = task_data["questionGeneration"][-1]
                if latest_questions.get("status") == "COMPLETED":
                    state["questions"] = latest_questions.get("questions", [])
            
            return state
            
        except Exception as e:
            logger.error(f"Error getting job state for {job_id}: {e}")
            return None

# Global database service instance
db_service = DatabaseService()
