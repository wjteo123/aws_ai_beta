# config.py - Updated for Bedrock API key authentication with GPT-OSS-120B only
import os
import logging
from dotenv import load_dotenv
from agno.models.aws import AwsBedrock
from agno.storage.agent.mongodb import MongoDbAgentStorage
from agno.memory.v2.db.mongodb import MongoMemoryDb
from agno.memory.v2.memory import Memory
from aws_embedder import BedrockEmbedder
from opensearch_vectordb import OpenSearchVectorDb
from agno.knowledge.combined import CombinedKnowledgeBase
from agno.knowledge.pdf import PDFKnowledgeBase
from agno.knowledge.text import TextKnowledgeBase
from agno.knowledge.docx import DocxKnowledgeBase

load_dotenv()

# Logging Configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Multi-Region AWS Configuration ---

# Primary regions for each service
AWS_REGION = os.getenv("AWS_REGION", "ap-southeast-1")  # Singapore for OpenSearch
AWS_BEDROCK_REGION = os.getenv("AWS_BEDROCK_REGION", "us-west-2")  # Oregon for Bedrock
AWS_DOCUMENTDB_REGION = os.getenv("AWS_DOCUMENTDB_REGION", "ap-southeast-1")  # Singapore for DocumentDB

# AWS Credentials (for OpenSearch and DocumentDB)
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

# AWS Bedrock API Key (for GPT-OSS models)
AWS_BEARER_TOKEN_BEDROCK = os.getenv("AWS_BEARER_TOKEN_BEDROCK")

# Amazon DocumentDB configuration (Singapore region)
DOCUMENTDB_URL = os.getenv("DOCUMENTDB_URL")
DATABASE_NAME = os.getenv("DATABASE_NAME", "legal_agent_system")

# Amazon OpenSearch Service configuration (Singapore region)
OPENSEARCH_ENDPOINT = os.getenv("OPENSEARCH_ENDPOINT")
OPENSEARCH_INDEX = os.getenv("OPENSEARCH_INDEX", "legalknowledge")
OPENSEARCH_USERNAME = os.getenv("OPENSEARCH_USERNAME", "Admin@123")
OPENSEARCH_PASSWORD = os.getenv("OPENSEARCH_PASSWORD", "Admin@123")

# Knowledge base directory
KNOWLEDGE_BASE_DIR = os.getenv("KNOWLEDGE_BASE_DIR", "./knowledge_base")

# GPT-OSS-120B Model - Only model you need!
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "openai.gpt-oss-120b-1:0")

# AWS Bedrock Model Configuration for GPT-OSS-120B with API Key
BASE_MODEL = AwsBedrock(
    id=BEDROCK_MODEL_ID,
    region=AWS_BEDROCK_REGION,  # Oregon for Bedrock
    # Use API key authentication instead of IAM credentials
    api_key=AWS_BEARER_TOKEN_BEDROCK,  # This is your Bedrock API key
    # Alternative: if AwsBedrock doesn't support api_key parameter, use these:
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    # Optimized parameters for GPT-OSS-120B (legal reasoning)
    max_tokens=4096,  # Can go up to 128K context
    temperature=0.1,  # Low for legal precision
    top_p=0.9,
    # GPT-OSS specific parameters
    extra_body={
        "reasoning_level": "medium",  # low, medium, high
        "enable_chain_of_thought": True,
        "tool_choice": "auto"
    }
)

# Frontend URL for CORS
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# --- Service Connections ---

# AWS Bedrock Embedder for Titan Text Embeddings V2 - Oregon region
# Note: Embeddings still use IAM credentials, not API key
embedder = BedrockEmbedder(
    model_id="amazon.titan-embed-text-v2:0",
    region=AWS_BEDROCK_REGION,  # Oregon for Bedrock
    dimensions=1024,
    normalize=True
)

# Amazon OpenSearch Service Vector Database - Singapore region  
vector_db = OpenSearchVectorDb(
    endpoint=OPENSEARCH_ENDPOINT,
    index_name=OPENSEARCH_INDEX,
    username=OPENSEARCH_USERNAME,
    password=OPENSEARCH_PASSWORD,
    embedder=embedder,
    region=AWS_REGION,  
    use_aws_auth=False,  # Using basic auth with username/password
    dimensions=1024
)

# Storage for agent session history using Amazon DocumentDB - Singapore region
agent_storage = MongoDbAgentStorage(
    collection_name="agent_data",
    db_url=DOCUMENTDB_URL,
    db_name=DATABASE_NAME,
    ssl=True,
    ssl_ca_certs="rds-ca-2019-root.pem",
    retryWrites=False
)

# Memory V2 with Amazon DocumentDB backend - Singapore region
memory_db = MongoMemoryDb(
    collection_name="agent_memories",
    db_url=DOCUMENTDB_URL,
    db_name=DATABASE_NAME,
    ssl=True,
    ssl_ca_certs="rds-ca-2019-root.pem",
    retryWrites=False
)
memory = Memory(db=memory_db)

# --- Knowledge Base Configuration ---

# Legal Knowledge Base with Amazon OpenSearch Service (Singapore)
legal_knowledge_base = CombinedKnowledgeBase(
    sources=[
        PDFKnowledgeBase(
            path=f"{KNOWLEDGE_BASE_DIR}/pdfs",
            vector_db=vector_db,
            reader_config={"chunk_size": 1500, "chunk_overlap": 200, "separator": "\n\n"},
        ),
        DocxKnowledgeBase(
            path=f"{KNOWLEDGE_BASE_DIR}/docx",
            vector_db=vector_db,
            reader_config={"chunk_size": 1500, "chunk_overlap": 200},
        ),
        TextKnowledgeBase(
            path=f"{KNOWLEDGE_BASE_DIR}/texts",
            vector_db=vector_db,
            reader_config={"chunk_size": 1500, "chunk_overlap": 200},
        ),
    ],
    vector_db=vector_db,
)

# Knowledge search configuration optimized for GPT-OSS-120B
KNOWLEDGE_SEARCH_CONFIG = {
    "num_documents": int(os.getenv("MAX_SEARCH_RESULTS", "5")),
    "similarity_threshold": float(os.getenv("SEARCH_SIMILARITY_THRESHOLD", "0.7"))
}

# Validation and logging
logger.info(f"Legal AI System Configuration:")
logger.info(f"  - LLM: GPT-OSS-120B in {AWS_BEDROCK_REGION} (Oregon)")
logger.info(f"  - Authentication: Bedrock API Key")
logger.info(f"  - Vector DB: OpenSearch in {AWS_REGION} (Singapore)")  
logger.info(f"  - Document DB: DocumentDB in {AWS_DOCUMENTDB_REGION} (Singapore)")
logger.info(f"  - Model: {BEDROCK_MODEL_ID}")

# Validate critical configurations
if not AWS_BEARER_TOKEN_BEDROCK:
    logger.error("AWS_BEARER_TOKEN_BEDROCK not found in environment variables!")
    raise ValueError("Bedrock API key is required")

if not OPENSEARCH_ENDPOINT or not DOCUMENTDB_URL:
    logger.warning("Critical service endpoints not configured")

logger.info("✅ GPT-OSS-120B configuration complete - ready for legal reasoning!")