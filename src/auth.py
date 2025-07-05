from fastapi import HTTPException, Header
from typing import Optional
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Hardcoded secret for testing
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "default-webhook-secret")


def verify_webhook_secret(x_webhook_secret: Optional[str] = Header(None)) -> str:
    """Verify the X-Webhook-Secret header"""
    if not x_webhook_secret:
        logger.warning("Missing X-Webhook-Secret header")
        raise HTTPException(status_code=401, detail="Missing X-Webhook-Secret header")
    
    if x_webhook_secret != WEBHOOK_SECRET:
        logger.warning(f"Invalid webhook secret: {x_webhook_secret}")
        raise HTTPException(status_code=401, detail="Invalid webhook secret")
    
    return x_webhook_secret


def verify_webhook_signature(x_webhook_signature: Optional[str] = Header(None)) -> str:
    """Verify the x-webhook-signature header for webhook callbacks"""
    if not x_webhook_signature:
        logger.warning("Missing x-webhook-signature header")
        raise HTTPException(status_code=401, detail="Missing x-webhook-signature header")
    
    # In a real implementation, this would involve HMAC verification
    if x_webhook_signature != WEBHOOK_SECRET:
        logger.warning(f"Invalid webhook signature: {x_webhook_signature}")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    
    return x_webhook_signature


def log_request(endpoint: str, request_body: dict, job_id: Optional[str] = None):
    """Log incoming requests"""
    if job_id:
        logger.info(f"[{endpoint}] Job ID: {job_id}, Request: {request_body}")
    else:
        logger.info(f"[{endpoint}] Request: {request_body}")
