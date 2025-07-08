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
    JobUpdateRequest, 
    JobCreateResponse,
    JobUpdateResponse,
    TaskApprovalResponse,
    JobAbortResponse,
    TaskRerunResponse,
    JobStatusResponse,
    JobErrorResponse,
    TaskStatus
)
from auth import verify_webhook_secret, log_request
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
    log_request("POST /jobs", jobData.dict())
    
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


@router.post("/{jobId}/update", response_model=JobUpdateResponse)
async def update_job(
    jobId: str,
    updateData: JobUpdateRequest,
    _: str = Depends(verify_webhook_secret)
):
    """Update job parameters"""
    requestBody = updateData.dict()
    log_request("POST /jobs/{jobId}/update", requestBody, jobId)
    
    return JobUpdateResponse(message="Job parameters updated successfully")


@router.post("/{jobId}/tasks/approve/start", response_model=TaskApprovalResponse)
async def approve_task_start(
    jobId: str,
    background_tasks: BackgroundTasks,
    _: str = Depends(verify_webhook_secret),
    taskData: Optional[JobUpdateRequest] = None
):
    """Approve any task to start - works for all tasks"""
    requestBody = taskData.dict() if taskData else {}
    log_request("POST /jobs/{jobId}/tasks/approve/start", requestBody, jobId)
    
    print(f"Approve task start called for job {jobId}")
    
    # Get job state from database
    job_state = await db_service.get_job_state(jobId)
    if not job_state:
        print(f"Job {jobId} not found in database")
        raise HTTPException(status_code=404, detail="Job not found")
    
    current_task = job_state.get("current_task", "PENDING")
    task_status = job_state.get("task_status", "PENDING")
    
    print(f"Job {jobId} current_task: {current_task}, task_status: {task_status}")
    
    # Only start if task is waiting for approval (PENDING or WAITING)
    if task_status not in ["PENDING", "WAITING"]:
        raise HTTPException(status_code=400, detail=f"Current task {current_task} is not waiting for approval (status: {task_status})")
    
    # Start the appropriate task based on current_task
    if current_task == "PENDING":
        # Start audio extraction task
        print(f"Starting audio extraction task for job {jobId}")
        background_tasks.add_task(run_async_task, start_audio_extraction_task, jobId, requestBody)
        return TaskApprovalResponse(message="Audio extraction task started")
    elif current_task == "AUDIO_EXTRACTION":
        # Start transcript generation task
        print(f"Starting transcript generation task for job {jobId}")
        background_tasks.add_task(run_async_task, start_transcript_generation_task, jobId, requestBody)
        return TaskApprovalResponse(message="Transcript generation task started")
    elif current_task == "TRANSCRIPT_GENERATION":
        # Start segmentation task
        print(f"Starting segmentation task for job {jobId}")
        background_tasks.add_task(run_async_task, start_segmentation_task, jobId, requestBody)
        return TaskApprovalResponse(message="Segmentation task started")
    elif current_task == "SEGMENTATION":
        # Start question generation task
        print(f"Starting question generation task for job {jobId}")
        background_tasks.add_task(run_async_task, start_question_generation_task, jobId, requestBody)
        return TaskApprovalResponse(message="Question generation task started")
    elif current_task == "QUESTION_GENERATION":
        # Question generation is the final task - no more tasks after this
        raise HTTPException(status_code=400, detail="Question generation is the final task. No more tasks available.")
    else:
        raise HTTPException(status_code=400, detail=f"Unknown task: {current_task}")


@router.post("/{jobId}/tasks/approve/continue", response_model=TaskApprovalResponse)
async def approve_task_continue(
    jobId: str,
    approvalData: JobUpdateRequest,
    background_tasks: BackgroundTasks,
    _: str = Depends(verify_webhook_secret)
):
    """Approve task completion and continue to next task"""
    requestBody = approvalData.dict()
    log_request("POST /jobs/{jobId}/tasks/approve/continue", requestBody, jobId)
    
    # Get job state from database
    job_state = await db_service.get_job_state(jobId)
    if not job_state:
        raise HTTPException(status_code=404, detail="Job not found")
    
    current_task = job_state.get("current_task")
    task_status = job_state.get("task_status")
    
    if task_status != "COMPLETED":
        raise HTTPException(status_code=400, detail=f"Current task {current_task} is not completed (status: {task_status})")
    
    # Determine next task and start it
    if current_task == "AUDIO_EXTRACTION":
        background_tasks.add_task(run_async_task, start_transcript_generation_task, jobId, requestBody)
        return TaskApprovalResponse(message="Transcript generation task started")
    elif current_task == "TRANSCRIPT_GENERATION":
        background_tasks.add_task(run_async_task, start_segmentation_task, jobId, requestBody)
        return TaskApprovalResponse(message="Segmentation task started")
    elif current_task == "SEGMENTATION":
        background_tasks.add_task(run_async_task, start_question_generation_task, jobId, requestBody)
        return TaskApprovalResponse(message="Question generation task started")
    elif current_task == "QUESTION_GENERATION":
        # Question generation is the final task - job is complete
        raise HTTPException(status_code=400, detail="Question generation is the final task. Job is complete.")
    else:
        raise HTTPException(status_code=400, detail=f"No next task available for current task: {current_task}")


@router.post("/{jobId}/abort", response_model=JobAbortResponse)
async def abort_job(
    jobId: str,
    _: str = Depends(verify_webhook_secret)
):
    """Abort the job"""
    log_request("POST /jobs/{jobId}/abort", {}, jobId)
    
    # Get job state from database
    job_state = await db_service.get_job_state(jobId)
    if not job_state:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Note: Job status updates are handled by the external system, not this read-only service
    
    return JobAbortResponse(message="Job aborted successfully")


@router.post("/{jobId}/tasks/rerun", response_model=TaskRerunResponse)
async def rerun_task(
    jobId: str,
    background_tasks: BackgroundTasks,
    _: str = Depends(verify_webhook_secret)
):
    """Rerun the current task"""
    log_request("POST /jobs/{jobId}/tasks/rerun", {}, jobId)
    
    # Get job state from database
    job_state = await db_service.get_job_state(jobId)
    if not job_state:
        raise HTTPException(status_code=404, detail="Job not found")
    
    current_task = job_state.get("current_task")
    
    # Reset task status and rerun current task
    if current_task:
        # Note: Job status updates are handled by the external system, not this read-only service
        pass
    
    if current_task == "AUDIO_EXTRACTION":
        background_tasks.add_task(run_async_task, start_audio_extraction_task, jobId, None)
        return TaskRerunResponse(message="Audio extraction task restarted", jobId=jobId)
    elif current_task == "TRANSCRIPT_GENERATION":
        background_tasks.add_task(run_async_task, start_transcript_generation_task, jobId, None)
        return TaskRerunResponse(message="Transcript generation task restarted", jobId=jobId)
    elif current_task == "SEGMENTATION":
        background_tasks.add_task(run_async_task, start_segmentation_task, jobId, None)
        return TaskRerunResponse(message="Segmentation task restarted", jobId=jobId)
    elif current_task == "QUESTION_GENERATION":
        background_tasks.add_task(run_async_task, start_question_generation_task, jobId, None)
        return TaskRerunResponse(message="Question generation task restarted", jobId=jobId)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown task: {current_task}")


@router.get("/{jobId}/status", response_model=JobStatusResponse)
async def get_job_status(
    jobId: str,
    _: str = Depends(verify_webhook_secret)
):
    """Get current job status and task information"""
    # Get job state from database
    job_state = await db_service.get_job_state(jobId)
    if not job_state:
        raise HTTPException(status_code=404, detail="Job not found")
    
    current_task = job_state.get("current_task", "UNKNOWN")
    task_status = job_state.get("task_status", "UNKNOWN")
    
    # Convert task_status to TaskStatus enum if it's a valid value
    try:
        status_enum = TaskStatus(task_status)
    except ValueError:
        status_enum = TaskStatus.PENDING
    
    return JobStatusResponse(
        jobId=jobId,
        status=status_enum,
        currentTask=current_task
    )
