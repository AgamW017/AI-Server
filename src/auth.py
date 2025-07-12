from fastapi import HTTPException, Header
from typing import Optional
import os

# Hardcoded secret for testing
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "default-webhook-secret")


def verify_webhook_secret(x_webhook_secret: Optional[str] = Header(None)) -> str:
    """Verify the x-webhook-signature header"""
    if not x_webhook_secret:
        raise HTTPException(status_code=401, detail="Missing x-webhook-signature header")
    
    if x_webhook_secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")
    
    return x_webhook_secret


def verify_webhook_signature(x_webhook_signature: Optional[str] = Header(None)) -> str:
    """Verify the x-webhook-signature header for webhook callbacks"""
    if not x_webhook_signature:
        raise HTTPException(status_code=401, detail="Missing x-webhook-signature header")
    
    # In a real implementation, this would involve HMAC verification
    if x_webhook_signature != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    
    return x_webhook_signature
