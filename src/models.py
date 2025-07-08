from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, HttpUrl, validator
from enum import Enum

class JobType(str, Enum):
    VIDEO  = "VIDEO"
    PLAYLIST = "PLAYLIST"

class LanguageType(str, Enum):
    ENGLISH = "en"
    HINDI = "hi"
    
class TranscriptParameters(BaseModel):
    language: Optional[LanguageType] = None
    model: Optional[str] = None

class SegmentationParameters(BaseModel):
    lambda_param: Optional[float] = Field(None, alias="lambda")
    epochs: Optional[int] = None
    model: Optional[str] = None

class QuestionGenerationParameters(BaseModel):
    prompt: Optional[str] = None
    model: Optional[str] = None
    questionSpecification: Optional[list[Dict[str, int]]] = None

class UploadParameters(BaseModel):
    courseId: str = Field(...)
    versionId: str = Field(...)
    moduleId: str = Field(...)
    sectionId: str = Field(...)
    afterItemId: Optional[str] = None
    beforeItemId: Optional[str] = None

class GenAIResponse(BaseModel):
    _id: Optional[str] = None
    type: JobType = Field(...)
    url: HttpUrl = Field(...)

class JobBody(BaseModel):
    type: JobType = Field(...)
    url: HttpUrl = Field(...)
    transcriptParameters: Optional[TranscriptParameters] = None
    segmentationParameters: Optional[SegmentationParameters] = None
    questionGenerationParameters: Optional[QuestionGenerationParameters] = None
    uploadParameters: Optional[UploadParameters] = None

class JobCreateRequest(BaseModel):
    data: JobBody
    userId: str
    jobId: str
    webhookUrl: str
    webhookSecret: str
    # Add other job fields as needed

class JobUpdateRequest(BaseModel):
    # Task parameters for job updates
    parameters: Optional[Dict[str, Any]] = None
    data: Optional[Dict[str, Any]] = None

class WebhookRequest(BaseModel):
    task: str
    status: str
    jobId: str
    data: Dict[str, Any]

class JobResponse(BaseModel):
    status: str
    jobId: Optional[str] = None
    received: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    error: str
    message: str

class TranscriptSegment(BaseModel):
    end_time: str
    transcript_lines: list[str]

class CleanedSegment(BaseModel):
    end_time: str
    transcript_lines: list[str]

class QuestionOption(BaseModel):
    text: str
    correct: Optional[bool] = None
    explanation: Optional[str] = None

class GeneratedQuestion(BaseModel):
    segmentId: Optional[str] = None
    questionType: Optional[str] = None
    questionText: str
    options: Optional[list[QuestionOption]] = None
    solution: Optional[Any] = None
    isParameterized: Optional[bool] = False
    timeLimitSeconds: Optional[int] = None
    points: Optional[int] = None

class SegmentationRequest(BaseModel):
    transcript: str
    model: Optional[str] = "gemma3"

class QuestionGenerationRequest(BaseModel):
    segments: Dict[str, str]
    globalQuestionSpecification: list[Dict[str, int]]
    model: Optional[str] = "gemma3"

class TaskStatus(str, Enum):
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class AudioData(BaseModel):
    status: TaskStatus
    error: Optional[str] = None
    fileName: Optional[str] = None
    fileUrl: Optional[str] = None
    
    def dict(self, **kwargs):
        # Exclude None values from the dictionary
        data = super().dict(**kwargs)
        return {k: v for k, v in data.items() if v is not None}

class TranscriptGenerationData(BaseModel):
    status: TaskStatus
    error: Optional[str] = None
    fileName: Optional[str] = None
    fileUrl: Optional[str] = None
    newParameters: Optional[TranscriptParameters] = None
    
    def dict(self, **kwargs):
        # Exclude None values from the dictionary
        data = super().dict(**kwargs)
        return {k: v for k, v in data.items() if v is not None}

class SegmentationData(BaseModel):
    status: TaskStatus
    error: Optional[str] = None
    fileName: Optional[str] = None
    fileUrl: Optional[str] = None
    newParameters: Optional[SegmentationParameters] = None
    
    def dict(self, **kwargs):
        # Exclude None values from the dictionary
        data = super().dict(**kwargs)
        return {k: v for k, v in data.items() if v is not None}

class QuestionGenerationData(BaseModel):
    status: TaskStatus
    error: Optional[str] = None
    fileName: Optional[str] = None
    fileUrl: Optional[str] = None
    questionType: Optional[str] = None
    question: Optional[GeneratedQuestion] = None
    newParameters: Optional[QuestionGenerationParameters] = None
    
    def dict(self, **kwargs):
        # Exclude None values from the dictionary
        data = super().dict(**kwargs)
        return {k: v for k, v in data.items() if v is not None}

class ContentUploadData(BaseModel):
    status: TaskStatus
    error: Optional[str] = None
    courseId: Optional[str] = None
    versionId: Optional[str] = None
    
    def dict(self, **kwargs):
        # Exclude None values from the dictionary
        data = super().dict(**kwargs)
        return {k: v for k, v in data.items() if v is not None}
