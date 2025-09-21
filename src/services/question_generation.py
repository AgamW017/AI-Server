import json
import re
import os
from typing import Dict, List, Optional
import requests
import asyncio
from fastapi import HTTPException
from schema import SOL_SCHEMA, SML_SCHEMA, OTL_SCHEMA, NAT_SCHEMA, DES_SCHEMA

from models import QuestionGenerationParameters

class QuestionGenerationService:
    """Service for generating questions from transcript segments"""
    
    def __init__(self):
        self.ollama_api_base_url = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api")
        self.active_sessions = {}  # Track active request sessions for cancellation
        
        # Question schemas for different types
        self.question_schemas = {
            "SOL": SOL_SCHEMA,
            "SML": SML_SCHEMA,
            "OTL": OTL_SCHEMA,
            "NAT": NAT_SCHEMA,
            "DES": DES_SCHEMA,
            "BIN": SOL_SCHEMA
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

    def create_question_prompt(self, question_type: str, count: int, transcript_content: str, base_prompt: str) -> str:
        """Create a prompt for question generation based on type and content"""
        base_prompt = f"""Based on the following transcript content, generate {count} educational question(s) of type {question_type}.

Transcript content:
{transcript_content}

Each question should:
{base_prompt}

"""

        type_specific_instructions = {
                "BIN": """Create BINARY questions:
- Focus on understanding concepts, principles, or cause-and-effect relationships
- Avoid questions about specific numbers, percentages, or statistical data
- Clear question text that tests comprehension of ideas
- 1 incorrect option with explanations that address common misconceptions
- 1 correct option with explanation that reinforces the concept
- Options should have text in the form of True/False or Yes/No
- There should only be 2 options in total
- Include a hint that points to the key concept or principle being tested
- Set timeLimitSeconds to 60 and points to 5""",

            "SOL": """Create SELECT_ONE_IN_LOT questions:
- Focus on understanding concepts, principles, or cause-and-effect relationships
- Avoid questions about specific numbers, percentages, or statistical data
- Clear question text that tests comprehension of ideas
- 3 or more incorrect option with explanations that address common misconceptions
- 1 correct option with explanation that reinforces the concept
- Total options should be atleast 3 and at max 6.
- Include a hint that points to the key concept or principle being tested
- Set timeLimitSeconds to 60 and points to 5""",

            "SML": """Create SELECT_MANY_IN_LOT questions (multiple correct answers):
- Test understanding of multiple related concepts or characteristics
- Focus on identifying key principles, factors, or elements discussed
- Avoid numerical data or statistical information
- Clear question text about conceptual relationships
- 2-3 incorrect options with explanations
- 2-3 correct options with explanations that reinforce understanding
- Include a hint that mentions the number of correct answers or key criteria
- Set timeLimitSeconds to 90 and points to 8""",

            "OTL": """Create ORDER_THE_LOTS questions (ordering/sequencing):
- Focus on logical sequences, processes, or hierarchical relationships
- Test understanding of how concepts build upon each other
- Avoid chronological ordering based on specific dates or times
- Clear question text asking to order concepts, steps, or principles
- 3-5 items that need to be ordered based on logical flow or importance
- Each item should represent a concept with explanation of its position
- Order should be numbered starting from 1
- Include a hint about the ordering logic or key principle to consider
- Set timeLimitSeconds to 120 and points to 10""",

            "NAT": """Create NUMERIC_ANSWER_TYPE questions (numerical answers):
- Focus on conceptual calculations or estimations rather than exact figures from the content
- Ask for ratios, proportions, or relative comparisons that require understanding
- Avoid questions asking for specific numbers mentioned in the content
- Test ability to apply concepts to derive approximate or relative numerical answers
- Questions should require reasoning and application rather than recall
- Appropriate decimal precision (0-3)
- Realistic ranges that test conceptual understanding
- Include a hint about the mathematical relationship or concept to apply
- Set timeLimitSeconds to 90 and points to 6""",

            "DES": """Create DESCRIPTIVE questions (text-based answers):
- Focus on explaining concepts, analyzing relationships, or evaluating ideas
- Test deep understanding through explanation and reasoning
- Avoid questions asking to repeat specific facts or figures
- Ask for analysis of why concepts work, how they relate, or what they imply
- Questions that require synthesis and application of multiple ideas
- Detailed solution text that demonstrates analytical thinking
- Include a hint that suggests the key aspects or framework to consider
- Set timeLimitSeconds to 300 and points to 15""",
        }

        return base_prompt + type_specific_instructions.get(
            question_type, f"Generate question of type {question_type}."
        )

    async def generate_questions(self, segments: Dict[str, str], question_params: Optional['QuestionGenerationParameters'] = None, job_id: str = None) -> List[str]:
        """
        Generate questions based on segments and question specifications
        """
        session = requests.Session()
        
        # Store session for potential cancellation
        if job_id:
            self.active_sessions[job_id] = session
        
        try:
            model = question_params.model if question_params and question_params.model else "deepseek-r1:70b"
            if model == 'default':
                model = "deepseek-r1:70b"
            print(question_params)
            question_specs = {
                "SOL": question_params.SOL if question_params and question_params.SOL is not None else 2,
                "BIN": question_params.BIN if question_params and question_params.BIN is not None else 2,
                "SML": question_params.SML if question_params and question_params.SML is not None else 2,
                "NAT": question_params.NAT if question_params and question_params.NAT is not None else 0,
                "DES": question_params.DES if question_params and question_params.DES is not None else 0,
            }
            print(question_specs)
            base_prompt = """
- Focus on conceptual understanding
- Test comprehension of key ideas, principles, and relationships discussed in the content
- Avoid questions that require memorizing exact numerical values, dates, or statistics mentioned in the content
- The answer of questions should be present within the content, but not directly quoted
- make all the options roughly the same length
- Set isParameterized to false unless the question uses variables
- Do not mention the word "transcript" for giving references, use the word "video" instead
            """
            if question_params and question_params.prompt:
                base_prompt = question_params.prompt
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
                            # Check for cancellation before making request
                            if job_id and job_id not in self.active_sessions:
                                print(f"Task cancelled for job {job_id}, stopping question generation")
                                raise asyncio.CancelledError("Task was cancelled")
                            
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

                            prompt = self.create_question_prompt(question_type, count, segment_transcript, base_prompt)

                            payload = {
                                "model": model,
                                "prompt": prompt,
                                "stream": False,
                                "options": {"temperature": 0}
                            }
                            
                            if format_schema:
                                payload["format"] = format_schema

                            response = session.post(
                                f"{self.ollama_api_base_url}/generate",
                                json=payload,
                                timeout=300  # 5 minute timeout
                            )
                            response.raise_for_status()

                            if response.json() and isinstance(response.json().get('response'), str):
                                generated_text = response.json()['response']
                                cleaned_json_text = self.extract_json_from_markdown(generated_text)
                                try:
                                    questions = json.loads(cleaned_json_text)
                                    if isinstance(questions, list):
                                        for q in questions:
                                            q["segmentId"] = segment_id
                                            q["questionType"] = question_type
                                    elif isinstance(questions, dict):
                                        questions["segmentId"] = segment_id
                                        questions["questionType"] = question_type
                                    # Convert back to string before appending
                                    all_generated_questions.append(json.dumps(questions, ensure_ascii=False))
                                except Exception as error:
                                    print(f"Error parsing or annotating questions for {question_type} in segment {segment_id}: {error}")
                                
                            else:
                              print(f"No response data or response.response is not a string for {question_type} in segment {segment_id}")

                        except requests.RequestException as error:
                            if "cancelled" in str(error).lower():
                                print(f"Request cancelled for job {job_id}")
                                raise asyncio.CancelledError("Request was cancelled")
                            print(f"Error calling Ollama API for {question_type} questions in segment {segment_id}: {error}")

                        except Exception as error:
                          print(f"Error generating {question_type} questions for segment {segment_id}: {error}")

            return all_generated_questions
        
        finally:
            # Clean up session
            if job_id and job_id in self.active_sessions:
                del self.active_sessions[job_id]
            session.close()

    def cancel_generation(self, job_id: str):
        """Cancel ongoing question generation for a specific job"""
        if job_id in self.active_sessions:
            session = self.active_sessions[job_id]
            session.close()
            del self.active_sessions[job_id]
            print(f"Cancelled question generation session for job {job_id}")
            print(f"Cancelled question generation session for job {job_id}")
