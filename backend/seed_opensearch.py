# seed_opensearch.py
"""
Seed Amazon OpenSearch Service for the Legal Multi-Agent System:
- Creates indexes with proper vector configuration
- Loads legal documents (PDF, DOCX, TXT) into vector database
- Links with Amazon DocumentDB through document metadata
"""

import os
import json
import uuid
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv
import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

# Document processing imports
from agno.knowledge.pdf import PDFReader
from agno.knowledge.docx import DocxReader
from agno.knowledge.text import TextReader

# MongoDB for cross-referencing
import pymongo

def create_knowledge_base_directories():
    """Create knowledge base directory structure if it doesn't exist."""
    base_dir = Path("./knowledge_base")
    subdirs = ["pdfs", "docx", "texts"]
    
    for subdir in subdirs:
        (base_dir / subdir).mkdir(parents=True, exist_ok=True)
    
    return base_dir

def create_sample_documents(base_dir: Path):
    """Create sample legal documents for testing."""
    
    # Sample legal texts
    sample_texts = {
        "contract_law_basics.txt": """
Contract Law Fundamentals

1. ESSENTIAL ELEMENTS OF A CONTRACT

For a contract to be legally binding, it must contain the following essential elements:

a) Offer: A clear proposal made by one party (offeror) to another party (offeree)
b) Acceptance: Unqualified agreement to the terms of the offer
c) Consideration: Something of value exchanged between the parties
d) Intention to create legal relations: Both parties must intend for the agreement to be legally binding
e) Capacity: Both parties must have the legal capacity to enter into the contract
f) Legality: The contract's purpose and terms must be legal

2. TYPES OF CONTRACTS

- Express Contracts: Terms are explicitly stated (written or oral)
- Implied Contracts: Terms are inferred from conduct or circumstances
- Bilateral Contracts: Both parties make promises
- Unilateral Contracts: One party makes a promise in exchange for performance

3. CONTRACT PERFORMANCE AND BREACH

Performance can be:
- Complete Performance: All obligations fulfilled
- Substantial Performance: Performance with minor deviations
- Material Breach: Significant failure to perform

Document ID: CONTRACT_LAW_001
Jurisdiction: General Common Law Principles
Last Updated: 2024-01-15
""",

        "gdpr_compliance.txt": """
General Data Protection Regulation (GDPR) Compliance Guide

1. FUNDAMENTAL PRINCIPLES

Article 5 establishes six key principles for data processing:
a) Lawfulness, fairness, and transparency
b) Purpose limitation
c) Data minimization
d) Accuracy
e) Storage limitation
f) Integrity and confidentiality

2. LAWFUL BASIS FOR PROCESSING (Article 6)

- Consent of the data subject
- Performance of a contract
- Compliance with legal obligation
- Protection of vital interests
- Performance of a task in the public interest
- Legitimate interests of the controller

3. DATA SUBJECT RIGHTS

- Right to information (Articles 13-14)
- Right of access (Article 15)
- Right to rectification (Article 16)
- Right to erasure (Article 17)
- Right to restrict processing (Article 18)
- Right to data portability (Article 20)
- Right to object (Article 21)

Document ID: GDPR_COMPLIANCE_001
Jurisdiction: European Union
Regulation: EU 2016/679
Last Updated: 2024-01-15
""",

        "intellectual_property_overview.txt": """
Intellectual Property Law Overview

1. TYPES OF INTELLECTUAL PROPERTY

a) PATENTS
- Protect inventions and innovations
- Duration: 20 years from filing date
- Requirements: Novel, non-obvious, useful

b) TRADEMARKS
- Protect brand names, logos, slogans
- Duration: Renewable indefinitely
- Requirements: Distinctive, used in commerce

c) COPYRIGHTS
- Protect original works of authorship
- Duration: Life of author + 70 years (generally)
- Requirements: Original, fixed in tangible medium

d) TRADE SECRETS
- Protect confidential business information
- Duration: As long as kept secret
- Requirements: Economic value, reasonable secrecy measures

Document ID: IP_OVERVIEW_001
Jurisdiction: United States
Last Updated: 2024-01-15
"""
    }
    
    # Create sample text files
    texts_dir = base_dir / "texts"
    for filename, content in sample_texts.items():
        (texts_dir / filename).write_text(content, encoding='utf-8')
    
    print(f"Created {len(sample_texts)} sample legal documents in {texts_dir}")

def generate_embeddings_bedrock(texts: list, region: str = "us-east-1") -> list:
    """Generate embeddings using AWS Bedrock Titan Text Embeddings V2."""
    bedrock_client = boto3.client('bedrock-runtime', region_name=region)
    embeddings = []
    
    for text in texts:
        body = json.dumps({
            "inputText": text,
            "dimensions": 1024,
            "normalize": True
        })
        
        response = bedrock_client.invoke_model(
            body=body,
            modelId="amazon.titan-embed-text-v2:0",
            accept="application/json",
            contentType="application/json"
        )
        
        response_body = json.loads(response.get('body').read())
        embeddings.append(response_body['embedding'])
    
    return embeddings

def seed_opensearch_database():
    """Main function to seed OpenSearch with legal documents."""
    load_dotenv()
    
    # Configuration
    AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
    OPENSEARCH_ENDPOINT = os.getenv("OPENSEARCH_ENDPOINT", "https://search-legal-knowledge-xyz.us-east-1.es.amazonaws.com")
    OPENSEARCH_INDEX = os.getenv("OPENSEARCH_INDEX", "legal_knowledge_base")
    
    # DocumentDB configuration for cross-referencing
    DOCUMENTDB_URL = os.getenv("DOCUMENTDB_URL", "mongodb://docdb-cluster.cluster-xyz.us-east-1.docdb.amazonaws.com:27017")
    DATABASE_NAME = os.getenv("DATABASE_NAME", "legal_agent_system")
    
    print("--- Starting OpenSearch Vector Database Seeding ---")
    
    # Initialize AWS authentication
    try:
        credentials = boto3.Session().get_credentials()
        awsauth = AWS4Auth(
            credentials.access_key,
            credentials.secret_key,
            AWS_REGION,
            'es',
            session_token=credentials.token
        )
        print(f"AWS authentication configured for region: {AWS_REGION}")
    except Exception as e:
        print(f"Error configuring AWS authentication: {e}")
        return
    
    # Initialize OpenSearch client
    try:
        opensearch_client = OpenSearch(
            hosts=[{'host': OPENSEARCH_ENDPOINT.replace('https://', ''), 'port': 443}],
            http_auth=awsauth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection
        )
        print(f"Connected to OpenSearch at {OPENSEARCH_ENDPOINT}")
    except Exception as e:
        print(f"Error connecting to OpenSearch: {e}")
        return
    
    # Initialize DocumentDB for metadata storage
    try:
        documentdb_client = pymongo.MongoClient(
            DOCUMENTDB_URL,
            ssl=True,
            ssl_ca_certs="rds-ca-2019-root.pem",
            retryWrites=False
        )
        db = documentdb_client[DATABASE_NAME]
        knowledge_metadata_col = db["knowledge_metadata"]
        print(f"Connected to DocumentDB at {DOCUMENTDB_URL}")
    except Exception as e:
        print(f"Error connecting to DocumentDB: {e}")
        return
    
    try:
        # Delete existing index if it exists
        try:
            if opensearch_client.indices.exists(index=OPENSEARCH_INDEX):
                opensearch_client.indices.delete(index=OPENSEARCH_INDEX)
                print(f"Deleted existing index: {OPENSEARCH_INDEX}")
        except:
            pass
        
        # Create new index with vector mapping
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
        
        opensearch_client.indices.create(
            index=OPENSEARCH_INDEX,
            body=index_mapping
        )
        print(f"Created index: {OPENSEARCH_INDEX}")
        
        # Create knowledge base directories and sample documents
        base_dir = create_knowledge_base_directories()
        create_sample_documents(base_dir)
        
        # Initialize document readers
        readers = {
            'pdf': PDFReader(),
            'docx': DocxReader(),
            'txt': TextReader()
        }
        
        opensearch_docs = []
        metadata_docs = []
        doc_id_counter = 1
        
        # Process documents from each directory
        for doc_type, reader in readers.items():
            doc_dir = base_dir / {"pdf": "pdfs", "docx": "docx", "txt": "texts"}[doc_type]
            
            if not doc_dir.exists():
                continue
                
            extensions = {
                'pdf': ['.pdf'],
                'docx': ['.docx', '.doc'],
                'txt': ['.txt', '.md']
            }
            
            for ext in extensions[doc_type]:
                for file_path in doc_dir.glob(f"*{ext}"):
                    try:
                        print(f"Processing {file_path}")
                        
                        # Read and chunk document
                        documents = reader.read(file_path)
                        
                        # Generate embeddings using Bedrock
                        contents = [doc.content for doc in documents]
                        if not contents:
                            continue
                        
                        embeddings = generate_embeddings_bedrock(contents, AWS_REGION)

                        for i, doc in enumerate(documents):
                            # Get pre-calculated embedding
                            embedding = embeddings[i]
                            
                            # Create unique IDs
                            opensearch_doc_id = str(uuid.uuid4())
                            mongo_id = f"doc_{doc_id_counter}_{i}"
                            
                            # Prepare metadata
                            metadata = {
                                "file_path": str(file_path),
                                "file_name": file_path.name,
                                "document_type": doc_type,
                                "category": "general",
                                "chunk_index": i,
                                "total_chunks": len(documents),
                                "mongo_doc_id": mongo_id,
                                "opensearch_doc_id": opensearch_doc_id,
                                "created_at": datetime.now(timezone.utc).isoformat()
                            }
                            
                            # Add document-specific metadata if available
                            if hasattr(doc, 'meta') and doc.meta:
                                metadata.update(doc.meta)
                            
                            # Create OpenSearch document
                            opensearch_doc = {
                                "vector": embedding,
                                "content": doc.content[:1000],  # Truncate for storage
                                "file_name": file_path.name,
                                "document_type": doc_type,
                                "category": "general",
                                "chunk_index": i,
                                "mongo_doc_id": mongo_id,
                                "created_at": metadata["created_at"]
                            }
                            opensearch_docs.append((opensearch_doc_id, opensearch_doc))
                            
                            # Prepare DocumentDB metadata document
                            mongo_doc = {
                                "_id": mongo_id,
                                "opensearch_doc_id": opensearch_doc_id,
                                "file_path": str(file_path),
                                "file_name": file_path.name,
                                "document_type": doc_type,
                                "category": "general",
                                "chunk_index": i,
                                "total_chunks": len(documents),
                                "content": doc.content,
                                "content_length": len(doc.content),
                                "metadata": metadata,
                                "created_at": datetime.now(timezone.utc),
                                "updated_at": datetime.now(timezone.utc)
                            }
                            metadata_docs.append(mongo_doc)
                            
                        doc_id_counter += 1
                            
                    except Exception as e:
                        print(f"Error processing {file_path}: {e}")
                        continue
        
        # Insert documents into OpenSearch
        if opensearch_docs:
            print(f"Inserting {len(opensearch_docs)} documents into OpenSearch...")
            for doc_id, doc_body in opensearch_docs:
                opensearch_client.index(
                    index=OPENSEARCH_INDEX,
                    id=doc_id,
                    body=doc_body
                )
            print(f"Successfully inserted {len(opensearch_docs)} documents into OpenSearch")
        
        # Insert metadata into DocumentDB
        if metadata_docs:
            print(f"Inserting {len(metadata_docs)} metadata documents into DocumentDB...")
            knowledge_metadata_col.delete_many({})  # Clear existing
            knowledge_metadata_col.insert_many(metadata_docs)
            print(f"Successfully inserted {len(metadata_docs)} metadata documents into DocumentDB")
        
        # Verify collections
        opensearch_stats = opensearch_client.indices.stats(index=OPENSEARCH_INDEX)
        documentdb_count = knowledge_metadata_col.count_documents({})
        
        print(f"\n--- Seeding Complete ---")
        print(f"OpenSearch index '{OPENSEARCH_INDEX}' documents: {opensearch_stats['_all']['total']['docs']['count']}")
        print(f"DocumentDB 'knowledge_metadata' documents: {documentdb_count}")
        print(f"Embedding model: amazon.titan-embed-text-v2:0")
        print(f"Vector dimensions: 1024")
        
    except Exception as e:
        print(f"Error during seeding: {e}")
    finally:
        if 'documentdb_client' in locals():
            documentdb_client.close()
        print("--- OpenSearch Seeding Finished ---")

if __name__ == "__main__":
    seed_opensearch_database()