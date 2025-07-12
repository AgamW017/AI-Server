from fastapi import APIRouter, Depends, Response, BackgroundTasks, HTTPException
from typing import Optional
from ai import (
    start_audio_extraction_task,
    start_transcript_generation_task,
    start_segmentation_task,
    start_question_generation_task
)
from models import (
    JobCreateRequest,
    JobState, 
    JobUpdateRequest, 
    JobCreateResponse,
    JobUpdateResponse,
    TaskApprovalRequest,
    TaskApprovalResponse,
    JobAbortResponse,
    TaskRerunResponse,
    JobStatusResponse,
    JobErrorResponse,
    TaskStatus
)
from auth import verify_webhook_secret
from services.database import db_service
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

router = APIRouter(prefix="/jobs", tags=["jobs"])

def run_async_task_in_thread(async_func, *args, **kwargs):
    """Helper function to run async tasks in a new thread with its own event loop"""
    def run_in_thread():
        try:
            print(f"Starting background task: {async_func.__name__}")
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(async_func(*args, **kwargs))
                print(f"Background task completed successfully: {async_func.__name__}")
                return result
            finally:
                loop.close()
        except Exception as e:
            print(f"Error in background task {async_func.__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            raise
    
    # Run in a separate thread
    thread = threading.Thread(target=run_in_thread)
    thread.start()

def run_async_task(async_func, *args, **kwargs):
    """Helper function to run async tasks in background"""
    return run_async_task_in_thread(async_func, *args, **kwargs)

@router.post("/", response_model=JobCreateResponse)
async def create_job(
    jobData: JobCreateRequest,
    background_tasks: BackgroundTasks,
    _: str = Depends(verify_webhook_secret)
):
    print(f"Create job called with data: {jobData.dict()}")
    
    if jobData.data.type == 'VIDEO':
        print(f"Processing VIDEO job {jobData.jobId}")
        
        # Don't start processing immediately - just prepare the job and ask for approval
        # The job should be created in the database by external system with status PENDING
        # and current_task as "PENDING" waiting for first task approval
        
        print(f"Job {jobData.jobId} prepared, waiting for task approval")
    else:
        print(f"Unsupported job type: {jobData.data.type}")
    
    return JobCreateResponse(message="Job created successfully, waiting for task approval")


@router.post("/{jobId}/tasks/approve/start", response_model=TaskApprovalResponse)
async def approve_task_start(
    jobId: str,
    background_tasks: BackgroundTasks,
    _: str = Depends(verify_webhook_secret),
    taskData: Optional[TaskApprovalRequest] = None,
):
    if not taskData:
        raise HTTPException(status_code=400, detail="Task data is required for approval")
    """Approve any task to start - works for all tasks"""
    print(f"Approve task start called for job {jobId}")
    current_task = taskData.task
    task_status = taskData.status
    print(f"Job {jobId} current_task: {taskData.task}, task_status: {taskData.status}")
    
    # Only start if task is waiting for approval (PENDING or WAITING)
    if task_status != "WAITING":
        raise HTTPException(status_code=400, detail=f"Current task {current_task} is not waiting for approval (status: {task_status})")
    
    # Start the appropriate task based on current_task
    if current_task is None:
        # Start audio extraction task
        print(f"Starting audio extraction task for job {jobId}")
        background_tasks.add_task(run_async_task, start_audio_extraction_task, jobId)
        return TaskApprovalResponse(message="Audio extraction task started")
    elif current_task == "AUDIO_EXTRACTION":
        # Start transcript generation task
        print(f"Starting transcript generation task for job {jobId}")
        background_tasks.add_task(run_async_task, start_transcript_generation_task, jobId, taskData.parameters if taskData else None)
        return TaskApprovalResponse(message="Transcript generation task started")
    elif current_task == "TRANSCRIPT_GENERATION":
        # Start segmentation task
        print(f"Starting segmentation task for job {jobId}")
        background_tasks.add_task(run_async_task, start_segmentation_task, jobId, taskData.parameters if taskData else None)
        return TaskApprovalResponse(message="Segmentation task started")
    elif current_task == "SEGMENTATION":
        # Start question generation task
        print(f"Starting question generation task for job {jobId}")
        background_tasks.add_task(run_async_task, start_question_generation_task, jobId, taskData.parameters if taskData else None)
        return TaskApprovalResponse(message="Question generation task started")
    elif current_task == "QUESTION_GENERATION":
        # Question generation is the final task - no more tasks after this
        raise HTTPException(status_code=400, detail="Question generation is the final task. No more tasks available.")
    else:
        raise HTTPException(status_code=400, detail=f"Unknown task: {current_task}")


@router.post("/{jobId}/tasks/rerun", response_model=TaskRerunResponse)
async def rerun_task(
    jobId: str,
    background_tasks: BackgroundTasks,
    taskData: JobState,
    _: str = Depends(verify_webhook_secret)
):
    """Rerun the current task"""
    current_task = taskData.currentTask
    task_status = taskData.taskStatus
    
    if task_status != "COMPLETED":
        raise HTTPException(status_code=400, detail=f"Current task {current_task} is not completed (status: {task_status})")
    
    if current_task == "AUDIO_EXTRACTION":
        background_tasks.add_task(run_async_task, start_audio_extraction_task, jobId)
        return TaskRerunResponse(message="Audio extraction task restarted", jobId=jobId)
    elif current_task == "TRANSCRIPT_GENERATION":
        background_tasks.add_task(run_async_task, start_transcript_generation_task, jobId, taskData.parameters if taskData else None)
        return TaskRerunResponse(message="Transcript generation task restarted", jobId=jobId)
    elif current_task == "SEGMENTATION":
        background_tasks.add_task(run_async_task, start_segmentation_task, jobId, taskData.parameters if taskData else None)
        return TaskRerunResponse(message="Segmentation task restarted", jobId=jobId)
    elif current_task == "QUESTION_GENERATION":
        background_tasks.add_task(run_async_task, start_question_generation_task, jobId, taskData.parameters if taskData else None)
        return TaskRerunResponse(message="Question generation task restarted", jobId=jobId)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown task: {current_task}")
