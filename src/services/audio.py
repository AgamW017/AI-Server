import os
import asyncio
from pathlib import Path
import yt_dlp

class AudioService:
    async def extractAudio(self, videoPath: str) -> str:
        """
        Extracts audio from a video URL, converts it to 16kHz, 1-channel WAV format.
        
        Args:
            videoPath: URL to the video (YouTube, etc.)
            
        Returns:
            str: Path to the processed audio file
            
        Raises:
            Exception: If download or audio processing fails
        """
        temp_audio_dir = Path(__file__).parent.parent / "temp_audio"
        os.makedirs(temp_audio_dir, exist_ok=True)
        
        # Download audio directly using yt-dlp
        downloaded_audio_path = await self._download_audio(videoPath, temp_audio_dir)
        
        print(f"Audio extraction finished: {downloaded_audio_path}")
        
        return downloaded_audio_path
    
    async def _download_audio(self, video_url: str, temp_dir: Path) -> str:
        """
        Download audio directly from URL using yt-dlp
        
        Args:
            video_url: URL to the video
            temp_dir: Directory to save the audio
            
        Returns:
            str: Path to the downloaded audio file
        """
        loop = asyncio.get_event_loop()
        
        def download():
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': str(temp_dir / '%(title)s_%(id)s.%(ext)s'),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'wav',
                    'preferredquality': '192',
                }],
                'postprocessor_args': ['-ar', '16000', '-ac', '1'],  # 16kHz, mono
                'quiet': True,
                'no_warnings': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                # The postprocessor will create a .wav file
                filename = ydl.prepare_filename(info)
                # Remove the original extension and add .wav
                audio_filename = os.path.splitext(filename)[0] + '.wav'
                return audio_filename
        
        return await loop.run_in_executor(None, download)
