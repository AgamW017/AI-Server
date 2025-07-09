import logging
import traceback
import json
import os
from datetime import datetime
from typing import Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# Configure error logger
def setup_error_logger():
    """Setup error logger to write to error.log file"""
    logger = logging.getLogger("error_logger")
    logger.setLevel(logging.ERROR)
    
    # Create logs directory if it doesn't exist
    log_dir = os.path.join(os.getcwd(), "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    # Create file handler
    log_file = os.path.join(log_dir, "error.log")
    file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
    file_handler.setLevel(logging.ERROR)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    
    # Add handler to logger if not already added
    if not logger.handlers:
        logger.addHandler(file_handler)
    
    return logger

# Global error logger instance
error_logger = setup_error_logger()

class ErrorLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to automatically log all errors to error.log file"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            response = await call_next(request)
            
            # Log HTTP errors (4xx, 5xx status codes)
            if response.status_code >= 400:
                await self.log_http_error(request, response.status_code)
            
            return response
            
        except Exception as e:
            # Log unhandled exceptions
            await self.log_exception(request, e)
            
            # Return proper error response
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"}
            )
    
    async def log_http_error(self, request: Request, status_code: int):
        """Log HTTP errors (4xx, 5xx)"""
        try:
            
            # Create error log entry
            error_info = {
                "timestamp": datetime.now().isoformat(),
                "type": "HTTP_ERROR",
                "status_code": status_code,
                "method": request.method,
                "url": str(request.url),
                "user_agent": request.headers.get("user-agent", "Unknown"),
            }
            
            error_logger.error(json.dumps(error_info))
            
        except Exception as log_error:
            # Fallback logging if structured logging fails
            error_logger.error(f"HTTP Error {status_code} on {request.method} {request.url} - Logging error: {log_error}")
    
    async def log_exception(self, request: Request, exception: Exception):
        """Log unhandled exceptions"""
        try:
            
            # Create error log entry
            error_info = {
                "timestamp": datetime.now().isoformat(),
                "type": "EXCEPTION",
                "exception_type": type(exception).__name__,
                "exception_message": str(exception),
                "method": request.method,
                "url": str(request.url),
                "user_agent": request.headers.get("user-agent", "Unknown"),
                "traceback": traceback.format_exc()
            }
            
            error_logger.error(json.dumps(error_info))
            
        except Exception as log_error:
            # Fallback logging if structured logging fails
            error_logger.error(f"Exception {type(exception).__name__}: {exception} - Logging error: {log_error}")
    
