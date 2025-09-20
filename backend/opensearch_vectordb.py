# opensearch_vectordb.py
"""
Amazon OpenSearch Service vector database implementation for Agno framework.
"""

import json
import uuid
from typing import List, Dict, Any, Optional
import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
from agno.vectordb.base import VectorDb
from agno.document import Document


class OpenSearchVectorDb(VectorDb):
    """Amazon OpenSearch Service vector database for Agno."""
    
    def __init__(
        self,
        endpoint: str,
        index_name: str,
        region: str = "ap-southeast-5",
        username: Optional[str] = None,
        password: Optional[str] = None,
        use_aws_auth: bool = True,
        dimensions: int = 1024,
        **kwargs
    ):
        """
        Initialize OpenSearch vector database.
        
        Args:
            endpoint: OpenSearch cluster endpoint
            index_name: Index name for storing vectors
            region: AWS region
            username: Username for basic auth (if not using AWS auth)
            password: Password for basic auth (if not using AWS auth)
            use_aws_auth: Whether to use AWS IAM authentication
            dimensions: Vector dimensions
        """
        super().__init__(**kwargs)
        self.endpoint = endpoint.replace('https://', '')
        self.index_name = index_name
        self.region = region
        self.dimensions = dimensions
        
        # Setup authentication
        if use_aws_auth:
            credentials = boto3.Session().get_credentials()
            awsauth = AWS4Auth(
                credentials.access_key,
                credentials.secret_key,
                region,
                'es',
                session_token=credentials.token
            )
            http_auth = awsauth
        else:
            http_auth = (username, password) if username and password else None
        
        # Initialize OpenSearch client
        self.client = OpenSearch(
            hosts=[{'host': self.endpoint, 'port': 443}],
            http_auth=http_auth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection
        )
        
        # Ensure index exists
        self._create_index_if_not_exists()
    
    def _create_index_if_not_exists(self):
        """Create index with proper vector mapping if it doesn't exist."""
        if not self.client.indices.exists(index=self.index_name):
            index_mapping = {
                "mappings": {
                    "properties": {
                        "vector": {
                            "type": "knn_vector",
                            "dimension": self.dimensions,
                            "method": {
                                "name": "hnsw",
                                "space_type": "cosinesimil",
                                "engine": "nmslib"
                            }
                        },
                        "content": {"type": "text"},
                        "metadata": {"type": "object"},
                        "doc_id": {"type": "keyword"}
                    }
                },
                "settings": {
                    "index": {
                        "knn": True,
                        "knn.algo_param.ef_search": 512
                    }
                }
            }
            
            self.client.indices.create(
                index=self.index_name,
                body=index_mapping
            )
    
    def insert(self, documents: List[Document]) -> None:
        """Insert documents into OpenSearch."""
        for doc in documents:
            if not doc.embedding:
                if self.embedder:
                    doc.embedding = self.embedder.get_embedding(doc.content)
                else:
                    raise ValueError("Document has no embedding and no embedder provided")
            
            doc_id = doc.id or str(uuid.uuid4())
            
            opensearch_doc = {
                "vector": doc.embedding,
                "content": doc.content,
                "metadata": doc.meta or {},
                "doc_id": doc_id
            }
            
            self.client.index(
                index=self.index_name,
                id=doc_id,
                body=opensearch_doc
            )
    
    def upsert(self, documents: List[Document]) -> None:
        """Upsert documents (same as insert for OpenSearch)."""
        self.insert(documents)
    
    def search(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """Search for similar documents."""
        if not self.embedder:
            raise ValueError("Embedder required for search")
        
        query_vector = self.embedder.get_embedding(query)
        
        # Build search query
        must_clauses = []
        if filters:
            for key, value in filters.items():
                must_clauses.append({"term": {f"metadata.{key}": value}})
        
        search_body = {
            "size": limit,
            "query": {
                "script_score": {
                    "query": {
                        "bool": {"must": must_clauses}
                    } if must_clauses else {"match_all": {}},
                    "script": {
                        "source": "cosineSimilarity(params.query_vector, 'vector') + 1.0",
                        "params": {"query_vector": query_vector}
                    }
                }
            }
        }
        
        response = self.client.search(
            index=self.index_name,
            body=search_body
        )
        
        # Convert results to Document objects
        documents = []
        for hit in response['hits']['hits']:
            source = hit['_source']
            doc = Document(
                id=source.get('doc_id'),
                content=source.get('content', ''),
                meta=source.get('metadata', {}),
                embedding=source.get('vector')
            )
            documents.append(doc)
        
        return documents
    
    def delete(self, ids: List[str]) -> None:
        """Delete documents by IDs."""
        for doc_id in ids:
            try:
                self.client.delete(
                    index=self.index_name,
                    id=doc_id
                )
            except Exception as e:
                # Log but don't fail if document doesn't exist
                print(f"Warning: Could not delete document {doc_id}: {e}")
    
    def drop(self) -> None:
        """Drop the entire index."""
        if self.client.indices.exists(index=self.index_name):
            self.client.indices.delete(index=self.index_name)
    
    def exists(self) -> bool:
        """Check if the index exists."""
        return self.client.indices.exists(index=self.index_name)
    
    def get_info(self) -> Dict[str, Any]:
        """Get information about the vector database."""
        try:
            stats = self.client.indices.stats(index=self.index_name)
            return {
                "index_name": self.index_name,
                "document_count": stats['_all']['total']['docs']['count'],
                "store_size": stats['_all']['total']['store']['size_in_bytes'],
                "dimensions": self.dimensions
            }
        except Exception as e:
            return {"error": str(e)}
    
    async def asearch(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """Async search (currently just calls sync version)."""
        return self.search(query, limit, filters)
    
    async def ainsert(self, documents: List[Document]) -> None:
        """Async insert (currently just calls sync version)."""
        self.insert(documents)
    
    async def aupsert(self, documents: List[Document]) -> None:
        """Async upsert (currently just calls sync version)."""
        self.upsert(documents)