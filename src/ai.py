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
    ContentUploadData,
    TranscriptParameters,
    SegmentationParameters,
    QuestionGenerationParameters
)
from services.ai_content import AIContentService
from services.audio import AudioService
from services.transcription import TranscriptionService
from services.storage import GCloudStorageService

# In-memory job state storage (in production, use Redis or database)
job_states: Dict[str, Dict[str, Any]] = {}

class JobState:
    def __init__(self, job_id: str, job_data: JobCreateRequest):
        self.job_id = job_id
        self.job_data = job_data
        self.current_task = "AUDIO_EXTRACTION"
        self.task_status = "PENDING"
        self.results = {}
        self.audio_file_path = None
        self.transcript = None
        self.segments = None
        self.questions = None
        
    def to_dict(self):
        return {
            "job_id": self.job_id,
            "current_task": self.current_task,
            "task_status": self.task_status,
            "results": self.results,
            "audio_file_path": self.audio_file_path,
            "transcript": self.transcript,
            "segments": self.segments,
            "questions": len(self.questions) if self.questions else 0
        }

async def process_video_async(jobData: JobCreateRequest):
    print("Processing video job with URL:", jobData.data.url)
    
    # Ensure webhookUrl has a protocol
    webhook_url = jobData.webhookUrl
    if not webhook_url.startswith("http://") and not webhook_url.startswith("https://"):
        webhook_url = "http://" + webhook_url
    
    # Initialize services
    audio_service = AudioService()
    transcription_service = TranscriptionService()
    ai_service = AIContentService()
    
    # Initialize job state
    job_id = jobData.jobId
    job_states[job_id] = {
        "job_data": jobData,
        "current_task": "AUDIO_EXTRACTION",
        "task_status": "PENDING",
        "results": {}
    }
    
    try:
        # Step 1: Audio Extraction
        try:
            # Send webhook - Starting audio extraction
            audio_data = AudioData(status=TaskStatus.STARTED)
            await send_webhook(webhook_url, jobData.jobId, jobData.webhookSecret, "AUDIO_EXTRACTION", audio_data.dict())
            
            # Update job state
            job_states[job_id]["current_task"] = "AUDIO_EXTRACTION"
            job_states[job_id]["task_status"] = "RUNNING"
            
            # Extract audio from video
            print(f"Extracting audio from video: {jobData.data.url}")
            audio_file_path = await audio_service.extractAudio(str(jobData.data.url))
            print(f"Audio extracted successfully to: {audio_file_path}")
            
            # Update job state with results
            job_states[job_id]["audio_file_path"] = audio_file_path
            job_states[job_id]["task_status"] = "COMPLETED"
            
            # Send webhook - Audio extraction completed
            audio_data = AudioData(
                status=TaskStatus.COMPLETED,
                fileName=audio_file_path.split('/')[-1] if audio_file_path else None,
                fileUrl=audio_file_path  # In production, this would be a public URL
            )
            await send_webhook(webhook_url, jobData.jobId, jobData.webhookSecret, "AUDIO_EXTRACTION", audio_data.dict())
            
        except Exception as e:
            print(f"Error in audio extraction: {str(e)}")
            job_states[job_id]["task_status"] = "FAILED"
            error_data = AudioData(status=TaskStatus.FAILED)
            error_data_dict = error_data.dict()
            error_data_dict["error"] = str(e)
            await send_webhook(webhook_url, jobData.jobId, jobData.webhookSecret, "AUDIO_EXTRACTION", error_data_dict)
            raise

        # Step 2: Transcription
        try:
            # Send webhook - Starting transcription
            transcript_data = TranscriptGenerationData(status=TaskStatus.STARTED)
            await send_webhook(webhook_url, jobData.jobId, jobData.webhookSecret, "TRANSCRIPT_GENERATION", transcript_data.dict())
            
            # Update job state
            job_states[job_id]["current_task"] = "TRANSCRIPT_GENERATION"
            job_states[job_id]["task_status"] = "RUNNING"
            
            # Generate transcript from audio
            print("Generating transcript from audio...")
            transcript = await transcription_service.transcribe(audio_file_path, jobData.data.transcriptParameters)
            
            # Update job state with results
            job_states[job_id]["transcript"] = transcript
            job_states[job_id]["task_status"] = "COMPLETED"
            
            # Send webhook - Transcription completed
            transcript_data = TranscriptGenerationData(
                status=TaskStatus.COMPLETED,
                newParameters=jobData.data.transcriptParameters
            )
            await send_webhook(webhook_url, jobData.jobId, jobData.webhookSecret, "TRANSCRIPT_GENERATION", transcript_data.dict())
            
        except Exception as e:
            print(f"Error in transcription: {str(e)}")
            job_states[job_id]["task_status"] = "FAILED"
            error_data = TranscriptGenerationData(status=TaskStatus.FAILED)
            error_data_dict = error_data.dict()
            error_data_dict["error"] = str(e)
            await send_webhook(webhook_url, jobData.jobId, jobData.webhookSecret, "TRANSCRIPT_GENERATION", error_data_dict)
            raise

        # Step 3: Segmentation
        try:
            # Send webhook - Starting segmentation
            segmentation_data = SegmentationData(status=TaskStatus.STARTED)
            await send_webhook(webhook_url, jobData.jobId, jobData.webhookSecret, "SEGMENTATION", segmentation_data.dict())
            
            # Update job state
            job_states[job_id]["current_task"] = "SEGMENTATION"
            job_states[job_id]["task_status"] = "RUNNING"
            
            # Segment the transcript
            print("Segmenting transcript...")
            segments = await ai_service.segment_transcript(transcript, jobData.data.segmentationParameters)
            
            # Update job state with results
            job_states[job_id]["segments"] = segments
            job_states[job_id]["task_status"] = "COMPLETED"
            
            # Send webhook - Segmentation completed
            segmentation_data = SegmentationData(
                status=TaskStatus.COMPLETED,
                newParameters=jobData.data.segmentationParameters
            )
            await send_webhook(webhook_url, jobData.jobId, jobData.webhookSecret, "SEGMENTATION", segmentation_data.dict())
            
        except Exception as e:
            print(f"Error in segmentation: {str(e)}")
            job_states[job_id]["task_status"] = "FAILED"
            error_data = SegmentationData(status=TaskStatus.FAILED)
            error_data_dict = error_data.dict()
            error_data_dict["error"] = str(e)
            await send_webhook(webhook_url, jobData.jobId, jobData.webhookSecret, "SEGMENTATION", error_data_dict)
            raise

        # Step 4: Question Generation
        try:
            # Send webhook - Starting question generation
            question_gen_data = QuestionGenerationData(status=TaskStatus.STARTED)
            await send_webhook(webhook_url, jobData.jobId, jobData.webhookSecret, "QUESTION_GENERATION", question_gen_data.dict())
            
            # Update job state
            job_states[job_id]["current_task"] = "QUESTION_GENERATION"
            job_states[job_id]["task_status"] = "RUNNING"
            
            # Generate questions from segments
            print("Generating questions...")
            questions = await ai_service.generate_questions(
                segments=segments,
                question_params=jobData.data.questionGenerationParameters
            )
            
            # Update job state with results
            job_states[job_id]["questions"] = questions
            job_states[job_id]["task_status"] = "COMPLETED"
            
            # Send webhook - Question generation completed (single webhook with all questions)
            if questions and len(questions) > 0:
                question_gen_data = QuestionGenerationData(
                    status=TaskStatus.COMPLETED,
                    newParameters=jobData.data.questionGenerationParameters
                )
                await send_webhook(webhook_url, jobData.jobId, jobData.webhookSecret, "QUESTION_GENERATION", question_gen_data.dict())
            else:
                question_gen_data = QuestionGenerationData(
                    status=TaskStatus.FAILED,
                    error="No questions were generated"
                )
                await send_webhook(webhook_url, jobData.jobId, jobData.webhookSecret, "QUESTION_GENERATION", question_gen_data.dict())
            
        except Exception as e:
            print(f"Error in question generation: {str(e)}")
            job_states[job_id]["task_status"] = "FAILED"
            error_data = QuestionGenerationData(status=TaskStatus.FAILED)
            error_data_dict = error_data.dict()
            error_data_dict["error"] = str(e)
            await send_webhook(webhook_url, jobData.jobId, jobData.webhookSecret, "QUESTION_GENERATION", error_data_dict)
            raise

        # Step 5: Content Upload (Final completion)
        upload_data = ContentUploadData(status=TaskStatus.COMPLETED)
        final_data = upload_data.dict()
        final_data.update({
            "transcript": transcript,
            "segments": segments,
            "questions": [question.dict() for question in questions],
            "total_questions": len(questions)
        })
        
        await send_webhook(webhook_url, jobData.jobId, jobData.webhookSecret, "UPLOAD_CONTENT", final_data)
        
        # Update job state
        job_states[job_id]["task_status"] = "COMPLETED"
        
        print("Processing completed successfully!")
        
    except Exception as e:
        # This catch is for any unexpected errors not caught by step-specific handlers
        print(f"Unexpected error in video processing: {str(e)}")
        # Note: Step-specific errors are already handled by their respective try-catch blocks
        # which send appropriate webhook notifications with the correct task names

async def start_audio_extraction_task(job_id: str, approval_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Start audio extraction task"""
    if job_id not in job_states:
        raise ValueError(f"Job {job_id} not found")
    
    job_state = job_states[job_id]
    jobData = job_state["job_data"]
    
    # Ensure webhookUrl has a protocol
    webhook_url = jobData.webhookUrl
    if not webhook_url.startswith("http://") and not webhook_url.startswith("https://"):
        webhook_url = "http://" + webhook_url

    audio_service = AudioService()
    storage_service = GCloudStorageService()
    
    try:
        # Send webhook - Starting audio extraction
        audio_data = AudioData(status=TaskStatus.STARTED)
        await send_webhook(webhook_url, jobData.jobId, jobData.webhookSecret, "AUDIO_EXTRACTION", audio_data.dict())
        
        # Update job state
        job_state["current_task"] = "AUDIO_EXTRACTION"
        job_state["task_status"] = "RUNNING"
        
        # Extract audio from video
        print(f"Extracting audio from video: {jobData.data.url}")
        audio_file_path = await audio_service.extractAudio(str(jobData.data.url))
        print(f"Audio extracted successfully to: {audio_file_path}")
        
        # Upload audio file to Google Cloud Storage
        file_name = f"audio/{job_id}_audio.wav"
        file_url = await storage_service.upload_file(audio_file_path, file_name, "audio/wav")
        
        # Update job state with results
        job_state["audio_file_path"] = audio_file_path
        job_state["task_status"] = "COMPLETED"
        
        # Send webhook - Audio extraction completed
        audio_data = AudioData(
            status=TaskStatus.COMPLETED,
            fileName=file_name if file_url else None,
            fileUrl=file_url
        )
        await send_webhook(webhook_url, jobData.jobId, jobData.webhookSecret, "AUDIO_EXTRACTION", audio_data.dict())
        
        return {
            "status": "COMPLETED",
            "next_task": "TRANSCRIPT_GENERATION",
            "data": audio_data.dict()
        }
        
    except Exception as e:
        print(f"Error in audio extraction: {str(e)}")
        job_state["task_status"] = "FAILED"
        error_data = AudioData(status=TaskStatus.FAILED, error=str(e))
        await send_webhook(webhook_url, jobData.jobId, jobData.webhookSecret, "AUDIO_EXTRACTION", error_data.dict())
        raise

async def start_transcript_generation_task(job_id: str, approval_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Start transcript generation task"""
    if job_id not in job_states:
        raise ValueError(f"Job {job_id} not found")
    
    job_state = job_states[job_id]
    jobData = job_state["job_data"]
    audio_file_path = job_state["audio_file_path"]
    
    if not audio_file_path:
        raise ValueError("Audio file path not found. Run audio extraction first.")
    
    # Use new parameters if provided in approval data, otherwise use original
    transcript_params = jobData.data.transcriptParameters
    new_params_provided = False
    
    if approval_data and ('language' in approval_data or 'model' in approval_data):
        # Create new TranscriptParameters from the approval body
        new_params_dict = {}
        if 'language' in approval_data:
            new_params_dict['language'] = approval_data['language']
        if 'model' in approval_data:
            new_params_dict['model'] = approval_data['model']
        
        transcript_params = TranscriptParameters(**new_params_dict)
        new_params_provided = True
    
    # Ensure webhookUrl has a protocol
    webhook_url = jobData.webhookUrl
    if not webhook_url.startswith("http://") and not webhook_url.startswith("https://"):
        webhook_url = "http://" + webhook_url

    transcription_service = TranscriptionService()
    storage_service = GCloudStorageService()
    
    try:
        # Send webhook - Starting transcription
        transcript_data = TranscriptGenerationData(status=TaskStatus.STARTED)
        await send_webhook(webhook_url, jobData.jobId, jobData.webhookSecret, "TRANSCRIPT_GENERATION", transcript_data.dict())
        
        # Update job state
        job_state["current_task"] = "TRANSCRIPT_GENERATION"
        job_state["task_status"] = "RUNNING"
        
        # Generate transcript from audio
        print("Generating transcript from audio...")
        transcript = await transcription_service.transcribe(audio_file_path, transcript_params)
        
        # Upload transcript to Google Cloud Storage
        file_name = f"transcripts/{job_id}_transcript.txt"
        file_url = await storage_service.upload_text_content(transcript, file_name, "text/plain")
        
        # Update job state with results
        job_state["transcript"] = transcript
        job_state["task_status"] = "COMPLETED"
        
        # Send webhook - Transcription completed
        transcript_data = TranscriptGenerationData(
            status=TaskStatus.COMPLETED,
            fileName=file_name if file_url else None,
            fileUrl=file_url
        )
        
        # Only include newParameters if they were provided in approval
        if new_params_provided:
            transcript_data.newParameters = transcript_params
            
        await send_webhook(webhook_url, jobData.jobId, jobData.webhookSecret, "TRANSCRIPT_GENERATION", transcript_data.dict())
        
        return {
            "status": "COMPLETED",
            "next_task": "SEGMENTATION",
            "data": transcript_data.dict()
        }
        
    except Exception as e:
        print(f"Error in transcription: {str(e)}")
        job_state["task_status"] = "FAILED"
        error_data = TranscriptGenerationData(status=TaskStatus.FAILED, error=str(e))
        await send_webhook(webhook_url, jobData.jobId, jobData.webhookSecret, "TRANSCRIPT_GENERATION", error_data.dict())
        raise

async def start_segmentation_task(job_id: str, approval_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Start segmentation task"""
    if job_id not in job_states:
        raise ValueError(f"Job {job_id} not found")
    
    job_state = job_states[job_id]
    jobData = job_state["job_data"]
    transcript = job_state["transcript"]
    
    if not transcript:
        raise ValueError("Transcript not found. Run transcript generation first.")
    
    # Use new parameters if provided in approval data, otherwise use original
    segmentation_params = jobData.data.segmentationParameters
    new_params_provided = False
    
    if approval_data and ('lambda' in approval_data or 'epochs' in approval_data):
        # Create new SegmentationParameters from the approval body
        new_params_dict = {}
        if 'lambda' in approval_data:
            new_params_dict['lambda'] = approval_data['lambda']
        if 'epochs' in approval_data:
            new_params_dict['epochs'] = approval_data['epochs']
        
        segmentation_params = SegmentationParameters(**new_params_dict)
        new_params_provided = True
    
    # Ensure webhookUrl has a protocol
    webhook_url = jobData.webhookUrl
    if not webhook_url.startswith("http://") and not webhook_url.startswith("https://"):
        webhook_url = "http://" + webhook_url

    ai_service = AIContentService()
    storage_service = GCloudStorageService()
    
    try:
        # Send webhook - Starting segmentation
        segmentation_data = SegmentationData(status=TaskStatus.STARTED)
        await send_webhook(webhook_url, jobData.jobId, jobData.webhookSecret, "SEGMENTATION", segmentation_data.dict())
        
        # Update job state
        job_state["current_task"] = "SEGMENTATION"
        job_state["task_status"] = "RUNNING"
        
        # Segment transcript
        print("Segmenting transcript...")
        segments = await ai_service.segment_transcript(transcript, segmentation_params)
        
        # Upload segments to Google Cloud Storage
        file_name = f"segments/{job_id}_segments.json"
        file_url = await storage_service.upload_json_content(segments, file_name)
        
        # Update job state with results
        job_state["segments"] = segments
        job_state["task_status"] = "COMPLETED"
        
        # Send webhook - Segmentation completed
        segmentation_data = SegmentationData(
            status=TaskStatus.COMPLETED,
            fileName=file_name if file_url else None,
            fileUrl=file_url
        )
        
        # Only include newParameters if they were provided in approval
        if new_params_provided:
            segmentation_data.newParameters = segmentation_params
            
        await send_webhook(webhook_url, jobData.jobId, jobData.webhookSecret, "SEGMENTATION", segmentation_data.dict())
        
        return {
            "status": "COMPLETED",
            "next_task": "QUESTION_GENERATION",
            "data": segmentation_data.dict(),
            "segments_count": len(segments)
        }
        
    except Exception as e:
        print(f"Error in segmentation: {str(e)}")
        job_state["task_status"] = "FAILED"
        error_data = SegmentationData(status=TaskStatus.FAILED, error=str(e))
        await send_webhook(webhook_url, jobData.jobId, jobData.webhookSecret, "SEGMENTATION", error_data.dict())
        raise

async def start_question_generation_task(job_id: str, approval_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Start question generation task"""
    if job_id not in job_states:
        raise ValueError(f"Job {job_id} not found")
    
    job_state = job_states[job_id]
    jobData = job_state["job_data"]
    segments = job_state["segments"]
    
    if not segments:
        raise ValueError("Segments not found. Run segmentation first.")
    
    # Use new parameters if provided in approval data, otherwise use original
    question_params = jobData.data.questionGenerationParameters
    new_params_provided = False
    
    if approval_data and ('prompt' in approval_data or 'model' in approval_data):
        # Create new QuestionGenerationParameters from the approval body
        new_params_dict = {}
        if 'prompt' in approval_data:
            new_params_dict['prompt'] = approval_data['prompt']
        if 'model' in approval_data:
            new_params_dict['model'] = approval_data['model']
        
        question_params = QuestionGenerationParameters(**new_params_dict)
        new_params_provided = True
    
    # Ensure webhookUrl has a protocol
    webhook_url = jobData.webhookUrl
    if not webhook_url.startswith("http://") and not webhook_url.startswith("https://"):
        webhook_url = "http://" + webhook_url

    ai_service = AIContentService()
    storage_service = GCloudStorageService()
    
    try:
        # Send webhook - Starting question generation
        question_gen_data = QuestionGenerationData(status=TaskStatus.STARTED)
        await send_webhook(webhook_url, jobData.jobId, jobData.webhookSecret, "QUESTION_GENERATION", question_gen_data.dict())
        
        # Update job state
        job_state["current_task"] = "QUESTION_GENERATION"
        job_state["task_status"] = "RUNNING"
        
        # Generate questions
        print("Generating questions...")
        questions = await ai_service.generate_questions(segments, question_params)
        
        # Upload questions to Google Cloud Storage
        questions_data = [question.dict() for question in questions] if questions else []
        file_name = f"questions/{job_id}_questions.json"
        file_url = await storage_service.upload_json_content(questions_data, file_name)
        
        # Update job state with results
        job_state["questions"] = questions
        job_state["task_status"] = "COMPLETED"
        
        # Send webhook - Question generation completed
        if questions and len(questions) > 0:
            # Send webhook with question data and file information
            question_gen_data = QuestionGenerationData(
                status=TaskStatus.COMPLETED,
                fileName=file_name if file_url else None,
                fileUrl=file_url
            )
            
            # Only include newParameters if they were provided in approval
            if new_params_provided:
                question_gen_data.newParameters = question_params
                
            await send_webhook(webhook_url, jobData.jobId, jobData.webhookSecret, "QUESTION_GENERATION", question_gen_data.dict())
        else:
            question_gen_data = QuestionGenerationData(
                status=TaskStatus.FAILED,
                error="No questions were generated"
            )
            await send_webhook(webhook_url, jobData.jobId, jobData.webhookSecret, "QUESTION_GENERATION", question_gen_data.dict())
            
        return {
            "status": "COMPLETED",
            "next_task": "UPLOAD_CONTENT",
            "data": question_gen_data.dict(),
            "questions_count": len(questions) if questions else 0
        }
        
    except Exception as e:
        print(f"Error in question generation: {str(e)}")
        job_state["task_status"] = "FAILED"
        error_data = QuestionGenerationData(status=TaskStatus.FAILED, error=str(e))
        await send_webhook(webhook_url, jobData.jobId, jobData.webhookSecret, "QUESTION_GENERATION", error_data.dict())
        raise

async def complete_job(job_id: str, approval_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Complete the job - only send webhook, no processing or uploads"""
    if job_id not in job_states:
        raise ValueError(f"Job {job_id} not found")
    
    job_state = job_states[job_id]
    jobData = job_state["job_data"]
    
    # Ensure webhookUrl has a protocol
    webhook_url = jobData.webhookUrl
    if not webhook_url.startswith("http://") and not webhook_url.startswith("https://"):
        webhook_url = "http://" + webhook_url
    
    try:
        # Update job state
        job_state["current_task"] = "UPLOAD_CONTENT"
        job_state["task_status"] = "RUNNING"
        
        # UPLOAD_CONTENT task only sends webhook - no processing or file uploads
        upload_data = ContentUploadData(status=TaskStatus.COMPLETED)
        
        await send_webhook(webhook_url, jobData.jobId, jobData.webhookSecret, "UPLOAD_CONTENT", upload_data.dict())
        
        # Update job state
        job_state["task_status"] = "COMPLETED"
        
        print("Job completed - webhook sent!")
        
        return {
            "status": "COMPLETED",
            "data": upload_data.dict()
        }
        
    except Exception as e:
        print(f"Error in content upload: {str(e)}")
        job_state["task_status"] = "FAILED"
        error_data = ContentUploadData(status=TaskStatus.FAILED, error=str(e))
        await send_webhook(webhook_url, jobData.jobId, jobData.webhookSecret, "UPLOAD_CONTENT", error_data.dict())
        raise

async def send_webhook(webhook_url: str, job_id: str, webhook_secret: str, task: str, data: dict):
    """Helper function to send webhook notifications"""
    payload = {
        "jobId": job_id,
        "task": task,
        "data": data
    }
    
    headers = {
        "Content-Type": "application/json",
        "x-webhook-signature": webhook_secret
    }
    
    try:
        response = requests.post(webhook_url, json=payload, headers=headers)
        print(f"Webhook sent - Task: {task}, Response: {response.status_code}")
    except Exception as e:
        print(f"Failed to send webhook: {str(e)}")

def ProcessVideo(jobData: JobCreateRequest):
    """Initialize job for approval-based workflow"""
    # Store job state for step-by-step processing
    job_states[jobData.jobId] = {
        "job_data": jobData,
        "current_task": "PENDING",
        "task_status": "WAITING_FOR_APPROVAL",
        "audio_file_path": None,
        "transcript": None,
        "segments": None,
        "questions": None
    }
    print(f"Job {jobData.jobId} initialized and waiting for approval to start")
