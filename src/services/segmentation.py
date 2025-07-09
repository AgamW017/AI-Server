import json
import re
import os
from typing import Dict, List, Optional, TYPE_CHECKING
import requests
from fastapi import HTTPException

if TYPE_CHECKING:
    from models import SegmentationParameters

from models import TranscriptSegment


class SegmentationService:
    """Service for segmenting transcripts into meaningful subtopics"""
    
    def __init__(self):
        self.ollama_api_base_url = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api")
    
    def extract_json_from_markdown(self, text: str) -> str:
        """Extract JSON content from markdown-formatted text"""
        # Remove markdown code blocks
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        
        # Remove any leading/trailing whitespace
        text = text.strip()
        
        # Try to find JSON content between { } or [ ]
        json_match = re.search(r'[\[\{].*[\]\}]', text, re.DOTALL)
        if json_match:
            return json_match.group(0)
        
        return text

    def clean_transcript_lines(self, transcript_lines: List[str]) -> str:
        """Clean transcript lines by removing timestamps and combining text"""
        cleaned_text = []
        
        for line in transcript_lines:
            # Remove timestamp patterns like "00:00.000 --> 01:30.000"
            cleaned_line = re.sub(r'\d{2}:\d{2}\.\d{3}\s*-->\s*\d{2}:\d{2}\.\d{3}', '', line)
            # Remove timestamp patterns like "[00:00.000 --> 01:30.000]"
            cleaned_line = re.sub(r'\[\d{2}:\d{2}\.\d{3}\s*-->\s*\d{2}:\d{2}\.\d{3}\]', '', cleaned_line)
            
            # Clean up extra whitespace
            cleaned_line = cleaned_line.strip()
            
            if cleaned_line:
                cleaned_text.append(cleaned_line)
        
        return ' '.join(cleaned_text)

    async def segment_transcript(self, transcript: str, segmentation_params: Optional['SegmentationParameters'] = None) -> Dict[str, str]:
        """
        Segment transcript into meaningful subtopics using LLM
        Returns: Dictionary with end_time as key and cleaned transcript as value
        """
        # Extract model from parameters or use default
        model = "gemma3"
        if segmentation_params and hasattr(segmentation_params, 'model') and segmentation_params.model:
            model = segmentation_params.model
        
        if not transcript or not isinstance(transcript, str) or not transcript.strip():
            raise HTTPException(
                status_code=400,
                detail="Transcript text is required and must be a non-empty string."
            )

        prompt = f"""Analyze the following timed lecture transcript. Your task is to segment it into meaningful subtopics (not too many, maximum 5 segments).
The transcript is formatted with each line as: [start_time --> end_time] text OR start_time --> end_time text.

For each identified subtopic, you must provide:
1. "end_time": The end timestamp of the *last transcript line* that belongs to this subtopic (e.g., "02:53.000").
2. "transcript_lines": An array of strings, where each string is an *original transcript line (including its timestamps and text)* that belongs to this subtopic.

IMPORTANT: Your response must be ONLY a valid JSON array. Do not include any explanatory text, markdown formatting, or comments.

Example format:
[
  {{
    "end_time": "01:30.000",
    "transcript_lines": ["00:00.000 --> 00:30.000 First topic content", "00:30.000 --> 01:30.000 More content"]
  }},
  {{
    "end_time": "03:00.000", 
    "transcript_lines": ["01:30.000 --> 02:15.000 Second topic content", "02:15.000 --> 03:00.000 Final content"]
  }}
]

Transcript to process:
{transcript}

JSON:"""

        segments = []
        generated_text = ""
        try:
            response = requests.post(
                f"{self.ollama_api_base_url}/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "top_p": 0.9,
                    }
                },
                timeout=300  # 5 minute timeout
            )
            response.raise_for_status()

            if response.json() and isinstance(response.json().get('response'), str):
                generated_text = response.json()['response']

                # Enhanced JSON extraction with multiple fallback strategies
                try:
                    cleaned_json_text = self.extract_json_from_markdown(generated_text)
                except Exception as extract_error:
                    cleaned_json_text = generated_text.strip()

                # Multiple robust JSON parsing strategies
                json_to_parse = ""
                
                # Strategy 1: Look for JSON array in the response
                array_match = re.search(r'\[[\s\S]*?\]', cleaned_json_text)
                if array_match:
                    json_to_parse = array_match.group(0)
                else:
                    # Strategy 2: Try to find JSON object and wrap in array
                    object_match = re.search(r'\{[\s\S]*?\}', cleaned_json_text)
                    if object_match:
                        json_to_parse = f"[{object_match.group(0)}]"
                    else:
                        # Strategy 3: Remove all non-JSON content before and after
                        lines = cleaned_json_text.split('\n')
                        start_idx = -1
                        end_idx = -1
                        
                        for i, line in enumerate(lines):
                            line = line.strip()
                            if line.startswith('[') or line.startswith('{'):
                                start_idx = i
                                break
                        
                        for i in range(len(lines) - 1, -1, -1):
                            line = lines[i].strip()
                            if line.endswith(']') or line.endswith('}'):
                                end_idx = i
                                break
                        
                        if start_idx != -1 and end_idx != -1 and end_idx >= start_idx:
                            json_to_parse = '\n'.join(lines[start_idx:end_idx + 1])
                        else:
                            json_to_parse = cleaned_json_text

                # Clean up common JSON formatting issues
                fixed_json = json_to_parse
                fixed_json = re.sub(r',\s*}]', '}]', fixed_json)  # Remove trailing commas before closing
                fixed_json = re.sub(r',\s*]', ']', fixed_json)    # Remove trailing commas in arrays
                fixed_json = re.sub(r'}\s*{', '},{', fixed_json)   # Add missing commas between objects
                fixed_json = re.sub(r']\s*\[', '],[', fixed_json)  # Add missing commas between arrays
                fixed_json = fixed_json.replace('\n', ' ').replace('\t', ' ')  # Replace newlines/tabs with spaces
                fixed_json = re.sub(r'\s+', ' ', fixed_json).strip()  # Normalize spaces

                segments_data = json.loads(fixed_json)

                # Validate the parsed segments
                if not isinstance(segments_data, list):
                    raise ValueError("Response is not an array")

                if len(segments_data) == 0:
                    raise ValueError("Segments array is empty")

                # Convert to TranscriptSegment objects and validate
                for i, segment_data in enumerate(segments_data):
                    if not segment_data.get('end_time') or not isinstance(segment_data.get('transcript_lines'), list):
                        raise ValueError(f"Invalid segment structure at index {i}")
                    
                    segments.append(TranscriptSegment(
                        end_time=segment_data['end_time'],
                        transcript_lines=segment_data['transcript_lines']
                    ))

        except requests.RequestException as error:
            raise HTTPException(
                status_code=500,
                detail=f"Ollama API error: {str(error)}"
            )

        except Exception as error:
            raise HTTPException(
                status_code=500,
                detail=f"Error segmenting transcript: {str(error)}"
            )

        # Convert to the required format: {"end_time": "cleaned_transcript"}
        segments_for_generation = {}
        for segment in segments:
            try:
                cleaned_transcript = self.clean_transcript_lines(segment.transcript_lines)
                if cleaned_transcript and cleaned_transcript.strip():
                    segments_for_generation[segment.end_time] = cleaned_transcript
            except Exception as clean_error:
                print(f"Error cleaning transcript lines for segment {segment.end_time}: {clean_error}")

        return segments_for_generation
