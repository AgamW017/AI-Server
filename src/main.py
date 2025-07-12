from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from routes import router
from middleware.error_logging import ErrorLoggingMiddleware

# Create FastAPI app
app = FastAPI(
    title="AI Server",
    description="FastAPI-based AI processing server with webhook integration",
    version="1.0.0"
)

# Add error logging middleware (should be added first to catch all errors)
app.add_middleware(ErrorLoggingMiddleware)

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

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "AI Server is running",
        "status": "healthy",
        "endpoints": {
            "jobs": [
                "POST /jobs",
                "POST /jobs/{job_id}/tasks/approve/start",
                "POST /jobs/{job_id}/tasks/approve/continue", 
                "POST /jobs/{job_id}/abort",
                "POST /jobs/{job_id}/tasks/rerun",
                "GET /jobs/{job_id}/status"
            ]
        },
        "webhook_info": {
            "description": "AI Server sends webhooks to main server after each task completion",
            "main_server_endpoint": "Main server's /genAI/webhook endpoint",
            "authentication": "x-webhook-signature header"
        }
    }


@app.get("/health")
async def health_check():
    """Simple health check"""
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )