from fastapi import APIRouter, Depends, Response
from typing import Dict, Any
from models import JobCreateRequest, JobUpdateRequest, JobResponse
from auth import verify_webhook_secret, log_request

router = APIRouter(prefix="/jobs", tags=["jobs"])

@router.post("/")
async def create_job(
    jobData: JobCreateRequest,
    _: str = Depends(verify_webhook_secret)
):
    """Accept job data and return a job ID"""
    log_request("POST /jobs", jobData.dict())
    
    if jobData.data.type == 'VIDEO':
        print("Processing video job with URL:", jobData.data.url)
    
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
    _: str = Depends(verify_webhook_secret)
):
    """Approve task to start"""
    requestBody = taskData.dict()
    log_request("POST /jobs/{jobId}/tasks/approve/start", requestBody, jobId)
    
    return JobResponse(
        jobId=jobId,
        status="TASK_START_APPROVED",
        received=requestBody
    )


@router.post("/{jobId}/tasks/approve/continue", response_model=JobResponse)
async def approve_task_continue(
    jobId: str,
    approvalData: JobUpdateRequest,
    _: str = Depends(verify_webhook_secret)
):
    """Approve task completion and continue to next task"""
    requestBody = approvalData.dict()
    log_request("POST /jobs/{jobId}/tasks/approve/continue", requestBody, jobId)
    
    return JobResponse(
        jobId=jobId,
        status="TASK_CONTINUE_APPROVED",
        received=requestBody
    )


@router.post("/{jobId}/abort", response_model=JobResponse)
async def abort_job(
    jobId: str,
    _: str = Depends(verify_webhook_secret)
):
    """Abort the job"""
    log_request("POST /jobs/{jobId}/abort", {}, jobId)
    
    return JobResponse(
        jobId=jobId,
        status="ABORTED"
    )


@router.post("/{jobId}/tasks/rerun", response_model=JobResponse)
async def rerun_task(
    jobId: str,
    _: str = Depends(verify_webhook_secret)
):
    """Rerun the current task"""
    log_request("POST /jobs/{jobId}/tasks/rerun", {}, jobId)
    
    return JobResponse(
        jobId=jobId,
        status="TASK_RERUN"
    )
