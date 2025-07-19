import os
from pydantic import BaseModel
from langchain_community.document_loaders import PyPDFLoader
from fastapi import HTTPException
from langchain_text_splitters import RecursiveCharacterTextSplitter
import tempfile
import logging
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Initialize text splitter
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    length_function=len,
    separators=["\n\n", "\n", " ", ""]
)


class PDFChunkingService:
    def __init__(self, text_splitter=text_splitter):
        self.text_splitter = text_splitter

    async def chunk_pdf(self, file_path):
        """
        Chunk a PDF file into smaller pieces of text.
        
        :param file_path: Path to the PDF file.
        :param chunk_size: Number of characters per chunk.
        :return: List of text chunks.
        """
        file = file_path
        try:
        # Create temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                # Write uploaded file content to temporary file
                content = await file.read()
                temp_file.write(content)
                temp_file_path = temp_file.name

            try:
                # Load PDF using LangChain
                loader = PyPDFLoader(temp_file_path)
                documents = await asyncio.get_event_loop().run_in_executor(
                    None, 
                    loader.load
                )

                if not documents:
                    raise HTTPException(
                        status_code=400,
                        detail="No content could be extracted from the PDF"
                    )

                # Split documents into chunks
                chunks = text_splitter.split_documents(documents)
                return chunks
            except Exception as e:
                logger.error(f"Error processing PDF file: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Error processing PDF file: {e}"
                )
            finally:
                # Clean up temporary file
                os.remove(temp_file_path)
                logger.info(f"Temporary file {temp_file_path} removed")

        except Exception as e:
                logger.error(f"Error processing PDF file: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Error processing PDF file: {e}"
                )

        

