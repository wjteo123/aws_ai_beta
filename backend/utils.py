# utils.py
from typing import Any, List, Dict, Tuple
from config import logger

def _run_and_extract(agent_or_team, message: str, stream: bool = False) -> Tuple[Any, List[Dict[str, Any]]]:
    """
    Runs an agent or team and extracts content and tool calls.
    Enhanced to handle knowledge base integration.
    If stream=True, returns the iterable result.
    """
    try:
        # Log knowledge search activity
        if hasattr(agent_or_team, 'search_knowledge') and agent_or_team.search_knowledge:
            logger.info(f"Running agent with knowledge search enabled for query: {message[:100]}...")
        
        run_result = agent_or_team.run(message, stream=stream)
        if stream:
            return run_result, []
    except TypeError:
        # Fallback for different run signatures
        run_result = agent_or_team.run(message)

    # Handle single response object
    if hasattr(run_result, "content"):
        content = getattr(run_result, "content", "") or ""
        tool_calls = getattr(run_result, "tool_calls", []) or []
        
        # Extract knowledge sources if available
        knowledge_sources = []
        if hasattr(run_result, "knowledge_sources"):
            knowledge_sources = getattr(run_result, "knowledge_sources", [])
        elif hasattr(run_result, "references"):
            # Alternative attribute name
            knowledge_sources = getattr(run_result, "references", [])
        
        # Log knowledge sources found
        if knowledge_sources:
            logger.info(f"Found {len(knowledge_sources)} knowledge sources for response")
        
        return content, tool_calls

    # Handle iterable response for non-streaming calls
    if hasattr(run_result, "__iter__") and not isinstance(run_result, (str, bytes)):
        content = ""
        tool_calls = []
        knowledge_sources = []
        
        for ev in run_result:
            if getattr(ev, "content", None):
                content += ev.content
            if getattr(ev, "tool_calls", None):
                tool_calls.extend(ev.tool_calls)
            if getattr(ev, "knowledge_sources", None):
                knowledge_sources.extend(ev.knowledge_sources)
            elif getattr(ev, "references", None):
                knowledge_sources.extend(ev.references)
        
        return content, tool_calls

    # Fallback to a simple string conversion
    return str(run_result), []

def extract_knowledge_metadata(knowledge_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extract metadata from knowledge search results for logging and tracking.
    """
    if not knowledge_results:
        return {"sources": 0, "documents": [], "categories": []}
    
    documents = []
    categories = set()
    document_types = set()
    
    for result in knowledge_results:
        documents.append({
            "file_name": result.get("file_name", ""),
            "similarity_score": result.get("similarity_score", 0),
            "chunk_index": result.get("chunk_index", 0)
        })
        
        if result.get("category"):
            categories.add(result["category"])
        if result.get("document_type"):
            document_types.add(result["document_type"])
    
    return {
        "sources": len(knowledge_results),
        "documents": documents,
        "categories": list(categories),
        "document_types": list(document_types),
        "avg_similarity": sum(r.get("similarity_score", 0) for r in knowledge_results) / len(knowledge_results)
    }

def format_knowledge_sources_for_response(knowledge_results: List[Dict[str, Any]]) -> str:
    """
    Format knowledge sources for inclusion in agent responses.
    """
    if not knowledge_results:
        return ""
    
    sources_text = "\n\n**Sources:**\n"
    for i, result in enumerate(knowledge_results[:3], 1):  # Limit to top 3
        file_name = result.get("file_name", "Unknown")
        similarity = result.get("similarity_score", 0)
        chunk = result.get("chunk_index", 0)
        
        sources_text += f"{i}. {file_name} (chunk {chunk}, similarity: {similarity:.2f})\n"
    
    if len(knowledge_results) > 3:
        sources_text += f"... and {len(knowledge_results) - 3} more sources\n"
    
    return sources_text

def create_mongodb_cross_reference(session_id: str, knowledge_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Create cross-reference data for linking MongoDB session data with Qdrant knowledge results.
    """
    cross_ref = {
        "session_id": session_id,
        "knowledge_sources": [],
        "metadata": {
            "total_sources": len(knowledge_results),
            "timestamp": str(datetime.now())
        }
    }
    
    for result in knowledge_results:
        source_ref = {
            "qdrant_point_id": result.get("qdrant_point_id", ""),
            "mongo_doc_id": result.get("mongo_doc_id", ""),
            "file_name": result.get("file_name", ""),
            "similarity_score": result.get("similarity_score", 0),
            "chunk_index": result.get("chunk_index", 0),
            "category": result.get("category", ""),
            "document_type": result.get("document_type", "")
        }
        cross_ref["knowledge_sources"].append(source_ref)
    
    return cross_ref