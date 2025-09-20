# main.py
import os
import json
import uvicorn
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

# Import your modules
from config import (
    logger, FRONTEND_URL, agent_storage, memory, embedder, 
    KNOWLEDGE_SEARCH_CONFIG
)
from models import QueryRequest, QueryResponse, KnowledgeDocument
from agents import legal_system
from websocket_manager import manager
from utils import _run_and_extract
from knowledge_manager import KnowledgeManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Load the AWS Bedrock embedder on startup and clean up on shutdown.
    """
    logger.info("Initializing AWS Bedrock embedder...")
    # The embedder is already initialized in config.py with Bedrock Titan Text Embeddings V2
    # so we just need to make it available to the app
    app.state.embedder = embedder
    logger.info("AWS Bedrock embedder loaded and ready.")
    yield
    # Clean up resources if needed on shutdown
    logger.info("Application shutting down...")

app = FastAPI(
    title="Legal Multi-Agent System with AWS Knowledge Base",
    version="3.0.0",
    description="Legal AI agents powered by AWS Bedrock, OpenSearch, and DocumentDB",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

knowledge_manager = KnowledgeManager()

# --- API Endpoints ---

@app.get("/")
async def root():
    return {
        "message": "Legal Multi-Agent System API with AWS Knowledge Base", 
        "version": "3.0.0",
        "features": [
            "Multi-Agent Legal Assistance", 
            "AWS Bedrock Integration",
            "OpenSearch Vector Search", 
            "DocumentDB Storage",
            "Titan Text Embeddings V2"
        ],
        "aws_services": {
            "llm": "AWS Bedrock (gpt-oss:120b)",
            "embeddings": "Titan Text Embeddings V2",
            "vector_db": "Amazon OpenSearch Service",
            "document_db": "Amazon DocumentDB"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for AWS load balancer."""
    try:
        # Test DocumentDB connection
        agent_storage_health = "healthy"
        try:
            # Quick connection test
            list(agent_storage.read("health_check"))
        except:
            agent_storage_health = "degraded"
        
        # Test OpenSearch connection  
        opensearch_health = "healthy"
        try:
            await knowledge_manager.get_stats()
        except:
            opensearch_health = "degraded"
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "services": {
                "document_db": agent_storage_health,
                "vector_db": opensearch_health,
                "embedder": "healthy"
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")

@app.get("/agents")
async def get_agents():
    return {
        "agents": {
            name: agent.instructions for name, agent in legal_system.agents.items()
        },
        "team_available": True,
        "aws_integration": {
            "bedrock_model": "gpt-oss:120b",
            "embedding_model": "amazon.titan-embed-text-v2:0",
            "knowledge_base": "OpenSearch + DocumentDB"
        }
    }

@app.post("/query", response_model=QueryResponse)
async def process_query(request: QueryRequest):
    try:
        agent_or_team = legal_system.team if request.agent_type == "team" else legal_system.agents.get(request.agent_type)
        if not agent_or_team:
            raise HTTPException(status_code=400, detail="Invalid agent type")
        
        agent_name = "Legal Team" if request.agent_type == "team" else agent_or_team.name
        agent_or_team.session_id = request.session_id
        agent_or_team.user_id = request.user_id

        # Log knowledge search for monitoring
        logger.info(f"Processing query with AWS Bedrock and OpenSearch: {request.message[:100]}...")

        content, tool_calls = _run_and_extract(agent_or_team, request.message, stream=False)

        return QueryResponse(
            response=content,
            agent_name=agent_name,
            session_id=getattr(agent_or_team, "session_id", "default") or "default",
            timestamp=datetime.now(),
            tool_calls=tool_calls,
        )
    except Exception as e:
        logger.exception("Error in /query")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/query/stream")
async def process_query_stream(request: QueryRequest):
    try:
        agent_or_team = legal_system.team if request.agent_type == "team" else legal_system.agents.get(request.agent_type)
        if not agent_or_team:
            raise HTTPException(status_code=400, detail="Invalid agent type")
        
        agent_name = "Legal Team" if request.agent_type == "team" else agent_or_team.name
        agent_or_team.session_id = request.session_id
        agent_or_team.user_id = request.user_id

        def generate_response():
            run_iter, _ = _run_and_extract(agent_or_team, request.message, stream=True)
            for chunk in run_iter:
                chunk_content = getattr(chunk, "content", "")
                if chunk_content:
                    yield f"data: {json.dumps({'content': chunk_content, 'agent': agent_name})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"

        return StreamingResponse(generate_response(), media_type="text/event-stream")
    except Exception as e:
        logger.exception("Error in /query/stream")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sessions/{session_id}/history")
async def get_session_history(session_id: str):
    try:
        messages = await agent_storage.read(session_id)
        return {"session_id": session_id, "messages": messages}
    except Exception as e:
        logger.exception("Error fetching session history from DocumentDB")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/users/{user_id}/memories")
async def get_user_memories(user_id: str):
    try:
        memories_data = memory.get_user_memories(user_id=user_id)
        if asyncio.iscoroutine(memories_data):
            memories_data = await memories_data
        return {"user_id": user_id, "memories": memories_data}
    except Exception as e:
        logger.exception("Error fetching user memories from DocumentDB")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/knowledge/upload")
async def upload_document(
    file: UploadFile = File(...),
    document_type: str = Form(...),
    category: str = Form(default="general")
):
    """Upload a new document to the AWS knowledge base (OpenSearch + DocumentDB)."""
    try:
        # Validate file type
        allowed_types = {
            'pdf': ['.pdf'],
            'docx': ['.docx', '.doc'],
            'text': ['.txt', '.md']
        }
        
        if document_type not in allowed_types:
            raise HTTPException(status_code=400, detail="Invalid document type")
        
        file_extension = os.path.splitext(file.filename)[1].lower()
        if file_extension not in allowed_types[document_type]:
            raise HTTPException(status_code=400, detail=f"File extension {file_extension} not allowed for type {document_type}")
        
        # Save and process document using AWS services
        result = await knowledge_manager.add_document(
            file=file,
            document_type=document_type,
            category=category
        )
        
        return {
            "message": "Document uploaded and processed successfully with AWS Bedrock embeddings",
            "document_id": result["document_id"],
            "chunks_created": result["chunks_created"],
            "file_name": file.filename,
            "services_used": {
                "embeddings": "AWS Bedrock Titan Text Embeddings V2",
                "vector_storage": "Amazon OpenSearch Service",
                "metadata_storage": "Amazon DocumentDB"
            }
        }
    except Exception as e:
        logger.exception("Error uploading document to AWS knowledge base")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/knowledge/documents")
async def list_documents(category: str = None, document_type: str = None):
    """List all documents in the AWS knowledge base."""
    try:
        documents = await knowledge_manager.list_documents(
            category=category,
            document_type=document_type
        )
        return {
            "documents": documents,
            "total_count": len(documents),
            "storage_info": {
                "vector_db": "Amazon OpenSearch Service",
                "metadata_db": "Amazon DocumentDB",
                "embedding_model": "amazon.titan-embed-text-v2:0"
            }
        }
    except Exception as e:
        logger.exception("Error listing documents from AWS knowledge base")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/knowledge/documents/{document_id}")
async def delete_document(document_id: str):
    """Delete a document from the AWS knowledge base."""
    try:
        result = await knowledge_manager.delete_document(document_id)
        return {
            "message": "Document deleted successfully from AWS knowledge base",
            "document_id": document_id,
            "chunks_deleted": result["chunks_deleted"],
            "services_updated": ["Amazon OpenSearch Service", "Amazon DocumentDB"]
        }
    except Exception as e:
        logger.exception("Error deleting document from AWS knowledge base")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/knowledge/stats")
async def get_knowledge_stats():
    """Get statistics about the AWS knowledge base."""
    try:
        stats = await knowledge_manager.get_stats()
        stats["aws_services"] = {
            "vector_database": "Amazon OpenSearch Service",
            "document_database": "Amazon DocumentDB", 
            "embedding_service": "AWS Bedrock Titan Text Embeddings V2",
            "llm_service": "AWS Bedrock"
        }
        return stats
    except Exception as e:
        logger.exception("Error getting AWS knowledge base stats")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/knowledge/reindex")
async def reindex_knowledge_base():
    """Reindex the entire AWS knowledge base with fresh embeddings."""
    try:
        result = await knowledge_manager.reindex_all()
        return {
            "message": "AWS knowledge base reindexed successfully with fresh Bedrock embeddings",
            "documents_processed": result["documents_processed"],
            "chunks_created": result["chunks_created"],
            "embedding_model": "amazon.titan-embed-text-v2:0",
            "services_updated": ["Amazon OpenSearch Service", "Amazon DocumentDB"]
        }
    except Exception as e:
        logger.exception("Error reindexing AWS knowledge base")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/knowledge/search")
async def search_knowledge(query: str, limit: int = 5, similarity_threshold: float = 0.7):
    """Search the AWS knowledge base using OpenSearch vector similarity."""
    try:
        results = await knowledge_manager.search_knowledge(
            query=query,
            limit=limit,
            similarity_threshold=similarity_threshold
        )
        return {
            "query": query,
            "results": results,
            "total_found": len(results),
            "search_info": {
                "embedding_model": "amazon.titan-embed-text-v2:0",
                "vector_database": "Amazon OpenSearch Service",
                "similarity_algorithm": "cosine",
                "threshold": similarity_threshold
            }
        }
    except Exception as e:
        logger.exception("Error searching AWS knowledge base")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/aws/status")
async def aws_services_status():
    """Check the status of AWS services integration."""
    try:
        status = {
            "bedrock": "connected",
            "opensearch": "connected", 
            "documentdb": "connected",
            "embeddings": "amazon.titan-embed-text-v2:0",
            "llm": "gpt-oss:120b"
        }
        
        # Test each service
        try:
            stats = await knowledge_manager.get_stats()
            status["opensearch_docs"] = stats.get("opensearch_docs", 0)
        except:
            status["opensearch"] = "error"
            
        try:
            list(agent_storage.read("test"))
            status["documentdb_collections"] = ["agent_data", "agent_memories", "knowledge_metadata"]
        except:
            status["documentdb"] = "error"
            
        return status
    except Exception as e:
        logger.exception("Error checking AWS services status")
        raise HTTPException(status_code=500, detail=str(e))
     
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            query = message_data.get("message", "")
            agent_type = message_data.get("agent_type", "legal_advisor")

            agent_or_team = legal_system.team if agent_type == "team" else legal_system.agents.get(agent_type)
            agent_or_team.session_id = session_id
            agent_or_team.user_id = message_data.get("user_id")

            run_iter, _ = _run_and_extract(agent_or_team, query, stream=True)
            for chunk in run_iter:
                if content := getattr(chunk, "content", ""):
                    await manager.send_personal_message(json.dumps({
                        "content": content,
                        "agent": getattr(agent_or_team, 'name', 'Legal Team'),
                        "timestamp": datetime.now().isoformat(),
                        "aws_powered": True
                    }), websocket)
            await manager.send_personal_message(json.dumps({"done": True}), websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.exception("WebSocket error")
        await manager.send_personal_message(json.dumps({"error": str(e)}), websocket)

if __name__ == "__main__":
    uvicorn.run(
        app,
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", 8000))
    )