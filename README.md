# AI Server

A FastAPI-based server that implements the AI server which comunicates with ViBe main server for gen AI tasks.

## Features

- Runs AI Pipeline and communicates with main backend using WebHooks
- Header-based authentication using webhook secrets
- Comprehensive logging of all requests
- CORS support for cross-origin requests
- Health check endpoints

## Endpoints

### Job Management
- `POST /jobs` - Create a new job
- `POST /jobs/{job_id}/update` - Update job parameters
- `POST /jobs/{job_id}/tasks/approve/start` - Approve task start
- `POST /jobs/{job_id}/tasks/approve/continue` - Approve task continuation
- `POST /jobs/{job_id}/abort` - Abort a job
- `POST /jobs/{job_id}/tasks/rerun` - Rerun a task

### Webhooks
- `POST /genAI/webhook` - Receive webhook callbacks

### Health Check
- `GET /` - Root endpoint with API documentation
- `GET /health` - Simple health check

## Authentication

All endpoints require authentication via headers:
- Job endpoints: `x-webhook-signature: test-secret`
- Webhook endpoint: `x-webhook-signature: test-secret`

## Installation

```bash
pip install -r requirements.txt
```

## Running the Server

```bash
# Development mode with auto-reload
python main.py

# Or using uvicorn directly
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The server will start on `http://localhost:8000`

## Testing

You can test the endpoints using curl:

```bash
# Create a job
curl -X POST "http://localhost:8000/jobs" \
  -H "Content-Type: application/json" \
  -H "x-webhook-signature: test-secret" \
  -d '{"webhookUrl": "http://example.com/webhook", "webhookSecret": "secret"}'

# Update a job
curl -X POST "http://localhost:8000/jobs/job_12345/update" \
  -H "Content-Type: application/json" \
  -H "x-webhook-signature: test-secret" \
  -d '{"parameters": {"key": "value"}}'

# Send webhook
curl -X POST "http://localhost:8000/genAI/webhook" \
  -H "Content-Type: application/json" \
  -H "x-webhook-signature: test-secret" \
  -d '{"task": "test", "status": "completed", "jobId": "job_12345", "data": {}}'
```
