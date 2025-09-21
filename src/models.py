from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime

class TaskType(str, Enum):
    AUDIO_EXTRACTION = "AUDIO_EXTRACTION"
    TRANSCRIPT_GENERATION = "TRANSCRIPT_GENERATION"
    SEGMENTATION = "SEGMENTATION"
    QUESTION_GENERATION = "QUESTION_GENERATION"

class JobType(str, Enum):
    VIDEO  = "VIDEO"
    PLAYLIST = "PLAYLIST"

class LanguageType(str, Enum):
    ENGLISH = "en"
    HINDI = "hi"
    
class TranscriptParameters(BaseModel):
    language: Optional[LanguageType] = None
    modelSize: Optional[str] = None

class SegmentationParameters(BaseModel):
    lam: Optional[float] = None
    runs: Optional[int] = None
    noiseId: Optional[int] = None

class QuestionGenerationParameters(BaseModel):
    model: Optional[str] = None
    SOL: Optional[int] = None
    SML: Optional[int] = None
    NAT: Optional[int] = None
    DES: Optional[int] = None
    BIN: Optional[int] = None
    prompt: Optional[str] = None

class TaskStatus(str, Enum):
    PENDING = 'PENDING'
    RUNNING = 'RUNNING'
    WAITING = 'WAITING'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'
    ABORTED = 'ABORTED'

class JobStatus(BaseModel):
    audioExtraction: TaskStatus = TaskStatus.PENDING
    transcriptGeneration: TaskStatus = TaskStatus.PENDING
    segmentation: TaskStatus = TaskStatus.PENDING
    questionGeneration: TaskStatus = TaskStatus.PENDING
    uploadContent: TaskStatus = TaskStatus.PENDING

class QuestionOption(BaseModel):
    text: str
    correct: Optional[bool] = None
    explanation: Optional[str] = None

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
    parameters: Optional[TranscriptParameters] = None
    
    def dict(self, **kwargs):
        # Exclude None values from the dictionary
        data = super().dict(**kwargs)
        return {k: v for k, v in data.items() if v is not None}

class SegmentationData(BaseModel):
    status: TaskStatus
    error: Optional[str] = None
    segmentationMap: Optional[List[float]] = None
    transcriptFileUrl: Optional[str] = None
    parameters: Optional[SegmentationParameters] = None
    
    def dict(self, **kwargs):
        # Exclude None values from the dictionary
        data = super().dict(**kwargs)
        return {k: v for k, v in data.items() if v is not None}
    
class QuestionGenerationData(BaseModel):
    status: TaskStatus
    error: Optional[str] = None
    fileName: Optional[str] = None
    fileUrl: Optional[str] = None
    segmentMapUsed: Optional[List[float]] = None
    parameters: Optional[QuestionGenerationParameters] = None
    
    def dict(self, **kwargs):
        # Exclude None values from the dictionary
        data = super().dict(**kwargs)
        return {k: v for k, v in data.items() if v is not None}

# New database models matching TypeScript interfaces
class GenAI(BaseModel):
    type: JobType
    url: str
    transcriptParameters: Optional[TranscriptParameters] = None
    segmentationParameters: Optional[SegmentationParameters] = None
    questionGenerationParameters: Optional[QuestionGenerationParameters] = None

class GenAIBody(GenAI):
    id: Optional[str] = Field(None, alias="_id")
    userId: str
    createdAt: datetime
    jobStatus: JobStatus
    currentTask: Optional[str] = None

class TaskData(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    jobId: str
    audioExtraction: Optional[List[AudioData]] = None
    transcriptGeneration: Optional[List[TranscriptGenerationData]] = None
    segmentation: Optional[List[SegmentationData]] = None
    questionGeneration: Optional[List[QuestionGenerationData]] = None

class GenAIResponse(BaseModel):
    _id: Optional[str] = None
    type: JobType = Field(...)
    url: str = Field(...)

class JobBody(BaseModel):
    type: JobType = Field(...)
    url: str = Field(...)
    transcriptParameters: Optional[TranscriptParameters] = None
    segmentationParameters: Optional[SegmentationParameters] = None
    questionGenerationParameters: Optional[QuestionGenerationParameters] = None

class JobCreateRequest(BaseModel):
    data: JobBody
    userId: str
    jobId: str

class WebhookRequest(BaseModel):
    task: str
    status: str
    jobId: str
    data: Dict[str, Any]

# Endpoint-specific response models
class JobResponse(BaseModel):
    message: str = "Job created successfully"

class JobStatusResponse(BaseModel):
    jobId: str
    status: TaskStatus
    currentTask: Optional[str] = None

class JobErrorResponse(BaseModel):
    error: str
    details: Optional[str] = None

class TranscriptSegment(BaseModel):
    timestamp: List[float]
    text: str

class CleanedSegment(BaseModel):
    end_time: str
    transcript_lines: list[str]

class SegmentationRequest(BaseModel):
    transcript: str
    model: Optional[str] = "gemma3"

class QuestionGenerationRequest(BaseModel):
    segments: List[float]
    globalQuestionSpecification: list[Dict[str, int]]
    model: Optional[str] = "gemma3"

# Job state model for combining data
class JobState(BaseModel):
    currentTask: TaskType | None = None
    taskStatus: TaskStatus
    url: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    file: Optional[str] = None
    segmentMap: Optional[List[float]] = None

class Transcript(BaseModel):
    chunks: List[TranscriptSegment] = []

class SegmentResponse(BaseModel):
    complete_segments: Dict[str, str]
    segments: List[float]
    segment_count: int
