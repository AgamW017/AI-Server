import json
import re
import time
import logging
from typing import Dict, List, Any, Optional, TYPE_CHECKING
import requests
from fastapi import HTTPException

if TYPE_CHECKING:
    from models import SegmentationParameters, QuestionGenerationParameters

from models import (
    TranscriptSegment, 
    CleanedSegment, 
    GeneratedQuestion, 
    QuestionOption,
    SegmentationRequest,
    QuestionGenerationRequest
)

logger = logging.getLogger(__name__)

class AIContentService:
    """AI Content Service for transcript segmentation and question generation"""
    
    def __init__(self):
        self.ollama_api_base_url = "http://localhost:11434/api"
        self.llm_api_url = "http://localhost:11434/api/generate"
        
        # Question schemas for different types
        self.question_schemas = {
            "SOL": {
                "type": "object",
                "properties": {
                    "questionText": {"type": "string"},
                    "options": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "text": {"type": "string"},
                                "correct": {"type": "boolean"},
                                "explanation": {"type": "string"}
                            }
                        }
                    },
                    "timeLimitSeconds": {"type": "number"},
                    "points": {"type": "number"}
                }
            },
            "SML": {
                "type": "object",
                "properties": {
                    "questionText": {"type": "string"},
                    "options": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "text": {"type": "string"},
                                "correct": {"type": "boolean"},
                                "explanation": {"type": "string"}
                            }
                        }
                    },
                    "timeLimitSeconds": {"type": "number"},
                    "points": {"type": "number"}
                }
            },
            "OTL": {
                "type": "object",
                "properties": {
                    "questionText": {"type": "string"},
                    "options": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "text": {"type": "string"},
                                "order": {"type": "number"},
                                "explanation": {"type": "string"}
                            }
                        }
                    },
                    "timeLimitSeconds": {"type": "number"},
                    "points": {"type": "number"}
                }
            },
            "NAT": {
                "type": "object",
                "properties": {
                    "questionText": {"type": "string"},
                    "solution": {"type": "number"},
                    "precision": {"type": "number"},
                    "upperLimit": {"type": "number"},
                    "lowerLimit": {"type": "number"},
                    "timeLimitSeconds": {"type": "number"},
                    "points": {"type": "number"}
                }
            },
            "DES": {
                "type": "object",
                "properties": {
                    "questionText": {"type": "string"},
                    "solution": {"type": "string"},
                    "timeLimitSeconds": {"type": "number"},
                    "points": {"type": "number"}
                }
            }
        }

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

        logger.info(f"Processing transcript for segmentation with LLM (length: {len(transcript)} chars) using model: {model}")

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
                logger.info(f"Ollama segmentation response received, length: {len(generated_text)}")
                logger.info(f"Response preview: {generated_text[:500]}")

                # Enhanced JSON extraction with multiple fallback strategies
                try:
                    cleaned_json_text = self.extract_json_from_markdown(generated_text)
                except Exception as extract_error:
                    logger.warning("Failed to extract JSON from markdown, using raw response")
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

                logger.info(f"Attempting to parse JSON: {fixed_json[:200]}...")
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

                logger.info(f"Successfully parsed {len(segments)} segments")

        except json.JSONDecodeError as parse_error:
            logger.error("All JSON parsing strategies failed.")
            logger.error(f"Parse error: {parse_error}")
            if 'generated_text' in locals():
                logger.error(f"Raw response: {generated_text}")
            
            # Final fallback: create a simple segmentation based on transcript length
            logger.info("Creating fallback segmentation...")
            transcript_lines = [line.strip() for line in transcript.split('\n') if line.strip()]
            lines_per_segment = max(1, len(transcript_lines) // 3)  # Create 3 segments
            
            for i in range(0, len(transcript_lines), lines_per_segment):
                segment_lines = transcript_lines[i:i + lines_per_segment]
                last_line = segment_lines[-1]
                
                # Extract end time from last line
                time_match = re.findall(r'(\d{2}:\d{2}:\d{2}\.\d{3})', last_line)
                end_time = time_match[-1] if time_match else f"{str(i // lines_per_segment + 1).zfill(2)}:00.000"
                
                segments.append(TranscriptSegment(
                    end_time=end_time,
                    transcript_lines=segment_lines
                ))
            
            logger.info(f"Created {len(segments)} fallback segments")

        except requests.RequestException as error:
            logger.error(f"Error in transcript segmentation: {error}")
            raise HTTPException(
                status_code=500,
                detail=f"Ollama API error: {str(error)}"
            )

        except Exception as error:
            logger.error(f"Error segmenting transcript: {error}")
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
                logger.warning(f"Failed to clean transcript for segment {segment.end_time}: {clean_error}")

        logger.info(f"Segmentation completed. Found {len(segments_for_generation)} segments.")
        return segments_for_generation

    def create_question_prompt(self, question_type: str, count: int, transcript_content: str) -> str:
        """Create a prompt for question generation based on type and content"""
        base_prompt = f"""Based on the following transcript content, generate {count} educational question(s) of type {question_type}.

Transcript content:
{transcript_content}

Each question should:
- Be based on the transcript content
- Have appropriate difficulty level
- Set isParameterized to false unless the question uses variables

"""

        type_specific_instructions = {
            "SOL": """Create SELECT_ONE_IN_LOT questions (single correct answer multiple choice):
- Clear question text
- 3-4 incorrect options with explanations
- 1 correct option with explanation
- Set timeLimitSeconds to 60 and points to 5""",

            "SML": """Create SELECT_MANY_IN_LOT questions (multiple correct answers):
- Clear question text
- 2-3 incorrect options with explanations
- 2-3 correct options with explanations
- Set timeLimitSeconds to 90 and points to 8""",

            "OTL": """Create ORDER_THE_LOTS questions (ordering/sequencing):
- Clear question text asking to order items
- 3-5 items that need to be ordered correctly
- Each item should have text and explanation
- Order should be numbered starting from 1
- Set timeLimitSeconds to 120 and points to 10""",

            "NAT": """Create NUMERIC_ANSWER_TYPE questions (numerical answers):
- Clear question text requiring a numerical answer
- Appropriate decimal precision (0-3)
- Realistic upper and lower limits for the answer
- Either a specific value or expression for the solution
- Set timeLimitSeconds to 90 and points to 6""",

            "DES": """Create DESCRIPTIVE questions (text-based answers):
- Clear question text requiring explanation or description
- Detailed solution text that demonstrates the expected answer
- Questions that test understanding of concepts from the transcript
- Set timeLimitSeconds to 300 and points to 15""",
        }

        return base_prompt + type_specific_instructions.get(
            question_type, f"Generate question of type {question_type}."
        )

    async def generate_questions(self, segments: Dict[str, str], question_params: Optional['QuestionGenerationParameters'] = None) -> List[GeneratedQuestion]:
        """
        Generate questions based on segments and question specifications
        """
        # Extract parameters from question_params or use defaults
        model = "gemma3"
        global_question_specification = [{"SOL": 2, "SML": 1, "NAT": 1, "DES": 1}]
        
        if question_params:
            if hasattr(question_params, 'model') and question_params.model:
                model = question_params.model
            if hasattr(question_params, 'questionSpecification') and question_params.questionSpecification:
                global_question_specification = question_params.questionSpecification

        if not segments or not isinstance(segments, dict) or not segments:
            raise HTTPException(
                status_code=400,
                detail="segments is required and must be a non-empty object with segmentId as keys and transcript as values."
            )

        if (not global_question_specification or 
            not isinstance(global_question_specification, list) or 
            not global_question_specification or
            not global_question_specification[0] or
            not isinstance(global_question_specification[0], dict) or
            not global_question_specification[0]):
            raise HTTPException(
                status_code=400,
                detail="globalQuestionSpecification is required and must be a non-empty array with a non-empty object defining question types and counts."
            )

        all_generated_questions = []
        logger.info(f"Using model: {model} for question generation.")

        question_specs = global_question_specification[0]  # Assuming the first spec in the array is the global one

        # Process each segment
        for segment_id, segment_transcript in segments.items():
            if not segment_transcript:
                logger.warning(f"No transcript found for segment {segment_id}. Skipping.")
                continue

            logger.info(f"Processing segment {segment_id} with global specs: {question_specs}")

            # Generate questions for each type based on globalQuestionSpecification
            for question_type, count in question_specs.items():
                if isinstance(count, int) and count > 0:
                    try:
                        # Build schema for structured output
                        base_schema = self.question_schemas.get(question_type)
                        format_schema = None
                        if base_schema:
                            if count == 1:
                                format_schema = base_schema
                            else:
                                format_schema = {
                                    "type": "array",
                                    "items": base_schema,
                                    "minItems": count,
                                    "maxItems": count,
                                }

                        prompt = self.create_question_prompt(question_type, count, segment_transcript)

                        payload = {
                            "model": model,
                            "prompt": prompt,
                            "stream": False,
                            "options": {"temperature": 0}
                        }
                        
                        if format_schema:
                            payload["format"] = format_schema

                        response = requests.post(
                            f"{self.ollama_api_base_url}/generate",
                            json=payload,
                            timeout=300  # 5 minute timeout
                        )
                        response.raise_for_status()

                        if response.json() and isinstance(response.json().get('response'), str):
                            generated_text = response.json()['response']
                            cleaned_json_text = self.extract_json_from_markdown(generated_text)

                            try:
                                generated = json.loads(cleaned_json_text)
                                arr = generated if isinstance(generated, list) else [generated]

                                for q in arr:
                                    question = GeneratedQuestion(
                                        segmentId=segment_id,
                                        questionType=question_type,
                                        questionText=q.get('questionText', ''),
                                        options=[QuestionOption(**opt) for opt in q.get('options', [])] if q.get('options') else None,
                                        solution=q.get('solution'),
                                        isParameterized=q.get('isParameterized', False),
                                        timeLimitSeconds=q.get('timeLimitSeconds'),
                                        points=q.get('points')
                                    )
                                    all_generated_questions.append(question)

                                logger.info(f"Generated {len(arr)} {question_type} questions for segment {segment_id}")

                            except json.JSONDecodeError as parse_error:
                                logger.error(f"Error parsing JSON for {question_type} questions in segment {segment_id}: {parse_error}")
                                logger.error(f"Raw response: {generated_text}")

                        else:
                            logger.warning(f"No response data or response.response is not a string for {question_type} in segment {segment_id}")

                    except requests.RequestException as error:
                        logger.error(f"Error generating {question_type} questions for segment {segment_id}: {error}")

                    except Exception as error:
                        logger.error(f"Error generating {question_type} questions for segment {segment_id}: {error}")

        logger.info(f"Question generation completed. Generated {len(all_generated_questions)} total questions.")
        return all_generated_questions
