from fastapi import APIRouter, Depends
from typing import Dict, Any
from .models import JobCreateRequest, JobUpdateRequest, TaskApprovalRequest, JobResponse
from .auth import verify_webhook_secret, log_request

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/", response_model=JobResponse)
async def create_job(
    job_data: JobCreateRequest,
    _: str = Depends(verify_webhook_secret)
):
    """Accept job data and return a job ID"""
    request_body = job_data.dict()
    log_request("POST /jobs", request_body)
    
    return JobResponse(
        status="RECEIVED"
    )


@router.post("/{jobId}/update", response_model=JobResponse)
async def update_job(
    jobId: str,
    update_data: JobUpdateRequest,
    _: str = Depends(verify_webhook_secret)
):
    """Update job parameters"""
    request_body = update_data.dict()
    log_request("POST /jobs/{jobId}/update", request_body, jobId)
    
    return JobResponse(
        jobId=jobId,
        status="UPDATED",
        received=request_body
    )


@router.post("/{jobId}/tasks/approve/start", response_model=JobResponse)
async def approve_task_start(
    jobId: str,
    task_data: TaskApprovalRequest,
    _: str = Depends(verify_webhook_secret)
):
    """Approve task to start"""
    request_body = task_data.dict()
    log_request("POST /jobs/{jobId}/tasks/approve/start", request_body, jobId)
    
    return JobResponse(
        jobId=jobId,
        status="TASK_START_APPROVED",
        received=request_body
    )


@router.post("/{jobId}/tasks/approve/continue", response_model=JobResponse)
async def approve_task_continue(
    jobId: str,
    approval_data: TaskApprovalRequest,
    _: str = Depends(verify_webhook_secret)
):
    """Approve task completion and continue to next task"""
    request_body = approval_data.dict()
    log_request("POST /jobs/{jobId}/tasks/approve/continue", request_body, jobId)
    
    return JobResponse(
        jobId=jobId,
        status="TASK_CONTINUE_APPROVED",
        received=request_body
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
