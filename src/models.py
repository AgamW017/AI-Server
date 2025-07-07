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

class QuestionGenerationParameters(BaseModel):
    prompt: str
    model: Optional[str] = None

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
