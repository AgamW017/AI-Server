import asyncio
from typing import Any, Dict, Optional
import whisper

class TranscriptionService:
    def __init__(self):
        self.model = None
        self.current_model_size = None
    
    async def _load_model(self, model_size: str = "medium"):
        """Load the Whisper model lazily"""
        loop = asyncio.get_event_loop()
        self.model = await loop.run_in_executor(None, lambda: whisper.load_model(model_size))
        self.current_model_size = model_size
    
    async def transcribe(self, audio_path: str, model_size: Optional[str] = 'medium',  language: Optional[str] = 'en') -> Dict[str, Any]:
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
        
        try:
            # Load the Whisper model with specified size
            await self._load_model(model_size if model_size else 'medium')
            
            print(f"Starting Whisper transcription for: {audio_path} (model: {model_size if model_size else 'medium'}, language: {language if language else 'en'})")
            
            # Run transcription in thread pool
            loop = asyncio.get_event_loop()
            
            def run_transcription():
                if self.model is None:
                    raise Exception("Whisper model is not loaded. Please check model loading.")
                result = self.model.transcribe(audio_path, language=language if language else 'en', verbose=True)
                return result
            
            result = await loop.run_in_executor(None, run_transcription)
            if not result or "text" not in result:
                raise Exception(f"Transcription failed")
            
            formatted_result = {
                "text": result["text"],  # Full transcript text
                "chunks": []
            }
            
            # Convert segments to chunks format with timestamp arrays
            for segment in result.get("segments", []):
                chunk = {
                    "timestamp": [segment["start"], segment["end"]],
                    "text": segment["text"]
                }
                formatted_result["chunks"].append(chunk)
            
            return formatted_result

            
        except Exception as error:
            # This catch handles errors from the try block above
            print(f"Error during transcription: {str(error)}")
            raise Exception(f"Transcription failed: {str(error)}")
