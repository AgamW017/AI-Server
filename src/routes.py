from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from typing import Optional
import asyncio
import threading
from ai import (
    start_audio_extraction_task,
    start_transcript_generation_task,
    start_segmentation_task,
    start_question_generation_task
)
from models import (
    JobResponse,
    JobState,
    SegmentationParameters,
    TranscriptParameters,
    QuestionGenerationParameters
)
from auth import verify_webhook_secret

router = APIRouter(prefix="/jobs", tags=["jobs"])

def run_async_task_in_thread(async_func, *args, **kwargs):
    """Helper function to run async tasks in a new thread with its own event loop"""
    def run_in_thread():
        try:
            print(f"Starting background task: {async_func.__name__}")
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(async_func(*args, **kwargs))
                print(f"Background task completed successfully: {async_func.__name__}")
                return result
            finally:
                loop.close()
        except Exception as e:
            print(f"Error in background task {async_func.__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            raise
    
    # Run in a separate thread
    thread = threading.Thread(target=run_in_thread)
    thread.start()

def run_async_task(async_func, *args, **kwargs):
    """Helper function to run async tasks in background"""
    return run_async_task_in_thread(async_func, *args, **kwargs)

@router.post("/{jobId}/tasks/approve/start", response_model=JobResponse)
async def approve_task_start(
    jobId: str,
    background_tasks: BackgroundTasks,
    _: str = Depends(verify_webhook_secret),
    taskData: Optional[JobState] = None,
):
    print(f"Raw request received for job {jobId}")
    print(f"TaskData received: {taskData}")
    print(f"TaskData type: {type(taskData)}")
    
    if not taskData:
        raise HTTPException(status_code=400, detail="Task data is required for approval")
    
    """Approve any task to start - works for all tasks"""
    print(f"Approve task start called for job {jobId}")
    current_task = taskData.currentTask
    task_status = taskData.taskStatus
    print(f"Job {jobId} current_task: {current_task}, task_status: {task_status}, file: {taskData.file if hasattr(taskData, 'file') else None}, parameters: {taskData.parameters if hasattr(taskData, 'parameters') else None}")
    
    # Only start if task is waiting for approval (WAITING)
    if task_status != "WAITING":
        raise HTTPException(status_code=400, detail=f"Current task {current_task} is not waiting for approval (status: {task_status})")
    
    # Start the appropriate task based on current_task
    if current_task is None:
        # Start audio extraction task - needs job_data object with url
        print(f"Starting audio extraction task for job {jobId}")
        job_data_obj = type('JobData', (), {'url': taskData.url if hasattr(taskData, 'url') else None})()
        background_tasks.add_task(run_async_task, start_audio_extraction_task, jobId, job_data_obj.url)
        return JobResponse(message="Audio extraction task started")
    elif current_task == "AUDIO_EXTRACTION":
        # Start transcript generation task - needs file and parameters
        file_url = taskData.file if hasattr(taskData, 'file') else None
        print(f"Starting transcript generation task for job {jobId}")
        params = TranscriptParameters(**taskData.parameters) if hasattr(taskData, 'parameters') else None
        background_tasks.add_task(run_async_task, start_transcript_generation_task, jobId, file_url, params)
        return JobResponse(message="Transcript generation task started")
    elif current_task == "TRANSCRIPT_GENERATION":
        # Start segmentation task - needs parameters only
        file_url = taskData.file if hasattr(taskData, 'file') else None
        print(f"Starting segmentation task for job {jobId}")
        params = SegmentationParameters(**taskData.parameters) if hasattr(taskData, 'parameters') else None
        background_tasks.add_task(run_async_task, start_segmentation_task, jobId, file_url, params)
        return JobResponse(message="Segmentation task started")
    elif current_task == "SEGMENTATION":
        # Start question generation task - needs parameters only
        print(f"Starting question generation task for job {jobId}")
        params = QuestionGenerationParameters(**taskData.parameters) if hasattr(taskData, 'parameters') else None
        background_tasks.add_task(run_async_task, start_question_generation_task, jobId, taskData.segmentMap, params)
        return JobResponse(message="Question generation task started")
    elif current_task == "QUESTION_GENERATION":
        # Question generation is the final task - no more tasks after this
        raise HTTPException(status_code=400, detail="Question generation is the final task. No more tasks available.")
    else:
        raise HTTPException(status_code=400, detail=f"Unknown task: {current_task}")


@router.post("/{jobId}/tasks/rerun", response_model=JobResponse)
async def rerun_task(
    jobId: str,
    background_tasks: BackgroundTasks,
    taskData: JobState,
    _: str = Depends(verify_webhook_secret)
):
    """Rerun the current task"""
    current_task = taskData.currentTask
    task_status = taskData.taskStatus
    print('file:', taskData.file if hasattr(taskData, 'file') else None)
    print('parameters:', taskData.parameters if hasattr(taskData, 'parameters') else None)
    if task_status not in ["COMPLETED", "FAILED"]:
        raise HTTPException(status_code=400, detail=f"Current task {current_task} is not completed (status: {task_status})")
    
    if current_task == "AUDIO_EXTRACTION":
        job_data_obj = type('JobData', (), {'url': taskData.url if hasattr(taskData, 'url') else None})()
        background_tasks.add_task(run_async_task, start_audio_extraction_task, jobId, job_data_obj.url)
        return JobResponse(message="Audio extraction task restarted", jobId=jobId)
    elif current_task == "TRANSCRIPT_GENERATION":
        file_url = taskData.file if hasattr(taskData, 'file') else None
        params = TranscriptParameters(**taskData.parameters) if hasattr(taskData, 'parameters') else None
        print(params)
        background_tasks.add_task(run_async_task, start_transcript_generation_task, jobId, file_url, params)
        return JobResponse(message="Transcript generation task restarted", jobId=jobId)
    elif current_task == "SEGMENTATION":
        file_url = taskData.file if hasattr(taskData, 'file') else None
        params = SegmentationParameters(**taskData.parameters) if hasattr(taskData, 'parameters') else None
        background_tasks.add_task(run_async_task, start_segmentation_task, jobId, file_url, params)
        return JobResponse(message="Segmentation task restarted", jobId=jobId)
    elif current_task == "QUESTION_GENERATION":
        params = QuestionGenerationParameters(**taskData.parameters) if hasattr(taskData, 'parameters') else None
        background_tasks.add_task(run_async_task, start_question_generation_task, jobId, taskData.segmentMap, params)
        return JobResponse(message="Question generation task restarted", jobId=jobId)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown task: {current_task}")
