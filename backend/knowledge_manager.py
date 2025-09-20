# knowledge_manager.py
import os
import uuid
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from fastapi import UploadFile
import boto3
import json
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
import pymongo
from agno.knowledge.pdf import PDFReader
from agno.knowledge.docx import DocxReader
from agno.knowledge.text import TextReader

# Import configuration
from config import (
    vector_db, embedder, DOCUMENTDB_URL, DATABASE_NAME,
    KNOWLEDGE_BASE_DIR, OPENSEARCH_ENDPOINT, OPENSEARCH_INDEX,
    AWS_REGION, AWS_BEDROCK_REGION, AWS_DOCUMENTDB_REGION, logger
)

class KnowledgeManager:
    """Manages knowledge base operations using Amazon OpenSearch Service and DocumentDB."""

    def __init__(self):
        # Initialize AWS credentials for OpenSearch
        credentials = boto3.Session().get_credentials()
        awsauth = AWS4Auth(
            credentials.access_key,
            credentials.secret_key,
            AWS_REGION,
            'es',
            session_token=credentials.token
        )
        
        # Amazon OpenSearch Service client
        self.opensearch_client = OpenSearch(
            hosts=[{'host': OPENSEARCH_ENDPOINT.replace('https://', ''), 'port': 443}],
            http_auth=awsauth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection
        )
        
        # Amazon DocumentDB client (MongoDB-compatible)
        self.documentdb_client = pymongo.MongoClient(
            DOCUMENTDB_URL,
            ssl=True,
            ssl_ca_certs='rds-ca-2019-root.pem',
            retryWrites=False
        )
        self.db = self.documentdb_client[DATABASE_NAME]
        self.metadata_collection = self.db["knowledge_metadata"]
        
        # AWS Bedrock client for embeddings
        self.bedrock_client = boto3.client(
            'bedrock-runtime',
            region_name=AWS_REGION
        )
        
        # Document readers
        self.readers = {
            'pdf': PDFReader(),
            'docx': DocxReader(),
            'text': TextReader()
        }
        
        # Ensure knowledge base directory exists
        Path(KNOWLEDGE_BASE_DIR).mkdir(parents=True, exist_ok=True)
        
        # Ensure OpenSearch index exists
        self._ensure_opensearch_index()

    def _ensure_opensearch_index(self):
        """Create OpenSearch index if it doesn't exist."""
        if not self.opensearch_client.indices.exists(index=OPENSEARCH_INDEX):
            index_mapping = {
                "mappings": {
                    "properties": {
                        "vector": {
                            "type": "knn_vector",
                            "dimension": 1024,
                            "method": {
                                "name": "hnsw",
                                "space_type": "cosinesimil",
                                "engine": "nmslib"
                            }
                        },
                        "content": {"type": "text"},
                        "file_name": {"type": "keyword"},
                        "document_type": {"type": "keyword"},
                        "category": {"type": "keyword"},
                        "chunk_index": {"type": "integer"},
                        "mongo_doc_id": {"type": "keyword"},
                        "created_at": {"type": "date"}
                    }
                },
                "settings": {
                    "index": {
                        "knn": True,
                        "knn.algo_param.ef_search": 512
                    }
                }
            }
            
            self.opensearch_client.indices.create(
                index=OPENSEARCH_INDEX,
                body=index_mapping
            )
            logger.info(f"Created OpenSearch index: {OPENSEARCH_INDEX}")

    def _generate_embeddings_bedrock(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using AWS Bedrock Titan Text Embeddings V2."""
        embeddings = []
        
        for text in texts:
            body = json.dumps({
                "inputText": text,
                "dimensions": 1024,
                "normalize": True
            })
            
            response = self.bedrock_client.invoke_model(
                body=body,
                modelId="amazon.titan-embed-text-v2:0",
                accept="application/json",
                contentType="application/json"
            )
            
            response_body = json.loads(response.get('body').read())
            embeddings.append(response_body['embedding'])
        
        return embeddings

    async def search_knowledge(
        self,
        query: str,
        limit: int = 5,
        similarity_threshold: float = 0.7,
        document_type: Optional[str] = None,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search the knowledge base using OpenSearch vector similarity."""
        try:
            # Generate embedding for the query using Bedrock
            query_embedding = self._generate_embeddings_bedrock([query])[0]
            
            # Build OpenSearch query
            must_clauses = []
            if document_type:
                must_clauses.append({"term": {"document_type": document_type}})
            if category:
                must_clauses.append({"term": {"category": category}})
            
            search_body = {
                "size": limit,
                "min_score": similarity_threshold,
                "query": {
                    "script_score": {
                        "query": {
                            "bool": {
                                "must": must_clauses
                            }
                        } if must_clauses else {"match_all": {}},
                        "script": {
                            "source": "cosineSimilarity(params.query_vector, 'vector') + 1.0",
                            "params": {"query_vector": query_embedding}
                        }
                    }
                }
            }
            
            # Perform search
            response = self.opensearch_client.search(
                index=OPENSEARCH_INDEX,
                body=search_body
            )
            
            # Format results
            results = []
            for hit in response['hits']['hits']:
                source = hit['_source']
                
                # Get additional metadata from DocumentDB
                mongo_doc = self.metadata_collection.find_one(
                    {"opensearch_doc_id": hit['_id']}
                )
                
                result = {
                    "opensearch_doc_id": hit['_id'],
                    "similarity_score": hit['_score'] - 1.0,  # Adjust for cosine similarity
                    "content": source.get("content", ""),
                    "file_name": source.get("file_name", ""),
                    "document_type": source.get("document_type", ""),
                    "category": source.get("category", "general"),
                    "chunk_index": source.get("chunk_index", 0),
                    "mongo_doc_id": source.get("mongo_doc_id", ""),
                    "metadata": source
                }
                
                # Add full content from DocumentDB if available
                if mongo_doc:
                    result["full_content"] = mongo_doc.get("content", "")
                    result["mongo_metadata"] = mongo_doc.get("metadata", {})
                
                results.append(result)
            
            logger.info(f"Knowledge search for '{query}' returned {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Error in knowledge search: {e}")
            raise

    async def add_document(
        self,
        file: UploadFile,
        document_type: str,
        category: str = "general",
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Add a new document to the knowledge base."""
        try:
            # Generate unique document ID
            document_id = str(uuid.uuid4())
            
            # Create category directory
            category_dir = Path(KNOWLEDGE_BASE_DIR) / category
            category_dir.mkdir(parents=True, exist_ok=True)
            
            # Save file
            file_path = category_dir / f"{document_id}_{file.filename}"
            content = await file.read()
            with open(file_path, "wb") as f:
                f.write(content)
            
            # Process document
            reader = self.readers.get(document_type)
            if not reader:
                raise ValueError(f"Unsupported document type: {document_type}")
            
            documents = reader.read(str(file_path))
            
            # Generate embeddings using Bedrock
            contents = [doc.content for doc in documents]
            if contents:
                embeddings = self._generate_embeddings_bedrock(contents)
            else:
                embeddings = []

            opensearch_docs = []
            metadata_docs = []
            
            # Process documents and embeddings
            for i, doc in enumerate(documents):
                embedding = embeddings[i]
                
                # Create unique IDs
                opensearch_id = str(uuid.uuid4())
                mongo_id = f"{document_id}_chunk_{i}"
                
                # Prepare metadata
                doc_metadata = {
                    "document_id": document_id,
                    "file_path": str(file_path),
                    "file_name": file.filename,
                    "document_type": document_type,
                    "category": category,
                    "chunk_index": i,
                    "total_chunks": len(documents),
                    "mongo_doc_id": mongo_id,
                    "opensearch_doc_id": opensearch_id,
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
                
                # Add custom metadata
                if metadata:
                    doc_metadata.update(metadata)
                
                # Add document-specific metadata
                if hasattr(doc, 'meta') and doc.meta:
                    doc_metadata.update(doc.meta)
                
                # Create OpenSearch document
                opensearch_doc = {
                    "vector": embedding,
                    "content": doc.content[:1000],  # Truncate for OpenSearch storage
                    "file_name": file.filename,
                    "document_type": document_type,
                    "category": category,
                    "chunk_index": i,
                    "mongo_doc_id": mongo_id,
                    "created_at": doc_metadata["created_at"]
                }
                opensearch_docs.append((opensearch_id, opensearch_doc))
                
                # Prepare DocumentDB document
                mongo_doc = {
                    "_id": mongo_id,
                    "document_id": document_id,
                    "opensearch_doc_id": opensearch_id,
                    "file_path": str(file_path),
                    "file_name": file.filename,
                    "document_type": document_type,
                    "category": category,
                    "chunk_index": i,
                    "total_chunks": len(documents),
                    "content": doc.content,
                    "content_length": len(doc.content),
                    "metadata": doc_metadata,
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc)
                }
                metadata_docs.append(mongo_doc)
            
            # Insert into OpenSearch
            for doc_id, doc_body in opensearch_docs:
                self.opensearch_client.index(
                    index=OPENSEARCH_INDEX,
                    id=doc_id,
                    body=doc_body
                )
            
            # Insert into DocumentDB
            if metadata_docs:
                self.metadata_collection.insert_many(metadata_docs)
            
            logger.info(f"Added document {file.filename} with {len(documents)} chunks")
            
            return {
                "document_id": document_id,
                "chunks_created": len(documents),
                "file_path": str(file_path)
            }
            
        except Exception as e:
            logger.error(f"Error adding document: {e}")
            raise

    async def delete_document(self, document_id: str) -> Dict[str, Any]:
        """Delete a document and all its chunks from the knowledge base."""
        try:
            # Find all chunks for this document
            mongo_docs = list(self.metadata_collection.find({"document_id": document_id}))
            
            if not mongo_docs:
                raise ValueError(f"Document {document_id} not found")
            
            # Get OpenSearch document IDs
            opensearch_ids = [doc["opensearch_doc_id"] for doc in mongo_docs]
            
            # Delete from OpenSearch
            for doc_id in opensearch_ids:
                self.opensearch_client.delete(
                    index=OPENSEARCH_INDEX,
                    id=doc_id
                )
            
            # Delete from DocumentDB
            self.metadata_collection.delete_many({"document_id": document_id})
            
            # Delete file if it exists
            if mongo_docs:
                file_path = Path(mongo_docs[0]["file_path"])
                if file_path.exists():
                    file_path.unlink()
            
            logger.info(f"Deleted document {document_id} with {len(mongo_docs)} chunks")
            
            return {
                "chunks_deleted": len(mongo_docs)
            }
            
        except Exception as e:
            logger.error(f"Error deleting document: {e}")
            raise

    async def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the knowledge base."""
        try:
            # OpenSearch stats
            opensearch_stats = self.opensearch_client.indices.stats(index=OPENSEARCH_INDEX)
            doc_count = opensearch_stats['_all']['total']['docs']['count']
            
            # DocumentDB stats
            total_documents = len(list(self.metadata_collection.distinct("document_id")))
            total_chunks = self.metadata_collection.count_documents({})
            
            return {
                "total_documents": total_documents,
                "total_chunks": total_chunks,
                "opensearch_docs": doc_count,
                "opensearch_index": OPENSEARCH_INDEX
            }
            
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            raise

    async def list_documents(
        self,
        category: Optional[str] = None,
        document_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List all documents in the knowledge base."""
        try:
            # Build query
            query = {}
            if category:
                query["category"] = category
            if document_type:
                query["document_type"] = document_type
            
            # Group by document_id to get unique documents
            pipeline = [
                {"$match": query},
                {
                    "$group": {
                        "_id": "$document_id",
                        "file_name": {"$first": "$file_name"},
                        "file_path": {"$first": "$file_path"},
                        "document_type": {"$first": "$document_type"},
                        "category": {"$first": "$category"},
                        "chunk_count": {"$sum": 1},
                        "created_at": {"$first": "$created_at"},
                        "updated_at": {"$max": "$updated_at"},
                        "total_content_length": {"$sum": "$content_length"}
                    }
                },
                {"$sort": {"created_at": -1}}
            ]
            
            documents = []
            for doc in self.metadata_collection.aggregate(pipeline):
                documents.append({
                    "document_id": doc["_id"],
                    "file_name": doc["file_name"],
                    "file_path": doc["file_path"],
                    "document_type": doc["document_type"],
                    "category": doc["category"],
                    "chunk_count": doc["chunk_count"],
                    "total_content_length": doc["total_content_length"],
                    "created_at": doc["created_at"],
                    "updated_at": doc["updated_at"]
                })
            
            return documents
            
        except Exception as e:
            logger.error(f"Error listing documents: {e}")
            raise

    async def reindex_all(self) -> Dict[str, Any]:
        """Reindex all documents in the knowledge base."""
        try:
            # Get all unique documents
            documents = await self.list_documents()
            
            total_processed = 0
            total_chunks = 0
            
            for doc in documents:
                # Delete existing chunks
                await self.delete_document(doc["document_id"])
                
                # Re-add document
                file_path = Path(doc["file_path"])
                if file_path.exists():
                    # Simulate UploadFile
                    with open(file_path, "rb") as f:
                        content = f.read()
                    
                    # Create a mock UploadFile object
                    class MockUploadFile:
                        def __init__(self, filename, content):
                            self.filename = filename
                            self._content = content
                        
                        async def read(self):
                            return self._content
                    
                    mock_file = MockUploadFile(doc["file_name"], content)
                    
                    result = await self.add_document(
                        file=mock_file,
                        document_type=doc["document_type"],
                        category=doc["category"]
                    )
                    
                    total_processed += 1
                    total_chunks += result["chunks_created"]
            
            logger.info(f"Reindexed {total_processed} documents with {total_chunks} chunks")
            
            return {
                "documents_processed": total_processed,
                "chunks_created": total_chunks
            }
            
        except Exception as e:
            logger.error(f"Error reindexing: {e}")
            raise    