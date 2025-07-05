from fastapi import APIRouter, Depends, HTTPException, Response
from models import WebhookRequest
from auth import verify_webhook_signature, log_request

router = APIRouter(prefix="/genAI", tags=["genAI"])


@router.post("/webhook")
async def receive_webhook(
    webhook_data: WebhookRequest,
    _: str = Depends(verify_webhook_signature)
):
    """Receive webhook callbacks from the AI server"""
    request_body = webhook_data.dict()
    log_request("POST /genAI/webhook", request_body)
    
    # Validate required fields
    if not all([webhook_data.task, webhook_data.status, webhook_data.jobId]):
        raise HTTPException(status_code=400, detail="Missing required fields: task, status, or jobId")
    
    # Return 200 OK if signature is valid
    return {"message": "Webhook received successfully"}
