import time
import requests

from models import JobCreateRequest

def ProcessVideo(jobData: JobCreateRequest):
    print("Processing video job with URL:", jobData.data.url)
    time.sleep(5)  # Set a timer for 5 seconds

    # Prepare payload and headers
    payload = {
        "jobId": jobData.jobId,
        "task" : "AUDIO_EXTRACTION",
        "status": "PENDING",
        
        
    }
    headers = {
        "Content-Type": "application/json",
        "x-webhook-signature": jobData.webhookSecret
    }

    # Send POST request to webhook server
    response = requests.post(jobData.webhookUrl, json=payload, headers=headers)
    print("Webhook response status:", response.status_code)
    print("Webhook response body:", response.text)
    print("Webhook URL:", jobData.webhookUrl)
