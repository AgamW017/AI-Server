import os
import asyncio
from typing import Optional
import whisper
from models import TranscriptParameters

# Supported languages for transcription  
SUPPORTED_LANGUAGES = ['English', 'Hindi']

class TranscriptionService:
    def __init__(self):
        self.model = None
        self.current_model_size = None
    
    async def _load_model(self, model_size: str = "small"):
        """Load the Whisper model lazily"""
        if self.model is None or self.current_model_size != model_size:
            loop = asyncio.get_event_loop()
            self.model = await loop.run_in_executor(None, lambda: whisper.load_model(model_size))
            self.current_model_size = model_size
    
    def _parse_vtt_to_timestamp_format(self, segments) -> str:
        """
        Converts Whisper segments to the desired timestamp format
        
        Args:
            segments: Whisper transcription segments with timestamps
            
        Returns:
            str: Formatted transcript with timestamps
        """
        result = []
        
        for segment in segments:
            start_time = segment['start']
            end_time = segment['end']
            text = segment['text'].strip()
            
            if text:
                # Convert seconds to MM:SS.mmm format
                def seconds_to_mmss(seconds):
                    minutes = int(seconds // 60)
                    secs = seconds % 60
                    return f"{minutes:02d}:{secs:06.3f}"
                
                start_formatted = seconds_to_mmss(start_time)
                end_formatted = seconds_to_mmss(end_time)
                
                result.append(f"[{start_formatted} --> {end_formatted}]  {text}")
        
        return '\n'.join(result)
    
    def _is_language_supported(self, language: str) -> bool:
        """
        Validates if the provided language is supported
        
        Args:
            language: The language to validate
            
        Returns:
            bool: True if language is supported
        """
        return language in SUPPORTED_LANGUAGES
    
    async def transcribe(self, audio_path: str, transcript_params: Optional[TranscriptParameters] = None) -> str:
        """
        Transcribes an audio file using Whisper package.
        
        Args:
            audio_path: Path to the input audio file (WAV format expected)
            transcript_params: Optional transcription parameters containing language and model settings
            
        Returns:
            str: The transcribed text with timestamps
            
        Raises:
            Exception: If transcription fails
        """
        if not os.path.exists(audio_path):
            raise Exception(f"Input audio file not found: {audio_path}")
        
        # Extract parameters or use defaults
        if transcript_params:
            language = transcript_params.language.value if transcript_params.language else 'en'
            model_size = transcript_params.model or 'small'
        else:
            language = 'en'  # Default to English
            model_size = 'small'  # Default to small model
        
        # Validate language support
        if not self._is_language_supported(language):
            raise Exception(
                f"Unsupported language: {language}. Supported languages: {', '.join(SUPPORTED_LANGUAGES)}"
            )
        
        try:
            # Load the Whisper model with specified size
            await self._load_model(model_size)
            
            print(f"Starting Whisper transcription for: {audio_path} (model: {model_size}, language: {language})")
            
            # Run transcription in thread pool
            loop = asyncio.get_event_loop()
            
            def run_transcription():
                if self.model is None:
                    raise Exception("Whisper model is not loaded. Please check model loading.")
                result = self.model.transcribe(audio_path, language=language)
                return result
            
            result = await loop.run_in_executor(None, run_transcription)
            
            # Parse segments to desired timestamp format
            formatted_transcript = self._parse_vtt_to_timestamp_format(result['segments'])
            
            print('Whisper transcription successful.')
            return formatted_transcript
            
        except Exception as error:
            # This catch handles errors from the try block above
            print(f"Error during transcription: {str(error)}")
            raise Exception(f"Transcription failed: {str(error)}")
