from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from models import JobCreateRequest, JobUpdateRequest, TaskApprovalRequest, JobResponse
from auth import verify_webhook_secret, log_request, generate_mock_job_id

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/", response_model=JobResponse)
async def create_job(
    job_data: JobCreateRequest,
    _: str = Depends(verify_webhook_secret)
):
    """Accept job data and return a mock job ID"""
    request_body = job_data.dict()
    log_request("POST /jobs", request_body)
    
    job_id = generate_mock_job_id()
    
    return JobResponse(
        job_id=job_id,
        status="RECEIVED"
    )


@router.post("/{job_id}/update", response_model=JobResponse)
async def update_job(
    job_id: str,
    update_data: JobUpdateRequest,
    _: str = Depends(verify_webhook_secret)
):
    """Update job parameters"""
    request_body = update_data.dict()
    log_request("POST /jobs/{job_id}/update", request_body, job_id)
    
    return JobResponse(
        job_id=job_id,
        status="UPDATED",
        received=request_body
    )


@router.post("/{job_id}/tasks/approve/start", response_model=JobResponse)
async def approve_task_start(
    job_id: str,
    task_data: TaskApprovalRequest,
    _: str = Depends(verify_webhook_secret)
):
    """Approve task to start"""
    request_body = task_data.dict()
    log_request("POST /jobs/{job_id}/tasks/approve/start", request_body, job_id)
    
    return JobResponse(
        job_id=job_id,
        status="TASK_START_APPROVED",
        received=request_body
    )


@router.post("/{job_id}/tasks/approve/continue", response_model=JobResponse)
async def approve_task_continue(
    job_id: str,
    approval_data: TaskApprovalRequest,
    _: str = Depends(verify_webhook_secret)
):
    """Approve task completion and continue to next task"""
    request_body = approval_data.dict()
    log_request("POST /jobs/{job_id}/tasks/approve/continue", request_body, job_id)
    
    return JobResponse(
        job_id=job_id,
        status="TASK_CONTINUE_APPROVED",
        received=request_body
    )


@router.post("/{job_id}/abort", response_model=JobResponse)
async def abort_job(
    job_id: str,
    _: str = Depends(verify_webhook_secret)
):
    """Abort the job"""
    log_request("POST /jobs/{job_id}/abort", {}, job_id)
    
    return JobResponse(
        job_id=job_id,
        status="ABORTED"
    )


@router.post("/{job_id}/tasks/rerun", response_model=JobResponse)
async def rerun_task(
    job_id: str,
    _: str = Depends(verify_webhook_secret)
):
    """Rerun the current task"""
    log_request("POST /jobs/{job_id}/tasks/rerun", {}, job_id)
    
    return JobResponse(
        job_id=job_id,
        status="TASK_RERUN"
    )
