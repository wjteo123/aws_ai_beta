# seed_documentdb.py
"""
Seed Amazon DocumentDB for the Legal Multi-Agent System:
- session documents -> collection "agent_data" (used by MongoDbAgentStorage)
- memory documents  -> collection "agent_memories" (used by MongoMemoryDb)
"""

import pymongo
import os
from dotenv import load_dotenv
from datetime import datetime, timezone

def seed_database():
    load_dotenv()

    DOCUMENTDB_URL = os.getenv("DOCUMENTDB_URL", "mongodb://docdb-cluster.cluster-xyz.us-east-1.docdb.amazonaws.com:27017")
    DATABASE_NAME = os.getenv("DATABASE_NAME", "legal_agent_system")

    # Collections used by our app
    SESSION_COLLECTION = "agent_data"
    MEMORY_COLLECTION = "agent_memories"

    print("--- Starting DocumentDB Seeding ---")

    client = None
    try:
        # Connect to Amazon DocumentDB with SSL
        client = pymongo.MongoClient(
            DOCUMENTDB_URL,
            ssl=True,
            ssl_ca_certs='rds-ca-2019-root.pem',  # Download from AWS
            retryWrites=False  # DocumentDB doesn't support retryable writes
        )
        
        db = client[DATABASE_NAME]
        session_col = db[SESSION_COLLECTION]
        memory_col = db[MEMORY_COLLECTION]

        print(f"Connected to DocumentDB at {DOCUMENTDB_URL}, DB: {DATABASE_NAME}")

        # Clean collections
        print("Clearing existing documents...")
        session_col.delete_many({})
        memory_col.delete_many({})

        # Sample session documents
        session_docs = [
            {
                "_id": "session_contract_review_123",
                "session_id": "session_contract_review_123",
                "user_id": "user_jane_doe",
                "history": [
                    {"role": "user", "content": "Can you review this non-disclosure agreement for me?"},
                    {"role": "assistant", "content": "Certainly. I will check for standard clauses and potential risks using my legal knowledge base."},
                    {"role": "user", "content": "The main points are the definition of confidential information and the term."},
                    {"role": "assistant", "content": "I'll analyze those sections against best practices and similar agreements in my knowledge base..."}
                ],
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            },
            {
                "_id": "session_compliance_check_456",
                "session_id": "session_compliance_check_456",
                "user_id": "user_john_smith",
                "history": [
                    {"role": "user", "content": "What are the GDPR compliance requirements for a small e-commerce website?"},
                    {"role": "assistant", "content": "Based on my knowledge of GDPR regulations, you need a clear privacy policy, lawful basis for processing, and data subject request handling procedures. Let me search for specific requirements..."}
                ],
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            },
            {
                "_id": "session_ip_consultation_789",
                "session_id": "session_ip_consultation_789", 
                "user_id": "user_startup_founder",
                "history": [
                    {"role": "user", "content": "Should I file for a patent or keep my invention as a trade secret?"},
                    {"role": "assistant", "content": "This is an important strategic decision. Let me analyze the factors based on intellectual property law principles..."},
                    {"role": "user", "content": "The invention is a software algorithm for data processing."},
                    {"role": "assistant", "content": "For software algorithms, you'll need to consider patentability requirements and disclosure implications. Let me search relevant case law and guidelines..."}
                ],
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
        ]

        # Sample memories documents (format friendly to Memory V2 MongoMemoryDb)
        memory_docs = [
            {
                "_id": "memories_user_jane_doe",
                "user_id": "user_jane_doe",
                "memories": [
                    {"memory": "Jane Doe is General Counsel for Innovatech Inc., a technology startup."},
                    {"memory": "Prefers detailed legal analysis with citations to relevant statutes and case law."},
                    {"memory": "Innovatech Inc. operates primarily in the European Union and United States."},
                    {"memory": "Has particular interest in data privacy and intellectual property matters."},
                    {"memory": "Frequently works on contract reviews and compliance assessments."}
                ],
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            },
            {
                "_id": "memories_user_john_smith",
                "user_id": "user_john_smith",
                "memories": [
                    {"memory": "John Smith is a solo founder of TechStart, an early-stage e-commerce startup."},
                    {"memory": "Primarily concerned with cost-effective legal solutions and practical guidance."},
                    {"memory": "Business operates in the US but ships to EU customers, requiring GDPR compliance."},
                    {"memory": "Prefers actionable checklists and step-by-step guidance over lengthy legal analysis."}
                ],
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            },
            {
                "_id": "memories_user_startup_founder",
                "user_id": "user_startup_founder",
                "memories": [
                    {"memory": "Represents an AI startup developing machine learning algorithms."},
                    {"memory": "Particularly interested in intellectual property strategy and patent vs trade secret decisions."},
                    {"memory": "Company is in Series A funding stage and needs IP portfolio development."},
                    {"memory": "Prefers strategic advice with business implications, not just legal theory."}
                ],
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
        ]

        print(f"Inserting {len(session_docs)} session docs into '{SESSION_COLLECTION}'...")
        session_col.insert_many(session_docs)

        print(f"Inserting {len(memory_docs)} memory docs into '{MEMORY_COLLECTION}'...")
        memory_col.insert_many(memory_docs)

        print("Seed complete. Document counts:")
        print(f"  - {SESSION_COLLECTION}: {session_col.count_documents({})}")
        print(f"  - {MEMORY_COLLECTION}: {memory_col.count_documents({})}")

        # Test connection and basic operations
        print("\nTesting DocumentDB operations...")
        
        # Test find operation
        test_session = session_col.find_one({"user_id": "user_jane_doe"})
        if test_session:
            print("✓ Successfully retrieved session data")
        else:
            print("✗ Failed to retrieve session data")
            
        # Test memory retrieval
        test_memory = memory_col.find_one({"user_id": "user_john_smith"})
        if test_memory:
            print("✓ Successfully retrieved memory data")
        else:
            print("✗ Failed to retrieve memory data")

    except pymongo.errors.ConnectionFailure as e:
        print(f"Error: Could not connect to DocumentDB. Details: {e}")
        print("Make sure:")
        print("1. DocumentDB cluster is running and accessible")
        print("2. Security groups allow connections from your IP")
        print("3. SSL certificate (rds-ca-2019-root.pem) is in the current directory")
        print("4. Connection string is correct")
    except pymongo.errors.OperationFailure as e:
        print(f"Error: DocumentDB operation failed. Details: {e}")
        print("Check authentication credentials and permissions")
    except Exception as e:
        print(f"Unexpected error: {e}")
    finally:
        if client:
            client.close()
        print("--- DocumentDB Seeding Finished ---")


if __name__ == "__main__":
    print("Amazon DocumentDB Seeding Script")
    print("Make sure you have:")
    print("1. Downloaded rds-ca-2019-root.pem from AWS")
    print("2. Configured proper environment variables")
    print("3. Set up VPC and security groups for DocumentDB access")
    print()
    
    seed_database()