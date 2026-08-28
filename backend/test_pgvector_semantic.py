"""Test pgvector semantic search functionality."""
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.services import create_memory, semantic_search_memories, generate_and_store_embedding, batch_generate_embeddings
from app.memory_service import MemoryService, MemoryCategory, MemorySource, MemoryImportance

def test_pgvector_semantic_search():
    """Test real semantic search with pgvector."""
    db = SessionLocal()
    try:
        print("=== Testing pgvector Semantic Search ===\n")
        
        # First, let's check if we have any memories with embeddings
        from app.models import Memory
        memories_with_embeddings = db.query(Memory).filter(Memory.embedding.isnot(None)).count()
        print(f"Memories with embeddings: {memories_with_embeddings}")
        
        # Generate embeddings for existing memories
        print("\nGenerating embeddings for existing memories...")
        count = batch_generate_embeddings(user_id=1, limit=20)
        print(f"Generated embeddings for {count} memories")
        
        # Check again
        memories_with_embeddings = db.query(Memory).filter(Memory.embedding.isnot(None)).count()
        print(f"Memories with embeddings after generation: {memories_with_embeddings}")
        
        # Create a test memory with explicit content
        print("\nCreating test memory: 'Antigen's backend uses PostgreSQL'")
        test_memory = MemoryService.create_memory(
            db=db,
            user_id=1,
            content="Antigen's backend uses PostgreSQL",
            memory_type="fact",
            category=MemoryCategory.EXPLICIT,
            source=MemorySource.USER_EXPLICIT,
            importance=MemoryImportance.HIGH,
            confidence=0.9
        )
        print(f"Created memory ID: {test_memory.id}")
        
        # Generate embedding for the test memory
        print("Generating embedding for test memory...")
        generate_and_store_embedding(test_memory.id)
        db.refresh(test_memory)
        print(f"Test memory has embedding: {test_memory.embedding is not None}")
        
        # Test semantic search with the exact phrase
        print("\n=== Test 1: Exact phrase search ===")
        print("Query: 'Antigen's backend uses PostgreSQL'")
        results = semantic_search_memories(db, "Antigen's backend uses PostgreSQL", top_k=5, user_id=1)
        print(f"Found {len(results)} results")
        for i, result in enumerate(results):
            print(f"  {i+1}. {result['content']} (distance: {result['distance']:.4f})")
        
        # Test semantic search with different wording
        print("\n=== Test 2: Semantic search with different wording ===")
        print("Query: 'What database does my assistant backend use?'")
        results = semantic_search_memories(db, "What database does my assistant backend use?", top_k=5, user_id=1)
        print(f"Found {len(results)} results")
        for i, result in enumerate(results):
            print(f"  {i+1}. {result['content']} (distance: {result['distance']:.4f})")
        
        # Test semantic search with related query
        print("\n=== Test 3: Related query search ===")
        print("Query: 'database technology for the chat system'")
        results = semantic_search_memories(db, "database technology for the chat system", top_k=5, user_id=1)
        print(f"Found {len(results)} results")
        for i, result in enumerate(results):
            print(f"  {i+1}. {result['content']} (distance: {result['distance']:.4f})")
        
        # Verify that our test memory is found
        print("\n=== Verification ===")
        test_memory_found = False
        for result in semantic_search_memories(db, "What database does my assistant backend use?", top_k=10, user_id=1):
            if result['id'] == test_memory.id:
                test_memory_found = True
                print("PASS: Test memory found in semantic search!")
                print(f"  Content: {result['content']}")
                print(f"  Distance: {result['distance']:.4f}")
                break
        
        if not test_memory_found:
            print("FAIL: Test memory NOT found in semantic search")
        
        print("\n=== Test Complete ===")
        return test_memory_found
        
    finally:
        db.close()

if __name__ == "__main__":
    success = test_pgvector_semantic_search()
    exit(0 if success else 1)