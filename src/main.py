from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging

from routes import router

# Import webhook routes
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from webhook_routes import router as webhook_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="AI Server",
    description="FastAPI-based AI processing server with webhook integration",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(router)
app.include_router(webhook_router)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "AI Server is running",
        "status": "healthy",
        "endpoints": {
            "jobs": [
                "POST /jobs",
                "POST /jobs/{job_id}/update",
                "POST /jobs/{job_id}/tasks/approve/start",
                "POST /jobs/{job_id}/tasks/approve/continue",
                "POST /jobs/{job_id}/abort",
                "POST /jobs/{job_id}/tasks/rerun"
            ],
            "webhooks": [
                "POST /genAI/webhook"
            ]
        },
        "authentication": {
            "header": "X-Webhook-Secret or x-webhook-signature",
            "test_secret": "test-secret"
        }
    }


@app.get("/health")
async def health_check():
    """Simple health check"""
    return {"status": "healthy"}


if __name__ == "__main__":
    logger.info("Starting AI Server...")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )