from typing import Dict, Any, Optional
from pydantic import BaseModel


class JobCreateRequest(BaseModel):
    webhookUrl: str
    webhookSecret: str
    # Add other job fields as needed
    data: Optional[Dict[str, Any]] = None


class JobUpdateRequest(BaseModel):
    # Task parameters for job updates
    parameters: Optional[Dict[str, Any]] = None
    data: Optional[Dict[str, Any]] = None


class TaskApprovalRequest(BaseModel):
    # Task parameters for approval
    taskId: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    data: Optional[Dict[str, Any]] = None


class WebhookRequest(BaseModel):
    task: str
    status: str
    jobId: str
    data: Dict[str, Any]


class JobResponse(BaseModel):
    job_id: str
    status: str
    received: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    error: str
    message: str
