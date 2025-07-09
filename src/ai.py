import time
import requests
import asyncio
from typing import Optional, Dict, Any
import json

from models import (
    JobCreateRequest, 
    TaskStatus, 
    AudioData, 
    TranscriptGenerationData, 
    SegmentationData, 
    QuestionGenerationData,
    TranscriptParameters,
    SegmentationParameters,
    QuestionGenerationParameters
)
from services.audio import AudioService
from services.transcription import TranscriptionService
from services.segmentation import SegmentationService
from services.question_generation import QuestionGenerationService
from services.storage import GCloudStorageService
from services.database import db_service

# Note: Removed the old JobState class and process_video_async function
# as they used in-memory job_states which is now replaced with MongoDB persistence

async def start_audio_extraction_task(job_id: str, approval_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Start audio extraction task - READ-ONLY database access"""
    print(f"start_audio_extraction_task called for job {job_id}")
    
    # Get job state from database (READ-ONLY)
    job_state = await db_service.get_job_state(job_id)
    if not job_state:
        error_msg = f"Job {job_id} not found"
        print(error_msg)
        raise ValueError(error_msg)
    
    job_data = job_state["job_data"]
    print(f"Job data found for {job_id}: {job_data.get('url')}")
    
    # Ensure webhookUrl has a protocol
    webhook_url = job_data.get("webhookUrl")
    if not webhook_url.startswith("http://") and not webhook_url.startswith("https://"):
        webhook_url = "http://" + webhook_url

    print(f"Webhook URL: {webhook_url}")

    audio_service = AudioService()
    storage_service = GCloudStorageService()
    
    try:
        # Send webhook - Starting audio extraction
        audio_data = AudioData(status=TaskStatus.RUNNING)
        await send_webhook(webhook_url, job_id, job_data.get("webhookSecret"), "AUDIO_EXTRACTION", audio_data.dict())
        
        # Note: Job status updates are handled by the external system, not this read-only service
        
        # Extract audio from video
        print(f"Extracting audio from video: {job_data.get('url')}")
        audio_file_path = await audio_service.extractAudio(str(job_data.get('url')))
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
        
        await send_webhook(webhook_url, job_id, job_data.get("webhookSecret"), "AUDIO_EXTRACTION", audio_data.dict())
        
        return {
            "status": "COMPLETED",
            "next_task": "TRANSCRIPT_GENERATION",
            "data": audio_data.dict()
        }
        
    except Exception as e:
        print(f"Error in audio extraction: {str(e)}")
        error_data = AudioData(status=TaskStatus.FAILED, error=str(e))
        await send_webhook(webhook_url, job_id, job_data.get("webhookSecret"), "AUDIO_EXTRACTION", error_data.dict())
        raise

async def start_transcript_generation_task(job_id: str, approval_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Start transcript generation task - READ-ONLY database access"""
    print(f"start_transcript_generation_task called for job {job_id}")
    
    # Get job state from database (READ-ONLY)
    job_state = await db_service.get_job_state(job_id)
    if not job_state:
        error_msg = f"Job {job_id} not found"
        print(error_msg)
        raise ValueError(error_msg)
    
    job_data = job_state["job_data"]
    audio_file_path = job_state.get("audio_file_path")
    
    if not audio_file_path:
        error_msg = f"No audio file found for job {job_id}"
        print(error_msg)
        raise ValueError(error_msg)
    
    # Ensure webhookUrl has a protocol
    webhook_url = job_data.get("webhookUrl")
    if not webhook_url.startswith("http://") and not webhook_url.startswith("https://"):
        webhook_url = "http://" + webhook_url

    transcription_service = TranscriptionService()
    storage_service = GCloudStorageService()
    
    try:
        # Handle approval data for parameter updates
        new_params_dict = {}
        if approval_data and approval_data.get("parameters"):
            new_params_dict = approval_data["parameters"]
        
        # Get original transcript parameters
        transcript_params_dict = job_data.get("transcriptParameters", {})
        
        # Merge with new parameters if provided
        if new_params_dict:
            transcript_params_dict.update(new_params_dict)
        
        # Create transcript parameters object
        transcript_params = TranscriptParameters(**transcript_params_dict) if transcript_params_dict else None
        
        print(f"Transcript parameters: {transcript_params}")
        
        # Send webhook - Starting transcription
        transcript_data = TranscriptGenerationData(status=TaskStatus.RUNNING)
        await send_webhook(webhook_url, job_id, job_data.get("webhookSecret"), "TRANSCRIPT_GENERATION", transcript_data.dict())
        
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
        
        # Create response dict
        transcript_data_dict = transcript_data.dict()
        transcript_data_dict["transcript"] = transcript
        
        # Note: Job status updates are handled by the external system, not this read-only service
        
        await send_webhook(webhook_url, job_id, job_data.get("webhookSecret"), "TRANSCRIPT_GENERATION", transcript_data_dict)
        
        return {
            "status": "COMPLETED",
            "next_task": "SEGMENTATION",
            "data": transcript_data_dict
        }
        
    except Exception as e:
        print(f"Error in transcription: {str(e)}")
        # Note: Job status updates are handled by the external system, not this read-only service
        
        error_data = TranscriptGenerationData(status=TaskStatus.FAILED, error=str(e))
        # Note: Job status updates are handled by the external system, not this read-only service
        
        await send_webhook(webhook_url, job_id, job_data.get("webhookSecret"), "TRANSCRIPT_GENERATION", error_data.dict())
        raise

async def start_segmentation_task(job_id: str, approval_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Start segmentation task - READ-ONLY database access"""
    print(f"start_segmentation_task called for job {job_id}")
    
    # Get job state from database (READ-ONLY)
    job_state = await db_service.get_job_state(job_id)
    if not job_state:
        error_msg = f"Job {job_id} not found"
        print(error_msg)
        raise ValueError(error_msg)
    
    job_data = job_state["job_data"]
    transcript = job_state.get("transcript")
    
    if not transcript:
        error_msg = f"No transcript found for job {job_id}"
        print(error_msg)
        raise ValueError(error_msg)
    
    # Ensure webhookUrl has a protocol
    webhook_url = job_data.get("webhookUrl")
    if not webhook_url.startswith("http://") and not webhook_url.startswith("https://"):
        webhook_url = "http://" + webhook_url

    storage_service = GCloudStorageService()
    
    try:
        # Handle approval data for parameter updates
        new_params_dict = {}
        if approval_data and approval_data.get("parameters"):
            new_params_dict = approval_data["parameters"]
        
        # Get original segmentation parameters
        segmentation_params_dict = job_data.get("segmentationParameters", {})
        
        # Merge with new parameters if provided
        if new_params_dict:
            segmentation_params_dict.update(new_params_dict)
        
        # Create segmentation parameters object
        segmentation_params = SegmentationParameters(**segmentation_params_dict) if segmentation_params_dict else None
        
        print(f"Segmentation parameters: {segmentation_params}")
        
        # Send webhook - Starting segmentation
        segmentation_data = SegmentationData(status=TaskStatus.RUNNING)
        await send_webhook(webhook_url, job_id, job_data.get("webhookSecret"), "SEGMENTATION", segmentation_data.dict())
        
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
        
        # Create response dict
        segmentation_data_dict = segmentation_data.dict()
        segmentation_data_dict["segments"] = segments
        
        # Note: Job status updates are handled by the external system, not this read-only service
        
        await send_webhook(webhook_url, job_id, job_data.get("webhookSecret"), "SEGMENTATION", segmentation_data_dict)
        
        return {
            "status": "COMPLETED",
            "next_task": "QUESTION_GENERATION",
            "data": segmentation_data_dict
        }
        
    except Exception as e:
        print(f"Error in segmentation: {str(e)}")
        # Note: Job status updates are handled by the external system, not this read-only service
        
        error_data = SegmentationData(status=TaskStatus.FAILED, error=str(e))
        # Note: Job status updates are handled by the external system, not this read-only service
        
        await send_webhook(webhook_url, job_id, job_data.get("webhookSecret"), "SEGMENTATION", error_data.dict())
        raise

async def start_question_generation_task(job_id: str, approval_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Start question generation task - READ-ONLY database access"""
    print(f"start_question_generation_task called for job {job_id}")
    
    # Get job state from database (READ-ONLY)
    job_state = await db_service.get_job_state(job_id)
    if not job_state:
        error_msg = f"Job {job_id} not found"
        print(error_msg)
        raise ValueError(error_msg)
    
    job_data = job_state["job_data"]
    segments = job_state.get("segments")
    
    if not segments:
        error_msg = f"No segments found for job {job_id}"
        print(error_msg)
        raise ValueError(error_msg)
    
    # Ensure webhookUrl has a protocol
    webhook_url = job_data.get("webhookUrl")
    if not webhook_url.startswith("http://") and not webhook_url.startswith("https://"):
        webhook_url = "http://" + webhook_url
        
    storage_service = GCloudStorageService()
    
    try:
        # Handle approval data for parameter updates
        new_params_dict = {}
        if approval_data and approval_data.get("parameters"):
            new_params_dict = approval_data["parameters"]
        
        # Get original question generation parameters
        question_params_dict = job_data.get("questionGenerationParameters", {})
        
        # Merge with new parameters if provided
        if new_params_dict:
            question_params_dict.update(new_params_dict)
        
        # Create question generation parameters object
        question_params = QuestionGenerationParameters(**question_params_dict) if question_params_dict else None
        
        print(f"Question generation parameters: {question_params}")
        
        # Send webhook - Starting question generation
        question_gen_data = QuestionGenerationData(status=TaskStatus.RUNNING)
        await send_webhook(webhook_url, job_id, job_data.get("webhookSecret"), "QUESTION_GENERATION", question_gen_data.dict())
        
        # Note: Job status updates are handled by the external system, not this read-only service
        
        # Generate questions from segments
        print("Generating questions...")
        question_service = QuestionGenerationService()
        questions = await question_service.generate_questions(
            segments=segments,
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
            
            # Create response dict
            question_gen_data_dict = question_gen_data.dict()
            question_gen_data_dict["questions"] = questions
            
            # Note: Job status updates are handled by the external system, not this read-only service
            
            await send_webhook(webhook_url, job_id, job_data.get("webhookSecret"), "QUESTION_GENERATION", question_gen_data_dict)
        else:
            question_gen_data = QuestionGenerationData(
                status=TaskStatus.FAILED,
                error="No questions were generated"
            )
            # Note: Job status updates are handled by the external system, not this read-only service
            
            await send_webhook(webhook_url, job_id, job_data.get("webhookSecret"), "QUESTION_GENERATION", question_gen_data.dict())
        
        return {
            "status": "COMPLETED",
            "next_task": None,
            "data": question_gen_data.dict()
        }
        
    except Exception as e:
        print(f"Error in question generation: {str(e)}")
        # Note: Job status updates are handled by the external system, not this read-only service
        
        error_data = QuestionGenerationData(status=TaskStatus.FAILED, error=str(e))
        # Note: Job status updates are handled by the external system, not this read-only service
        
        await send_webhook(webhook_url, job_id, job_data.get("webhookSecret"), "QUESTION_GENERATION", error_data.dict())
        raise

async def send_webhook(webhook_url: str, job_id: str, webhook_secret: str, task: str, data: dict):
    """Send webhook notification"""
    webhook_data = {
        "task": task,
        "status": data.get("status", "UNKNOWN"),
        "jobId": job_id,
        "data": data
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
