import requests
from typing import Optional, Dict, Any

from models import (
    JobCreateRequest, 
    TaskStatus, 
    AudioData, 
    TranscriptGenerationData, 
    SegmentationData, 
    QuestionGenerationData,
    TranscriptParameters,
    SegmentationParameters,
    QuestionGenerationParameters,
    JobState,
    GenAIBody
)
from services.audio import AudioService
from services.transcription import TranscriptionService
from services.segmentation import SegmentationService
from services.question_generation import QuestionGenerationService
from services.storage import GCloudStorageService
from services.database import db_service

# Note: Removed the old JobState class and process_video_async function
# as they used in-memory job_states which is now replaced with MongoDB persistence

async def start_audio_extraction_task(job_id: str) -> Dict[str, Any]:
    """Start audio extraction task - READ-ONLY database access"""
    print(f"start_audio_extraction_task called for job {job_id}")
    
    # Get job state from database (READ-ONLY) - now returns Pydantic object
    job_state = await db_service.get_job_state(job_id)
    if not job_state:
        error_msg = f"Job {job_id} not found"
        print(error_msg)
        raise ValueError(error_msg)
    
    job_data = job_state.job_data
    print(f"Job data found for {job_id}: {job_data.url}")
    
    # Ensure webhookUrl has a protocol
    webhook_url = job_data.webhookUrl
    if not webhook_url.startswith("http://") and not webhook_url.startswith("https://"):
        webhook_url = "http://" + webhook_url

    print(f"Webhook URL: {webhook_url}")

    audio_service = AudioService()
    storage_service = GCloudStorageService()
    
    try:
        # Send webhook - Starting audio extraction
        audio_data = AudioData(status=TaskStatus.RUNNING)
        await send_webhook(webhook_url, job_id, job_data.webhookSecret, "AUDIO_EXTRACTION", audio_data)
        
        # Note: Job status updates are handled by the external system, not this read-only service
        
        # Extract audio from video
        print(f"Extracting audio from video: {job_data.url}")
        audio_file_path = await audio_service.extractAudio(str(job_data.url))
        print(f"Audio extracted successfully to: {audio_file_path}")
        
        # Upload audio file to Google Cloud Storage
        file_name = f"audio/{job_id}_audio.wav"
        file_url = await storage_service.upload_file(audio_file_path, file_name, "audio/wav")
        
        # Send webhook - Audio extraction completed
        audio_data = AudioData(
            status=TaskStatus.COMPLETED,
            fileName=file_name if file_url else None,
            fileUrl=file_url
        )
        
        # Note: Job status updates are handled by the external system, not this read-only service
        
        await send_webhook(webhook_url, job_id, job_data.webhookSecret, "AUDIO_EXTRACTION", audio_data)
        
        return {
            "status": "COMPLETED",
            "next_task": "TRANSCRIPT_GENERATION",
            "data": audio_data
        }
        
    except Exception as e:
        print(f"Error in audio extraction: {str(e)}")
        error_data = AudioData(status=TaskStatus.FAILED, error=str(e))
        await send_webhook(webhook_url, job_id, job_data.webhookSecret, "AUDIO_EXTRACTION", error_data)
        raise

async def start_transcript_generation_task(job_id: str, approval_data: TranscriptParameters) -> Dict[str, Any]:
    """Start transcript generation task - READ-ONLY database access"""
    print(f"start_transcript_generation_task called for job {job_id}")
    
    # Get job state from database (READ-ONLY)
    job_state = await db_service.get_job_state(job_id)
    if not job_state:
        error_msg = f"Job {job_id} not found"
        print(error_msg)
        raise ValueError(error_msg)
    
    job_data = job_state.job_data
    audio_file_path = job_state.audio_file_path
    
    if not audio_file_path:
        error_msg = f"No audio file found for job {job_id}"
        print(error_msg)
        raise ValueError(error_msg)
    
    # Ensure webhookUrl has a protocol
    webhook_url = job_data.webhookUrl
    if not webhook_url.startswith("http://") and not webhook_url.startswith("https://"):
        webhook_url = "http://" + webhook_url

    transcription_service = TranscriptionService()
    storage_service = GCloudStorageService()
    
    try:
        
        # Get original transcript parameters
        transcript_params = job_data.transcriptParameters
        
        # Merge with new parameters if provided
        if approval_data and transcript_params:
            # Create a new instance with updated parameters
            transcript_params = transcript_params.model_copy(
                update=approval_data.model_dump(exclude_unset=True)
            )
        elif approval_data:
            # If no original parameters, use the approval data
            transcript_params = approval_data
            
        print(f"Transcript parameters: {transcript_params}")
        
        # Send webhook - Starting transcription
        transcript_data = TranscriptGenerationData(status=TaskStatus.RUNNING)
        await send_webhook(webhook_url, job_id, job_data.webhookSecret, "TRANSCRIPT_GENERATION", transcript_data)
        
        # Note: Job status updates are handled by the external system, not this read-only service
        
        # Generate transcript from audio
        print("Generating transcript from audio...")
        transcript = await transcription_service.transcribe(audio_file_path, transcript_params)
        
        # Note: Job status updates are handled by the external system, not this read-only service
        
        # Upload transcript to Google Cloud Storage
        transcript_file_name = f"transcripts/{job_id}_transcript.txt"
        transcript_file_url = await storage_service.upload_text_content(transcript, transcript_file_name, "text/plain")
        
        # Send webhook - Transcription completed
        transcript_data = TranscriptGenerationData(
            status=TaskStatus.COMPLETED,
            fileName=transcript_file_name if transcript_file_url else None,
            fileUrl=transcript_file_url,
            newParameters=transcript_params
        )
        
        # Note: Job status updates are handled by the external system, not this read-only service
        
        await send_webhook(webhook_url, job_id, job_data.webhookSecret, "TRANSCRIPT_GENERATION", transcript_data)
        
        return {
            "status": "COMPLETED",
            "next_task": "SEGMENTATION",
            "data": transcript_data
        }
        
    except Exception as e:
        print(f"Error in transcription: {str(e)}")
        # Note: Job status updates are handled by the external system, not this read-only service
        
        error_data = TranscriptGenerationData(status=TaskStatus.FAILED, error=str(e))
        # Note: Job status updates are handled by the external system, not this read-only service
        
        await send_webhook(webhook_url, job_id, job_data.webhookSecret, "TRANSCRIPT_GENERATION", error_data)
        raise

async def start_segmentation_task(job_id: str, approval_data: Optional[SegmentationParameters] = None) -> Dict[str, Any]:
    """Start segmentation task - READ-ONLY database access"""
    print(f"start_segmentation_task called for job {job_id}")
    
    # Get job state from database (READ-ONLY)
    job_state = await db_service.get_job_state(job_id)
    if not job_state:
        error_msg = f"Job {job_id} not found"
        print(error_msg)
        raise ValueError(error_msg)
    
    job_data = job_state.job_data
    
    # Get transcript from the specified transcription run using usePrevious (default to 0 if not provided)
    transcript = None
    if approval_data and job_state.task_data:
        use_previous = approval_data.usePrevious if approval_data.usePrevious is not None else 0
        if (job_state.task_data.transcriptGeneration and 
            len(job_state.task_data.transcriptGeneration) > use_previous):
            transcription_run = job_state.task_data.transcriptGeneration[use_previous]
            if transcription_run.status == TaskStatus.COMPLETED and transcription_run.fileUrl:
                # Download the transcript file from GCloud bucket
                print(f"Downloading transcript from: {transcription_run.fileUrl}")
                try:
                    import requests
                    response = requests.get(transcription_run.fileUrl)
                    response.raise_for_status()
                    transcript = response.text
                    print(f"Successfully downloaded transcript: {len(transcript)} characters")
                except Exception as e:
                    error_msg = f"Failed to download transcript from {transcription_run.fileUrl}: {str(e)}"
                    print(error_msg)
                    raise ValueError(error_msg)
    
    if not transcript:
        error_msg = f"No transcript found for job {job_id}. Check usePrevious index and transcription task status."
        print(error_msg)
        raise ValueError(error_msg)
    
    # Ensure webhookUrl has a protocol
    webhook_url = job_data.webhookUrl
    if not webhook_url.startswith("http://") and not webhook_url.startswith("https://"):
        webhook_url = "http://" + webhook_url

    storage_service = GCloudStorageService()
    
    try:
        # Handle approval data for parameter updates
        segmentation_params = job_data.segmentationParameters
        
        if approval_data:
            # Create new parameters from approval data, excluding usePrevious
            approval_params_dict = approval_data.model_dump(exclude={'usePrevious'}, exclude_unset=True)
            
            if segmentation_params:
                # Update existing parameters
                segmentation_params = segmentation_params.model_copy(update=approval_params_dict)
            else:
                # Create new parameters from approval data
                segmentation_params = SegmentationParameters(**approval_params_dict)
        
        print(f"Segmentation parameters: {segmentation_params}")
        
        # Send webhook - Starting segmentation
        segmentation_data = SegmentationData(status=TaskStatus.RUNNING)
        await send_webhook(webhook_url, job_id, job_data.webhookSecret, "SEGMENTATION", segmentation_data)
        
        # Note: Job status updates are handled by the external system, not this read-only service
        
        # Segment the transcript
        print("Segmenting transcript...")
        segmentation_service = SegmentationService()
        segments = await segmentation_service.segment_transcript(transcript, segmentation_params)
        
        # Note: Job status updates are handled by the external system, not this read-only service
        
        # Upload segments to Google Cloud Storage
        segments_file_name = f"segments/{job_id}_segments.json"
        segments_file_url = await storage_service.upload_json_content(segments, segments_file_name)
        
        # Send webhook - Segmentation completed
        segmentation_data = SegmentationData(
            status=TaskStatus.COMPLETED,
            fileName=segments_file_name if segments_file_url else None,
            fileUrl=segments_file_url,
            newParameters=segmentation_params
        )
        
        # Note: Job status updates are handled by the external system, not this read-only service
        
        await send_webhook(webhook_url, job_id, job_data.webhookSecret, "SEGMENTATION", segmentation_data)
        
        return {
            "status": "COMPLETED",
            "next_task": "QUESTION_GENERATION",
            "data": segmentation_data
        }
        
    except Exception as e:
        print(f"Error in segmentation: {str(e)}")
        # Note: Job status updates are handled by the external system, not this read-only service
        
        error_data = SegmentationData(status=TaskStatus.FAILED, error=str(e))
        # Note: Job status updates are handled by the external system, not this read-only service
        
        await send_webhook(webhook_url, job_id, job_data.webhookSecret, "SEGMENTATION", error_data)
        raise

async def start_question_generation_task(job_id: str, approval_data: Optional[QuestionGenerationParameters] = None) -> Dict[str, Any]:
    """Start question generation task - READ-ONLY database access"""
    print(f"start_question_generation_task called for job {job_id}")
    
    # Get job state from database (READ-ONLY)
    job_state = await db_service.get_job_state(job_id)
    if not job_state:
        error_msg = f"Job {job_id} not found"
        print(error_msg)
        raise ValueError(error_msg)
    
    job_data = job_state.job_data
    
    # Get segments from the specified segmentation run using usePrevious (default to 0 if not provided)
    segments = None
    if approval_data and job_state.task_data:
        use_previous = approval_data.usePrevious if approval_data.usePrevious is not None else 0
        if (job_state.task_data.segmentation and 
            len(job_state.task_data.segmentation) > use_previous):
            segmentation_run = job_state.task_data.segmentation[use_previous]
            if segmentation_run.status == TaskStatus.COMPLETED and segmentation_run.fileUrl:
                # Download the segments file from GCloud bucket
                print(f"Downloading segments from: {segmentation_run.fileUrl}")
                storage_service = GCloudStorageService()
                try:
                    # Download and parse the segments JSON file
                    import json
                    import requests
                    response = requests.get(segmentation_run.fileUrl)
                    response.raise_for_status()
                    segments = json.loads(response.text)
                    print(f"Successfully downloaded segments: {len(segments) if isinstance(segments, list) else 'dict'}")
                except Exception as e:
                    error_msg = f"Failed to download segments from {segmentation_run.fileUrl}: {str(e)}"
                    print(error_msg)
                    raise ValueError(error_msg)
    
    if not segments:
        error_msg = f"No segments found for job {job_id}. Check usePrevious index and segmentation task status."
        print(error_msg)
        raise ValueError(error_msg)
    
    # Ensure webhookUrl has a protocol
    webhook_url = job_data.webhookUrl
    if not webhook_url.startswith("http://") and not webhook_url.startswith("https://"):
        webhook_url = "http://" + webhook_url
        
    storage_service = GCloudStorageService()
    
    try:
        # Handle approval data for parameter updates
        question_params = job_data.questionGenerationParameters
        
        if approval_data:
            # Create new parameters from approval data, excluding usePrevious
            approval_params_dict = approval_data.model_dump(exclude={'usePrevious'}, exclude_unset=True)
            
            if question_params:
                # Update existing parameters
                question_params = question_params.model_copy(update=approval_params_dict)
            else:
                # Create new parameters from approval data
                question_params = QuestionGenerationParameters(**approval_params_dict)
        
        print(f"Question generation parameters: {question_params}")
        
        # Send webhook - Starting question generation
        question_gen_data = QuestionGenerationData(status=TaskStatus.RUNNING)
        await send_webhook(webhook_url, job_id, job_data.webhookSecret, "QUESTION_GENERATION", question_gen_data)
        
        # Note: Job status updates are handled by the external system, not this read-only service
        
        # Convert segments to the format expected by question generation service
        # The service expects Dict[str, str] where key is segment ID and value is segment text
        segments_dict: Dict[str, str] = {}
        if isinstance(segments, list):
            for i, segment in enumerate(segments):
                if isinstance(segment, dict):
                    # Extract text from segment based on its structure
                    segment_text = ""
                    if "transcript_lines" in segment:
                        if isinstance(segment["transcript_lines"], list):
                            segment_text = " ".join(segment["transcript_lines"])
                    elif "text" in segment:
                        segment_text = str(segment["text"])
                    elif "content" in segment:
                        segment_text = str(segment["content"])
                    
                    segments_dict[f"segment_{i}"] = segment_text
        elif isinstance(segments, dict):
            # Ensure all values are strings
            segments_dict = {str(k): str(v) for k, v in segments.items()}
        
        # Generate questions from segments
        print("Generating questions...")
        question_service = QuestionGenerationService()
        questions = await question_service.generate_questions(
            segments=segments_dict,
            question_params=question_params
        )
        
        # Note: Job status updates are handled by the external system, not this read-only service
        
        # Upload questions to Google Cloud Storage
        questions_file_name = f"questions/{job_id}_questions.json"
        questions_file_url = await storage_service.upload_json_content(questions, questions_file_name)
        
        # Send webhook - Question generation completed
        if questions and len(questions) > 0:
            question_gen_data = QuestionGenerationData(
                status=TaskStatus.COMPLETED,
                fileName=questions_file_name if questions_file_url else None,
                fileUrl=questions_file_url,
                newParameters=question_params
            )
            
            # Note: Job status updates are handled by the external system, not this read-only service
            
            await send_webhook(webhook_url, job_id, job_data.webhookSecret, "QUESTION_GENERATION", question_gen_data)
            
            return {
                "status": "COMPLETED",
                "next_task": None,
                "data": question_gen_data
            }
        else:
            question_gen_data = QuestionGenerationData(
                status=TaskStatus.FAILED,
                error="No questions were generated"
            )
            # Note: Job status updates are handled by the external system, not this read-only service
            
            await send_webhook(webhook_url, job_id, job_data.webhookSecret, "QUESTION_GENERATION", question_gen_data)
            
            return {
                "status": "COMPLETED",
                "next_task": None,
                "data": question_gen_data
            }
        
    except Exception as e:
        print(f"Error in question generation: {str(e)}")
        # Note: Job status updates are handled by the external system, not this read-only service
        
        error_data = QuestionGenerationData(status=TaskStatus.FAILED, error=str(e))
        # Note: Job status updates are handled by the external system, not this read-only service
        
        await send_webhook(webhook_url, job_id, job_data.webhookSecret, "QUESTION_GENERATION", error_data)
        raise

async def send_webhook(webhook_url: str, job_id: str, webhook_secret: str, task: str, data):
    """Send webhook notification"""
    # Convert data to dict if it's a Pydantic model
    if hasattr(data, 'dict'):
        data_dict = data.dict()
    else:
        data_dict = data
    
    webhook_data = {
        "task": task,
        "status": data_dict.get("status", "UNKNOWN"),
        "jobId": job_id,
        "data": data_dict
    }
    
    headers = {
        "Content-Type": "application/json",
        "x-webhook-signature": webhook_secret
    }
    
    try:
        print(f"Sending webhook to {webhook_url} for task {task}")
        response = requests.post(webhook_url, json=webhook_data, headers=headers, timeout=10)
        print(f"Webhook response: {response.status_code}")
        response.raise_for_status()
    except Exception as e:
        print(f"Error sending webhook: {str(e)}")
        # Don't raise the error, just log it
