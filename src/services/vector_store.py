from pymongo import MongoClient
from fastapi import HTTPException
from langchain_mongodb import MongoDBAtlasVectorSearch
from langchain_ollama import OllamaEmbeddings
import logging
import asyncio
import os
from models import PDFUploadResponse


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MongoDB configuration
MONGODB_CONNECTION_STRING = os.getenv("MONGODB_CONNECTION_STRING")
MONGODB_DATABASE_NAME = os.getenv("MONGODB_DATABASE_NAME", "pdf_vector_db")
MONGODB_COLLECTION_NAME = os.getenv("MONGODB_COLLECTION_NAME", "pdf_embeddings")
VECTOR_INDEX_NAME = os.getenv("VECTOR_INDEX_NAME", "vector_index")


# Initialize Ollama embeddings
try:
    # Ensure Ollama is running and the model is available
    embeddings = OllamaEmbeddings(
        model="mxbai-embed-large",
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    )
    print("OllamaEmbeddings initialized successfully.")
except Exception as e:
    # This will help debug if Ollama is not reachable
    print(f"Error initializing OllamaEmbeddings: {e}")


# Initialize MongoDB client
try:
    client = MongoClient(MONGODB_CONNECTION_STRING)
    db = client[MONGODB_DATABASE_NAME]
    collection = db[MONGODB_COLLECTION_NAME]
    logger.info("MongoDB connection established successfully")
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {e}")
    raise

# Initialize vector store
vector_store = MongoDBAtlasVectorSearch(
    collection=collection,
    embedding=embeddings,
    index_name=VECTOR_INDEX_NAME,
    relevance_score_fn="cosine",
)

class VectorStoreService:
    """
    A service class to provide access to the vector store.
    """
    def __init__(self, vector_store=vector_store):
        self.vector_store = vector_store
    
    async def upload_chunks_embeddings(self, file, chunks):
        vector_store = self.vector_store
        try:
            # Add metadata to chunks
            for i, chunk in enumerate(chunks):
                chunk.metadata.update({
                    "source_filename": file.filename,
                    "chunk_index": i,
                    "total_chunks": len(chunks)
                })

            # Generate embeddings and store in MongoDB
            document_ids = await asyncio.get_event_loop().run_in_executor(
                None,
                vector_store.add_documents,
                chunks
            )

            logger.info(f"Successfully processed {file.filename}: {len(chunks)} chunks, {len(document_ids)} documents stored")

            return PDFUploadResponse(
                message="Chunks uploaded successfully",
                filename=file.filename,
                chunks_processed=len(chunks),
                document_id=document_ids[0] if document_ids else "unknown"
            )
        
        except Exception as e:
            logger.error(f"Error uploading chunks : {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Error uploading chunks: {str(e)}"
            )

        

