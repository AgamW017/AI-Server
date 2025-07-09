import json
import re
import os
from typing import Dict, List, Optional, TYPE_CHECKING
import requests
from fastapi import HTTPException

if TYPE_CHECKING:
    from models import QuestionGenerationParameters

from models import GeneratedQuestion, QuestionOption


class QuestionGenerationService:
    """Service for generating questions from transcript segments"""
    
    def __init__(self):
        self.ollama_api_base_url = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api")
        
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
        model = question_params.model if question_params and question_params.model else "gemma3"
        question_specs = {
            "SOL": question_params.SOL if question_params and question_params.SOL else 2,
            "SML": question_params.SML if question_params and question_params.SML else 1,
            "NAT": question_params.NAT if question_params and question_params.NAT else 1,
            "DES": question_params.DES if question_params and question_params.DES else 1,
        }
        
        if not segments or not isinstance(segments, dict) or not segments:
            raise HTTPException(
                status_code=400,
                detail="segments is required and must be a non-empty object with segmentId as keys and transcript as values."
            )

        all_generated_questions = []

        # Process each segment
        for segment_id, segment_transcript in segments.items():
            if not segment_transcript:
                continue

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

                                print(f"Generated {len(arr)} {question_type} questions for segment {segment_id}")

                            except json.JSONDecodeError as parse_error:
                                print(f"Error parsing JSON for {question_type} questions in segment {segment_id}: {parse_error}")
                                print(f"Raw response: {generated_text}")

                        else:
                            print(f"No response data or response.response is not a string for {question_type} in segment {segment_id}")

                    except requests.RequestException as error:
                        print(f"Error calling Ollama API for {question_type} questions in segment {segment_id}: {error}")

                    except Exception as error:
                        print(f"Error generating {question_type} questions for segment {segment_id}: {error}")

        return all_generated_questions
