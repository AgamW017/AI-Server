import json
import re
import os
from typing import Dict, List, Optional, TYPE_CHECKING
import requests
from fastapi import HTTPException
from schema import SOL_SCHEMA, SML_SCHEMA, OTL_SCHEMA, NAT_SCHEMA, DES_SCHEMA

if TYPE_CHECKING:
    from models import QuestionGenerationParameters

class QuestionGenerationService:
    """Service for generating questions from transcript segments"""
    
    def __init__(self):
        self.ollama_api_base_url = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api")
        
        # Question schemas for different types
        self.question_schemas = {
            "SOL": SOL_SCHEMA,
            "SML": SML_SCHEMA,
            "OTL": OTL_SCHEMA,
            "NAT": NAT_SCHEMA,
            "DES": DES_SCHEMA
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
- Focus on conceptual understanding
- Test comprehension of key ideas, principles, and relationships discussed in the content
- Avoid quesitons that require memorizing exact numerical values, dates, or statistics mentioned in the content
- The answer of questions should be present within the content, but not directly quoted
- make all the options roughly the same length
- Set isParameterized to false unless the question uses variables

"""

        type_specific_instructions = {
            "SOL": """Create SELECT_ONE_IN_LOT questions (single correct answer multiple choice):
- Focus on understanding concepts, principles, or cause-and-effect relationships
- Avoid questions about specific numbers, percentages, or statistical data
- Clear question text that tests comprehension of ideas
- 3-4 incorrect options with explanations that address common misconceptions
- 1 correct option with explanation that reinforces the concept
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

    async def generate_questions(self, segments: Dict[str, str], question_params: Optional['QuestionGenerationParameters'] = None) -> List[str]:
        """
        Generate questions based on segments and question specifications
        """
        model = question_params.model if question_params and question_params.model else "deepseek-r1:70b"
        question_specs = {
            "SOL": question_params.SOL if question_params and question_params.SOL else 2,
            "SML": question_params.SML if question_params and question_params.SML else 2,
            "NAT": question_params.NAT if question_params and question_params.NAT else 0,
            "DES": question_params.DES if question_params and question_params.DES else 0,
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
                            json=payload
                        )
                        response.raise_for_status()

                        if response.json() and isinstance(response.json().get('response'), str):
                            generated_text = response.json()['response']
                            cleaned_json_text = self.extract_json_from_markdown(generated_text)
                            all_generated_questions.append(cleaned_json_text)
                            
                        else:
                          print(f"No response data or response.response is not a string for {question_type} in segment {segment_id}")

                    except requests.RequestException as error:
                      print(f"Error calling Ollama API for {question_type} questions in segment {segment_id}: {error}")

                    except Exception as error:
                      print(f"Error generating {question_type} questions for segment {segment_id}: {error}")

        return all_generated_questions
