import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import uvicorn
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from routes import router
from middleware.error_logging import ErrorLoggingMiddleware
import sentry_sdk

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    environment=os.getenv("ENVIRONMENT", "development"),
    send_default_pii=True,
)
# Create FastAPI app
app = FastAPI(
    title="AI Server",
    description="FastAPI-based AI processing server with webhook integration",
    version="1.0.0"
)

# Add custom validation error handler
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    print(f"Validation error on {request.method} {request.url}")
    print(f"Request body: {await request.body()}")
    print(f"Validation errors: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": str(await request.body())}
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
            "authentication": "X-Webhook-Secret header"
        }
    }


@app.get("/health")
async def health_check():
    """Simple health check"""
    return {"status": "healthy"}


@app.get("/sentry-debug")
async def sentry_debug():
    """Endpoint to trigger a test error for Sentry integration"""
    division_by_zero = 1 / 0  # This will raise ZeroDivisionError
    return {"message": "This should never be returned."}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=9017,
        reload=True,
        log_level="info"
    )
