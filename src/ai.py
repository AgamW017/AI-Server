import time
import requests
import asyncio
from typing import Optional

from models import (
    JobCreateRequest, 
    TaskStatus, 
    AudioData, 
    TranscriptGenerationData, 
    SegmentationData, 
    QuestionGenerationData,
    ContentUploadData
)
from services.ai_content import AIContentService
from services.audio import AudioService
from services.transcription import TranscriptionService

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
    
    try:
        # Step 1: Audio Extraction
        try:
            # Send webhook - Starting audio extraction
            audio_data = AudioData(status=TaskStatus.STARTED)
            await send_webhook(webhook_url, jobData.jobId, jobData.webhookSecret, "AUDIO_EXTRACTION", audio_data.dict())
            
            # Extract audio from video
            print(f"Extracting audio from video: {jobData.data.url}")
            audio_file_path = await audio_service.extractAudio(str(jobData.data.url))
            print(f"Audio extracted successfully to: {audio_file_path}")
            
            # Send webhook - Audio extraction completed
            audio_data = AudioData(
                status=TaskStatus.COMPLETED,
                fileName=audio_file_path.split('/')[-1] if audio_file_path else None,
                fileUrl=audio_file_path  # In production, this would be a public URL
            )
            await send_webhook(webhook_url, jobData.jobId, jobData.webhookSecret, "AUDIO_EXTRACTION", audio_data.dict())
            
        except Exception as e:
            print(f"Error in audio extraction: {str(e)}")
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
            
            # Generate transcript from audio
            print("Generating transcript from audio...")
            transcript = await transcription_service.transcribe(audio_file_path, jobData.data.transcriptParameters)
            
            # Send webhook - Transcription completed
            transcript_data = TranscriptGenerationData(
                status=TaskStatus.COMPLETED,
                newParameters=jobData.data.transcriptParameters
            )
            await send_webhook(webhook_url, jobData.jobId, jobData.webhookSecret, "TRANSCRIPT_GENERATION", transcript_data.dict())
            
        except Exception as e:
            print(f"Error in transcription: {str(e)}")
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
            
            # Segment the transcript
            print("Segmenting transcript...")
            segments = await ai_service.segment_transcript(transcript, jobData.data.segmentationParameters)
            
            # Send webhook - Segmentation completed
            segmentation_data = SegmentationData(
                status=TaskStatus.COMPLETED,
                newParameters=jobData.data.segmentationParameters
            )
            await send_webhook(webhook_url, jobData.jobId, jobData.webhookSecret, "SEGMENTATION", segmentation_data.dict())
            
        except Exception as e:
            print(f"Error in segmentation: {str(e)}")
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
            
            # Generate questions from segments
            print("Generating questions...")
            questions = await ai_service.generate_questions(
                segments=segments,
                question_params=jobData.data.questionGenerationParameters
            )
            
            # Send webhook for each generated question
            for question in questions:
                question_gen_data = QuestionGenerationData(
                    status=TaskStatus.COMPLETED,
                    questionType=question.questionType,
                    question=question,
                    newParameters=jobData.data.questionGenerationParameters
                )
                await send_webhook(webhook_url, jobData.jobId, jobData.webhookSecret, "QUESTION_GENERATION", question_gen_data.dict())
            
        except Exception as e:
            print(f"Error in question generation: {str(e)}")
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
        
        print("Processing completed successfully!")
        
    except Exception as e:
        # This catch is for any unexpected errors not caught by step-specific handlers
        print(f"Unexpected error in video processing: {str(e)}")
        # Note: Step-specific errors are already handled by their respective try-catch blocks
        # which send appropriate webhook notifications with the correct task names

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
    """Synchronous wrapper for async ProcessVideo function"""
    asyncio.run(process_video_async(jobData))
