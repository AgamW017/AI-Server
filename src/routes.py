from fastapi import APIRouter, Depends, Response, BackgroundTasks
from ai import (
    ProcessVideo, 
    start_audio_extraction_task,
    start_transcript_generation_task,
    start_segmentation_task,
    start_question_generation_task,
    complete_job,
    job_states
)
from models import JobCreateRequest, JobUpdateRequest, JobResponse
from auth import verify_webhook_secret, log_request
import asyncio

router = APIRouter(prefix="/jobs", tags=["jobs"])

def run_async_task(async_func, *args, **kwargs):
    """Helper function to run async tasks in background"""
    asyncio.create_task(async_func(*args, **kwargs))

@router.post("/")
async def create_job(
    jobData: JobCreateRequest,
    background_tasks: BackgroundTasks,
    _: str = Depends(verify_webhook_secret)
):
    log_request("POST /jobs", jobData.dict())
    
    if jobData.data.type == 'VIDEO':
        background_tasks.add_task(ProcessVideo, jobData)
    
    return Response(content="CREATED", media_type="text/plain")


@router.post("/{jobId}/update", response_model=JobResponse)
async def update_job(
    jobId: str,
    updateData: JobUpdateRequest,
    _: str = Depends(verify_webhook_secret)
):
    """Update job parameters"""
    requestBody = updateData.dict()
    log_request("POST /jobs/{jobId}/update", requestBody, jobId)
    
    return JobResponse(
        jobId=jobId,
        status="UPDATED",
        received=requestBody
    )


@router.post("/{jobId}/tasks/approve/start", response_model=JobResponse)
async def approve_task_start(
    jobId: str,
    taskData: JobUpdateRequest,
    background_tasks: BackgroundTasks,
    _: str = Depends(verify_webhook_secret)
):
    """Approve task to start"""
    requestBody = taskData.dict()
    log_request("POST /jobs/{jobId}/tasks/approve/start", requestBody, jobId)
    
    if jobId not in job_states:
        return JobResponse(
            jobId=jobId,
            status="ERROR_JOB_NOT_FOUND"
        )
    
    job_state = job_states[jobId]
    current_task = job_state.get("current_task", "PENDING")
    
    # Determine which task to start based on current state
    if current_task == "PENDING":
        # Start audio extraction - no parameters needed for this task
        background_tasks.add_task(run_async_task, start_audio_extraction_task, jobId, requestBody)
        job_state["current_task"] = "AUDIO_EXTRACTION"
        return JobResponse(
            jobId=jobId,
            status="AUDIO_EXTRACTION_STARTED",
            received=requestBody
        )
    else:
        return JobResponse(
            jobId=jobId,
            status=f"ERROR_INVALID_STATE_{current_task}"
        )


@router.post("/{jobId}/tasks/approve/continue", response_model=JobResponse)
async def approve_task_continue(
    jobId: str,
    approvalData: JobUpdateRequest,
    background_tasks: BackgroundTasks,
    _: str = Depends(verify_webhook_secret)
):
    """Approve task completion and continue to next task"""
    requestBody = approvalData.dict()
    log_request("POST /jobs/{jobId}/tasks/approve/continue", requestBody, jobId)
    
    if jobId not in job_states:
        return JobResponse(
            jobId=jobId,
            status="ERROR_JOB_NOT_FOUND"
        )
    
    job_state = job_states[jobId]
    current_task = job_state.get("current_task")
    task_status = job_state.get("task_status")
    
    if task_status != "COMPLETED":
        return JobResponse(
            jobId=jobId,
            status=f"ERROR_TASK_NOT_COMPLETED_{current_task}"
        )
    
    # Determine next task and start it
    if current_task == "AUDIO_EXTRACTION":
        background_tasks.add_task(run_async_task, start_transcript_generation_task, jobId, requestBody)
        job_state["current_task"] = "TRANSCRIPT_GENERATION"
        return JobResponse(
            jobId=jobId,
            status="TRANSCRIPT_GENERATION_STARTED",
            received=requestBody
        )
    elif current_task == "TRANSCRIPT_GENERATION":
        background_tasks.add_task(run_async_task, start_segmentation_task, jobId, requestBody)
        job_state["current_task"] = "SEGMENTATION"
        return JobResponse(
            jobId=jobId,
            status="SEGMENTATION_STARTED",
            received=requestBody
        )
    elif current_task == "SEGMENTATION":
        background_tasks.add_task(run_async_task, start_question_generation_task, jobId, requestBody)
        job_state["current_task"] = "QUESTION_GENERATION"
        return JobResponse(
            jobId=jobId,
            status="QUESTION_GENERATION_STARTED",
            received=requestBody
        )
    elif current_task == "QUESTION_GENERATION":
        background_tasks.add_task(run_async_task, complete_job, jobId, requestBody)
        job_state["current_task"] = "UPLOAD_CONTENT"
        return JobResponse(
            jobId=jobId,
            status="UPLOAD_CONTENT_STARTED",
            received=requestBody
        )
    else:
        return JobResponse(
            jobId=jobId,
            status=f"ERROR_NO_NEXT_TASK_{current_task}"
        )


@router.post("/{jobId}/abort", response_model=JobResponse)
async def abort_job(
    jobId: str,
    _: str = Depends(verify_webhook_secret)
):
    """Abort the job"""
    log_request("POST /jobs/{jobId}/abort", {}, jobId)
    
    if jobId not in job_states:
        return JobResponse(
            jobId=jobId,
            status="ERROR_JOB_NOT_FOUND"
        )
    
    # Update job state to aborted
    job_state = job_states[jobId]
    job_state["task_status"] = "ABORTED"
    
    return JobResponse(
        jobId=jobId,
        status="ABORTED"
    )


@router.post("/{jobId}/tasks/rerun", response_model=JobResponse)
async def rerun_task(
    jobId: str,
    background_tasks: BackgroundTasks,
    _: str = Depends(verify_webhook_secret)
):
    """Rerun the current task"""
    log_request("POST /jobs/{jobId}/tasks/rerun", {}, jobId)
    
    if jobId not in job_states:
        return JobResponse(
            jobId=jobId,
            status="ERROR_JOB_NOT_FOUND"
        )
    
    job_state = job_states[jobId]
    current_task = job_state.get("current_task")
    
    # Reset task status and rerun current task
    job_state["task_status"] = "PENDING"
    
    if current_task == "AUDIO_EXTRACTION":
        background_tasks.add_task(run_async_task, start_audio_extraction_task, jobId, None)
        return JobResponse(
            jobId=jobId,
            status="AUDIO_EXTRACTION_RESTARTED"
        )
    elif current_task == "TRANSCRIPT_GENERATION":
        background_tasks.add_task(run_async_task, start_transcript_generation_task, jobId, None)
        return JobResponse(
            jobId=jobId,
            status="TRANSCRIPT_GENERATION_RESTARTED"
        )
    elif current_task == "SEGMENTATION":
        background_tasks.add_task(run_async_task, start_segmentation_task, jobId, None)
        return JobResponse(
            jobId=jobId,
            status="SEGMENTATION_RESTARTED"
        )
    elif current_task == "QUESTION_GENERATION":
        background_tasks.add_task(run_async_task, start_question_generation_task, jobId, None)
        return JobResponse(
            jobId=jobId,
            status="QUESTION_GENERATION_RESTARTED"
        )
    elif current_task == "UPLOAD_CONTENT":
        background_tasks.add_task(run_async_task, complete_job, jobId, None)
        return JobResponse(
            jobId=jobId,
            status="UPLOAD_CONTENT_RESTARTED"
        )
    else:
        return JobResponse(
            jobId=jobId,
            status=f"ERROR_UNKNOWN_TASK_{current_task}"
        )


@router.get("/{jobId}/status", response_model=JobResponse)
async def get_job_status(
    jobId: str,
    _: str = Depends(verify_webhook_secret)
):
    """Get current job status and task information"""
    if jobId not in job_states:
        return JobResponse(
            jobId=jobId,
            status="ERROR_JOB_NOT_FOUND"
        )
    
    job_state = job_states[jobId]
    return JobResponse(
        jobId=jobId,
        status=f"{job_state.get('current_task', 'UNKNOWN')}_{job_state.get('task_status', 'UNKNOWN')}",
        received={
            "current_task": job_state.get("current_task"),
            "task_status": job_state.get("task_status"),
            "has_audio": bool(job_state.get("audio_file_path")),
            "has_transcript": bool(job_state.get("transcript")),
            "has_segments": bool(job_state.get("segments")),
            "questions_count": len(job_state.get("questions", []))
        }
    )
