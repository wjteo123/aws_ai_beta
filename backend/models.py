# models.py
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime

class QueryRequest(BaseModel):
    message: str
    agent_type: Optional[str] = "team"
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    search_knowledge: Optional[bool] = True
    knowledge_search_limit: Optional[int] = 5

class QueryResponse(BaseModel):
    response: str
    agent_name: str
    session_id: str
    timestamp: datetime
    tool_calls: List[Dict[str, Any]] = []
    knowledge_sources: List[Dict[str, Any]] = []

class KnowledgeDocument(BaseModel):
    id: str
    file_name: str
    file_path: str
    document_type: str
    category: str
    content_preview: str
    chunk_count: int
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = {}

class KnowledgeSearchResult(BaseModel):
    document_id: str
    chunk_id: str
    content: str
    similarity_score: float
    file_name: str
    document_type: str
    category: str
    metadata: Dict[str, Any] = {}

class DocumentUploadRequest(BaseModel):
    document_type: str
    category: Optional[str] = "general"
    metadata: Optional[Dict[str, Any]] = {}

class KnowledgeSearchRequest(BaseModel):
    query: str
    limit: Optional[int] = 5
    similarity_threshold: Optional[float] = 0.7
    document_type: Optional[str] = None
    category: Optional[str] = None